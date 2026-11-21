import networkx as nx
import numpy as np
import pytest

from gffs.motifs import MOTIFS
from gffs.synthworld import family_items, make_world, split_families


def test_split_families_is_disjoint_complete_and_deterministic():
    f = split_families(0)
    assert sorted(len(v) for v in f.values()) == [2, 3, 3] and set(f) == {"A", "B", "C"}
    assert sorted(m for v in f.values() for m in v) == sorted(MOTIFS)
    assert split_families(0) == f and split_families(1) != f


def test_family_items_are_singles_and_within_family_pairs():
    items = family_items(["fan_in", "fan_out", "layering"])
    assert ("fan_in",) in items and ("fan_in", "fan_out") in items and len(items) == 3 + 3


@pytest.fixture(scope="module")
def worlds():
    kw = dict(seed=3, families=split_families(0), n_steps=8, train_end=5, licit_per_step=120, illicit_per_step=3)
    return {k: make_world(kind=k, **kw) for k in ("W0", "W1", "W2")}


def test_world_shape_labels_and_no_cross_step_edges(worlds):
    d = worlds["W1"]
    assert set(d.X["time_step"].unique()) == set(range(1, 9))
    ill = (d.y == 1).mean()
    assert 0.01 < ill < 0.4 and d.y.isna().any() and (d.y == 0).any()
    step = d.X["time_step"]
    assert (step.reindex(d.edges["txId1"]).to_numpy() == step.reindex(d.edges["txId2"]).to_numpy()).all()
    g = nx.DiGraph(list(zip(d.edges["txId1"], d.edges["txId2"])))
    assert nx.is_directed_acyclic_graph(g)


def test_training_period_is_identical_across_world_types(worlds):
    def train_part(d):
        ids = d.X.index[d.X["time_step"] <= 5]
        e = d.edges[d.edges["txId1"].isin(ids)]
        return sorted(ids.tolist()), sorted(map(tuple, e.to_numpy().tolist())), d.y.reindex(ids).fillna(-1).tolist()
    assert train_part(worlds["W0"]) == train_part(worlds["W1"]) == train_part(worlds["W2"])


def test_shift_changes_the_holdout(worlds):
    hold = lambda d: d.edges[d.edges["txId1"].isin(d.X.index[d.X["time_step"] > 5])].shape[0]
    assert hold(worlds["W1"]) != hold(worlds["W0"]) or hold(worlds["W2"]) != hold(worlds["W0"])
    assert hold(worlds["W2"]) > hold(worlds["W1"])          # camouflage adds edges


def test_run_cutoff_accepts_custom_stress_sets(worlds):
    from gffs.e3e4 import run_cutoff
    d = worlds["W1"]
    r = run_cutoff(d, cutoff=5, holdout_end=8, val_len=2, instances_per_pair=3, n_boot=5,
                   detectors=["lr", "tree", "nb"], sampler=lambda g: (2, 3),
                   stress_sets={"SA": [("fan_in",)], "SC": [("peel_chain", "layering")]})
    assert set(r["agreement"]["all"]) == {"S0_recent_data", "SA", "SC"}
