"""E3/E4/E5 on Elliptic with graph-only detectors, as frozen in docs/e3e4-design.md.

    python -m gffs.e3e4 --data data/elliptic --literature results/literature_graph_v2.json --out results/

Reads time steps 35-49 only to score the frozen detectors at their frozen thresholds.
"""
from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.stats import spearmanr
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from gffs.motifs import MOTIFS
from gffs.scenarios import graph_features, inject, size_sampler_from

GRAPH_DETECTORS = {
    "lr": lambda: LogisticRegression(solver="liblinear"),
    "lr_scaled": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)),
    "rf": lambda: RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=0),
    "rf_balanced": lambda: RandomForestClassifier(n_estimators=100, class_weight="balanced", n_jobs=-1, random_state=0),
    "extra_trees": lambda: ExtraTreesClassifier(n_estimators=100, n_jobs=-1, random_state=0),
    "hgb": lambda: HistGradientBoostingClassifier(random_state=0),
    "tree": lambda: DecisionTreeClassifier(random_state=0),
    "nb": lambda: GaussianNB(),
    "knn": lambda: make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=15)),
    "mlp": lambda: make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(50,), max_iter=300, random_state=0)),
}
FPR_TARGET = 0.05
INSTANCES_PER_PAIR = 200


def _rho(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(spearmanr(a, b)[0])


def _recalls(preds: dict, idx=None) -> np.ndarray:
    return np.array([preds[n][idx].mean() if idx is not None else preds[n].mean() for n in sorted(preds)])


def agreement(stress: dict, hold: dict, n_boot: int = 1000, seed: int = 0) -> dict:
    """Spearman rho and recall error between a stress test and the holdout, across detectors.
    Each dict maps detector -> boolean array of flags over that set's illicit transactions."""
    rs, rh = _recalls(stress), _recalls(hold)
    rng = np.random.default_rng(seed)
    ns, nh = len(next(iter(stress.values()))), len(next(iter(hold.values())))
    boots = [_rho(_recalls(stress, rng.integers(0, ns, ns)), _recalls(hold, rng.integers(0, nh, nh))) for _ in range(n_boot)]
    boots = [b for b in boots if not np.isnan(b)]
    ci = tuple(np.percentile(boots, [2.5, 97.5]).tolist()) if boots else (float("nan"), float("nan"))
    return {"spearman": _rho(rs, rh), "ci": ci, "mean_abs_error": float(np.abs(rs - rh).mean()),
            "mean_signed_error": float((rs - rh).mean()),
            "recall_stress": dict(zip(sorted(stress), rs.tolist())), "recall_holdout": dict(zip(sorted(hold), rh.tolist()))}


def compare_stress_tests(a: dict, b: dict, hold: dict, n_boot: int = 1000, seed: int = 0) -> dict:
    """rho(a, hold) - rho(b, hold) and the error difference, with paired bootstrap intervals (same holdout draws)."""
    rng = np.random.default_rng(seed)
    na, nb, nh = (len(next(iter(x.values()))) for x in (a, b, hold))
    dr, de = [], []
    for _ in range(n_boot):
        rh = _recalls(hold, rng.integers(0, nh, nh))
        ra, rb = _recalls(a, rng.integers(0, na, na)), _recalls(b, rng.integers(0, nb, nb))
        d = _rho(ra, rh) - _rho(rb, rh)
        if not np.isnan(d):
            dr.append(d)
        de.append(np.abs(ra - rh).mean() - np.abs(rb - rh).mean())
    rh0 = _recalls(hold)
    pct = lambda x: tuple(np.percentile(x, [2.5, 97.5]).tolist()) if x else (float("nan"), float("nan"))
    return {"rho_diff": _rho(_recalls(a), rh0) - _rho(_recalls(b), rh0), "rho_diff_ci": pct(dr),
            "abs_error_diff": float(np.abs(_recalls(a) - rh0).mean() - np.abs(_recalls(b) - rh0).mean()),
            "abs_error_diff_ci": pct(de)}


def _graph(d, lo: int, hi: int) -> nx.DiGraph:
    step = d.X["time_step"]
    ids = set(step.index[(step >= lo) & (step <= hi)])
    e = d.edges[d.edges["txId1"].isin(ids) & d.edges["txId2"].isin(ids)]
    g = nx.DiGraph(); g.add_nodes_from(ids); g.add_edges_from(zip(e["txId1"], e["txId2"]))
    return g


def _flags(model, thr: float, X) -> np.ndarray:
    return model.predict_proba(X)[:, 1] >= thr


ALL_PAIRS = [tuple(p) for p in combinations(sorted(MOTIFS), 2)]


def run_cutoff(d, cutoff: int, holdout_end: int, val_len: int = 6, shutdown_step: int | None = None,
               s1_pairs: list | None = None, instances_per_pair: int = INSTANCES_PER_PAIR, n_boot: int = 1000,
               detectors: list[str] | None = None, sampler=None, seed: int = 0, stress_sets: dict | None = None) -> dict:
    """One frozen E3/E4 run at `cutoff` (docs/e3e4-design.md). Training uses steps <= cutoff only;
    steps cutoff+1..holdout_end are read only to score the frozen detectors at their frozen thresholds."""
    names = detectors or list(GRAPH_DETECTORS)
    rng = np.random.default_rng(seed)
    step = d.X["time_step"]
    f_train = graph_features(_graph(d, 1, cutoff))
    y_train = d.y.reindex(f_train.index)
    st = step.reindex(f_train.index)
    val_start = cutoff - val_len + 1
    early = y_train.notna() & (st < val_start)
    val_licit = (y_train == 0) & (st >= val_start)
    val_illicit = (y_train == 1) & (st >= val_start)
    full = y_train.notna()

    models, thresholds, s0 = {}, {}, {}
    for name in names:
        m0 = GRAPH_DETECTORS[name]().fit(f_train[early], y_train[early].astype(int))
        thresholds[name] = float(np.quantile(m0.predict_proba(f_train[val_licit])[:, 1], 1 - FPR_TARGET))
        s0[name] = _flags(m0, thresholds[name], f_train[val_illicit])
        models[name] = GRAPH_DETECTORS[name]().fit(f_train[full], y_train[full].astype(int))

    base = _graph(d, val_start, cutoff)
    sampler = sampler or size_sampler_from(f_train[y_train.notna()], y_train[y_train.notna()])
    if stress_sets is not None:                     # mechanism check: caller-defined synthetic sets
        sets = {k: [tuple(p) for p in v] for k, v in stress_sets.items()}
    else:
        sets = {"S2_uniform_pairs": [ALL_PAIRS[i] for i in np.random.default_rng(0).choice(len(ALL_PAIRS), 10, replace=False)],
                "S3_single_motifs": [(m,) for m in MOTIFS]}
        if s1_pairs:
            sets["S1_graph_forecast"] = [tuple(p) for p in s1_pairs]
    stress = {"S0_recent_data": s0}
    for sname, pairs in sets.items():
        g, syn = inject(base, [p for p in pairs for _ in range(instances_per_pair)], rng, sampler)
        fs = graph_features(g).loc[syn]
        stress[sname] = {n: _flags(models[n], thresholds[n], fs) for n in names}

    f_hold = graph_features(_graph(d, cutoff + 1, holdout_end))
    y_hold = d.y.reindex(f_hold.index); sh = step.reindex(f_hold.index)
    windows = {"all": (cutoff + 1, holdout_end)}
    if shutdown_step and cutoff + 1 < shutdown_step <= holdout_end:
        windows["pre_shutdown"] = (cutoff + 1, shutdown_step - 1)
        windows["post_shutdown"] = (shutdown_step, holdout_end)
    hold = {}
    for w, (lo, hi) in windows.items():
        mask = (y_hold == 1) & (sh >= lo) & (sh <= hi)
        if mask.sum():
            hold[w] = {n: _flags(models[n], thresholds[n], f_hold[mask]) for n in names}
    e5 = {n: float(_flags(models[n], thresholds[n], f_hold[y_hold == 0]).mean()) for n in names} if (y_hold == 0).any() else {}
    res = {"cutoff": cutoff, "windows": {w: list(v) for w, v in windows.items()}, "thresholds": thresholds,
           "e5_fpr_licit": e5, "stress_pairs": {k: [list(p) for p in v] for k, v in sets.items()},
           "stress_recall": {s: {n: float(v[n].mean()) for n in names} for s, v in stress.items()},
           "agreement": {w: {s: agreement(stress[s], hold[w], n_boot) for s in stress} for w in hold},
           "comparisons": {}}
    if "S1_graph_forecast" in stress:
        for w in hold:
            res["comparisons"][w] = {f"S1_vs_{b}": compare_stress_tests(stress["S1_graph_forecast"], stress[b], hold[w], n_boot)
                                     for b in ("S0_recent_data", "S2_uniform_pairs", "S3_single_motifs")}
    return res


def main(argv: list[str] | None = None) -> None:
    from gffs.elliptic import SHUTDOWN_STEP, load

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=Path("data/elliptic"))
    ap.add_argument("--literature", type=Path, default=Path("results/literature_graph_v2.json"))
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--n-boot", type=int, default=1000)
    args = ap.parse_args(argv)
    d = load(args.data)
    s1, lit_note = None, "missing"
    if args.literature.exists():
        lit = json.loads(args.literature.read_text())
        s1 = [tuple(x["pair"]) for x in lit.get("scenarios", [])][:10] or None
        lit_note = f"{len(s1 or [])} pairs, method {lit.get('scenario_method')}"
    # Main result: cutoff 34, holdout 35-49 (and 35-42 / 43-49). Robustness: cutoffs 24, 29, 39, next 10 steps.
    runs = {"main_34": run_cutoff(d, 34, 49, shutdown_step=SHUTDOWN_STEP, s1_pairs=s1, n_boot=args.n_boot)}
    for t in (24, 29, 39):
        runs[f"robust_{t}"] = run_cutoff(d, t, min(t + 10, 49), shutdown_step=SHUTDOWN_STEP, s1_pairs=s1, n_boot=args.n_boot)
    out = {"design": "docs/e3e4-design.md", "literature": lit_note, "runs": runs}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "e3e4_elliptic.json").write_text(json.dumps(out, indent=1))
    for rname, r in runs.items():
        for w, a in r["agreement"].items():
            for s, x in a.items():
                print(f"{rname:10s} {w:13s} {s:20s} rho {x['spearman']:+.2f} [{x['ci'][0]:+.2f},{x['ci'][1]:+.2f}] "
                      f"abs err {x['mean_abs_error']:.3f} signed {x['mean_signed_error']:+.3f}")


if __name__ == "__main__":
    main()
