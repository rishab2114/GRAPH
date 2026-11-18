"""Phase 0 check of the Elliptic Bitcoin dataset (Weber et al. 2019, arXiv 1908.02591).

Loads the three original CSVs, computes the dataset facts, and backtests detectors with the
paper's temporal split (train on time steps 1-34, test on 35-49; dark-market shutdown at 43).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

# Published facts (Weber et al. 2019, section 2.1 and section 4).
PUBLISHED_FACTS = {"n_nodes": 203_769, "n_edges": 234_355, "n_illicit": 4_545, "n_licit": 42_019,
                   "n_steps": 49, "n_features": 166, "edges_cross_time_steps": 0}
# Published illicit-class test results, Table 1 (precision, recall, F1).
PUBLISHED_TABLE1 = {"lr_af": (0.404, 0.593, 0.481), "lr_lf": (0.348, 0.668, 0.457),
                    "rf_af": (0.956, 0.670, 0.788), "rf_lf": (0.803, 0.611, 0.694)}
TRAIN_END, SHUTDOWN_STEP = 34, 43

COLUMNS = ["time_step"] + [f"local_{i}" for i in range(1, 94)] + [f"agg_{i}" for i in range(1, 73)]
LOCAL = COLUMNS[:94]  # the paper's "LF": the first 94 features, time step included


@dataclass
class Elliptic:
    X: pd.DataFrame        # index txId, 166 feature columns
    y: pd.Series           # 1 = illicit, 0 = licit, NaN = unknown
    edges: pd.DataFrame    # txId1 -> txId2


def load(directory: Path) -> Elliptic:
    d = Path(directory)
    feats = pd.read_csv(d / "elliptic_txs_features.csv", header=None)
    feats.columns = ["txId"] + COLUMNS
    X = feats.set_index("txId")
    cls = pd.read_csv(d / "elliptic_txs_classes.csv", dtype={"class": str}).set_index("txId")["class"]
    y = cls.map({"1": 1, "2": 0}).reindex(X.index).astype(float)
    edges = pd.read_csv(d / "elliptic_txs_edgelist.csv")
    return Elliptic(X, y, edges)


def compute_facts(d: Elliptic) -> dict:
    step = d.X["time_step"]
    cross = int((step.reindex(d.edges["txId1"]).to_numpy() != step.reindex(d.edges["txId2"]).to_numpy()).sum())
    return {"n_nodes": len(d.X), "n_edges": len(d.edges), "n_illicit": int((d.y == 1).sum()),
            "n_licit": int((d.y == 0).sum()), "n_unknown": int(d.y.isna().sum()),
            "n_steps": int(step.nunique()), "n_features": d.X.shape[1], "edges_cross_time_steps": cross}


def temporal_split(d: Elliptic, train_end: int = TRAIN_END, start: int = 1, end: int | None = None):
    """Labelled rows only. Train = steps start..train_end, test = steps train_end+1..end."""
    lab = d.y.notna()
    step = d.X["time_step"]
    end = int(step.max()) if end is None else end
    tr, te = lab & step.between(start, train_end), lab & step.between(train_end + 1, end)
    return (Elliptic(d.X[tr], d.y[tr].astype(int), d.edges), Elliptic(d.X[te], d.y[te].astype(int), d.edges))


def _cols(model, cols):
    return (model, cols)


# Ten detector variants (review note 3 asks for >= 8). The four paper models use the paper's
# settings: scikit-learn defaults for LR (liblinear was the 2019 default), RF with 50 trees, max_features=50.
DETECTORS = {
    "lr_af": lambda: _cols(LogisticRegression(solver="liblinear"), COLUMNS),
    "lr_lf": lambda: _cols(LogisticRegression(solver="liblinear"), LOCAL),
    "rf_af": lambda: _cols(RandomForestClassifier(n_estimators=50, max_features=50, n_jobs=-1, random_state=0), COLUMNS),
    "rf_lf": lambda: _cols(RandomForestClassifier(n_estimators=50, max_features=50, n_jobs=-1, random_state=0), LOCAL),
    "lr_scaled_af": lambda: _cols(make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)), COLUMNS),
    "extra_trees_af": lambda: _cols(ExtraTreesClassifier(n_estimators=100, n_jobs=-1, random_state=0), COLUMNS),
    "hgb_af": lambda: _cols(HistGradientBoostingClassifier(random_state=0), COLUMNS),
    "tree_af": lambda: _cols(DecisionTreeClassifier(random_state=0), COLUMNS),
    "nb_af": lambda: _cols(GaussianNB(), COLUMNS),
    "knn_af": lambda: _cols(make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=15)), COLUMNS),
    "mlp_af": lambda: _cols(make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(50,), learning_rate_init=1e-3,
                                                                        max_iter=200, random_state=0)), COLUMNS),
}


def _metrics(y: np.ndarray, p: np.ndarray) -> dict:
    return {"precision": float(precision_score(y, p, zero_division=0)),
            "recall": float(recall_score(y, p, zero_division=0)),
            "f1": float(f1_score(y, p, zero_division=0))}


def backtest(d: Elliptic, names: list[str], train_end: int = TRAIN_END, shutdown_step: int = SHUTDOWN_STEP,
             start: int = 1, end: int | None = None) -> dict[str, dict]:
    """Fit each detector on steps start..train_end; score illicit-class metrics on later steps."""
    tr, te = temporal_split(d, train_end, start, end)
    steps = te.X["time_step"].to_numpy()
    y = te.y.to_numpy()
    out = {}
    for name in names:
        model, cols = DETECTORS[name]()
        model.fit(tr.X[cols], tr.y)
        p = model.predict(te.X[cols])
        m = _metrics(y, p)
        m["per_step_f1"] = {int(s): float(f1_score(y[steps == s], p[steps == s], zero_division=0)) for s in np.unique(steps)}
        m["per_step_recall"] = {int(s): float(recall_score(y[steps == s], p[steps == s], zero_division=0)) for s in np.unique(steps)}
        before, after = steps < shutdown_step, steps >= shutdown_step
        m["recall_before_shutdown"] = float(recall_score(y[before], p[before], zero_division=0)) if before.any() else None
        m["recall_after_shutdown"] = float(recall_score(y[after], p[after], zero_division=0)) if after.any() else None
        out[name] = m
    return out
