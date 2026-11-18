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
