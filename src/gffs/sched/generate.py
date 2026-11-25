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
    for i in range(n):
        t = {"id": f"t{i}", "duration": dur[i], "demand": dem[i]}
        if "release_dates" in composition and rng.random() < 0.5:
            t["release"] = rng.randint(0, 4)
        if "deadlines" in composition and rng.random() < 0.5:
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


def canonical_hash(spec: dict) -> str:
    """Weisfeiler-Lehman hash of the labelled precedence/lag graph plus resource data: invariant to names and order."""
    g = nx.DiGraph()
    for t in spec["tasks"]:
        g.add_node(t["id"], label=f"{t['duration']}/{t['demand']}/{t.get('release', 0)}/{t.get('deadline', '-')}")
    for a, b in spec["precedence"]:
        g.add_edge(a, b, label="fs")
    for a, b, l in spec.get("lags", []):
        g.add_edge(a, b, label=f"lag{l}")
    wl = nx.weisfeiler_lehman_graph_hash(g, node_attr="label", edge_attr="label", iterations=4)
    res = json.dumps({"r": spec["resource"], "h": spec["horizon"]}, sort_keys=True)
    return hashlib.sha256((wl + res).encode()).hexdigest()[:16]
