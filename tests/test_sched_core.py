"""E01 scheduling core: compiler, verifier, exact solver (AGENT_DISCUSSION.md, L03 / request 1)."""
from gffs.sched.spec import Invalid, compile_spec
from gffs.sched.solve import solve
from gffs.sched.verify import verify

BASE = {"tasks": [{"id": "a", "duration": 2, "demand": 1}, {"id": "b", "duration": 3, "demand": 1},
                  {"id": "c", "duration": 2, "demand": 2}],
        "precedence": [["a", "c"]], "resource": {"capacity": 2}, "horizon": 12}


def test_compiler_rejects_cycles_unknown_ids_and_bad_numbers():
    assert isinstance(compile_spec({**BASE, "precedence": [["a", "c"], ["c", "a"]]}), Invalid)
    assert isinstance(compile_spec({**BASE, "precedence": [["a", "z"]]}), Invalid)
    bad = {**BASE, "tasks": [{"id": "a", "duration": 0, "demand": 1}]}
    assert isinstance(compile_spec(bad), Invalid)
    assert not isinstance(compile_spec(BASE), Invalid)


def test_solver_is_optimal_and_its_schedule_passes_the_independent_verifier():
    inst = compile_spec(BASE)
    r = solve(inst)
    # a(0-2) and b(0-3) run together (demand 2 = capacity); c needs both units, after a and when b is done -> 3..5
    assert r["status"] == "optimal" and r["makespan"] == 5
    assert verify(inst, r["starts"]) == []


def test_calendar_drop_and_release_dates_change_the_optimum():
    spec = {**BASE, "resource": {"capacity": 2, "calendar": [{"start": 3, "end": 5, "capacity": 1}]},
            "tasks": [{"id": "a", "duration": 2, "demand": 1}, {"id": "b", "duration": 3, "demand": 1, "release": 1},
                      {"id": "c", "duration": 2, "demand": 2}]}
    inst = compile_spec(spec)
    r = solve(inst)
    assert r["status"] == "optimal" and verify(inst, r["starts"]) == []
    assert r["makespan"] > 5


def test_infeasible_instance_is_reported_with_a_certificate():
    spec = {**BASE, "tasks": [{"id": "a", "duration": 2, "demand": 3}], "precedence": []}   # demand > capacity always
    r = solve(compile_spec(spec))
    assert r["status"] == "infeasible" and "demand exceeds capacity" in r["certificate"]
    tight = {**BASE, "horizon": 4}                                                            # critical path a->c = 4 fits; b+c resource forces 5
    r2 = solve(compile_spec(tight))
    assert r2["status"] == "infeasible"


def test_verifier_catches_each_violation_type():
    inst = compile_spec({**BASE, "tasks": [{"id": "a", "duration": 2, "demand": 1, "release": 1},
                                           {"id": "b", "duration": 3, "demand": 1}, {"id": "c", "duration": 2, "demand": 2}]})
    v = verify(inst, {"a": 0, "b": 0, "c": 1})
    kinds = {x.split(":")[0] for x in v}
    assert {"release", "precedence", "capacity"} <= kinds


def _brute(inst):
    import itertools
    best = None
    ranges = [range(t.release, inst.horizon - t.duration + 1) for t in inst.tasks]
    for combo in itertools.product(*ranges):
        st = {t.id: s for t, s in zip(inst.tasks, combo)}
        if not verify(inst, st):
            ms = max(s + t.duration for t, s in zip(inst.tasks, combo))
            best = ms if best is None else min(best, ms)
    return best


def test_solver_matches_brute_force_on_random_tiny_instances():
    import random
    rng = random.Random(0)
    for _ in range(25):
        n = rng.randint(2, 4)
        tasks = [{"id": f"t{i}", "duration": rng.randint(1, 3), "demand": rng.randint(0, 2), "release": rng.randint(0, 2)}
                 for i in range(n)]
        prec = [[f"t{i}", f"t{j}"] for i in range(n) for j in range(i + 1, n) if rng.random() < 0.3]
        cal = [{"start": 2, "end": 4, "capacity": rng.randint(0, 2)}] if rng.random() < 0.5 else []
        spec = {"tasks": tasks, "precedence": prec, "resource": {"capacity": 2, "calendar": cal}, "horizon": 8}
        inst = compile_spec(spec)
        r, b = solve(inst), _brute(inst)
        if b is None:
            assert r["status"] == "infeasible"
        else:
            assert r["status"] == "optimal" and r["makespan"] == b and verify(inst, r["starts"]) == []
