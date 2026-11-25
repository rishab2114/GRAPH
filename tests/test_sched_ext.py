"""E01 solver extensions: multiple renewable resources, maximum lags, multi-mode activities with nonrenewable budgets."""
import itertools
import random

from gffs.sched.solve import solve
from gffs.sched.spec import Invalid, compile_spec
from gffs.sched.verify import verify

MM = {"tasks": [{"id": "a", "modes": [{"duration": 4, "demand": {"r1": 1}, "consumption": {"money": 0}},
                                      {"duration": 2, "demand": {"r1": 1}, "consumption": {"money": 3}}]},
                {"id": "b", "modes": [{"duration": 3, "demand": {"r1": 1, "r2": 1}, "consumption": {"money": 0}},
                                      {"duration": 1, "demand": {"r1": 1, "r2": 1}, "consumption": {"money": 3}}]}],
      "precedence": [["a", "b"]], "resources": {"r1": {"capacity": 1}, "r2": {"capacity": 1}},
      "nonrenewable": {"money": 3}, "horizon": 10}


def test_multimode_with_budget_picks_the_best_affordable_modes():
    inst = compile_spec(MM)
    r = solve(inst)
    # budget 3 buys one fast mode: fast a (2) + slow b (3) = 5, or slow a (4) + fast b (1) = 5
    assert r["status"] == "optimal" and r["makespan"] == 5 and verify(inst, r["starts"], r["modes"]) == []


def test_max_lag_and_budget_violations_are_caught_by_the_verifier():
    inst = compile_spec({**MM, "max_lags": [["a", "b", 2]]})
    r = solve(inst)
    assert r["status"] == "optimal" and verify(inst, r["starts"], r["modes"]) == []
    v = verify(inst, {"a": 0, "b": 5}, {"a": 1, "b": 1})
    assert any(x.startswith("max_lag") for x in v) and any(x.startswith("budget") for x in v)


def test_unknown_resource_reference_is_invalid():
    bad = {**MM, "tasks": [{"id": "a", "modes": [{"duration": 1, "demand": {"zz": 1}}]}], "precedence": []}
    assert isinstance(compile_spec(bad), Invalid)


def _brute(inst):
    best = None
    ids = [t.id for t in inst.tasks]
    for modes in itertools.product(*[range(len(t.modes)) for t in inst.tasks]):
        md = dict(zip(ids, modes))
        ranges = [range(t.release, inst.horizon - t.modes[md[t.id]].duration + 1) for t in inst.tasks]
        for combo in itertools.product(*ranges):
            st = dict(zip(ids, combo))
            if not verify(inst, st, md):
                ms = max(st[t.id] + t.modes[md[t.id]].duration for t in inst.tasks)
                best = ms if best is None else min(best, ms)
    return best


def test_extended_solver_matches_brute_force():
    rng = random.Random(1)
    for _ in range(20):
        n = rng.randint(2, 3)
        tasks = [{"id": f"t{i}", "modes": [{"duration": rng.randint(1, 3), "demand": {"r1": rng.randint(0, 2), "r2": rng.randint(0, 1)},
                                            "consumption": {"m": rng.randint(0, 2)}} for _ in range(rng.randint(1, 2))]}
                 for i in range(n)]
        prec = [[f"t{i}", f"t{j}"] for i in range(n) for j in range(i + 1, n) if rng.random() < 0.4]
        spec = {"tasks": tasks, "precedence": prec, "resources": {"r1": {"capacity": 2}, "r2": {"capacity": 1}},
                "nonrenewable": {"m": rng.randint(1, 4)}, "horizon": 7}
        if prec and rng.random() < 0.5:
            spec["max_lags"] = [[prec[0][0], prec[0][1], rng.randint(1, 4)]]
        inst = compile_spec(spec); r = solve(inst); b = _brute(inst)
        if b is None:
            assert r["status"] == "infeasible"
        else:
            assert r["status"] == "optimal" and r["makespan"] == b and verify(inst, r["starts"], r["modes"]) == []
