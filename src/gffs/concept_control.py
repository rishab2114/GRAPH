"""Control experiment on the Impact4Cast concept graph (Gu & Krenn; Zenodo 10.5281/zenodo.10692137).

Question: does the same forecaster beat the popularity baseline on a large, sparse research-concept
graph, where the 'shared bridge' idea came from? If yes, ATT&CK's density is the likely reason it
failed there. If no, the method or our code is the more likely cause.

The edge table has one row per (concept, concept, paper); `time` is days since 1990-01-01.
Unlinked pairs are sampled, as in Impact4Cast; the graph is too large to list all ~720M pairs.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import scipy.sparse as sp

from gffs.features import FEATURES

ORIGIN = date(1990, 1, 1)


def day_of_year_end(year: int) -> int:
    return (date(year, 12, 31) - ORIGIN).days


def adjacency_at(edges: pd.DataFrame, day: int, n: int) -> sp.csr_matrix:
    """Symmetric matrix of paper counts per concept pair, using papers up to `day`."""
    e = edges[edges["time"] <= day]
    counts = e.groupby(["v1", "v2"]).size()
    r = counts.index.get_level_values(0).to_numpy(); c = counts.index.get_level_values(1).to_numpy()
    w = counts.to_numpy().astype(float)
    A = sp.coo_matrix((np.r_[w, w], (np.r_[r, c], np.r_[c, r])), shape=(n, n)).tocsr()
    A.sum_duplicates()
    return A


def sample_unconnected(A: sp.csr_matrix, n_pairs: int, rng: np.random.Generator,
                       min_degree: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Uniform sample of distinct unlinked pairs (u < v) among nodes with degree >= min_degree."""
    deg = np.diff(A.indptr)
    nodes = np.flatnonzero(deg >= min_degree)
    sub = A[nodes][:, nodes]
    available = len(nodes) * (len(nodes) - 1) // 2 - (sub.nnz - sub.diagonal().astype(bool).sum()) // 2
    if n_pairs > available:
        raise ValueError(f"asked for {n_pairs} pairs but there are only {available} unlinked pairs")
    seen: set[tuple[int, int]] = set()
    while len(seen) < n_pairs:
        a = rng.choice(nodes, 2 * n_pairs); b = rng.choice(nodes, 2 * n_pairs)
        u, v = np.minimum(a, b), np.maximum(a, b)
        keep = u != v
        u, v = u[keep], v[keep]
        linked = np.asarray(A[u, v]).ravel() > 0
        for x, y in zip(u[~linked], v[~linked]):
            seen.add((int(x), int(y)))
            if len(seen) == n_pairs:
                break
    pairs = np.array(sorted(seen))
    return pairs[:, 0], pairs[:, 1]


