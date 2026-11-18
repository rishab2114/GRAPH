import networkx as nx
import pandas as pd
import pytest

from gffs.motifs import motif_flags, node_features, thresholds


def _g(edges):
    g = nx.DiGraph(); g.add_edges_from(edges); return g


def test_node_features_degrees_depth_and_peel_runs():
    # a -> b -> c -> d is a peel run (b, c, d have in=1, out<=2); e feeds into hub h with f, g
    g = _g([("a", "b"), ("b", "c"), ("c", "d"), ("e", "h"), ("f", "h"), ("g", "h"), ("h", "i"), ("h", "j")])
    f = node_features(g)
    assert f.loc["h", "in_deg"] == 3 and f.loc["h", "out_deg"] == 2
    assert f.loc["d", "depth"] == 3 and f.loc["a", "depth"] == 0
    assert f.loc["c", "peel_run"] == 3 and f.loc["h", "peel_run"] == 0   # b, c, d are peel transactions
    assert f.loc["a", "peel_run"] == 0                                     # a has in-degree 0


def test_smurfing_requires_reconvergence():
    split_and_merge = _g([("s", "x"), ("s", "y"), ("x", "m"), ("y", "m")])
    split_only = _g([("s", "x"), ("s", "y"), ("x", "p"), ("y", "q")])
    assert node_features(split_and_merge).loc["s", "reconverges"]
    assert not node_features(split_only).loc["s", "reconverges"]


def test_mixing_needs_a_neighbouring_coinjoin():
    # c1 and c2 each have in>=2 and out>=2 and c1 feeds c2 -> both are mixing; c3 is a lone coinjoin
    e = [("u1", "c1"), ("u2", "c1"), ("c1", "c2"), ("c1", "o1"), ("u3", "c2"), ("c2", "o2"), ("c2", "o3"),
         ("v1", "c3"), ("v2", "c3"), ("c3", "w1"), ("c3", "w2")]
    f = node_features(_g(e))
    m = motif_flags(f, k=2, length=2)
    assert m.loc["c1", "mixing_service"] and m.loc["c2", "mixing_service"] and not m.loc["c3", "mixing_service"]
    assert m.loc["c3", "coinjoin"]


def test_thresholds_are_rounded_up_95th_percentiles():
    f = pd.DataFrame({"in_deg": range(1, 101), "out_deg": [1] * 100, "peel_run": [0] * 50 + list(range(1, 51)),
                      "depth": range(100)})
    t = thresholds(f)
    assert t["k"] == 96 and t["length"] == 95   # max of the separate 95th percentiles, rounded up
