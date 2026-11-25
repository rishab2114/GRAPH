"""Exact solver: time-indexed MILP (x[j,t] = 1 if task j starts at t), minimise makespan, via scipy's HiGHS."""
from __future__ import annotations

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from gffs.sched.spec import Instance


def _certificate(inst: Instance) -> str | None:
    for task in inst.tasks:
        windows = range(task.release, inst.horizon - task.duration + 1)
        if not any(all(inst.cap(u) >= task.demand for u in range(s, s + task.duration)) for s in windows):
            return f"demand exceeds capacity in every window for task {task.id}"
    return None


def solve(inst: Instance, time_limit: float = 60.0) -> dict:
    cert = _certificate(inst)
    if cert:
        return {"status": "infeasible", "certificate": cert}
    T = inst.horizon
    tasks = inst.tasks
    idx, var = {}, 0
    for j, task in enumerate(tasks):
        last = T - task.duration if task.deadline is None else min(T, task.deadline) - task.duration
        for s in range(task.release, last + 1):
            idx[(j, s)] = var; var += 1
    C = var; n = var + 1                                        # makespan variable
    rows, lo, hi = [], [], []

    def add(coefs: dict, l: float, h: float):
        r = lil_matrix((1, n))
        for k, v in coefs.items():
            r[0, k] = v
        rows.append(r); lo.append(l); hi.append(h)

    pos = {t.id: j for j, t in enumerate(tasks)}
    for j, task in enumerate(tasks):
        add({idx[(j, s)]: 1 for (jj, s) in idx if jj == j}, 1, 1)                       # start exactly once
        add({**{idx[(j, s)]: -(s + task.duration) for (jj, s) in idx if jj == j}, C: 1}, 0, np.inf)   # C >= finish
    for a, b in inst.precedence:
        ja, jb = pos[a], pos[b]
        co = {idx[(jb, s)]: s for (jj, s) in idx if jj == jb}
        for (jj, s) in idx:
            if jj == ja:
                co[idx[(ja, s)]] = co.get(idx[(ja, s)], 0) - s
        add(co, tasks[ja].duration, np.inf)                                             # S_b - S_a >= d_a
    for a, b, lag in inst.lags:
        ja, jb = pos[a], pos[b]
        co = {idx[(jb, s)]: s for (jj, s) in idx if jj == jb}
        for (jj, s) in idx:
            if jj == ja:
                co[idx[(ja, s)]] = co.get(idx[(ja, s)], 0) - s
        add(co, lag, np.inf)
    for tau in range(T):
        co = {idx[(j, s)]: tasks[j].demand for (j, s) in idx if s <= tau < s + tasks[j].duration and tasks[j].demand}
        if co:
            add(co, -np.inf, inst.cap(tau))
    A = lil_matrix((len(rows), n))
    for i, r in enumerate(rows):
        A[i] = r
    c = np.zeros(n); c[C] = 1.0
    integrality = np.ones(n); integrality[C] = 0
    res = milp(c, constraints=LinearConstraint(A.tocsr(), lo, hi), integrality=integrality,
               bounds=Bounds(np.zeros(n), np.r_[np.ones(var), T]), options={"time_limit": time_limit})
    if res.status == 2 or res.x is None:
        return {"status": "infeasible", "certificate": "MILP proves no schedule fits the horizon" if res.status == 2 else res.message}
    starts = {tasks[j].id: s for (j, s), k in idx.items() if res.x[k] > 0.5}
    gap = getattr(res, "mip_gap", 0.0) or 0.0
    return {"status": "optimal" if res.status == 0 and gap < 1e-9 else "feasible", "makespan": int(round(res.x[C])),
            "starts": starts, "gap": float(gap)}
