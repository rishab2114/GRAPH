"""Independent feasibility check of a schedule (start times and chosen modes); does not use the solver."""
from __future__ import annotations

from gffs.sched.spec import Instance


def verify(inst: Instance, starts: dict, modes: dict | None = None) -> list:
    t = inst.by_id()
    modes = modes or {k: 0 for k in t}
    if set(starts) != set(t) or set(modes) != set(t):
        return [f"coverage: scheduled {sorted(starts)} vs tasks {sorted(t)}"]
    if any(not (0 <= modes[k] < len(t[k].modes)) for k in t):
        return ["mode: index out of range"]
    m = {k: t[k].modes[modes[k]] for k in t}
    v = []
    for k, s in starts.items():
        if s < t[k].release:
            v.append(f"release: {k} starts {s} < {t[k].release}")
        if t[k].deadline is not None and s + m[k].duration > t[k].deadline:
            v.append(f"deadline: {k} ends {s + m[k].duration} > {t[k].deadline}")
        if s + m[k].duration > inst.horizon:
            v.append(f"horizon: {k} ends {s + m[k].duration} > {inst.horizon}")
    for a, b in inst.precedence:
        if starts[b] < starts[a] + m[a].duration:
            v.append(f"precedence: {b} starts {starts[b]} before {a} ends {starts[a] + m[a].duration}")
    for a, b, lag in inst.lags:
        if starts[b] < starts[a] + lag:
            v.append(f"lag: {b} starts {starts[b]} < {a} start + {lag}")
    for a, b, lag in inst.max_lags:
        if starts[b] > starts[a] + lag:
            v.append(f"max_lag: {b} starts {starts[b]} > {a} start + {lag}")
    for nr, budget in inst.nonrenewable.items():
        used = sum(m[k].consumption.get(nr, 0) for k in t)
        if used > budget:
            v.append(f"budget: {nr} uses {used} > {budget}")
    end = max(s + m[k].duration for k, s in starts.items())
    for r in inst.resources:
        for tau in range(end):
            use = sum(m[k].demand.get(r, 0) for k, s in starts.items() if s <= tau < s + m[k].duration)
            if use > inst.cap_r(r, tau):
                v.append(f"capacity: {r} period {tau} uses {use} > {inst.cap_r(r, tau)}")
    return v
