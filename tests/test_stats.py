import numpy as np
import pytest

from gffs.stats import paired_bootstrap_diff, popularity_strata, stratified_auc


def test_stratified_auc_is_half_when_scores_only_track_strata():
    strata = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    labels = np.array([1, 0, 1, 0, 1, 0, 1, 0])
    scores = strata.astype(float)  # pure popularity: constant inside each stratum
    assert stratified_auc(scores, labels, strata) == pytest.approx(0.5)


def test_stratified_auc_is_one_when_perfect_within_strata():
    strata = np.array([0, 0, 1, 1])
    labels = np.array([1, 0, 1, 0])
    scores = np.array([0.2, 0.1, 0.9, 0.8])  # overall AUC would be 0.75
    assert stratified_auc(scores, labels, strata) == pytest.approx(1.0)


def test_stratified_auc_skips_single_class_strata():
    strata = np.array([0, 0, 1, 1])
    labels = np.array([1, 0, 0, 0])
    assert stratified_auc(np.array([0.9, 0.1, 0.5, 0.5]), labels, strata) == pytest.approx(1.0)


def test_paired_bootstrap_identical_scores_gives_zero():
    rng = np.random.default_rng(0)
    s, y = rng.random(200), rng.integers(0, 2, 200)
    r = paired_bootstrap_diff(s, s, y, n_boot=50)
    assert r == {"diff": 0.0, "lo": 0.0, "hi": 0.0}


def test_paired_bootstrap_detects_clear_winner():
    y = np.array([1] * 50 + [0] * 150)
    good = y + np.random.default_rng(1).normal(0, 0.3, 200)
    bad = np.random.default_rng(2).random(200)
    r = paired_bootstrap_diff(good, bad, y, n_boot=200)
    assert r["lo"] > 0


def test_popularity_strata_are_deciles():
    s = popularity_strata(np.arange(1, 101, dtype=float), n_bins=10)
    assert sorted(set(s)) == list(range(10)) and (np.bincount(s) == 10).all()
