"""Shared-neighbour pair features (the Swanson ABC 'bridge' signal) for candidate pairs."""
from __future__ import annotations

import networkx as nx
import pandas as pd

from gffs.graph import Pair

FEATURES = [
    "freq_min", "freq_max", "deg_min", "deg_max", "common_neighbours",
    "jaccard", "adamic_adar", "resource_allocation", "weighted_cn",
]


def pair_features(g: nx.Graph, pairs: list[Pair]) -> pd.DataFrame:
    """One row per pair, in the order given, indexed by (u, v)."""
    jac = {(u, v): s for u, v, s in nx.jaccard_coefficient(g, pairs)}
    aa = {(u, v): s for u, v, s in nx.adamic_adar_index(g, pairs)}
    ra = {(u, v): s for u, v, s in nx.resource_allocation_index(g, pairs)}
    rows = []
    for u, v in pairs:
        fu, fv = g.nodes[u]["freq"], g.nodes[v]["freq"]
        du, dv = g.degree(u), g.degree(v)
        common = set(g[u]) & set(g[v])
        rows.append({
            "freq_min": min(fu, fv), "freq_max": max(fu, fv),
            "deg_min": min(du, dv), "deg_max": max(du, dv),
            "common_neighbours": len(common),
            "jaccard": jac[(u, v)],
            "adamic_adar": aa[(u, v)],
            "resource_allocation": ra[(u, v)],
            "weighted_cn": sum(min(g[u][w]["weight"], g[v][w]["weight"]) for w in common),
        })
    index = pd.MultiIndex.from_tuples(pairs, names=["u", "v"])
    return pd.DataFrame(rows, columns=FEATURES, index=index).astype(float)
