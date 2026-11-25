"""Bounded JSON spec -> validated Instance, or Invalid(reason). Nothing is executed from the spec."""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx


@dataclass(frozen=True)
class Invalid:
    reason: str


@dataclass
class Task:
    id: str
    duration: int
    demand: int
    release: int = 0
    deadline: int | None = None


@dataclass
class Instance:
    tasks: list[Task]
    precedence: list[tuple[str, str]]
    capacity: int
    calendar: list[tuple[int, int, int]] = field(default_factory=list)   # [start, end) intervals with reduced capacity
    horizon: int = 0
    lags: list[tuple[str, str, int]] = field(default_factory=list)       # start-to-start minimum lags (a, b, lag)

    def cap(self, t: int) -> int:
        c = self.capacity
        for s, e, k in self.calendar:
            if s <= t < e:
                c = min(c, k)
        return c

    def by_id(self) -> dict[str, Task]:
        return {t.id: t for t in self.tasks}


ALLOWED = {"tasks", "precedence", "resource", "horizon", "lags"}


def _int(x, lo=None) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and (lo is None or x >= lo)


def compile_spec(spec: dict) -> Instance | Invalid:
    if not isinstance(spec, dict) or set(spec) - ALLOWED:
        return Invalid(f"unknown fields: {sorted(set(spec) - ALLOWED) if isinstance(spec, dict) else type(spec).__name__}")
    tasks = []
    for t in spec.get("tasks", []):
        if not (isinstance(t, dict) and isinstance(t.get("id"), str) and _int(t.get("duration"), 1) and _int(t.get("demand"), 0)
                and _int(t.get("release", 0), 0) and (t.get("deadline") is None or _int(t["deadline"], 1))):
            return Invalid(f"bad task {t!r}")
        tasks.append(Task(t["id"], t["duration"], t["demand"], t.get("release", 0), t.get("deadline")))
    ids = [t.id for t in tasks]
    if not tasks or len(set(ids)) != len(ids):
        return Invalid("no tasks or duplicate ids")
    prec = [tuple(p) for p in spec.get("precedence", [])]
    lags = [tuple(x) for x in spec.get("lags", [])]
    for p in prec + [x[:2] for x in lags]:
        if len(p) != 2 or p[0] not in ids or p[1] not in ids or p[0] == p[1]:
            return Invalid(f"bad precedence {p!r}")
    if any(not _int(x[2], 0) for x in lags if len(x) == 3) or any(len(x) != 3 for x in lags):
        return Invalid("bad lag")
    g = nx.DiGraph(); g.add_nodes_from(ids); g.add_edges_from(prec); g.add_edges_from(x[:2] for x in lags)
    if not nx.is_directed_acyclic_graph(g):
        return Invalid("precedence cycle")
    res = spec.get("resource", {})
    if not _int(res.get("capacity"), 1):
        return Invalid("bad capacity")
    cal = []
    for c in res.get("calendar", []):
        if not (_int(c.get("start"), 0) and _int(c.get("end"), 1) and c["end"] > c["start"] and _int(c.get("capacity"), 0)):
            return Invalid(f"bad calendar entry {c!r}")
        cal.append((c["start"], c["end"], c["capacity"]))
    if not _int(spec.get("horizon"), 1):
        return Invalid("bad horizon")
    return Instance(tasks, prec, res["capacity"], cal, spec["horizon"], lags)
