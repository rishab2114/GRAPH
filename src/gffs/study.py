"""Multi-split study: rolling time-travel splits x edge definitions x pre-registered methods.

For each split: train on (train_from -> T), score candidate pairs at T, label pairs newly
documented together by test_to. Reports AUC, precision@k, popularity-stratified AUC (signal
beyond popularity), AUC on niche pairs, and a paired-bootstrap CI of AUC minus the
frequency baseline.

    python -m gffs.study --config config/study.toml --out results/
"""
from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

import networkx as nx
import numpy as np
from sklearn.metrics import roc_auc_score

from gffs.attack import load_bundle, technique_sets
from gffs.baselines import frequency_scores, random_scores
from gffs.evaluate import evaluate
from gffs.features import pair_features
from gffs.fetch import fetch_release
from gffs.graph import build_graph, candidate_pairs, new_edges
from gffs.models import MODELS, fit_model
from gffs.stats import paired_bootstrap_diff, popularity_strata, stratified_auc

Sets = dict[str, frozenset[str]]


def _labels(pairs, positives) -> np.ndarray:
    return np.array([p in positives for p in pairs], dtype=int)


def run_split(sets_before: Sets, sets_t: Sets, sets_after: Sets, *, k: int = 100,
              n_boot: int = 1000, n_strata: int = 10, seed: int = 0) -> dict:
    g_b, g_t, g_a = build_graph(sets_before), build_graph(sets_t), build_graph(sets_after)

    train_pairs = candidate_pairs(g_b)
    X_train = pair_features(g_b, train_pairs).reset_index(drop=True)
    y_train = _labels(train_pairs, new_edges(g_b, g_t))

    pairs = candidate_pairs(g_t)
    X = pair_features(g_t, pairs).reset_index(drop=True)
    y = _labels(pairs, new_edges(g_t, g_a))  # g_a is used for labels only

    scores = {"frequency": frequency_scores(g_t, pairs), "random": random_scores(pairs, seed)}
    for name in MODELS:
        scores[name] = fit_model(name, X_train, y_train)(X)

    strata = popularity_strata(scores["frequency"], n_strata)
    median = np.median([g_t.nodes[n]["freq"] for n in g_t])
    niche = np.array([g_t.nodes[u]["freq"] <= median and g_t.nodes[v]["freq"] <= median for u, v in pairs])
    niche_ok = niche.any() and 0 < y[niche].sum() < niche.sum()

    methods = {}
    for name, s in scores.items():
        m = evaluate(s, y, k)
        m["strat_auc"] = stratified_auc(s, y, strata)
        m["niche_auc"] = float(roc_auc_score(y[niche], s[niche])) if niche_ok else None
        m["vs_frequency"] = paired_bootstrap_diff(s, scores["frequency"], y, n_boot, seed)
        methods[name] = m

    return {
        "graph": {
            "nodes_t": g_t.number_of_nodes(), "entities_t": len(sets_t),
            "density_t": nx.density(g_t), "n_candidates": len(pairs),
            "n_positive": int(y.sum()), "train_positive": int(y_train.sum()),
            "n_niche": int(niche.sum()), "niche_positive": int(y[niche].sum()),
        },
        "methods": methods,
    }


def _release_date(bundle: dict) -> str:
    return max(o.get("modified", "") for o in bundle["objects"])[:10]


def _table(results: list[dict]) -> str:
    lines = ["| Split | Edges | Density at T | Positives / candidates | Method | AUC | P@100 | Stratified AUC | Niche AUC | AUC − freq [95% CI] |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        g = r["graph"]
        for name, m in r["methods"].items():
            v = m["vs_frequency"]
            niche = "–" if m["niche_auc"] is None else f"{m['niche_auc']:.3f}"
            lines.append(f"| {r['split']} | {r['edges']} | {g['density_t']:.2f} | {g['n_positive']} / {g['n_candidates']} | "
                         f"{name} | {m['auc']:.3f} | {m['precision_at_k']:.2f} | {m['strat_auc']:.3f} | {niche} | "
                         f"{v['diff']:+.3f} [{v['lo']:+.3f}, {v['hi']:+.3f}] |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=Path("config/study.toml"))
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args(argv)
    cfg = tomllib.loads(args.config.read_text())

    bundles: dict[str, dict] = {}

    def sets(tag: str, types: list[str]) -> Sets:
        if tag not in bundles:
            bundles[tag] = load_bundle(fetch_release(tag))
        return technique_sets(bundles[tag], tuple(types))

    results = []
    for sp in cfg["splits"]:
        for edge_name, types in cfg["edge_sets"].items():
            r = run_split(sets(sp["train_from"], types), sets(sp["t"], types), sets(sp["test_to"], types),
                          k=cfg["k"], n_boot=cfg["n_boot"], n_strata=cfg["n_strata"])
            r.update(split=sp["name"], edges=edge_name,
                     releases={x: f"{sp[x]} ({_release_date(bundles[sp[x]])})" for x in ("train_from", "t", "test_to")})
            results.append(r)
            best = max(r["methods"].items(), key=lambda kv: kv[1]["auc"])
            print(f"{sp['name']} {edge_name}: best={best[0]} auc={best[1]['auc']:.3f} "
                  f"freq={r['methods']['frequency']['auc']:.3f}", flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "study.json").write_text(json.dumps(results, indent=2))
    (args.out / "study_table.md").write_text(_table(results))


if __name__ == "__main__":
    main()
