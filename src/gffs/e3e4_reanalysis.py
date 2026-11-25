"""Disclosed reanalysis of the Elliptic E3/E4 result under Codex review G01-G03 (AGENT_DISCUSSION.md).

NOT a confirmation: the Elliptic holdout was already seen. It asks whether the exploratory lead ("synthetic stress
tests predict post-shift recall better than recent data") survives:
  G01  one fitted model (m0, trained on the early steps) scores every arm and the holdout, instead of S0 by m0 and
       everything else by a refit;
  G02  intervals from a cluster bootstrap over whole synthetic instances (paired across detectors, shared holdout draw),
       plus an equal-instance sensitivity and a time-block bootstrap of real positives;
  G03  threshold = smallest score with at most 5% of validation licit scores strictly above; flag iff score > threshold;
  and the cheap baselines B_const / B_shrink / B_zero (review, "Investigate").
The frozen module gffs.e3e4 is untouched; scenario generation reuses it with the same seeds.

    python -m gffs.e3e4_reanalysis        # -> results/e3e4_reanalysis.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from gffs.e3e4 import ALL_PAIRS, FPR_TARGET, GRAPH_DETECTORS, INSTANCES_PER_PAIR, _graph, _rho
from gffs.motifs import MOTIFS
from gffs.scenarios import graph_features, inject, size_sampler_from


# ---------- statistics (tested) ----------

def strict_threshold(scores: np.ndarray, alpha: float) -> tuple[float, float]:
    """Smallest observed score t with mean(scores > t) <= alpha. Returns (t, realised rate)."""
    s = np.sort(np.asarray(scores, float))
    u = np.unique(s)
    above = 1.0 - np.searchsorted(s, u, side="right") / len(s)      # share strictly above each unique value
    t = float(u[np.argmax(above <= alpha)])
    return t, float((s > t).mean())


def cluster_recall(flags: np.ndarray, inst: np.ndarray, draw: np.ndarray, equal_instances: bool = False) -> float:
    """Recall over a draw of instance ids (with repetition). Node-weighted by default; equal-instance on request."""
    ids, inv = np.unique(inst, return_inverse=True)
    hits = np.bincount(inv, weights=flags.astype(float), minlength=len(ids))
    size = np.bincount(inv, minlength=len(ids)).astype(float)
    pos = np.searchsorted(ids, draw)
    if equal_instances:
        return float((hits[pos] / size[pos]).mean())
    return float(hits[pos].sum() / size[pos].sum())


# ---------- reanalysis ----------

def _instances(nodes) -> np.ndarray:
    return np.array([int(str(n).split(":")[0][3:]) for n in nodes])


def run(d, cutoff: int, holdout_end: int, shutdown_step: int | None, s1_pairs, n_boot: int = 1000, seed: int = 0,
        val_len: int = 6) -> dict:
    names = sorted(GRAPH_DETECTORS)
    rng = np.random.default_rng(seed)
    step = d.X["time_step"]
    f_train = graph_features(_graph(d, 1, cutoff))
    y = d.y.reindex(f_train.index); st = step.reindex(f_train.index)
    val_start = cutoff - val_len + 1
    early = y.notna() & (st < val_start)
    vl, vi, full = (y == 0) & (st >= val_start), (y == 1) & (st >= val_start), y.notna()

    m0, refit, thr, thr_pub = {}, {}, {}, {}
    for n in names:
        m0[n] = GRAPH_DETECTORS[n]().fit(f_train[early], y[early].astype(int))
        sv = m0[n].predict_proba(f_train[vl])[:, 1]
        thr[n] = strict_threshold(sv, FPR_TARGET)
        thr_pub[n] = float(np.quantile(sv, 1 - FPR_TARGET))                   # the published rule: score >= quantile
        refit[n] = GRAPH_DETECTORS[n]().fit(f_train[full], y[full].astype(int))
    strict = lambda model, n, X: model.predict_proba(X)[:, 1] > thr[n][0]
    published = lambda model, n, X: model.predict_proba(X)[:, 1] >= thr_pub[n]

    # synthetic sets: identical generator, seeds and order as gffs.e3e4.run_cutoff
    base = _graph(d, val_start, cutoff)
    sampler = size_sampler_from(f_train[y.notna()], y[y.notna()])
    sets = {"S2": [ALL_PAIRS[i] for i in np.random.default_rng(0).choice(len(ALL_PAIRS), 10, replace=False)],
            "S3": [(m,) for m in MOTIFS]}
    if s1_pairs:
        sets["S1"] = [tuple(p) for p in s1_pairs]
    syn_X, syn_inst = {}, {}
    for s, pairs in sets.items():
        g, nodes = inject(base, [p for p in pairs for _ in range(INSTANCES_PER_PAIR)], rng, sampler)
        syn_X[s] = graph_features(g).loc[nodes]; syn_inst[s] = _instances(nodes)

    f_hold = graph_features(_graph(d, cutoff + 1, holdout_end))
    yh = d.y.reindex(f_hold.index); sh = step.reindex(f_hold.index)
    windows = {"all": (cutoff + 1, holdout_end)}
    if shutdown_step and cutoff + 1 < shutdown_step <= holdout_end:
        windows["pre_shutdown"] = (cutoff + 1, shutdown_step - 1); windows["post_shutdown"] = (shutdown_step, holdout_end)

    out = {"cutoff": cutoff,
           "thresholds": {n: {"tau_strict": thr[n][0], "realised_val_fpr_strict": thr[n][1], "tau_published": thr_pub[n],
                              "realised_val_fpr_published": float((m0[n].predict_proba(f_train[vl])[:, 1] >= thr_pub[n]).mean())}
                          for n in names},
           "workflows": {}}
    # as_published reproduces gffs.e3e4 (check); common_model_m0 is the G01+G03 primary; refit_strict isolates G03
    for wf, scorer, flag in (("as_published", refit, published), ("common_model_m0", m0, strict), ("refit_strict", refit, strict)):
        F = {"S0": {n: flag(m0[n], n, f_train[vi]) for n in names}}       # S0 is always m0 (it is the recent-data test)
        for s in sets:
            F[s] = {n: flag(scorer[n], n, syn_X[s]) for n in names}
        S0_steps = st[vi].to_numpy()
        res_w = {}
        for w, (lo, hi) in windows.items():
            mask = (yh == 1) & (sh >= lo) & (sh <= hi)
            if not mask.any():
                continue
            H = {n: flag(scorer[n], n, f_hold[mask]) for n in names}
            h_steps = sh[mask].to_numpy()
            res_w[w] = _compare(F, syn_inst, H, h_steps, S0_steps, names, n_boot, seed)
            res_w[w]["n_holdout_positives"] = int(mask.sum())
        out["workflows"][wf] = res_w
    return out


def _point(F, syn_inst, H, names, eq=False):
    rec = {"S0": np.array([F["S0"][n].mean() for n in names])}
    for s, inst in syn_inst.items():
        allids = np.unique(inst)
        rec[s] = np.array([cluster_recall(F[s][n], inst, allids, eq) for n in names])
    rec["SYN"] = np.mean([rec[s] for s in syn_inst], axis=0)
    m = rec["S0"].mean()
    rec["B_const"] = np.full(len(names), m); rec["B_shrink"] = 0.5 * rec["S0"] + 0.5 * m; rec["B_zero"] = np.zeros(len(names))
    hold = np.array([H[n].mean() for n in names])
    return rec, hold


def _metrics(rec, hold):
    return {a: {"e4": float(np.abs(r - hold).mean()), "rho": _rho(r, hold)} for a, r in rec.items()}


CONTRASTS = [("SYN", "S0"), ("S1", "S0"), ("S2", "S0"), ("S3", "S0"), ("S1", "S2"), ("SYN", "B_shrink"), ("SYN", "B_const")]


def _compare(F, syn_inst, H, h_steps, S0_steps, names, n_boot, seed):
    rec, hold = _point(F, syn_inst, H, names)
    point = _metrics(rec, hold)
    rng = np.random.default_rng(seed)
    nh, n0 = len(next(iter(H.values()))), len(next(iter(F["S0"].values())))
    boots = {k: {"e4": [], "rho": []} for k in CONTRASTS}
    block = {k: [] for k in CONTRASTS}
    usteps_h, usteps_0 = np.unique(h_steps), np.unique(S0_steps)
    for b in range(n_boot):
        ih, i0 = rng.integers(0, nh, nh), rng.integers(0, n0, n0)
        r = {"S0": np.array([F["S0"][n][i0].mean() for n in names])}
        for s, inst in syn_inst.items():
            ids = np.unique(inst); draw = ids[rng.integers(0, len(ids), len(ids))]
            r[s] = np.array([cluster_recall(F[s][n], inst, draw) for n in names])
        r["SYN"] = np.mean([r[s] for s in syn_inst], axis=0)
        m = r["S0"].mean(); r["B_const"] = np.full(len(names), m); r["B_shrink"] = 0.5 * r["S0"] + 0.5 * m
        hb = np.array([H[n][ih].mean() for n in names])
        # time-block sensitivity: resample whole time steps of real positives (holdout and S0), synthetic as above
        sb_h = rng.choice(usteps_h, len(usteps_h)); sb_0 = rng.choice(usteps_0, len(usteps_0))
        ih_b = np.concatenate([np.flatnonzero(h_steps == t) for t in sb_h])
        i0_b = np.concatenate([np.flatnonzero(S0_steps == t) for t in sb_0])
        rb = dict(r); rb["S0"] = np.array([F["S0"][n][i0_b].mean() for n in names])
        m2 = rb["S0"].mean(); rb["B_const"] = np.full(len(names), m2); rb["B_shrink"] = 0.5 * rb["S0"] + 0.5 * m2
        hbb = np.array([H[n][ih_b].mean() for n in names])
        for a, c in CONTRASTS:
            boots[(a, c)]["e4"].append(np.abs(r[a] - hb).mean() - np.abs(r[c] - hb).mean())
            d = _rho(r[a], hb) - _rho(r[c], hb)
            if not np.isnan(d):
                boots[(a, c)]["rho"].append(d)
            block[(a, c)].append(np.abs(rb[a] - hbb).mean() - np.abs(rb[c] - hbb).mean())
    pct = lambda x: [float(v) for v in np.percentile(x, [2.5, 97.5])] if len(x) else [float("nan")] * 2
    rec_eq, _ = _point(F, syn_inst, H, names, eq=True)
    return {"recall_holdout": dict(zip(names, hold.tolist())),
            "recall_arms": {a: dict(zip(names, v.tolist())) for a, v in rec.items()},
            "metrics": point, "metrics_equal_instance": _metrics(rec_eq, hold),
            "contrasts": {f"{a}-{c}": {"e4_diff": point[a]["e4"] - point[c]["e4"], "e4_ci_instance": pct(boots[(a, c)]["e4"]),
                                       "e4_ci_timeblock": pct(block[(a, c)]),
                                       "rho_diff": point[a]["rho"] - point[c]["rho"] if not np.isnan(point[c]["rho"]) else None,
                                       "rho_ci_instance": pct(boots[(a, c)]["rho"])} for a, c in CONTRASTS}}


def main(argv=None):
    from gffs.elliptic import SHUTDOWN_STEP, load
    ap = argparse.ArgumentParser(); ap.add_argument("--n-boot", type=int, default=1000); a = ap.parse_args(argv)
    d = load(Path("data/elliptic"))
    lit = json.loads(Path("results/literature_graph_v2.json").read_text())
    s1 = [tuple(x["pair"]) for x in lit["scenarios"]][:10]
    runs = {"main_34": run(d, 34, 49, SHUTDOWN_STEP, s1, a.n_boot)}
    for t in (24, 29, 39):
        runs[f"robust_{t}"] = run(d, t, min(t + 10, 49), SHUTDOWN_STEP, s1, a.n_boot)
    out = {"what": "disclosed reanalysis of results/e3e4_elliptic.json under Codex review G01-G03; not a confirmation",
           "runs": runs}
    Path("results/e3e4_reanalysis.json").write_text(json.dumps(out, indent=1))
    for rn, r in runs.items():
        for wf, ws in r["workflows"].items():
            for w, x in ws.items():
                c = x["contrasts"]
                print(f"{rn:10s} {wf:16s} {w:13s} n={x['n_holdout_positives']:4d} " + " ".join(
                    f"{k} {c[k]['e4_diff']:+.3f}[{c[k]['e4_ci_instance'][0]:+.3f},{c[k]['e4_ci_instance'][1]:+.3f}]"
                    for k in ("SYN-S0", "SYN-B_shrink", "S1-S2")), flush=True)


if __name__ == "__main__":
    main()