def pair_labels(A_later: sp.csr_matrix, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    return (np.asarray(A_later[u, v]).ravel() > 0).astype(int)


def sparse_pair_features(A: sp.csr_matrix, u: np.ndarray, v: np.ndarray, chunk: int = 20_000) -> pd.DataFrame:
    """Same columns and definitions as gffs.features.pair_features, computed with sparse algebra.
    Popularity (`freq`) is the paper-weighted degree."""
    B = (A > 0).astype(float).tocsr()
    deg = np.asarray(B.sum(1)).ravel()
    freq = np.asarray(A.sum(1)).ravel()
    with np.errstate(divide="ignore"):
        aa_w = np.where(deg > 1, 1.0 / np.log(np.maximum(deg, 2)), 0.0)
        ra_w = np.where(deg > 0, 1.0 / np.maximum(deg, 1), 0.0)
    B_aa, B_ra = (B @ sp.diags(aa_w)).tocsr(), (B @ sp.diags(ra_w)).tocsr()
    cn, aa, ra, wcn = (np.empty(len(u)) for _ in range(4))
    for s in range(0, len(u), chunk):
        a, b = u[s:s + chunk], v[s:s + chunk]
        Bb = B[b]
        cn[s:s + chunk] = np.asarray(B[a].multiply(Bb).sum(1)).ravel()
        aa[s:s + chunk] = np.asarray(B_aa[a].multiply(Bb).sum(1)).ravel()
        ra[s:s + chunk] = np.asarray(B_ra[a].multiply(Bb).sum(1)).ravel()
        wcn[s:s + chunk] = np.asarray(A[a].minimum(A[b]).multiply(Bb).sum(1)).ravel()
    union = deg[u] + deg[v] - cn
    df = pd.DataFrame({
        "freq_min": np.minimum(freq[u], freq[v]), "freq_max": np.maximum(freq[u], freq[v]),
        "deg_min": np.minimum(deg[u], deg[v]), "deg_max": np.maximum(deg[u], deg[v]),
        "common_neighbours": cn, "jaccard": np.where(union > 0, cn / np.maximum(union, 1), 0.0),
        "adamic_adar": aa, "resource_allocation": ra, "weighted_cn": wcn,
    })
    return df[FEATURES]


def adjacencies_from_parquet(path, years: list[int], n: int) -> dict[int, sp.csr_matrix]:
    """Stream the edge table once, row group by row group, and return the paper-count adjacency
    at the end of each year in `years` (sorted ascending)."""
    import pyarrow.parquet as pq

    years = sorted(years)
    cut = np.array([day_of_year_end(y) for y in years])
    nb = len(years) + 1
    keys_all, counts_all = [], []
    pf = pq.ParquetFile(path)
    for g in range(pf.num_row_groups):
        t = pf.read_row_group(g, columns=["v1", "v2", "time"])
        a = t.column("v1").to_numpy(); b = t.column("v2").to_numpy(); tm = t.column("time").to_numpy()
        lo, hi = np.minimum(a, b).astype(np.int64), np.maximum(a, b).astype(np.int64)
        bucket = np.searchsorted(cut, tm, side="left")          # 0 = by first year ... len = later
        code = (lo * n + hi) * nb + bucket
        k, c = np.unique(code, return_counts=True)
        keys_all.append(k); counts_all.append(c)
        del t, a, b, tm, lo, hi, bucket, code
    k = np.concatenate(keys_all); c = np.concatenate(counts_all)
    uk, inv = np.unique(k, return_inverse=True)
    c = np.bincount(inv, weights=c)
    pair, bucket = uk // nb, uk % nb
    out = {}
    for i, y in enumerate(years):
        m = bucket <= i
        p, w = pair[m], c[m]
        pu, pinv = np.unique(p, return_inverse=True)
        w = np.bincount(pinv, weights=w)
        r, cc = pu // n, pu % n
        A = sp.coo_matrix((np.r_[w, w], (np.r_[r, cc], np.r_[cc, r])), shape=(n, n)).tocsr()
        A.sum_duplicates()
        out[y] = A
    return out


def run_control(adj: dict[int, sp.csr_matrix], train: tuple[int, int], test: tuple[int, int],
                n_pairs: int = 200_000, n_boot: int = 1000, n_strata: int = 10, k: int = 1000, seed: int = 0) -> dict:
    """Same methods and metrics as gffs.study.run_split, on sampled unlinked pairs."""
    from gffs.baselines import random_scores
    from gffs.evaluate import evaluate
    from gffs.models import MODELS, fit_model
    from gffs.stats import paired_bootstrap_diff, popularity_strata, stratified_auc

    rng = np.random.default_rng(seed)
    A_b, A_t, A_a = adj[train[0]], adj[train[1]], adj[test[1]]
    assert train[1] == test[0], "the test graph must be the training label year (cutoff T)"
    ub, vb = sample_unconnected(A_b, n_pairs, rng)
    X_train, y_train = sparse_pair_features(A_b, ub, vb), pair_labels(A_t, ub, vb)
    u, v = sample_unconnected(A_t, n_pairs, rng)
    X, y = sparse_pair_features(A_t, u, v), pair_labels(A_a, u, v)

    freq = (X["freq_min"] * X["freq_max"]).to_numpy()
    scores = {"frequency": freq, "random": random_scores(list(zip(u, v)), seed)}
    for name in MODELS:
        scores[name] = fit_model(name, X_train, y_train)(X)
    strata = popularity_strata(freq, n_strata)
    methods = {}
    for name, s in scores.items():
        m = evaluate(s, y, k)
        m["strat_auc"] = stratified_auc(s, y, strata)
        m["vs_frequency"] = paired_bootstrap_diff(s, freq, y, n_boot, seed)
        methods[name] = m
    active = int((np.diff(A_t.indptr) > 0).sum())
    return {"graph": {"nodes_t": active, "edges_t": int(A_t.nnz // 2),
                      "density_t": (A_t.nnz / 2) / (active * (active - 1) / 2),
                      "n_pairs": n_pairs, "train_positive": int(y_train.sum()), "test_positive": int(y.sum())},
            "methods": methods}


def main(argv: list[str] | None = None) -> None:
    import argparse
    import json
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Impact4Cast concept-graph control")
    ap.add_argument("--parquet", type=Path,
                    default=Path("data/zenodo/impact4cast/data_concept_graph/full_dynamic_graph.parquet"))
    ap.add_argument("--n-concepts", type=int, default=37_960)
    ap.add_argument("--n-pairs", type=int, default=200_000)
    ap.add_argument("--out", type=Path, default=Path("results/control_impact4cast.json"))
    args = ap.parse_args(argv)
    adj = adjacencies_from_parquet(args.parquet, [2016, 2019, 2022], args.n_concepts)
    print({y: A.nnz // 2 for y, A in adj.items()}, flush=True)
    r = run_control(adj, train=(2016, 2019), test=(2019, 2022), n_pairs=args.n_pairs)
    r["design"] = {"train": "graph 2016 -> new links by 2019", "test": "graph 2019 -> new links by 2022",
                   "n_pairs": args.n_pairs, "sampling": "uniform unlinked pairs among nodes with degree >= 1"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(r, indent=1))
    print(json.dumps(r["graph"]), flush=True)
    for n, m in r["methods"].items():
        v = m["vs_frequency"]
        print(f"{n:24s} auc {m['auc']:.3f} strat {m['strat_auc']:.3f} p@1000 {m['precision_at_k']:.3f} "
              f"d {v['diff']:+.3f} [{v['lo']:+.3f},{v['hi']:+.3f}]", flush=True)


if __name__ == "__main__":
    main()
