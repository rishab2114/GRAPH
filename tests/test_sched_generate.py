from gffs.sched.atoms import ATOMS, BASE
from gffs.sched.generate import canonical_hash, generate, rename
from gffs.sched.heuristic import serial_sgs
from gffs.sched.solve import solve
from gffs.sched.spec import Invalid, compile_spec
from gffs.sched.verify import verify


def test_atoms_have_sources_and_mapping_status():
    assert set(BASE) <= set(ATOMS)
    for a in ATOMS.values():
        assert a["source_doi"] and a["mapping_status"] in ("unverified", "verified") and a["definition"]


def test_generator_is_deterministic_and_always_compiles():
    for comp in [BASE, BASE + ("release_dates",), BASE + ("resource_calendar", "min_time_lags"), BASE + ("deadlines",)]:
        for seed in range(5):
            s1, s2 = generate(comp, "layered", seed), generate(comp, "layered", seed)
            assert s1 == s2 and not isinstance(compile_spec(s1), Invalid)


def test_canonical_hash_ignores_names_and_order_but_not_structure():
    s = generate(BASE + ("release_dates",), "random", 3)
    assert canonical_hash(s) == canonical_hash(rename(s, seed=7))
    t = dict(s); t["precedence"] = s["precedence"][1:]
    assert canonical_hash(t) != canonical_hash(s) or not s["precedence"]


def test_deadline_families_contain_infeasible_instances_and_heuristic_schedules_verify():
    statuses = []
    for seed in range(30):
        spec = generate(BASE + ("deadlines",), "layered", seed)
        inst = compile_spec(spec)
        r = solve(inst)
        statuses.append(r["status"])
        h = serial_sgs(inst)
        if h is not None:
            assert verify(inst, h) == []
            if r["status"] == "optimal":
                assert max(h[t.id] + t.duration for t in inst.tasks) >= r["makespan"]
    assert "infeasible" in statuses and "optimal" in statuses
