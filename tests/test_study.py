from gffs.attack import technique_sets
from gffs.models import MODELS
from gffs.study import run_split


def _sets(make_bundle, uses):
    return technique_sets(make_bundle(uses))


def test_run_split_reports_every_method_with_ci_and_strata(make_bundle):
    names = [f"T{i}" for i in range(12)]

    def sets(offsets, extra=()):
        # Group Gi uses techniques at the given offsets from i; groups in `extra` also use i+4.
        return _sets(make_bundle, {f"G{i}": [names[(i + d) % 12] for d in offsets + ([4] if i in extra else [])]
                                   for i in range(12)})

    before = sets([0, 1, 3])             # links at distances 1, 2, 3
    t = sets([0, 1, 3, 6])               # adds distances 5, 6 -> training positives
    after = sets([0, 1, 3, 6], extra={0, 1, 2})  # adds some distance-4 links -> mixed test labels
    r = run_split(before, t, after, k=5, n_boot=20, n_strata=2)
    assert set(r["methods"]) == set(MODELS) | {"frequency", "random"}
    for m in r["methods"].values():
        assert {"auc", "precision_at_k", "strat_auc", "vs_frequency"} <= set(m)
    assert r["methods"]["frequency"]["vs_frequency"] == {"diff": 0.0, "lo": 0.0, "hi": 0.0}
    assert r["graph"]["n_positive"] > 0 and 0 < r["graph"]["density_t"] <= 1
