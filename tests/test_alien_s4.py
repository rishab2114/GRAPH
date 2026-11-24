import numpy as np

from gffs.alien_s4 import bridging_counts, coherence, fuse, recovery, repertoires, vendi_pairs


def _works():
    # year, concepts; authors per work
    return {"w1": {"year": 2010, "concepts": ["a", "b"]}, "w2": {"year": 2011, "concepts": ["a", "b", "c"]},
            "w3": {"year": 2012, "concepts": ["c", "d"]}, "w4": {"year": 2015, "concepts": ["a", "d"]}}


def test_repertoires_only_use_works_up_to_the_year():
    auth = {"w1": ["x"], "w3": ["x"], "w4": ["y"]}
    r = repertoires(_works(), auth, upto=2013)
    assert r == {"x": {"a", "b", "c", "d"}}


def test_bridging_counts_authors_holding_every_atom_even_in_separate_papers():
    reps = {"x": {"a", "b", "c", "d"}, "y": {"a", "c"}, "z": {"b"}}
    assert bridging_counts(reps, [("a", "d"), ("a", "c"), ("b", "c"), ("d", "e")]) == [1, 2, 1, 0]


def test_coherence_scores_cooccurring_pairs_above_unrelated_ones():
    works = {f"p{i}": {"year": 2010, "concepts": c} for i, c in enumerate(
        [["a", "b"]] * 5 + [["b", "c"]] * 5 + [["d", "e"]] * 5 + [["a", "c"]] * 2)}
    s = coherence(works, upto=2010, pairs=[("a", "b"), ("a", "d")], dim=3)
    assert s[0] > s[1]


def test_fuse_is_zscore_mix_and_beta_one_is_pure_unavailability():
    c = np.array([1.0, 2.0, 3.0]); u = np.array([3.0, 1.0, 2.0])
    assert np.allclose(fuse(c, u, 0.0), (c - c.mean()) / c.std())
    assert np.argmax(fuse(c, u, 1.0)) == 0


def test_recovery_reports_enrichment_over_chance():
    scores = np.array([0.9, 0.8, 0.1, 0.0]); hit = np.array([1, 0, 0, 1])
    r = recovery(scores, hit, k=2)
    assert r == {"k": 2, "hits": 1, "expected": 1.0, "enrichment": 1.0}


def test_vendi_of_identical_pairs_is_one_and_of_disjoint_pairs_is_n():
    assert abs(vendi_pairs([("a", "b"), ("a", "b")]) - 1.0) < 1e-9
    assert abs(vendi_pairs([("a", "b"), ("c", "d"), ("e", "f")]) - 3.0) < 1e-9
