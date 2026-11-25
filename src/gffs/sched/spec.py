"""Bounded JSON spec -> validated Instance, or Invalid(reason). Nothing is executed from the spec.

Supported atoms: precedence, renewable resources (one or several, with calendars), release dates, deadlines,
minimum and maximum start-to-start lags, multi-mode activities and nonrenewable budgets. A single-resource spec
(`"resource": {...}` and integer `demand`) is still accepted; its resource is named "r".
"""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx


@dataclass(frozen=True)
class Invalid:
    reason: str


@dataclass
class Mode:
    duration: int
    demand: dict            # renewable resource -> units per period
    consumption: dict       # nonrenewable resource -> units in total


@dataclass
class Task:
    id: str
    modes: list
    release: int = 0
    deadline: int | None = None

    @property
    def duration(self) -> int:                       # single-mode convenience (heuristic, older callers)
        return self.modes[0].duration

    @property
    def demand(self) -> int:
        return sum(self.modes[0].demand.values())


@dataclass
class Instance:
    tasks: list
    precedence: list
    resources: dict                                  # name -> (capacity, [(start, end, capacity)])
    horizon: int
    lags: list = field(default_factory=list)         # (a, b, lag): S_b >= S_a + lag
    max_lags: list = field(default_factory=list)     # (a, b, lag): S_b <= S_a + lag
    nonrenewable: dict = field(default_factory=dict) # name -> budget

    def cap_r(self, r: str, t: int) -> int:
        c, cal = self.resources[r]
        for s, e, k in cal:
            if s <= t < e:
                c = min(c, k)
        return c

    def cap(self, t: int) -> int:                    # single-resource convenience
        return self.cap_r(next(iter(self.resources)), t)

    @property
    def capacity(self) -> int:
        return self.resources[next(iter(self.resources))][0]

    @property
    def calendar(self) -> list:
        return self.resources[next(iter(self.resources))][1]

    def by_id(self) -> dict:
        return {t.id: t for t in self.tasks}


ALLOWED = {"tasks", "precedence", "resource", "resources", "horizon", "lags", "max_lags", "nonrenewable"}
MAX_TASKS, MAX_HORIZON, MAX_MODES = 60, 400, 4       # explicit size limits for the bounded compiler (Codex L10)


def _int(x, lo=None) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and (lo is None or x >= lo)


def _calendar(res: dict):
    cal = []
    for c in res.get("calendar", []):
        if not (isinstance(c, dict) and _int(c.get("start"), 0) and _int(c.get("end"), 1) and c["end"] > c["start"]
                and _int(c.get("capacity"), 0)):
            return None
        cal.append((c["start"], c["end"], c["capacity"]))
    return cal


def compile_spec(spec: dict):
    try:
        return _compile(spec)
    except (TypeError, AttributeError, ValueError, KeyError) as e:      # any shape error is a typed rejection, never a crash
        return Invalid(f"malformed spec: {type(e).__name__}")


def _list(x) -> bool:
    return isinstance(x, list)


def _compile(spec: dict):
    if not isinstance(spec, dict) or set(spec) - ALLOWED:
        return Invalid(f"unknown fields: {sorted(set(spec) - ALLOWED) if isinstance(spec, dict) else type(spec).__name__}")
    if "resource" in spec and "resources" in spec:
        return Invalid("give either 'resource' or 'resources'")
    raw_res = spec.get("resources") or ({"r": spec["resource"]} if "resource" in spec else None)
    if not isinstance(raw_res, dict) or not raw_res:
        return Invalid("no resources")
    resources = {}
    for name, res in raw_res.items():
        cal = _calendar(res) if isinstance(res, dict) else None
        if not (isinstance(name, str) and isinstance(res, dict) and _int(res.get("capacity"), 1) and cal is not None):
            return Invalid(f"bad resource {name!r}")
        resources[name] = (res["capacity"], cal)
    nonren = spec.get("nonrenewable", {})
    if not isinstance(nonren, dict) or any(not (isinstance(k, str) and _int(v, 0)) for k, v in nonren.items()):
        return Invalid("bad nonrenewable budgets")
    single = next(iter(resources))
    for key in ("tasks", "precedence", "lags", "max_lags"):
        if key in spec and not _list(spec[key]):
            return Invalid(f"{key} must be a list")
    if not _list(spec.get("tasks")) or not (0 < len(spec["tasks"]) <= MAX_TASKS):
        return Invalid(f"tasks must be a non-empty list of at most {MAX_TASKS}")
    if not _int(spec.get("horizon"), 1) or spec["horizon"] > MAX_HORIZON:
        return Invalid(f"horizon must be an integer in [1, {MAX_HORIZON}]")
    tasks = []
    for t in spec.get("tasks", []):
        if not (isinstance(t, dict) and isinstance(t.get("id"), str) and _int(t.get("release", 0), 0)
                and (t.get("deadline") is None or _int(t["deadline"], 1))):
            return Invalid(f"bad task {t!r}")
        if "modes" in t and not (_list(t["modes"]) and 0 < len(t["modes"]) <= MAX_MODES):
            return Invalid(f"bad modes in task {t.get('id')!r}")
        raw_modes = t.get("modes") or [{"duration": t.get("duration"),
                                        "demand": t.get("demand") if isinstance(t.get("demand"), dict) else {single: t.get("demand")},
                                        "consumption": {}}]
        modes = []
        for m in raw_modes:
            dem, con = m.get("demand", {}), m.get("consumption", {})
            if not (isinstance(m, dict) and _int(m.get("duration"), 1) and isinstance(dem, dict) and isinstance(con, dict)
                    and all(k in resources and _int(v, 0) for k, v in dem.items())
                    and all(k in nonren and _int(v, 0) for k, v in con.items())):
                return Invalid(f"bad mode in task {t.get('id')!r}")
            modes.append(Mode(m["duration"], dict(dem), dict(con)))
        tasks.append(Task(t["id"], modes, t.get("release", 0), t.get("deadline")))
    ids = [t.id for t in tasks]
    if not tasks or len(set(ids)) != len(ids):
        return Invalid("no tasks or duplicate ids")
    for key in ("precedence", "lags", "max_lags"):
        if any(not _list(x) for x in spec.get(key, [])):
            return Invalid(f"{key} entries must be lists")
    prec = [tuple(p) for p in spec.get("precedence", [])]
    lags, max_lags = [tuple(x) for x in spec.get("lags", [])], [tuple(x) for x in spec.get("max_lags", [])]
    for p in prec:
        if len(p) != 2 or p[0] not in ids or p[1] not in ids or p[0] == p[1]:
            return Invalid(f"bad precedence {p!r}")
    for x in lags + max_lags:
        if len(x) != 3 or x[0] not in ids or x[1] not in ids or x[0] == x[1] or not _int(x[2], 0):
            return Invalid(f"bad lag {x!r}")
    g = nx.DiGraph(); g.add_nodes_from(ids); g.add_edges_from(prec); g.add_edges_from(x[:2] for x in lags)
    if not nx.is_directed_acyclic_graph(g):
        return Invalid("precedence cycle")
    if not _int(spec.get("horizon"), 1):
        return Invalid("bad horizon")
    return Instance(tasks, prec, resources, spec["horizon"], lags, max_lags, dict(nonren))
