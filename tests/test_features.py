import pytest

from gffs.baselines import frequency_scores, random_scores
from gffs.features import FEATURES, pair_features
from gffs.graph import build_graph


def test_shared_neighbour_features():
    g = build_graph({"a": frozenset({"T1", "T2"}), "b": frozenset({"T2", "T3"}),
                     "c": frozenset({"T1", "T4"}), "d": frozenset({"T4", "T3"})})
    df = pair_features(g, [("T1", "T3")])
    assert list(df.columns) == FEATURES
    f = df.iloc[0]
    assert f.common_neighbours == 2          # T2 and T4
    assert f.jaccard == pytest.approx(2 / 2)  # N(T1)={T2,T4}, N(T3)={T2,T4}
    assert f.weighted_cn == 2


def test_features_keep_pair_order():
    g = build_graph({"a": frozenset({"T1", "T2"}), "b": frozenset({"T3", "T4"})})
    pairs = [("T2", "T4"), ("T1", "T3")]
    assert list(pair_features(g, pairs).index) == pairs


def test_frequency_baseline_is_product_of_freq():
    g = build_graph({"a": frozenset({"T1", "T2"}), "b": frozenset({"T2"}), "c": frozenset({"T3"})})
    assert frequency_scores(g, [("T1", "T2"), ("T2", "T3")]).tolist() == [2, 2]


def test_random_scores_reproducible():
    p = [("T1", "T2"), ("T1", "T3")]
    assert (random_scores(p, 7) == random_scores(p, 7)).all()
