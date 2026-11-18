"""E1 metrics: AUC and precision at top k."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_auc_score


def evaluate(scores: np.ndarray, labels: np.ndarray, k: int = 100) -> dict:
    scores, labels = np.asarray(scores, dtype=float), np.asarray(labels, dtype=int)
    if labels.sum() == 0:
        raise ValueError("no newly documented pairs in test window")
    top = np.argsort(-scores, kind="stable")[:k]
    return {
        "auc": float(roc_auc_score(labels, scores)),
        "precision_at_k": float(labels[top].mean()),
        "k": int(min(k, len(labels))),
        "n_candidates": int(len(labels)),
        "n_positive": int(labels.sum()),
    }
