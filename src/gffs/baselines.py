"""E1 baselines. The frequency-matched baseline, used as a ranker, is freq(u) * freq(v)."""
from __future__ import annotations

import networkx as nx
import numpy as np

from gffs.graph import Pair


def frequency_scores(g: nx.Graph, pairs: list[Pair]) -> np.ndarray:
    return np.array([g.nodes[u]["freq"] * g.nodes[v]["freq"] for u, v in pairs], dtype=float)


def random_scores(pairs: list[Pair], seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).random(len(pairs))
