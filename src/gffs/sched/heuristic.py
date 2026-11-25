"""Serial schedule-generation scheme with a priority rule: the first 'learner' (a fixed heuristic) for the E01 trace.
Returns starts, or None when the greedy pass cannot respect deadlines or the horizon (it is not complete)."""
from __future__ import annotations

from gffs.sched.spec import Instance


def serial_sgs(inst: Instance, priority=None) -> dict | None:
    t = inst.by_id()
    preds = {k: [a for a, b in inst.precedence if b == k] for k in t}
    lagp = {k: [(a, l) for a, b, l in inst.lags if b == k] for k in t}
    priority = priority or (lambda k: (t[k].deadline if t[k].deadline is not None else inst.horizon, -t[k].duration))
    usage = [0] * (inst.horizon + 1)
    starts: dict[str, int] = {}
    while len(starts) < len(t):
        ready = [k for k in t if k not in starts and all(p in starts for p in preds[k] + [a for a, _ in lagp[k]])]
        k = min(ready, key=lambda x: (priority(x), x))
        est = max([t[k].release] + [starts[p] + t[p].duration for p in preds[k]] + [starts[a] + l for a, l in lagp[k]])
        s = est
        while s + t[k].duration <= inst.horizon:
            if all(usage[u] + t[k].demand <= inst.cap(u) for u in range(s, s + t[k].duration)):
                break
            s += 1
        if s + t[k].duration > inst.horizon or (t[k].deadline is not None and s + t[k].duration > t[k].deadline):
            return None
        for u in range(s, s + t[k].duration):
            usage[u] += t[k].demand
        starts[k] = s
    return starts
