"""Codex L07 (solver outcomes), L08 (family vs instance keys), L10 (typed rejections at the input boundary)."""
from types import SimpleNamespace

import pytest

from gffs.sched import solve as solve_mod
from gffs.sched.generate import family_id, generate, instance_fingerprint, rename
from gffs.sched.solve import solve
from gffs.sched.spec import Invalid, compile_spec
from gffs.sched.verify import verify

BASE = {"tasks": [{"id": "a", "duration": 2, "demand": 1}, {"id": "b", "duration": 3, "demand": 1}],
        "precedence": [["a", "b"]], "resource": {"capacity": 2}, "horizon": 10}


# ---- L07: four distinct outcomes; only a certified optimum gives an optimality reference
def _fake(status, x=None, gap=0.0):
    return lambda *a, **k: SimpleNamespace(status=status, x=x, mip_gap=gap, message="fake")


def test_timeout_without_incumbent_is_unknown_not_infeasible(monkeypatch):
    monkeypatch.setattr(solve_mod, "milp", _fake(1, None))
    r = solve(compile_spec(BASE))
    assert r["status"] == "unknown" and "certificate" not in r


def test_incumbent_without_proof_is_feasible_and_not_optimal(monkeypatch):
    real = solve(compile_spec(BASE))
    inst = compile_spec(BASE)
    # replay the real incumbent but say "time limit reached" with a positive gap
    import numpy as np
    from scipy.optimize import milp as real_milp
    def fake(*a, **k):
        res = real_milp(*a, **k); return SimpleNamespace(status=1, x=res.x, mip_gap=0.2, message="time limit")
    monkeypatch.setattr(solve_mod, "milp", fake)
    r = solve(inst)
    assert r["status"] == "feasible" and r["certified_optimal"] is False and verify(inst, r["starts"], r["modes"]) == []
    assert real["status"] == "optimal" and real["certified_optimal"] is True


def test_proven_infeasible_keeps_its_certificate():
    r = solve(compile_spec({**BASE, "horizon": 4}))
    assert r["status"] == "infeasible" and r["certificate"]


# ---- L08: family id ignores parameters; instance fingerprint ignores names; parallel relations both kept
def test_family_id_is_the_same_across_parameter_draws_but_instances_differ():
    a, b = generate(("precedence", "renewable_capacity", "deadlines"), "layered", 0), generate(("precedence", "renewable_capacity", "deadlines"), "layered", 1)
    assert family_id(a) == family_id(b) and instance_fingerprint(a) != instance_fingerprint(b)
    c = generate(("precedence", "renewable_capacity", "release_dates"), "layered", 0)
    assert family_id(c) != family_id(a)
    assert instance_fingerprint(a) == instance_fingerprint(rename(a, seed=3))


def test_precedence_and_lag_on_the_same_pair_are_both_kept():
    only_p = {**BASE}
    both = {**BASE, "lags": [["a", "b", 1]]}
    assert instance_fingerprint(only_p) != instance_fingerprint(both)


# ---- L10: malformed input returns a typed rejection, never an exception
@pytest.mark.parametrize("bad", [
    {"tasks": None, "precedence": [], "resource": {"capacity": 1}, "horizon": 5},
    {**BASE, "precedence": [None]},
    {**BASE, "precedence": "a,b"},
    {**BASE, "resource": None},
    {**BASE, "horizon": 10 ** 6},
    {**BASE, "tasks": [{"id": "a", "duration": 2.5, "demand": 1}]},
    [1, 2, 3],
])
def test_malformed_specs_are_invalid(bad):
    assert isinstance(compile_spec(bad), Invalid)


def test_verifier_rejects_non_integer_or_missing_starts():
    inst = compile_spec(BASE)
    assert verify(inst, {"a": 0.5, "b": 3})[0].startswith("type")
    assert verify(inst, {"a": 0})[0].startswith("coverage")
