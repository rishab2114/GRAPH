"""Mechanism check runner (docs/mechanism-design.md): 20 worlds x {W0, W1, W2} x family splits {0, 1}.

    python -m gffs.mechanism --out results/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from gffs.e3e4 import run_cutoff
from gffs.synthworld import family_items, make_world, split_families

STRESS = ("SA", "SB", "SC")


def world_sampler(rng):
    return int(rng.integers(2, 7)), int(rng.integers(2, 13))   # same size ranges as the world's illicit motifs


def run_one(kind: str, seed: int, split_seed: int, n_boot: int = 200, instances: int = 50, **world_kw) -> dict:
    fam = split_families(split_seed)
    d = make_world(kind, seed, fam, **world_kw)
    sets = {f"S{k}": family_items(fam[k]) for k in ("A", "B", "C")}
    r = run_cutoff(d, cutoff=world_kw.get("train_end", 24), holdout_end=world_kw.get("n_steps", 40), val_len=6,
                   instances_per_pair=instances, n_boot=n_boot, sampler=world_sampler, stress_sets=sets, seed=seed)
    a = r["agreement"]["all"]
    return {"kind": kind, "seed": seed, "split": split_seed,
            **{f"{s}_rho": a[s]["spearman"] for s in ("S0_recent_data",) + STRESS},
            **{f"{s}_err": a[s]["mean_abs_error"] for s in ("S0_recent_data",) + STRESS}}


def summarise(rows: list[dict], n_boot: int = 2000, seed: int = 0) -> dict:
    """For each stress test vs S0: worlds where it has lower error / higher rho, and the median difference with a
    95% bootstrap interval over worlds."""
    rng = np.random.default_rng(seed)
    out = {}
    for s in STRESS:
        de = np.array([r[f"{s}_err"] - r["S0_recent_data_err"] for r in rows])
        dr = np.array([r[f"{s}_rho"] - r["S0_recent_data_rho"] for r in rows], dtype=float)
        dr = dr[~np.isnan(dr)]
        boot = lambda x: tuple(np.percentile([np.median(rng.choice(x, len(x))) for _ in range(n_boot)], [2.5, 97.5]).tolist()) if len(x) else (np.nan, np.nan)
        out[s] = {"n": len(rows), "wins_error": int((de < 0).sum()), "wins_rho": int((dr > 0).sum()), "n_rho": int(len(dr)),
                  "median_err_diff": float(np.median(de)), "err_diff_ci": boot(de),
                  "median_rho_diff": float(np.median(dr)) if len(dr) else float("nan"), "rho_diff_ci": boot(dr)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--worlds", type=int, default=20); args = ap.parse_args(argv)
    rows = []
    for split in (0, 1):
        for kind in ("W0", "W1", "W2"):
            for seed in range(args.worlds):
                rows.append(run_one(kind, seed, split)); print(rows[-1], flush=True)
    summary = {f"split{sp}_{k}": summarise([r for r in rows if r["kind"] == k and r["split"] == sp])
               for sp in (0, 1) for k in ("W0", "W1", "W2")}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "mechanism.json").write_text(json.dumps({"families": {s: split_families(s) for s in (0, 1)},
                                                         "rows": rows, "summary": summary}, indent=1))


if __name__ == "__main__":
    main()
