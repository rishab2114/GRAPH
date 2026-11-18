"""Pre-registered forecaster variants. Every choice is made on training data only."""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from gffs.features import FEATURES

Scorer = Callable[[pd.DataFrame], np.ndarray]
POPULARITY = ["freq_min", "freq_max", "deg_min", "deg_max"]


def _logreg(cols: list[str]):
    def fit(X: pd.DataFrame, y: np.ndarray) -> Scorer:
        m = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=2000))
        m.fit(X[cols], y)
        return lambda Z: m.predict_proba(Z[cols])[:, 1]
    return fit


def _hgb(X: pd.DataFrame, y: np.ndarray) -> Scorer:
    m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                       class_weight="balanced", random_state=0)
    m.fit(X[FEATURES], y)
    return lambda Z: m.predict_proba(Z[FEATURES])[:, 1]


def _best_single(X: pd.DataFrame, y: np.ndarray) -> Scorer:
    best = max(FEATURES, key=lambda c: roc_auc_score(y, X[c]))
    return lambda Z: Z[best].to_numpy(dtype=float)


def _rank_mean(X: pd.DataFrame, y: np.ndarray) -> Scorer:
    # Unsupervised: average percentile rank of the structural features (no fitting).
    cols = ["common_neighbours", "jaccard", "adamic_adar", "resource_allocation", "weighted_cn"]
    return lambda Z: Z[cols].rank(pct=True).mean(axis=1).to_numpy()


MODELS: dict[str, Callable[[pd.DataFrame, np.ndarray], Scorer]] = {
    "logreg_all": _logreg(FEATURES),
    "logreg_popularity": _logreg(POPULARITY),
    "hgb_all": _hgb,
    "train_best_single": _best_single,
    "structural_rank_mean": _rank_mean,
}


def fit_model(name: str, X: pd.DataFrame, y: np.ndarray) -> Scorer:
    return MODELS[name](X, y)
