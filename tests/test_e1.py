from gffs.attack import technique_sets
from gffs.e1 import run_e1


def test_run_e1_reports_three_methods_on_same_candidates(make_bundle):
    before = technique_sets(make_bundle({"A": ["T1", "T2"], "B": ["T2", "T3"], "C": ["T3", "T4"]}))
    t = technique_sets(make_bundle({"A": ["T1", "T2", "T3"], "B": ["T2", "T3"], "C": ["T3", "T4"]}))
    after = technique_sets(make_bundle({"A": ["T1", "T2", "T3"], "B": ["T2", "T3", "T4"], "C": ["T3", "T4"]}))
    r = run_e1(before, t, after, k=2)
    assert set(r) == {"forecaster", "frequency", "random"}
    assert len({m["n_candidates"] for m in r.values()}) == 1
    assert r["forecaster"]["n_positive"] == 1   # only T2–T4 is new between T and after
