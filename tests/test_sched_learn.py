import numpy as np

from gffs.sched.learn import FEATURES, fit_priority, pairwise_examples, policy_schedule, task_features
from gffs.sched.spec import compile_spec
from gffs.sched.verify import verify

SPEC = {"tasks": [{"id": "a", "duration": 3, "demand": 1}, {"id": "b", "duration": 1, "demand": 1},
                  {"id": "c", "duration": 2, "demand": 2, "deadline": 9}],
        "precedence": [["a", "c"]], "resource": {"capacity": 2}, "horizon": 12}


def test_task_features_have_fixed_columns_and_sensible_values():
    f = task_features(compile_spec(SPEC))
    assert list(f.columns) == FEATURES and set(f.index) == {"a", "b", "c"}
    assert f.loc["a", "tail"] == 5 and f.loc["c", "has_deadline"] == 1 and f.loc["b", "n_succ"] == 0


def test_pairwise_examples_label_who_starts_first_in_the_optimal_schedule():
    X, y = pairwise_examples(compile_spec(SPEC), {"a": 0, "b": 0, "c": 3})
    assert len(X) == len(y) and set(np.unique(y)) <= {0, 1} and len(y) == 4     # (a,c),(c,a),(b,c),(c,b); ties a/b skipped


def test_learned_policy_schedules_are_always_verified():
    inst = compile_spec(SPEC)
    X, y = pairwise_examples(inst, {"a": 0, "b": 0, "c": 3})
    w = fit_priority([X], [y])
    st = policy_schedule(inst, w)
    assert st is not None and verify(inst, st) == []
