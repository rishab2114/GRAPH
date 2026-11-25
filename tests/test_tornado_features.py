import pandas as pd

from gffs.tornado_features import FEATURES, account_features


def _e(rows):
    return pd.DataFrame(rows, columns=["src", "dst", "category"])


def test_layer_counts_are_distinct_counterparties_and_layers_never_merge():
    e = _e([("a", "b", "simple_transfer"), ("a", "b", "simple_transfer"), ("a", "c", "value_call"), ("a", "k", "call")])
    f = account_features(e, classes={})
    assert (f.loc["a", "out_S"], f.loc["a", "out_V"], f.loc["a", "out_K"], f.loc["a", "out_W"]) == (1, 1, 1, 2)
    assert f.loc["b", "in_S"] == 1 and f.loc["k", "in_K"] == 1 and list(f.columns) == FEATURES


def test_peel_run_depth_and_reconvergence():
    chain = [("p0", "p1", "simple_transfer"), ("p1", "p2", "simple_transfer"), ("p2", "p3", "simple_transfer"),
             ("p1", "s1", "simple_transfer"), ("p2", "s2", "simple_transfer")]
    smurf = [("x", "m1", "simple_transfer"), ("x", "m2", "simple_transfer"), ("m1", "z", "simple_transfer"),
             ("m2", "z", "simple_transfer")]
    f = account_features(_e(chain + smurf), classes={})
    assert f.loc["p2", "peel_run_W"] >= 3          # p1 -> p2 -> p3 are peel accounts (in=1, out<=2)
    assert f.loc["p3", "depth_W"] == 3 and f.loc["p0", "depth_W"] == 0
    assert f.loc["x", "reconverges_W"] == 1 and f.loc["p0", "reconverges_W"] == 0


def test_contract_and_unknown_shares_use_the_supplied_as_of_classes():
    e = _e([("a", "k1", "call"), ("a", "e1", "simple_transfer"), ("a", "u1", "value_call")])
    f = account_features(e, classes={"k1": "contract", "e1": "eoa", "u1": "unknown"})
    assert abs(f.loc["a", "share_contract"] - 1 / 3) < 1e-9 and abs(f.loc["a", "share_unknown"] - 1 / 3) < 1e-9


def test_neighbour_aggregates():
    e = _e([("h1", "a", "simple_transfer"), ("h2", "a", "simple_transfer"), ("h2", "b", "simple_transfer"),
            ("a", "c", "simple_transfer")])
    f = account_features(e, classes={})
    assert f.loc["a", "pred_out_W_max"] == 2 and f.loc["a", "pred_out_W_mean"] == 1.5 and f.loc["a", "succ_in_W_max"] == 1
