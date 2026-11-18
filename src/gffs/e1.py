"""E1: does the graph forecaster pick pairs newly documented together after T
better than frequency-matched and uniform-random baselines?

    python -m gffs.e1 --config config/releases.toml --out results/
"""
from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

from gffs.attack import load_bundle, technique_sets
from gffs.baselines import frequency_scores, random_scores
from gffs.evaluate import evaluate
from gffs.fetch import fetch_release
from gffs.forecaster import fit_forecaster, forecast
from gffs.graph import build_graph, candidate_pairs, new_edges

Sets = dict[str, frozenset[str]]


def score_all(sets_before: Sets, sets_t: Sets, sets_after: Sets, seed: int = 0):
    """Return (pairs, labels, {method: scores}) over the candidate pairs at T."""
    g_before, g_t, g_after = build_graph(sets_before), build_graph(sets_t), build_graph(sets_after)
    pairs = candidate_pairs(g_t)
    positives = new_edges(g_t, g_after)
    labels = np.array([p in positives for p in pairs], dtype=int)
    fc = forecast(fit_forecaster(g_before, g_t), g_t)  # never sees g_after
    scores = {
        "forecaster": fc.reindex(pd.MultiIndex.from_tuples(pairs)).to_numpy(),
        "frequency": frequency_scores(g_t, pairs),
        "random": random_scores(pairs, seed),
    }
    return pairs, labels, scores


def run_e1(sets_before: Sets, sets_t: Sets, sets_after: Sets, k: int = 100, seed: int = 0) -> dict[str, dict]:
    _, labels, scores = score_all(sets_before, sets_t, sets_after, seed)
    return {name: evaluate(s, labels, k) for name, s in scores.items()}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=Path("config/releases.toml"))
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--k", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    cfg = tomllib.loads(args.config.read_text())
    tags = [cfg["train_from"], cfg["train_to"], cfg["test_to"]]
    before, t, after = (technique_sets(load_bundle(fetch_release(tag))) for tag in tags)
    pairs, labels, scores = score_all(before, t, after, args.seed)
    metrics = {name: evaluate(s, labels, args.k) for name, s in scores.items()}

    args.out.mkdir(parents=True, exist_ok=True)
    report = {"releases": dict(zip(["train_from", "train_to_T", "test_to"], tags)), "metrics": metrics}
    (args.out / "e1.json").write_text(json.dumps(report, indent=2))
    top = np.argsort(-scores["forecaster"], kind="stable")[: args.k]
    pd.DataFrame({
        "u": [pairs[i][0] for i in top], "v": [pairs[i][1] for i in top],
        "score": scores["forecaster"][top], "newly_documented": labels[top].astype(bool),
    }).to_csv(args.out / f"e1_top{args.k}.csv", index=False)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
