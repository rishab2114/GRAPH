"""Synthetic Elliptic-like worlds for the mechanism check (docs/mechanism-design.md).

Each world has time steps of licit transaction flows plus injected illicit motif instances. Steps up to `train_end`
are identical for every world type with the same seed; after it, illicit activity uses family A (W0), family B (W1),
or family B with licit-looking camouflage edges (W2).
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from gffs.elliptic import Elliptic
from gffs.motifs import MOTIFS
from gffs.scenarios import scenario

KIND_CODE = {"W0": 0, "W1": 1, "W2": 2}


def split_families(seed: int) -> dict[str, list[str]]:
    order = list(np.random.default_rng(seed).permutation(sorted(MOTIFS)))
    return {"A": sorted(order[:3]), "B": sorted(order[3:6]), "C": sorted(order[6:])}


def family_items(family: list[str]) -> list[tuple[str, ...]]:
    """Single motifs plus every within-family pair."""
    return [(m,) for m in sorted(family)] + [tuple(p) for p in combinations(sorted(family), 2)]


def _step(step: int, rng, items, licit_n: int, illicit_n: int, camouflage: bool,
          p_label_licit: float, p_label_illicit: float):
    ids, labels, edges = [], [], []
    licit = [f"s{step}_l{i}" for i in range(licit_n)]
    ids += licit
    labels += [0.0 if rng.random() < p_label_licit else np.nan for _ in licit]
    for i in range(1, licit_n):
        parent = i - 1 if rng.random() < 0.5 else int(rng.integers(0, i))
        edges.append((licit[parent], licit[i]))
        if i > 1 and rng.random() < 0.15:                       # some fan-in among licit flows
            extra = int(rng.integers(0, i))
            if extra != parent:
                edges.append((licit[extra], licit[i]))
    for k in range(illicit_n):
        item = items[int(rng.integers(len(items)))]
        nodes, e, entry = scenario(item, int(rng.integers(2, 7)), int(rng.integers(2, 13)), prefix=f"s{step}_i{k}")
        ids += nodes
        labels += [1.0 if rng.random() < p_label_illicit else np.nan for _ in nodes]
        edges += e
        edges.append((licit[int(rng.integers(licit_n))], entry))
        if camouflage:                                          # licit-looking outflows to fresh licit sinks
            for j, n in enumerate(nodes):
                if rng.random() < 0.5:
                    sink = f"s{step}_c{k}_{j}"
                    ids.append(sink); labels.append(0.0 if rng.random() < p_label_licit else np.nan)
                    edges.append((n, sink))
    return ids, labels, edges


def make_world(kind: str, seed: int, families: dict[str, list[str]], n_steps: int = 40, train_end: int = 24,
               licit_per_step: int = 600, illicit_per_step: int = 8, p_label_licit: float = 0.3,
               p_label_illicit: float = 0.8) -> Elliptic:
    all_ids, all_steps, all_labels, all_edges = [], [], [], []
    for step in range(1, n_steps + 1):
        if step <= train_end:
            rng = np.random.default_rng([seed, step])
            fam, camo = families["A"], False
        else:
            rng = np.random.default_rng([seed, step, KIND_CODE[kind]])
            fam = families["A"] if kind == "W0" else families["B"]
            camo = kind == "W2"
        ids, labels, edges = _step(step, rng, family_items(fam), licit_per_step, illicit_per_step, camo,
                                   p_label_licit, p_label_illicit)
        all_ids += ids; all_steps += [step] * len(ids); all_labels += labels; all_edges += edges
    X = pd.DataFrame({"time_step": all_steps}, index=pd.Index(all_ids, name="txId"))
    y = pd.Series(all_labels, index=X.index, dtype=float)
    return Elliptic(X, y, pd.DataFrame(all_edges, columns=["txId1", "txId2"]))
