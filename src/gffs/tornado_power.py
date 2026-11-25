"""Stage 2 power simulation (Amendment A1 item 4 and its clarification; Codex G05). Run before any Stage 2 score.

Simulates the H1 statistic, Delta = E4(SYN) - E4(S0), for 10 detectors:
- real positives (holdout and S0) come in 8 weekly blocks with a shared logit shift per week, u_w ~ N(0, tau)
  (week-to-week dependence), plus a per-positive latent shared across detectors;
- synthetic positives come as instances (3 sets of ~1,870 instances, mean 8 nodes) with a per-instance latent shared
  by the instance's nodes and the detectors (instance clustering).
The interval is the A1 primary (positives i.i.d., instances resampled whole) and, as sensitivity, a block version
(holdout and S0 resampled by week). Power = share of simulations whose 95% interval lies below 0.

    python -m gffs.tornado_power      # -> results/tornado_power.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.special import expit, logit

WEEKS = 8
INST_SD = 1.5            # per-instance latent sd (logit scale): strong within-instance correlation
POS_SD = 1.0             # per-positive latent sd shared across detectors


def _real(rng, r, n, tau):
    w = np.repeat(np.arange(WEEKS), int(np.ceil(n / WEEKS)))[:n]
    u = rng.normal(0, tau, WEEKS)[w][:, None] if tau > 0 else 0.0
    z = rng.normal(0, POS_SD, n)[:, None]
    return (rng.random((n, len(r))) < expit(logit(np.clip(r, 1e-4, 1 - 1e-4))[None, :] + u + z)).astype(float), w


def _synthetic(rng, r, n_inst=1867, mean_size=8):
    size = rng.poisson(mean_size - 1, n_inst) + 1
    v = rng.normal(0, INST_SD, n_inst)[:, None]
    p = expit(logit(np.clip(r, 1e-4, 1 - 1e-4))[None, :] + v)
    hits = rng.binomial(size[:, None], p)
    return hits.astype(float), size.astype(float)


def _e4(arm, hold):
    return np.abs(arm - hold).mean()


def simulate(r_h, r_0, r_syn, n_hold, n_s0, tau, sims=200, boots=200, seed=0) -> dict:
    rng = np.random.default_rng(seed)
    r_h, r_0, r_syn = map(np.asarray, (r_h, r_0, r_syn))
    rej_iid = rej_blk = 0; widths_iid, widths_blk, deltas = [], [], []
    for _ in range(sims):
        H, wh = _real(rng, r_h, n_hold, tau); S0, w0 = _real(rng, r_0, n_s0, tau)
        syn = [_synthetic(rng, r_syn) for _ in range(3)]
        rec_syn = lambda idx: np.mean([s[0][i].sum(0) / s[1][i].sum() for s, i in zip(syn, idx)], axis=0)
        full = [np.arange(len(s[1])) for s in syn]
        deltas.append(_e4(rec_syn(full), H.mean(0)) - _e4(S0.mean(0), H.mean(0)))
        d_iid, d_blk = [], []
        for _ in range(boots):
            idx = [rng.integers(0, len(s[1]), len(s[1])) for s in syn]
            rs = rec_syn(idx)
            ih, i0 = rng.integers(0, n_hold, n_hold), rng.integers(0, n_s0, n_s0)
            h = H[ih].mean(0); d_iid.append(_e4(rs, h) - _e4(S0[i0].mean(0), h))
            bh, b0 = rng.integers(0, WEEKS, WEEKS), rng.integers(0, WEEKS, WEEKS)
            hb = np.concatenate([H[wh == b] for b in bh]).mean(0); s0b = np.concatenate([S0[w0 == b] for b in b0]).mean(0)
            d_blk.append(_e4(rs, hb) - _e4(s0b, hb))
        lo_i, hi_i = np.percentile(d_iid, [2.5, 97.5]); lo_b, hi_b = np.percentile(d_blk, [2.5, 97.5])
        rej_iid += hi_i < 0; rej_blk += hi_b < 0
        widths_iid.append(hi_i - lo_i); widths_blk.append(hi_b - lo_b)
    return {"n_hold": n_hold, "n_s0": n_s0, "tau": tau, "sims": sims, "mean_delta": float(np.mean(deltas)),
            "power_iid": rej_iid / sims, "power_block": rej_blk / sims,
            "mean_ci_width_iid": float(np.mean(widths_iid)), "mean_ci_width_block": float(np.mean(widths_blk))}


def main() -> None:
    re = json.loads(Path("results/e3e4_reanalysis.json").read_text())
    x = re["runs"]["main_34"]["workflows"]["common_model_m0"]["post_shutdown"]
    names = sorted(x["recall_holdout"])
    r_h = np.array([x["recall_holdout"][n] for n in names])
    r_0 = np.array([x["recall_arms"]["S0"][n] for n in names])
    r_syn = np.array([x["recall_arms"]["SYN"][n] for n in names])
    rows = []
    for scenario, rs in (("elliptic_effect", r_syn), ("null_syn_equals_s0", r_0)):
        for n in (50, 100, 200, 500):
            for tau in (0.0, 0.5, 1.0):
                r = simulate(r_h, r_0, rs, n_hold=n, n_s0=600, tau=tau)
                r["scenario"] = scenario; rows.append(r)
                print(scenario, n, tau, r["power_iid"], r["power_block"], round(r["mean_delta"], 3), flush=True)
    out = {"what": "Stage 2 H1 power simulation (A1 item 4), run before any Stage 2 score",
           "template": "Elliptic common-model post-shutdown recalls (docs/results/e3e4-reanalysis.md)",
           "assumptions": {"weeks": WEEKS, "instance_sd_logit": INST_SD, "positive_sd_logit": POS_SD, "n_s0": 600,
                           "synthetic": "3 sets x ~1,867 instances, mean 8 nodes", "sims": 200, "boots": 200},
           "rows": rows}
    Path("results/tornado_power.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
