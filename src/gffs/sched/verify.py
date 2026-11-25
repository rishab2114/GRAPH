"""Independent feasibility check of a schedule (does not use the solver)."""
from __future__ import annotations

from gffs.sched.spec import Instance


def verify(inst: Instance, starts: dict[str, int]) -> list[str]:
    v = []
    t = inst.by_id()
    if set(starts) != set(t):
        return [f"coverage: scheduled {sorted(starts)} vs tasks {sorted(t)}"]
    for k, s in starts.items():
        if s < t[k].release:
            v.append(f"release: {k} starts {s} < {t[k].release}")
        if t[k].deadline is not None and s + t[k].duration > t[k].deadline:
            v.append(f"deadline: {k} ends {s + t[k].duration} > {t[k].deadline}")
        if s + t[k].duration > inst.horizon:
            v.append(f"horizon: {k} ends {s + t[k].duration} > {inst.horizon}")
    for a, b in inst.precedence:
        if starts[b] < starts[a] + t[a].duration:
            v.append(f"precedence: {b} starts {starts[b]} before {a} ends {starts[a] + t[a].duration}")
    for a, b, lag in inst.lags:
        if starts[b] < starts[a] + lag:
            v.append(f"lag: {b} starts {starts[b]} < {a} start + {lag}")
    end = max(s + t[k].duration for k, s in starts.items())
    for tau in range(end):
        use = sum(t[k].demand for k, s in starts.items() if s <= tau < s + t[k].duration)
        if use > inst.cap(tau):
            v.append(f"capacity: period {tau} uses {use} > {inst.cap(tau)}")
    return v
