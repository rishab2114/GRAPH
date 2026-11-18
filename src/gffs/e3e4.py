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


def main(argv: list[str] | None = None) -> None:
    from gffs.elliptic import SHUTDOWN_STEP, load

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=Path("data/elliptic"))
    ap.add_argument("--literature", type=Path, default=Path("results/literature_graph_v2.json"))
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--n-boot", type=int, default=1000)
    args = ap.parse_args(argv)
    rng = np.random.default_rng(0)
    d = load(args.data)
    step = d.X["time_step"]

    f_train = graph_features(_graph(d, 1, 34))
    y_train = d.y.reindex(f_train.index)
    st = step.reindex(f_train.index)
    early = y_train.notna() & (st <= 28)
    val_licit = (y_train == 0) & (st >= 29)
    val_illicit = (y_train == 1) & (st >= 29)
    full = y_train.notna()

    models, thresholds, s0 = {}, {}, {}
    for name, make in GRAPH_DETECTORS.items():
        m0 = make().fit(f_train[early], y_train[early].astype(int))
        thresholds[name] = float(np.quantile(m0.predict_proba(f_train[val_licit])[:, 1], 1 - FPR_TARGET))
        s0[name] = _flags(m0, thresholds[name], f_train[val_illicit])
        models[name] = make().fit(f_train[full], y_train[full].astype(int))

    base = _graph(d, 29, 34)
    sampler = size_sampler_from(f_train[y_train.notna()], y_train[y_train.notna()])
    pairs_all = [tuple(p) for p in combinations(sorted({"fan_in", "fan_out", "peel_chain", "mixing_service", "coinjoin",
                                                         "pass_through", "layering", "smurfing"}), 2)]
    stress_sets = {"S2_uniform_pairs": [pairs_all[i] for i in np.random.default_rng(0).choice(len(pairs_all), 10, replace=False)],
                   "S3_single_motifs": [(m,) for m in MOTIFS]}
    lit_note = "missing"
    if args.literature.exists():
        lit = json.loads(args.literature.read_text())
        top = [tuple(s["pair"]) for s in lit.get("scenarios", [])][:10]
        if top:
            stress_sets["S1_graph_forecast"] = top
            lit_note = f"{len(top)} pairs, method {lit.get('scenario_method')}"
    stress = {"S0_recent_data": s0}
    for sname, pairs in stress_sets.items():
        g, syn = inject(base, [p for p in pairs for _ in range(INSTANCES_PER_PAIR)], rng, sampler)
        fs = graph_features(g).loc[syn]
        stress[sname] = {n: _flags(models[n], thresholds[n], fs) for n in models}

    f_hold = graph_features(_graph(d, 35, 49))
    y_hold = d.y.reindex(f_hold.index); sh = step.reindex(f_hold.index)
    windows = {"35-49": sh >= 35, "35-42": sh < SHUTDOWN_STEP, "43-49": sh >= SHUTDOWN_STEP}
    hold = {w: {n: _flags(models[n], thresholds[n], f_hold[(y_hold == 1) & m]) for n in models} for w, m in windows.items()}
    e5 = {n: float(_flags(models[n], thresholds[n], f_hold[y_hold == 0]).mean()) for n in models}

    res = {"design": "docs/e3e4-design.md", "literature": lit_note, "thresholds": thresholds, "e5_fpr_licit_35_49": e5,
           "stress_pairs": {k: [list(p) for p in v] for k, v in stress_sets.items()},
           "agreement": {w: {s: agreement(stress[s], hold[w], args.n_boot) for s in stress} for w in hold},
           "comparisons": {}}
    if "S1_graph_forecast" in stress:
        for w in hold:
            res["comparisons"][w] = {f"S1_vs_{b}": compare_stress_tests(stress["S1_graph_forecast"], stress[b], hold[w], args.n_boot)
                                     for b in ("S0_recent_data", "S2_uniform_pairs", "S3_single_motifs")}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "e3e4_elliptic.json").write_text(json.dumps(res, indent=1))
    for w, a in res["agreement"].items():
        for s, r in a.items():
            print(f"{w:6s} {s:20s} rho {r['spearman']:+.2f} [{r['ci'][0]:+.2f},{r['ci'][1]:+.2f}] "
                  f"abs err {r['mean_abs_error']:.3f} signed {r['mean_signed_error']:+.3f}")


if __name__ == "__main__":
    main()
