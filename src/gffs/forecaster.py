"""Time-travel forecaster: learn from (T-k -> T), score the graph at T.

`fit_forecaster` only ever sees graphs up to the cutoff T (leakage rule, spec section 5).
"""
from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from gffs.features import pair_features
from gffs.graph import candidate_pairs, new_edges


def fit_forecaster(g_before: nx.Graph, g_t: nx.Graph) -> Pipeline:
    pairs = candidate_pairs(g_before)
    positives = new_edges(g_before, g_t)
    X = pair_features(g_before, pairs)
    y = np.array([p in positives for p in pairs], dtype=int)
    if y.sum() == 0:
        raise ValueError("no newly documented pairs in training window")
    model = make_pipeline(StandardScaler(),
                          LogisticRegression(class_weight="balanced", max_iter=1000))
    return model.fit(X, y)


def forecast(model: Pipeline, g_t: nx.Graph) -> pd.Series:
    """Scores for every candidate pair of `g_t`, indexed by (u, v), best first."""
    X = pair_features(g_t, candidate_pairs(g_t))
    scores = pd.Series(model.predict_proba(X)[:, 1], index=X.index, name="score")
    return scores.sort_values(ascending=False, kind="stable")
