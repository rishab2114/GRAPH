"""Write motif-pair scenarios as synthetic transaction subgraphs, inject them into real Elliptic
components, and compute the graph-only features detectors see (docs/e3e4-design.md).
"""
from __future__ import annotations

from typing import Callable

import networkx as nx
import numpy as np
import pandas as pd

from gffs.motifs import node_features

Sub = tuple[list, list, object, object]   # nodes, edges, entry node, exit node


def motif_subgraph(name: str, k: int, L: int, prefix: str) -> Sub:
    n = lambda tag, i=0: f"{prefix}:{name}:{tag}{i}"
    if name == "fan_in":
        src = [n("s", i) for i in range(k)]; hub = n("h")
        return src + [hub], [(s, hub) for s in src], src[0], hub
    if name == "fan_out":
        hub = n("h"); dst = [n("t", i) for i in range(k)]
        return [hub] + dst, [(hub, t) for t in dst], hub, dst[0]
    if name in ("peel_chain", "layering"):
        path = [n("p", i) for i in range(L + 1)]
        edges = list(zip(path, path[1:]))
        nodes = list(path)
        if name == "peel_chain":                       # each inner hop peels a small output off
            for i in range(1, L):
                side = n("side", i); nodes.append(side); edges.append((path[i], side))
        return nodes, edges, path[0], path[-1]
    if name == "pass_through":
        a, m, b = n("a"), n("m"), n("b")
        return [a, m, b], [(a, m), (m, b)], a, b
    if name == "coinjoin":
        ins = [n("i", i) for i in range(k)]; c = n("c"); outs = [n("o", i) for i in range(k)]
        return ins + [c] + outs, [(i, c) for i in ins] + [(c, o) for o in outs], ins[0], outs[0]
    if name == "mixing_service":
        ins = [n("i", i) for i in range(k)]; c1, c2 = n("c", 1), n("c", 2)
        outs = [n("o", i) for i in range(k)]
        extra_out = [n("xo", i) for i in range(k - 1)]; extra_in = [n("xi", i) for i in range(k - 1)]
        edges = [(i, c1) for i in ins] + [(c1, c2)] + [(c1, x) for x in extra_out] \
            + [(x, c2) for x in extra_in] + [(c2, o) for o in outs]
        return ins + [c1, c2] + outs + extra_out + extra_in, edges, ins[0], outs[0]
    if name == "smurfing":
        s = n("s"); mids = [n("x", i) for i in range(k)]; m = n("m")
        return [s] + mids + [m], [(s, x) for x in mids] + [(x, m) for x in mids], s, m
    raise ValueError(f"unknown motif {name!r}")


def scenario(pair: tuple[str, ...], k: int, L: int, prefix: str) -> tuple[list, list, object]:
    """Motif A's exit feeds motif B's entry. Returns nodes, edges and the scenario's entry node.
    A one-element tuple gives a single-motif scenario (stress test S3)."""
    if len(pair) == 1:
        nodes, edges, entry, _ = motif_subgraph(pair[0], k, L, prefix + ":A")
        return nodes, edges, entry
    na, ea, ina, outa = motif_subgraph(pair[0], k, L, prefix + ":A")
    nb, eb, inb, _ = motif_subgraph(pair[1], k, L, prefix + ":B")
    return na + nb, ea + eb + [(outa, inb)], ina


def inject(base: nx.DiGraph, pairs: list[tuple[str, str]], rng: np.random.Generator,
           size_sampler: Callable[[np.random.Generator], tuple[int, int]]) -> tuple[nx.DiGraph, list]:
    """Copy `base` and attach one scenario instance per entry of `pairs`, each by a single edge from a
    random real transaction to the scenario's entry. Returns the graph and the synthetic node ids."""
    g = base.copy()
    real = list(base.nodes)
    synthetic = []
    for i, pair in enumerate(pairs):
        k, L = size_sampler(rng)
        nodes, edges, entry = scenario(pair, k, L, prefix=f"syn{i}")
        g.add_nodes_from(nodes); g.add_edges_from(edges)
        g.add_edge(real[int(rng.integers(len(real)))], entry)
        synthetic.extend(nodes)
    return g, synthetic


def size_sampler_from(train_features: pd.DataFrame, train_y: pd.Series) -> Callable:
    """k from real illicit hub degrees (>= 2) and L from real illicit peel-run lengths (>= 2), steps 1-34."""
    ill = train_features[train_y == 1]
    ks = np.concatenate([ill["in_deg"][ill["in_deg"] >= 2], ill["out_deg"][ill["out_deg"] >= 2]]).astype(int)
    ls = ill["peel_run"][ill["peel_run"] >= 2].to_numpy().astype(int)
    if len(ks) == 0 or len(ls) == 0:
        raise ValueError("no illicit hub or peel examples to draw sizes from")
    # A chain of length L contributes L transactions; weight each by 1/L so every chain counts once.
    w = 1.0 / ls
    w = w / w.sum()
    return lambda rng: (int(rng.choice(ks)), int(rng.choice(ls, p=w)))


def graph_features(g: nx.DiGraph) -> pd.DataFrame:
    """node_features plus mean/max in-degree, out-degree and depth over predecessors and successors."""
    f = node_features(g)
    base = f[["in_deg", "out_deg", "depth"]]
    cols = {}
    for side, nbrs in (("pred", g.predecessors), ("succ", g.successors)):
        for col in ("in_deg", "out_deg", "depth"):
            vals = base[col].to_dict()
            means, maxes = [], []
            for node in f.index:
                v = [vals[m] for m in nbrs(node)]
                means.append(float(np.mean(v)) if v else 0.0); maxes.append(float(max(v)) if v else 0.0)
            cols[f"{side}_mean_{col}"] = means; cols[f"{side}_max_{col}"] = maxes
    out = pd.concat([f.astype({"reconverges": int}), pd.DataFrame(cols, index=f.index)], axis=1)
    return out.astype(float)
