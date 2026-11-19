import numpy as np
import pytest

from gffs.e3e4 import GRAPH_DETECTORS, agreement, compare_stress_tests


def _preds(rates, n, seed):
    rng = np.random.default_rng(seed)
    return {f"d{i}": rng.random(n) < r for i, r in enumerate(rates)}


def test_agreement_perfect_ranking_and_offset():
    hold = _preds([0.1, 0.3, 0.5, 0.7, 0.9], 4000, 1)
    stress = _preds([0.3, 0.5, 0.7, 0.9, 0.95], 4000, 2)
    a = agreement(stress, hold, n_boot=50, seed=0)
    assert a["spearman"] == pytest.approx(1.0)
    assert a["mean_signed_error"] > 0.1 and a["mean_abs_error"] > 0.1 and a["ci"][0] > 0.5


def test_compare_detects_the_better_stress_test():
    hold = _preds([0.1, 0.3, 0.5, 0.7, 0.9, 0.2, 0.6, 0.4], 3000, 1)
    good = _preds([0.15, 0.35, 0.55, 0.75, 0.95, 0.25, 0.65, 0.45], 3000, 2)
    bad = _preds([0.9, 0.1, 0.8, 0.2, 0.7, 0.3, 0.6, 0.4], 3000, 3)
    c = compare_stress_tests(good, bad, hold, n_boot=100, seed=0)
    assert c["rho_diff"] > 0 and c["rho_diff_ci"][0] > 0


def test_ten_graph_detectors():
    assert len(GRAPH_DETECTORS) == 10 and "lr_lf" not in GRAPH_DETECTORS and "rf_balanced" in GRAPH_DETECTORS


def test_run_cutoff_on_tiny_data_produces_every_stress_test(tmp_path):
    import numpy as np
    import pandas as pd
    from gffs.e3e4 import run_cutoff
    from gffs.elliptic import load
    rng = np.random.default_rng(0)
    rows, classes, edges, tx = [], [], [], 1
    for step in range(1, 9):
        for j in range(12):
            label = "1" if j < 3 else ("2" if j < 10 else "unknown")
            f = rng.normal(0, 0.1, 165); rows.append([tx, step, *f]); classes.append((tx, label))
            if j % 3:                                    # small chains within each step
                edges.append((tx - 1, tx))
            if j == 11:
                edges.append((tx - 11, tx)); edges.append((tx - 10, tx))   # a fan-in hub
            tx += 1
    pd.DataFrame(rows).to_csv(tmp_path / "elliptic_txs_features.csv", header=False, index=False)
    pd.DataFrame(classes, columns=["txId", "class"]).to_csv(tmp_path / "elliptic_txs_classes.csv", index=False)
    pd.DataFrame(edges, columns=["txId1", "txId2"]).to_csv(tmp_path / "elliptic_txs_edgelist.csv", index=False)
    r = run_cutoff(load(tmp_path), cutoff=6, holdout_end=8, val_len=2, shutdown_step=8, s1_pairs=[("fan_in", "pass_through")],
                   instances_per_pair=3, n_boot=5, detectors=["lr", "tree", "nb"], sampler=lambda g: (2, 3))
    assert {"S0_recent_data", "S1_graph_forecast", "S2_uniform_pairs", "S3_single_motifs"} <= set(r["agreement"]["all"])
    assert r["windows"]["all"] == [7, 8] and r["cutoff"] == 6
