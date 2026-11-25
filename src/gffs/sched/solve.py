"""Exact solver: time-indexed MILP, x[j,m,s] = 1 if task j runs in mode m starting at s; minimise makespan (HiGHS)."""
from __future__ import annotations

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from gffs.sched.spec import Instance


def _certificate(inst: Instance) -> str | None:
    for task in inst.tasks:
        ok = False
        for m in task.modes:
            last = inst.horizon - m.duration if task.deadline is None else min(inst.horizon, task.deadline) - m.duration
            if any(all(inst.cap_r(r, u) >= q for r, q in m.demand.items() for u in range(s, s + m.duration))
                   for s in range(task.release, last + 1)):
                ok = True; break
        if not ok:
            return f"demand exceeds capacity in every window for task {task.id}"
    return None


def solve(inst: Instance, time_limit: float = 60.0) -> dict:
    cert = _certificate(inst)
    if cert:
        return {"status": "infeasible", "certificate": cert, "certified_optimal": False}
    T, tasks = inst.horizon, inst.tasks
    idx = {}
    for j, task in enumerate(tasks):
        for mi, m in enumerate(task.modes):
            last = T - m.duration if task.deadline is None else min(T, task.deadline) - m.duration
            for s in range(task.release, last + 1):
                idx[(j, mi, s)] = len(idx)
    C = len(idx); n = C + 1
    rows, cols, vals, lo, hi = [], [], [], [], []

    def add(coefs: dict, l, h):
        r = len(lo)
        for k, v in coefs.items():
            if v:
                rows.append(r); cols.append(k); vals.append(v)
        lo.append(l); hi.append(h)

    by_task = {j: [(mi, s, k) for (jj, mi, s), k in idx.items() if jj == j] for j in range(len(tasks))}
    start = lambda j: {k: s for (mi, s, k) in by_task[j]}
    finish = lambda j: {k: s + tasks[j].modes[mi].duration for (mi, s, k) in by_task[j]}

    def diff(pos: dict, neg: dict) -> dict:
        out = dict(pos)
        for k, v in neg.items():
            out[k] = out.get(k, 0) - v
        return out

    pos = {t.id: j for j, t in enumerate(tasks)}
    for j in range(len(tasks)):
        add({k: 1 for (_, _, k) in by_task[j]}, 1, 1)
        add({**{k: -v for k, v in finish(j).items()}, C: 1}, 0, np.inf)
    for a, b in inst.precedence:
        add(diff(start(pos[b]), finish(pos[a])), 0, np.inf)               # S_b - F_a >= 0
    for a, b, lag in inst.lags:
        add(diff(start(pos[b]), start(pos[a])), lag, np.inf)
    for a, b, lag in inst.max_lags:
        add(diff(start(pos[b]), start(pos[a])), -np.inf, lag)
    for nr, budget in inst.nonrenewable.items():
        add({k: tasks[j].modes[mi].consumption.get(nr, 0) for (j, mi, s), k in idx.items()}, -np.inf, budget)
    for r in inst.resources:
        for tau in range(T):
            co = {k: tasks[j].modes[mi].demand.get(r, 0) for (j, mi, s), k in idx.items()
                  if s <= tau < s + tasks[j].modes[mi].duration}
            if any(co.values()):
                add(co, -np.inf, inst.cap_r(r, tau))
    A = coo_matrix((vals, (rows, cols)), shape=(len(lo), n)).tocsr()
    c = np.zeros(n); c[C] = 1.0
    integ = np.ones(n); integ[C] = 0
    res = milp(c, constraints=LinearConstraint(A, lo, hi), integrality=integ,
               bounds=Bounds(np.zeros(n), np.r_[np.ones(C), T]),
               options={"time_limit": time_limit, "mip_rel_gap": 0.0})
    # Four distinct outcomes (Codex L07). Only "optimal" is a certified reference for optimality gaps.
    if res.status == 2:
        return {"status": "infeasible", "certificate": "MILP proves no schedule fits the horizon", "certified_optimal": False}
    if res.x is None:
        return {"status": "unknown", "reason": str(res.message), "solver_status": int(res.status), "certified_optimal": False}
    starts, modes = {}, {}
    for (j, mi, s), k in idx.items():
        if res.x[k] > 0.5:
            starts[tasks[j].id], modes[tasks[j].id] = s, mi
    gap = float(getattr(res, "mip_gap", 0.0) or 0.0)
    certified = res.status == 0 and gap <= 1e-9
    return {"status": "optimal" if certified else "feasible", "certified_optimal": bool(certified),
            "makespan": int(round(res.x[C])), "starts": starts, "modes": modes, "gap": gap, "solver_status": int(res.status)}
