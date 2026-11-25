"""Seeded instance generator for compositions of atoms, DAG templates and a canonical (name/order-free) family hash."""
from __future__ import annotations

import hashlib
import json
import random

import networkx as nx

from gffs.sched.atoms import ATOMS

TEMPLATES = ("chain", "parallel", "layered", "random")


def _dag(rng: random.Random, n: int, template: str) -> list[tuple[int, int]]:
    if template == "chain":
        return [(i, i + 1) for i in range(n - 1)]
    if template == "parallel":
        return []
    if template == "layered":
        layers, i = [], 0
        while i < n:
            k = rng.randint(1, 3); layers.append(list(range(i, min(n, i + k)))); i += k
        return [(a, b) for l1, l2 in zip(layers, layers[1:]) for a in l1 for b in l2 if rng.random() < 0.6] or \
            [(layers[0][0], layers[1][0])] if len(layers) > 1 else []
    return [(a, b) for a in range(n) for b in range(a + 1, n) if rng.random() < 0.3]


def generate(composition: tuple[str, ...], template: str, seed: int, n: int | None = None) -> dict:
    assert all(a in ATOMS for a in composition) and template in TEMPLATES
    rng = random.Random(f"{'|'.join(sorted(composition))}|{template}|{seed}")
    n = n or rng.randint(5, 7)
    cap = rng.randint(2, 4)
    dur = [rng.randint(1, 4) for _ in range(n)]
    dem = [rng.randint(0, cap) for _ in range(n)]
    edges = _dag(rng, n, template)
    g = nx.DiGraph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    es = {i: 0 for i in range(n)}
    for i in nx.topological_sort(g):
        es[i] = max([es[p] + dur[p] for p in g.predecessors(i)], default=0)
    horizon = sum(dur) + 4
    tasks = []
    must_r, must_d = rng.randrange(n), rng.randrange(n)             # each listed atom is present in every instance (L08)
    for i in range(n):
        t = {"id": f"t{i}", "duration": dur[i], "demand": dem[i]}
        if "release_dates" in composition and (i == must_r or rng.random() < 0.5):
            t["release"] = rng.randint(1, 4)
        if "deadlines" in composition and (i == must_d or rng.random() < 0.5):
            t["deadline"] = es[i] + dur[i] + rng.randint(0, 3)          # tight: some instances become infeasible
        tasks.append(t)
    spec = {"tasks": tasks, "precedence": [[f"t{a}", f"t{b}"] for a, b in edges],
            "resource": {"capacity": cap}, "horizon": horizon}
    if "resource_calendar" in composition:
        s = rng.randint(1, max(1, horizon // 2))
        spec["resource"]["calendar"] = [{"start": s, "end": s + rng.randint(2, 4), "capacity": rng.randint(0, cap - 1)}]
    if "min_time_lags" in composition:
        a, b = sorted(rng.sample(range(n), 2))
        spec["lags"] = [[f"t{a}", f"t{b}", rng.randint(1, 3)]]
    return spec


def rename(spec: dict, seed: int) -> dict:
    """Same instance, tasks renamed and listed in a different order (a semantics-preserving transformation)."""
    rng = random.Random(seed)
    ids = [t["id"] for t in spec["tasks"]]
    new = dict(zip(ids, rng.sample([f"x{i}" for i in range(len(ids))], len(ids))))
    tasks = [{**t, "id": new[t["id"]]} for t in spec["tasks"]]; rng.shuffle(tasks)
    out = {**spec, "tasks": tasks, "precedence": [[new[a], new[b]] for a, b in spec["precedence"]]}
    if "lags" in spec:
        out["lags"] = [[new[a], new[b], l] for a, b, l in spec["lags"]]
    return out


MECHANISMS = ("release_dates", "deadlines", "resource_calendar", "min_time_lags", "max_time_lags", "multi_mode",
              "nonrenewable", "multiple_resources")


def mechanisms(spec: dict) -> list[str]:
    """Typed mechanisms present in a spec, independent of every numeric parameter."""
    tasks = spec.get("tasks", [])
    res = spec.get("resources") or {"r": spec.get("resource", {})}
    present = {"release_dates": any(t.get("release", 0) > 0 for t in tasks),
               "deadlines": any(t.get("deadline") is not None for t in tasks),
               "resource_calendar": any(r.get("calendar") for r in res.values()),
               "min_time_lags": bool(spec.get("lags")), "max_time_lags": bool(spec.get("max_lags")),
               "multi_mode": any(len(t.get("modes", [])) > 1 for t in tasks),
               "nonrenewable": bool(spec.get("nonrenewable")), "multiple_resources": len(res) > 1}
    return [m for m in MECHANISMS if present[m]]


def family_id(spec: dict) -> str:
    """Composition family = the set of typed mechanisms (plus the always-present core). Split units are families, so
    no family appears on both sides of a split; numeric parameters never change the family (Codex L08)."""
    return "fam:" + "+".join(["precedence", "renewable_capacity"] + mechanisms(spec))


def instance_fingerprint(spec: dict) -> str:
    """Name- and order-invariant fingerprint of one instance, for deduplication and renaming checks. Parallel relations
    on the same pair (precedence and a lag) are kept together in one edge label, never overwritten (Codex L08)."""
    g = nx.DiGraph()
    for t in spec["tasks"]:
        g.add_node(t["id"], label=f"{t.get('duration')}/{t.get('demand')}/{t.get('release', 0)}/{t.get('deadline', '-')}"
                                  f"/{json.dumps(t.get('modes'), sort_keys=True)}")
    rel: dict = {}
    for a, b in spec["precedence"]:
        rel.setdefault((a, b), []).append("fs")
    for a, b, l in spec.get("lags", []):
        rel.setdefault((a, b), []).append(f"min{l}")
    for a, b, l in spec.get("max_lags", []):
        rel.setdefault((a, b), []).append(f"max{l}")
    for (a, b), labels in rel.items():
        g.add_edge(a, b, label="|".join(sorted(labels)))
    wl = nx.weisfeiler_lehman_graph_hash(g, node_attr="label", edge_attr="label", iterations=4)
    res = json.dumps({"r": spec.get("resources") or spec.get("resource"), "n": spec.get("nonrenewable"), "h": spec["horizon"]},
                     sort_keys=True)
    return hashlib.sha256((wl + res).encode()).hexdigest()[:16]


canonical_hash = instance_fingerprint      # earlier name, kept for the existing trace
