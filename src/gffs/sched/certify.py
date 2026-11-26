"""E01 certification gate on a harder development set (AGENT_DISCUSSION.md, response to L07-L10).

Go only if certification coverage (optimal + proven infeasible) is >= 95% overall and in every difficulty band and
composition, and a 10% re-solve with a 10x time limit shows no status flip among certified outcomes.
Difficulty bands use the greedy rule against the critical-path lower bound (L09); "cp_bound_is_optimal" is the
shortcut check from L03.

    python -m gffs.sched.certify     # -> results/e01_certification.json
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

from gffs.sched.generate import TEMPLATES, family_id, generate
from gffs.sched.heuristic import serial_sgs
from gffs.sched.solve import solve
from gffs.sched.spec import compile_spec
from gffs.sched.trace import compositions

LIMIT, RECHECK_FACTOR, RECHECK_SHARE, GATE = 30.0, 10, 0.10, 0.95
SECOND_STAGE = 300.0     # adopted 2026-11-26 after the first gate run (docs/e01-scheduling.md): uncertified -> re-solve


def cp_bound(inst) -> int:
    g = nx.DiGraph(); g.add_nodes_from(t.id for t in inst.tasks); g.add_edges_from(inst.precedence)
    t = inst.by_id(); ef = {}
    for k in nx.topological_sort(g):
        ef[k] = max([t[k].release] + [ef[p] for p in g.predecessors(k)]) + t[k].duration
    return max(ef.values())


def band(greedy_ms, bound) -> str:
    if greedy_ms is None:
        return "greedy_fails"
    r = greedy_ms / bound
    return "tight" if r <= 1.0 else ("moderate" if r <= 1.15 else "hard")


def main(seeds: int = 4) -> dict:
    rows = []
    for comp in compositions():
        for tpl in TEMPLATES:
            for seed in range(seeds):
                spec = generate(comp, tpl, seed, hard=True); inst = compile_spec(spec)
                r = solve(inst, time_limit=LIMIT)
                if r["status"] not in ("optimal", "infeasible"):
                    r = {**solve(inst, time_limit=SECOND_STAGE), "second_stage": True}
                h = serial_sgs(inst); hm = max(h[x.id] + x.duration for x in inst.tasks) if h else None
                b = cp_bound(inst)
                rows.append({"family": family_id(spec), "template": tpl, "seed": seed, "status": r["status"],
                             "makespan": r.get("makespan"), "cp_bound": b, "greedy": hm, "band": band(hm, b),
                             "spec": spec})
    cert = lambda xs: sum(x["status"] in ("optimal", "infeasible") for x in xs) / max(1, len(xs))
    by_band, by_fam = defaultdict(list), defaultdict(list)
    for x in rows:
        by_band[x["band"]].append(x); by_fam[x["family"]].append(x)
    rng = random.Random(0)
    sample = rng.sample([x for x in rows if x["status"] in ("optimal", "infeasible")], max(1, int(RECHECK_SHARE * len(rows))))
    flips = []
    for x in sample:
        r2 = solve(compile_spec(x["spec"]), time_limit=LIMIT * RECHECK_FACTOR)
        if r2["status"] != x["status"] or r2.get("makespan") != x["makespan"]:
            flips.append({"family": x["family"], "seed": x["seed"], "first": x["status"], "recheck": r2["status"]})
    opt = [x for x in rows if x["status"] == "optimal"]
    out = {"instances": len(rows), "time_limit_s": LIMIT, "status": dict(Counter(x["status"] for x in rows)),
           "coverage_overall": cert(rows),
           "coverage_by_band": {k: {"n": len(v), "coverage": cert(v)} for k, v in by_band.items()},
           "min_coverage_by_family": min(cert(v) for v in by_fam.values()),
           "recheck": {"n": len(sample), "flips": flips},
           "cp_bound_is_optimal_share": sum(x["makespan"] == x["cp_bound"] for x in opt) / max(1, len(opt)),
           "greedy_gap_vs_certified": {"mean": sum((x["greedy"] - x["makespan"]) / x["makespan"] for x in opt if x["greedy"]) /
                                       max(1, sum(1 for x in opt if x["greedy"])),
                                       "greedy_optimal_share": sum(x["greedy"] == x["makespan"] for x in opt) / max(1, len(opt))}}
    out["go"] = bool(out["coverage_overall"] >= GATE and all(v["coverage"] >= GATE for v in out["coverage_by_band"].values())
                     and out["min_coverage_by_family"] >= GATE and not flips)
    Path("results/e01_certification.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "recheck"}, indent=1), "\nflips:", len(flips))
    return out


if __name__ == "__main__":
    main()
