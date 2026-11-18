import numpy as np
import pytest

from gffs.evaluate import evaluate
from gffs.forecaster import fit_forecaster, forecast
from gffs.graph import build_graph


def test_evaluate_perfect_ranking():
    r = evaluate(np.array([0.9, 0.8, 0.1, 0.0]), np.array([1, 1, 0, 0]), k=2)
    assert r["auc"] == 1.0 and r["precision_at_k"] == 1.0 and r["n_positive"] == 2


def test_evaluate_rejects_no_positives():
    with pytest.raises(ValueError, match="no newly documented pairs"):
        evaluate(np.array([0.5, 0.4]), np.array([0, 0]))


def test_forecaster_prefers_bridged_pair():
    # Training: A–C and B–D (two bridges each) get linked by T; pairs with E (no bridge) do not.
    # Scoring: T1–T3 has two bridges (T2, T4); T1–T5 has none.
    before = build_graph({"a": frozenset({"A", "B"}), "b": frozenset({"B", "C"}), "c": frozenset({"A", "D"}),
                          "d": frozenset({"D", "C"}), "e": frozenset({"E"})})
    t = build_graph({"a2": frozenset({"A", "B", "C", "D"}),
                     "z": frozenset({"E"}), "y": frozenset({"T1", "T2"}), "x": frozenset({"T2", "T3"}),
                     "w": frozenset({"T1", "T4"}), "v": frozenset({"T4", "T3"}), "u": frozenset({"T5"})})
    s = forecast(fit_forecaster(before, t), t)
    assert s[("T1", "T3")] > s[("T1", "T5")]
