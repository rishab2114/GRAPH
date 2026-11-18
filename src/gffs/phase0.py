"""Phase 0 on Elliptic: facts check, paper reproduction, and a rolling backtest of the
simplest stress test (a detector's score on the last pre-cutoff window) against the later period.

    python -m gffs.phase0 --data data/elliptic --out results/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from gffs.elliptic import (DETECTORS, PUBLISHED_FACTS, PUBLISHED_TABLE1, SHUTDOWN_STEP, Elliptic, backtest,
                           compute_facts, load)

METRICS = ("recall", "precision", "f1")


def rank_agreement(val: dict, test: dict, metric: str) -> dict:
    names = sorted(val)
    a = np.array([val[n][metric] for n in names]); b = np.array([test[n][metric] for n in names])
    rho, p = spearmanr(a, b) if a.std() > 0 and b.std() > 0 else (float("nan"), float("nan"))
    return {"spearman": float(rho), "p_value": float(p), "mean_abs_error": float(np.abs(a - b).mean()),
            "mean_signed_error": float((a - b).mean()), "n_detectors": len(names)}


def rolling_backtest(d: Elliptic, names: list[str], cutoffs: list[int], val_len: int = 6, horizon: int = 10,
                     shutdown_step: int = SHUTDOWN_STEP) -> list[dict]:
    """For each cutoff T: the 'stress test' is each detector trained on 1..T-val_len and scored on
    T-val_len+1..T (all known before T). The 'holdout' is the detector trained on 1..T and scored on
    T+1..T+horizon. Agreement compares the two across detectors."""
    last = int(d.X["time_step"].max())
    rows = []
    for t in cutoffs:
        val = backtest(d, names, train_end=t - val_len, end=t, shutdown_step=shutdown_step)
        test = backtest(d, names, train_end=t, end=min(t + horizon, last), shutdown_step=shutdown_step)
        rows.append({"cutoff": t, "validation_steps": [t - val_len + 1, t], "test_steps": [t + 1, min(t + horizon, last)],
                     "validation": val, "test": test,
                     "agreement": {m: rank_agreement(val, test, m) for m in METRICS}})
    return rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=Path("data/elliptic"))
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args(argv)
    d = load(args.data)
    names = list(DETECTORS)

    facts = compute_facts(d)
    fact_check = {k: {"published": v, "observed": facts[k], "match": facts[k] == v} for k, v in PUBLISHED_FACTS.items()}
    print("facts:", all(x["match"] for x in fact_check.values()), flush=True)

    paper = backtest(d, names)  # train 1-34, test 35-49
    repro = {n: {"published": {"precision": p, "recall": r, "f1": f},
                 "observed": {m: paper[n][m] for m in METRICS}} for n, (p, r, f) in PUBLISHED_TABLE1.items()}
    for n, r in repro.items():
        print(n, "published F1", r["published"]["f1"], "observed F1", round(r["observed"]["f1"], 3), flush=True)

    rolling = rolling_backtest(d, names, cutoffs=[24, 29, 34, 39], val_len=6, horizon=10)
    for row in rolling:
        a = row["agreement"]["recall"]
        print(f"cutoff {row['cutoff']}: recall spearman {a['spearman']:.2f} (p={a['p_value']:.3f}), "
              f"signed error {a['mean_signed_error']:+.3f}", flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "phase0_elliptic.json").write_text(json.dumps(
        {"facts": fact_check, "paper_split": paper, "reproduction": repro, "rolling": rolling}, indent=1))


if __name__ == "__main__":
    main()
