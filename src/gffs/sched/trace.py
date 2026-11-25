"""E01 end-to-end trace (Codex E01): atom -> combination -> validated scenario -> solver answer -> learner prediction ->
evaluation record, for every composition of the base with 0-2 extension atoms, 4 DAG templates and a few seeds.

    python -m gffs.sched.trace        # -> results/e01_trace.jsonl and results/e01_summary.json
"""
from __future__ import annotations

import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

from gffs.sched.atoms import ATOMS, BASE
from gffs.sched.generate import TEMPLATES, canonical_hash, generate
from gffs.sched.heuristic import serial_sgs
from gffs.sched.records import Combination, Run, Scenario, to_json
from gffs.sched.solve import solve
from gffs.sched.spec import Invalid, compile_spec
from gffs.sched.verify import verify

EXTENSIONS = [a for a in ATOMS if a not in BASE]


def compositions(max_extra: int = 2) -> list[tuple[str, ...]]:
    return [BASE + tuple(c) for k in range(max_extra + 1) for c in itertools.combinations(EXTENSIONS, k)]


def complexity(spec: dict) -> dict:
    g = nx.DiGraph(); g.add_nodes_from(t["id"] for t in spec["tasks"]); g.add_edges_from(map(tuple, spec["precedence"]))
    dem = sum(t["duration"] * t["demand"] for t in spec["tasks"])
    return {"tasks": len(spec["tasks"]), "depth": nx.dag_longest_path_length(g) if g.number_of_edges() else 0,
            "edges": g.number_of_edges(), "resource_load": round(dem / (spec["resource"]["capacity"] * spec["horizon"]), 3)}


def main(seeds: int = 3) -> None:
    out = Path("results/e01_trace.jsonl"); out.parent.mkdir(exist_ok=True)
    stats = defaultdict(Counter); hashes = Counter(); rows = 0
    with out.open("w") as fh:
        for comp in compositions():
            cmb = Combination(list(comp))
            fh.write(json.dumps({"type": "Combination", **json.loads(to_json(cmb))}) + "\n")
            for tpl in TEMPLATES:
                for seed in range(seeds):
                    spec = generate(comp, tpl, seed)
                    inst = compile_spec(spec)
                    if isinstance(inst, Invalid):
                        stats[comp]["invalid"] += 1; continue
                    target = solve(inst)
                    ver = verify(inst, target["starts"]) if target["status"] in ("optimal", "feasible") else []
                    scn = Scenario(cmb.id, tpl, seed, spec, canonical_hash(spec), target, ver, complexity(spec))
                    hashes[scn.family_hash] += 1
                    h = serial_sgs(inst)
                    pred = {"feasible": h is not None, "makespan": (max(h[t.id] + t.duration for t in inst.tasks) if h else None)}
                    truth_feasible = target["status"] != "infeasible"
                    outcome = {"feasibility_correct": pred["feasible"] == truth_feasible,
                               "gap": (pred["makespan"] - target["makespan"]) / target["makespan"]
                               if pred["feasible"] and truth_feasible else None,
                               "schedule_valid": (verify(inst, h) == []) if h else None}
                    run = Run(scn.id, "serial_sgs_deadline_rule", pred, outcome)
                    for rec, kind in ((scn, "Scenario"), (run, "Run")):
                        fh.write(json.dumps({"type": kind, **json.loads(to_json(rec))}) + "\n")
                    s = stats[comp]
                    s["scenarios"] += 1; s[target["status"]] += 1; s["verifier_failures"] += bool(ver)
                    s["heuristic_feasibility_correct"] += outcome["feasibility_correct"]
                    if outcome["gap"] is not None:
                        s["gap_n"] += 1; s["gap_sum_x1000"] += round(1000 * outcome["gap"]); s["optimal_hits"] += outcome["gap"] == 0
                    rows += 1
    summary = {"scenarios": rows, "distinct_family_hashes": len(hashes), "duplicate_hashes": sum(c - 1 for c in hashes.values() if c > 1),
               "by_composition": {"+".join(c[2:]) or "base": dict(v) for c, v in stats.items()}}
    Path("results/e01_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: summary[k] for k in ("scenarios", "distinct_family_hashes", "duplicate_hashes")}))
    for c, v in summary["by_composition"].items():
        print(f"{c:40s} n={v.get('scenarios',0):3d} infeasible={v.get('infeasible',0):2d} verifier_fail={v.get('verifier_failures',0)} "
              f"heur_feas_ok={v.get('heuristic_feasibility_correct',0)} mean_gap={(v.get('gap_sum_x1000',0)/1000/max(1,v.get('gap_n',0))):.3f}")


if __name__ == "__main__":
    main()
