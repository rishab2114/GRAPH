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
