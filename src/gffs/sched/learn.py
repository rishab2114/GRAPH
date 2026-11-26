"""E01 learner v0: a priority rule for the serial schedule-generation scheme, learned by imitating certified optimal
schedules (pairwise ranking of task features). Evaluated on held-out composition families against fixed rules.

    python -m gffs.sched.learn        # -> results/e01_learner_v0.json
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from gffs.sched.heuristic import serial_sgs
from gffs.sched.spec import compile_spec

FEATURES = ["duration", "demand_share", "n_succ", "n_pred", "tail", "head", "slack", "release", "has_deadline",
            "deadline_slack", "calendar_overlap"]


def task_features(inst) -> pd.DataFrame:
    t = inst.by_id()
    g = nx.DiGraph(); g.add_nodes_from(t); g.add_edges_from(inst.precedence)
    order = list(nx.topological_sort(g))
    head, tail = {}, {}
    for k in order:
        head[k] = max([t[k].release] + [head[p] + t[p].duration for p in g.predecessors(k)])
    for k in reversed(order):
        tail[k] = t[k].duration + max([tail[s] for s in g.successors(k)], default=0)
    cap = inst.capacity
    cal = inst.calendar
    rows = {}
    for k in t:
        lf = t[k].deadline if t[k].deadline is not None else inst.horizon
        overlap = sum(max(0, min(e, head[k] + t[k].duration + 5) - max(s, head[k])) for s, e, _ in cal)
        rows[k] = [t[k].duration, t[k].demand / cap, len(nx.descendants(g, k)), len(nx.ancestors(g, k)), tail[k], head[k],
                   inst.horizon - head[k] - tail[k], t[k].release, int(t[k].deadline is not None),
                   (lf - head[k] - t[k].duration) if t[k].deadline is not None else inst.horizon, overlap]
    return pd.DataFrame.from_dict(rows, orient="index", columns=FEATURES)


def pairwise_examples(inst, starts: dict) -> tuple[np.ndarray, np.ndarray]:
    """For each ordered pair with different optimal starts: x = phi(a) - phi(b), y = 1 if a starts first."""
    f = task_features(inst)
    X, y = [], []
    ids = list(starts)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if starts[a] == starts[b]:
                continue
            d = (f.loc[a] - f.loc[b]).to_numpy(float)
            first = int(starts[a] < starts[b])
            X += [d, -d]; y += [first, 1 - first]
    return np.array(X).reshape(-1, len(FEATURES)), np.array(y)


def fit_priority(Xs, ys) -> np.ndarray:
    X, y = np.vstack(Xs), np.concatenate(ys)
    mu, sd = np.zeros(X.shape[1]), X.std(0) + 1e-9               # pairwise differences are centred by construction
    m = LogisticRegression(max_iter=2000, fit_intercept=False).fit(X / sd, y)
    return m.coef_[0] / sd


def policy_schedule(inst, w: np.ndarray):
    f = task_features(inst)
    score = dict(zip(f.index, f.to_numpy(float) @ w))
    return serial_sgs(inst, priority=lambda k: -score[k])         # highest learned "starts first" score is scheduled first


RULES = {
    "deadline_rule": None,                                          # serial_sgs default: earliest deadline, then longest
    "latest_finish": lambda inst, f: (lambda k: f.loc[k, "head"] + f.loc[k, "slack"]),
    "most_successors": lambda inst, f: (lambda k: -f.loc[k, "n_succ"]),
    "random": None,
}


def evaluate_rule(rows, make_priority) -> dict:
    gaps, feas_ok, n_feas, n_inf, inf_ok, opt = [], 0, 0, 0, 0, 0
    for r in rows:
        inst = compile_spec(r["spec"]); tgt = r["target"]
        st = make_priority(inst)
        if tgt["status"] == "infeasible":
            n_inf += 1; inf_ok += st is None
        elif tgt["status"] == "optimal":
            n_feas += 1; feas_ok += st is not None
            if st is not None:
                ms = max(st[t.id] + t.duration for t in inst.tasks)
                gaps.append((ms - tgt["makespan"]) / tgt["makespan"]); opt += ms == tgt["makespan"]
    sens = feas_ok / n_feas if n_feas else float("nan"); spec_ = inf_ok / n_inf if n_inf else float("nan")
    return {"n_certified_feasible": n_feas, "n_infeasible": n_inf, "mean_gap": float(np.mean(gaps)) if gaps else None,
            "optimal_share": opt / max(1, len(gaps)), "schedules_found_share": sens,
            "infeasibility_detected_share": spec_, "balanced_accuracy_feasibility": (sens + spec_) / 2 if n_inf else None}


def main() -> dict:
    from gffs.sched.dataset import OUT, held_out_families
    rows = [json.loads(l) for l in OUT.read_text().splitlines()]
    test_f = held_out_families()
    train = [r for r in rows if r["family"] not in test_f and r["target"]["status"] == "optimal"]
    test = [r for r in rows if r["family"] in test_f and r["target"]["status"] in ("optimal", "infeasible")]
    Xs, ys = zip(*[pairwise_examples(compile_spec(r["spec"]), r["target"]["starts"]) for r in train])
    w = fit_priority(list(Xs), list(ys))
    rng = np.random.default_rng(0)
    policies = {
        "learned_v0": lambda inst: policy_schedule(inst, w),
        "deadline_rule": lambda inst: serial_sgs(inst),
        "latest_finish": lambda inst: (lambda f: serial_sgs(inst, priority=lambda k: f.loc[k, "head"] + f.loc[k, "slack"]))(task_features(inst)),
        "most_successors": lambda inst: (lambda f: serial_sgs(inst, priority=lambda k: -f.loc[k, "n_succ"]))(task_features(inst)),
        "random": lambda inst: (lambda r_: serial_sgs(inst, priority=lambda k: r_[k]))({t.id: rng.random() for t in inst.tasks}),
    }
    train_eval = [r for r in rows if r["family"] not in test_f and r["target"]["status"] in ("optimal", "infeasible")]
    out = {"split": {"held_out_families": sorted(test_f), "train_instances": len(train), "test_instances": len(test),
                     "train_families": sorted({r["family"] for r in train}), "family_overlap": len({r["family"] for r in train} & test_f)},
           "weights": dict(zip(FEATURES, map(float, w))),
           "test": {k: evaluate_rule(test, p) for k, p in policies.items()},
           "train_in_distribution": {k: evaluate_rule(train_eval, p) for k, p in policies.items()}}
    Path("results/e01_learner_v0.json").write_text(json.dumps(out, indent=1))
    for part in ("test", "train_in_distribution"):
        print(part)
        for k, v in out[part].items():
            print(f"  {k:16s} gap {v['mean_gap'] if v['mean_gap'] is None else round(v['mean_gap'], 4)}  optimal {v['optimal_share']:.2f}  "
                  f"found {v['schedules_found_share']:.2f}  infeasible-detected {v['infeasibility_detected_share']}")
    return out


if __name__ == "__main__":
    main()
