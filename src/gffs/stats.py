"""Statistics for the multi-split study: popularity-stratified AUC and paired bootstrap."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


def popularity_strata(popularity: np.ndarray, n_bins: int = 10) -> np.ndarray:
    """Quantile bins (0..n_bins-1) of a popularity score; ties broken by rank order."""
    ranks = pd.Series(popularity).rank(method="first").to_numpy()
    return pd.qcut(ranks, n_bins, labels=False).astype(int)


def stratified_auc(scores: np.ndarray, labels: np.ndarray, strata: np.ndarray) -> float:
    """AUC computed only over (positive, negative) pairs in the same stratum.

    Each stratum's AUC is weighted by n_pos * n_neg, its number of comparable pairs.
    A score that only tracks the strata gets 0.5; this isolates signal beyond popularity.
    """
    num = den = 0.0
    for s in np.unique(strata):
        m = strata == s
        y = labels[m]
        n_pos = int(y.sum()); n_neg = int(len(y) - n_pos)
        if n_pos == 0 or n_neg == 0:
            continue
        w = n_pos * n_neg
        num += w * roc_auc_score(y, scores[m])
        den += w
    if den == 0:
        raise ValueError("no stratum contains both classes")
    return num / den


def paired_bootstrap_diff(a: np.ndarray, b: np.ndarray, labels: np.ndarray,
                          n_boot: int = 1000, seed: int = 0) -> dict:
    """AUC(a) - AUC(b) with a 95% percentile interval, resampling candidate pairs."""
    diff = roc_auc_score(labels, a) - roc_auc_score(labels, b)
    rng = np.random.default_rng(seed)
    n = len(labels)
    out = []
    while len(out) < n_boot:
        idx = rng.integers(0, n, n)
        y = labels[idx]
        if y.min() == y.max():
            continue
        out.append(roc_auc_score(y, a[idx]) - roc_auc_score(y, b[idx]))
    lo, hi = np.percentile(out, [2.5, 97.5])
    return {"diff": float(diff), "lo": float(lo), "hi": float(hi)}
