"""Technique co-occurrence graph, candidate (missing) pairs, and new-edge labels."""
from __future__ import annotations

from collections import Counter
from itertools import combinations

import networkx as nx

Pair = tuple[str, str]  # always ordered u < v


def build_graph(sets: dict[str, frozenset[str]]) -> nx.Graph:
    """Nodes = techniques (attr `freq` = #entities using it).
    Edge weight = #entities using both techniques."""
    freq: Counter[str] = Counter()
    weight: Counter[Pair] = Counter()
    for techniques in sets.values():
        freq.update(techniques)
        weight.update(combinations(sorted(techniques), 2))
    g = nx.Graph()
    for t, f in freq.items():
        g.add_node(t, freq=f)
    for (u, v), w in weight.items():
        g.add_edge(u, v, weight=w)
    return g


def candidate_pairs(g: nx.Graph) -> list[Pair]:
    """All non-edges among the nodes of `g`, canonical and sorted."""
    nodes = sorted(g.nodes)
    return [(u, v) for u, v in combinations(nodes, 2) if not g.has_edge(u, v)]


def new_edges(g_t: nx.Graph, g_later: nx.Graph) -> set[Pair]:
    """Pairs newly documented together: edges of `g_later` between two nodes
    that already existed in `g_t`, and that were not an edge in `g_t`."""
    out: set[Pair] = set()
    for u, v in g_later.edges:
        if u in g_t and v in g_t and not g_t.has_edge(u, v):
            out.add((u, v) if u < v else (v, u))
    return out
