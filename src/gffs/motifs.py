"""Transaction-subgraph motifs on the Elliptic payment graph (vocabulary v1, the 8 expressible concepts).

Label-free: every feature comes from graph shape only. Thresholds are fixed from training-period data.
Design and rulings: docs/RESEARCH_LOG.md, "Step B".

    python -m gffs.motifs --data data/elliptic --out results/
"""
from __future__ import annotations

import argparse
import json
import math
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

MOTIFS = ["fan_in", "fan_out", "peel_chain", "mixing_service", "coinjoin", "pass_through", "layering", "smurfing"]
RECONVERGE_HOPS = 3


def node_features(g: nx.DiGraph) -> pd.DataFrame:
    if not nx.is_directed_acyclic_graph(g):
        raise ValueError("motif features assume an acyclic transaction graph")
    nodes = list(g.nodes)
    indeg, outdeg = dict(g.in_degree()), dict(g.out_degree())
    order = list(nx.topological_sort(g))
    depth = {}
    for n in order:
        depth[n] = max((depth[p] + 1 for p in g.predecessors(n)), default=0)
    peel = {n for n in nodes if indeg[n] == 1 and outdeg[n] <= 2}
    sub = g.subgraph(peel)
    down, up = {}, {}
    for n in order:
        if n in peel:
            up[n] = max((up[p] + 1 for p in sub.predecessors(n)), default=0)
    for n in reversed(order):
        if n in peel:
            down[n] = max((down[s] + 1 for s in sub.successors(n)), default=0)
    mio = {n: min(indeg[n], outdeg[n]) for n in nodes}
    reconv = {}
    for n in nodes:
        succ = list(g.successors(n))
        if len(succ) < 2:
            reconv[n] = False
            continue
        seen: dict = {}
        hit = False
        for s in succ:
            reach = nx.single_source_shortest_path_length(g, s, cutoff=RECONVERGE_HOPS - 1)
            for r in reach:
                if r in seen and seen[r] != s:
                    hit = True
                    break
                seen[r] = s
            if hit:
                break
        reconv[n] = hit
    return pd.DataFrame({
        "in_deg": [indeg[n] for n in nodes], "out_deg": [outdeg[n] for n in nodes],
        "depth": [depth[n] for n in nodes],
        "peel_run": [up[n] + down[n] + 1 if n in peel else 0 for n in nodes],
        "max_neighbour_min_io": [max((mio[m] for m in nx.all_neighbors(g, n)), default=0) for n in nodes],
        "reconverges": [reconv[n] for n in nodes],
    }, index=pd.Index(nodes, name="txId"))


def thresholds(f: pd.DataFrame) -> dict:
    p95 = lambda s: float(np.percentile(s, 95))
    return {"k": int(math.ceil(max(p95(f["in_deg"]), p95(f["out_deg"])))),
            "length": int(math.ceil(max(p95(f["peel_run"]), p95(f["depth"]))))}


def motif_flags(f: pd.DataFrame, k: int, length: int) -> pd.DataFrame:
    coin = (f["in_deg"] >= k) & (f["out_deg"] >= k)
    return pd.DataFrame({
        "fan_in": f["in_deg"] >= k,
        "fan_out": f["out_deg"] >= k,
        "peel_chain": f["peel_run"] >= length,
        "mixing_service": coin & (f["max_neighbour_min_io"] >= k),
        "coinjoin": coin,
        "pass_through": (f["in_deg"] == 1) & (f["out_deg"] == 1),
        "layering": f["depth"] >= length,
        "smurfing": (f["out_deg"] >= k) & f["reconverges"],
    }, index=f.index)[MOTIFS]


def _wilson(x: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def prevalence(flags: pd.DataFrame, y: pd.Series) -> dict:
    """Per motif: rate among illicit (y=1) and licit (y=0) with Wilson 95% intervals, and the lift."""
    out = {}
    ill, lic = flags[y == 1], flags[y == 0]
    for m in flags.columns:
        xi, ni, xl, nl = int(ill[m].sum()), len(ill), int(lic[m].sum()), len(lic)
        ri, rl = xi / ni, xl / nl
        out[m] = {"illicit": xi, "n_illicit": ni, "rate_illicit": ri, "ci_illicit": _wilson(xi, ni),
                  "licit": xl, "n_licit": nl, "rate_licit": rl, "ci_licit": _wilson(xl, nl),
                  "lift": ri / rl if rl > 0 else float("inf")}
    return out


def pair_counts(flags: pd.DataFrame, y: pd.Series) -> list[dict]:
    rows = []
    for a, b in combinations(flags.columns, 2):
        both = flags[a] & flags[b]
        rows.append({"pair": [a, b], "illicit": int(both[y == 1].sum()), "licit": int(both[y == 0].sum())})
    return sorted(rows, key=lambda r: -r["illicit"])


def main(argv: list[str] | None = None) -> None:
    from gffs.elliptic import TRAIN_END, load

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=Path("data/elliptic"))
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args(argv)
    d = load(args.data)
    step = d.X["time_step"]
    train_ids = set(step.index[step <= TRAIN_END])
    e = d.edges[d.edges["txId1"].isin(train_ids) & d.edges["txId2"].isin(train_ids)]
    g = nx.DiGraph(); g.add_nodes_from(train_ids); g.add_edges_from(zip(e["txId1"], e["txId2"]))
    f = node_features(g)
    t = thresholds(f)
    flags = motif_flags(f, t["k"], t["length"])
    y = d.y.reindex(flags.index)
    lab = y.notna()
    res = {"steps": [1, TRAIN_END], "n_transactions": len(f), "thresholds": t,
           "share_any_motif_all": float(flags.any(axis=1).mean()),
           "prevalence": prevalence(flags[lab], y[lab]), "pairs": pair_counts(flags[lab], y[lab])}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "motifs_elliptic.json").write_text(json.dumps(res, indent=1))
    print("thresholds", t)
    for m, r in res["prevalence"].items():
        print(f"{m:15s} illicit {r['rate_illicit']:.3f} ({r['illicit']}/{r['n_illicit']})  "
              f"licit {r['rate_licit']:.3f} ({r['licit']}/{r['n_licit']})  lift {r['lift']:.2f}")


if __name__ == "__main__":
    main()
