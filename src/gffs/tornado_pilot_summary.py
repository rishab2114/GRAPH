"""Helpers for the pilot summary. The P1-P8 report itself is `gffs.tornado_feasibility.report`.

The first `summarise()` that lived here was withdrawn (RESEARCH_LOG 2026-11-22): it treated destinations of non-simple
transactions as contracts and split edges by `gas == 21000`, both wrong. It was never used for a reported number."""
from __future__ import annotations

from collections import defaultdict


def leaf_gaps(deposits: list[dict]) -> dict:
    by = defaultdict(list)
    for d in deposits:
        by[d["pool"]].append(d["leaf_index"])
    out = {}
    for pool, idx in by.items():
        u = sorted(set(idx))
        out[pool] = {"first": u[0], "last": u[-1], "count": len(idx),
                     "missing": (u[-1] - u[0] + 1) - len(u), "duplicates": len(idx) - len(u)}
    return out
