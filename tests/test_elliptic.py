import numpy as np
import pandas as pd
import pytest

from gffs.elliptic import DETECTORS, backtest, compute_facts, load, temporal_split


@pytest.fixture
def tiny(tmp_path):
    """6 time steps, 4 tx per step; illicit = first 120 features at +1 (learnable by any model)."""
    rng = np.random.default_rng(0)
    rows, classes, edges = [], [], []
    tx = 1
    for step in range(1, 7):
        for j in range(4):
            label = ["1", "2", "2", "unknown"][j]
            f = rng.normal(0, 0.1, 165)
            f[:120] = 1.0 if label == "1" else -1.0  # strong signal across many columns
            rows.append([tx, step, *f]); classes.append((tx, label))
            if j > 0:
                edges.append((tx - 1, tx))
            tx += 1
    pd.DataFrame(rows).to_csv(tmp_path / "elliptic_txs_features.csv", header=False, index=False)
    pd.DataFrame(classes, columns=["txId", "class"]).to_csv(tmp_path / "elliptic_txs_classes.csv", index=False)
    pd.DataFrame(edges, columns=["txId1", "txId2"]).to_csv(tmp_path / "elliptic_txs_edgelist.csv", index=False)
    return tmp_path


def test_load_shapes_and_labels(tiny):
    d = load(tiny)
    assert d.X.shape == (24, 166) and list(d.X.columns[:2]) == ["time_step", "local_1"]
    assert d.X.columns[93] == "local_93" and d.X.columns[94] == "agg_1"
    assert set(d.y.dropna().unique()) == {0, 1} and d.y.isna().sum() == 6


def test_facts(tiny):
    f = compute_facts(load(tiny))
    assert f == {"n_nodes": 24, "n_edges": 18, "n_illicit": 6, "n_licit": 12, "n_unknown": 6,
                 "n_steps": 6, "n_features": 166, "edges_cross_time_steps": 0}


def test_temporal_split_drops_unknown_and_respects_cutoff(tiny):
    tr, te = temporal_split(load(tiny), train_end=4)
    assert tr.X["time_step"].max() == 4 and te.X["time_step"].min() == 5
    assert len(tr.y) == 12 and len(te.y) == 6 and not tr.y.isna().any()


def test_backtest_reports_overall_per_step_and_shutdown(tiny):
    d = load(tiny)
    r = backtest(d, ["lr_af", "rf_af"], train_end=4, shutdown_step=6)
    assert r["rf_af"]["f1"] == pytest.approx(1.0)
    assert set(r["rf_af"]["per_step_f1"]) == {5, 6}
    assert {"recall_before_shutdown", "recall_after_shutdown"} <= set(r["rf_af"])


def test_at_least_eight_detectors():
    assert len(DETECTORS) >= 8 and {"lr_af", "lr_lf", "rf_af", "rf_lf"} <= set(DETECTORS)


def test_rank_agreement_perfect_order_and_offset():
    from gffs.phase0 import rank_agreement
    val = {"a": {"recall": 0.9}, "b": {"recall": 0.7}, "c": {"recall": 0.5}}
    test = {"a": {"recall": 0.6}, "b": {"recall": 0.4}, "c": {"recall": 0.2}}
    r = rank_agreement(val, test, "recall")
    assert r["spearman"] == pytest.approx(1.0) and r["mean_abs_error"] == pytest.approx(0.3)
    assert r["mean_signed_error"] == pytest.approx(0.3)   # stress test overstates by 30 points


def test_rolling_backtest_structure(tiny):
    from gffs.phase0 import rolling_backtest
    rows = rolling_backtest(load(tiny), ["lr_af", "rf_af"], cutoffs=[4], val_len=2, horizon=2)
    assert len(rows) == 1 and rows[0]["cutoff"] == 4
    assert set(rows[0]["validation"]) == {"lr_af", "rf_af"} and set(rows[0]["test"]) == {"lr_af", "rf_af"}
    assert "recall" in rows[0]["agreement"]
