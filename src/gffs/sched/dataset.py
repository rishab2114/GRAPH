"""E01 learner dataset: hard instances labelled by the two-stage certified solver (resumable JSONL cache).

Split rule, fixed before any instance exists (docs/e01-scheduling.md, "Learner v0"):
compositional axis: sort the six two-extension families by name and hold out every third (indices 2 and 5);
every single atom still appears in training.

    python -m gffs.sched.dataset        # -> data/sched/dataset.jsonl
"""
from __future__ import annotations

import json
from pathlib import Path

from gffs.sched.atoms import BASE
from gffs.sched.generate import TEMPLATES, family_id, generate, instance_fingerprint
from gffs.sched.solve import solve
from gffs.sched.spec import compile_spec
from gffs.sched.trace import EXTENSIONS, compositions

OUT = Path("data/sched/dataset.jsonl")
SEEDS = 20
FIRST, SECOND = 30.0, 300.0


def held_out_families() -> set[str]:
    pairs = sorted(c for c in compositions() if len(c) == len(BASE) + 2)
    pairs = sorted(pairs, key=lambda c: "+".join(sorted(c[2:])))
    return {"fam:" + "+".join(list(BASE) + [m for m in ("release_dates", "deadlines", "resource_calendar", "min_time_lags")
                                           if m in c]) for i, c in enumerate(pairs) if i % 3 == 2}


def build() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        done = {(r["family"], r["template"], r["seed"]) for r in map(json.loads, OUT.read_text().splitlines())}
    with OUT.open("a") as fh:
        for comp in compositions():
            for tpl in TEMPLATES:
                for seed in range(SEEDS):
                    spec = generate(comp, tpl, seed, hard=True)
                    key = (family_id(spec), tpl, seed)
                    if key in done:
                        continue
                    inst = compile_spec(spec)
                    r = solve(inst, time_limit=FIRST)
                    if r["status"] not in ("optimal", "infeasible"):
                        r = {**solve(inst, time_limit=SECOND), "second_stage": True}
                    fh.write(json.dumps({"family": key[0], "template": tpl, "seed": seed, "fingerprint": instance_fingerprint(spec),
                                         "spec": spec, "target": {k: r.get(k) for k in ("status", "makespan", "starts", "certified_optimal")}}) + "\n")
                    fh.flush()


if __name__ == "__main__":
    print("held-out families:", sorted(held_out_families()))
    build()
