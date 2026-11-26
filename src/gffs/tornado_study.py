"""Stage 2 runner (docs/tornado-design.md with Amendments A1, A2). Pre-cutoff parts and the gated post-cutoff part.

    python -m gffs.tornado_study dry-run      # training + calibration tasks only, every evaluated cutoff (no study scores)
    python -m gffs.tornado_study run          # the single frozen run; refuses post-cutoff labels without approval

Gate: no label or history dated on or after 2022-08-08 is read unless docs/tornado-approval.md exists, written after
the owner approves the frozen design (STATUS.md, rules in force).
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from gffs.tornado_pilot import CUTOFF
from gffs.tornado_study_data import STUDY

APPROVAL = Path("docs/tornado-approval.md")
WEEKS = 8


class ApprovalRequired(RuntimeError):
    pass


def require_approval(last_day: date, approval_file: Path = APPROVAL) -> None:
    if last_day >= CUTOFF and not approval_file.exists():
        raise ApprovalRequired(f"reading data dated {last_day} needs the owner's approval ({approval_file} missing)")


def load_history(start: date, end: date) -> list[dict]:
    """History day records with start <= day < end."""
    require_approval(end - timedelta(days=1))
    out, d = [], start
    while d < end:
        p = STUDY / "history" / f"{d}.json"
        if p.exists():
            out.append(json.loads(p.read_text()))
        d += timedelta(days=1)
    return out


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def participation(history: list[dict], t: date) -> tuple[set, set, set]:
    """(prior participants, relayers, relayed-withdrawal senders), all from days before t (design s3, A1 item 6)."""
    prior, rel, senders = set(), set(), set()
    for h in history:
        if _d(h["day"]) >= t:
            continue
        prior.update(x["sender"] for x in h.get("tornado_txs", []))
        prior.update(x["depositor"] for x in h.get("deposits", []) if x.get("depositor"))
        for w in h.get("withdrawals", []):
            prior.update(p for p in w.get("payees", []) if p)
            if w.get("recipient"):
                prior.add(w["recipient"])
            if w.get("fee_payee"):
                rel.add(w["fee_payee"])
            if w.get("tx_sender") and w.get("tx_sender") != w.get("recipient"):
                senders.add(w["tx_sender"])
    return prior, rel, senders


def infrastructure(t: date, ofac_created: dict[str, str], relayers: set, relayed_senders: set) -> set:
    return {a for a, c in ofac_created.items() if c and _d(c) < t} | relayers | relayed_senders


def labels_for_task(history: list[dict], eligible: set, t: date, weeks: int = WEEKS) -> dict[str, int]:
    """Eligible addresses whose first ETH-pool deposit (as top-level sender) falls in [t, t + weeks) -> week index."""
    end = t + timedelta(weeks=weeks)
    first: dict[str, date] = {}
    for h in history:
        d = _d(h["day"])
        for x in h.get("deposits", []):
            a = x.get("depositor")
            if a and (a not in first or d < first[a]):
                first[a] = d
    return {a: (d - t).days // 7 for a, d in first.items() if a in eligible and t <= d < end}


def block_recall_draws(flags: np.ndarray, weeks: np.ndarray, n_weeks: int, draws: int, rng) -> np.ndarray:
    """Bootstrap recall per detector, resampling whole weeks of real positives (A2 primary)."""
    by_week = [np.flatnonzero(weeks == w) for w in range(n_weeks)]
    out = np.empty((draws, flags.shape[1]))
    for b in range(draws):
        idx = np.concatenate([by_week[w] for w in rng.integers(0, n_weeks, n_weeks)])
        out[b] = flags[idx].mean(0) if len(idx) else np.nan
    return out


# ---------------------------------------------------------------- task assembly (needs the pre-cutoff data build)

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from gffs.tornado_features import FEATURES, account_features  # noqa: E402
from gffs.tornado_study_data import ofac_addresses, reference_month, task_dates  # noqa: E402

REGISTRY = STUDY / "contracts_registry.parquet"
TRAIN_UNLABELLED, CAL_SAMPLE, ALERT_RATE, ROUND = 50_000, 200_000, 0.01, 10


def week_edges(t: date) -> pd.DataFrame:
    days = [t - timedelta(days=k) for k in range(7, 0, -1)]
    require_approval(days[-1])
    e = pd.concat([pq.read_table(STUDY / "edges" / f"{d}.parquet").to_pandas() for d in days], ignore_index=True)
    e["category"] = e["category"].astype(str)
    return e[(e["category"] != "failed") & e["dst"].notna()]


def frame_for(t: date, week: pd.DataFrame) -> set:
    a, _ = reference_month(t)
    month = set(pq.read_table(STUDY / "frames" / f"{a:%Y-%m}.parquet")["address"].to_pylist())
    return month | set(week["src"].unique())


def load_registry() -> dict:
    t = pq.read_table(REGISTRY).to_pydict()
    return dict(zip(t["address"], t["created"]))


def build_task(t: date, history: list[dict], registry: dict, with_labels: bool = True, keep_edges: bool = False) -> dict:
    """Eligible set, positives (address -> deposit week) and features for task date t (design s3-s4, A1 item 6)."""
    week = week_edges(t)
    frame = frame_for(t, week)
    prior, rel, senders = participation(history, t)
    # Listed addresses with no contract creation record are externally owned accounts (no creation event exists):
    # treated as infrastructure at every task date (deviation logged 2026-11-26, before any evaluation).
    ofac_created = {a: registry.get(a) or "1970-01-01" for a in ofac_addresses()}
    infra = infrastructure(t, ofac_created, rel, senders)
    eligible = frame - prior - infra
    clean = week[~week["src"].isin(infra) & ~week["dst"].isin(infra)]
    eoa = frame | set(clean["src"].unique())
    nodes = pd.unique(pd.concat([clean["src"], clean["dst"]]))
    classes = {n: ("contract" if registry.get(n) and _d(registry[n]) < t else "eoa" if n in eoa else "unknown") for n in nodes}
    positives = labels_for_task(history, eligible, t) if with_labels else {}
    active = set(nodes) & eligible
    feats = account_features(clean, classes, targets=pd.Index(sorted(active)))
    out = {"t": t, "eligible": eligible, "positives": positives, "features": feats,
           "infra_size": len(infra), "frame_size": len(frame), "prior_excluded": len(frame & prior)}
    if keep_edges:                       # only the evaluation task needs them (synthetic injection); saves memory
        out.update(clean_edges=clean, classes=classes)
    return out


def X_for(task: dict, addresses) -> pd.DataFrame:
    """Feature rows for addresses; eligible addresses with no edge in the week get the all-zero vector."""
    return task["features"].reindex(pd.Index(list(addresses)), fill_value=0.0)[FEATURES].astype(float)


def detectors() -> dict:
    """The 10 Elliptic graph-only detector types, single-threaded (A1 clarification: deterministic scores)."""
    from gffs.e3e4 import GRAPH_DETECTORS
    out = {}
    for name, make in GRAPH_DETECTORS.items():
        def f(make=make):
            m = make()
            target = m.steps[-1][1] if hasattr(m, "steps") else m
            if hasattr(target, "n_jobs"):
                target.set_params(n_jobs=1)
            return m
        out[name] = f
    return out


def scores(model, X: pd.DataFrame) -> np.ndarray:
    return np.round(model.predict_proba(X)[:, 1], ROUND)


def strict_tau(s: np.ndarray, alpha: float = ALERT_RATE) -> tuple[float, float]:
    from gffs.e3e4_reanalysis import strict_threshold
    return strict_threshold(s, alpha)


def training_set(tasks: list[dict], seed: int = 0) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    Xs, ys = [], []
    pool = [(i, a) for i, tk in enumerate(tasks) for a in tk["eligible"] if a not in tk["positives"]]
    pick = rng.choice(len(pool), min(TRAIN_UNLABELLED, len(pool)), replace=False)
    by_task: dict[int, list] = {}
    for k in pick:
        i, a = pool[k]; by_task.setdefault(i, []).append(a)
    for i, tk in enumerate(tasks):
        pos = sorted(tk["positives"])
        Xs.append(X_for(tk, pos)); ys.append(np.ones(len(pos)))
        neg = sorted(by_task.get(i, []))
        Xs.append(X_for(tk, neg)); ys.append(np.zeros(len(neg)))
    return pd.concat(Xs, ignore_index=True), np.concatenate(ys)


def calibration_sample(task: dict, seed: int = 0) -> list:
    rng = np.random.default_rng(seed)
    el = sorted(task["eligible"])
    return [el[i] for i in rng.choice(len(el), min(CAL_SAMPLE, len(el)), replace=False)]


def dry_run(cutoffs=None) -> dict:
    """Training and calibration tasks only. Reports task sizes, feature coverage and realised calibration alert rates.
    No S0, synthetic or holdout recall is computed (those are study results)."""
    from gffs.tornado_study_data import EVAL_CUTOFFS
    cutoffs = cutoffs or EVAL_CUTOFFS
    registry = load_registry()
    out = {}
    for c in cutoffs:
        td = task_dates(c)
        history = load_history(date(2019, 12, 16), td["calibration"] + timedelta(weeks=WEEKS))   # never past the cutoff
        train = [build_task(t, history, registry) for t in td["train"]]
        cal = build_task(td["calibration"], history, registry)
        X, y = training_set(train)
        sample = calibration_sample(cal)
        Xc = X_for(cal, sample)
        rep = {"tasks": {str(tk["t"]): {"frame": tk["frame_size"], "eligible": len(tk["eligible"]),
                                         "positives": len(tk["positives"]), "active_eligible": len(tk["features"]),
                                         "prior_excluded": tk["prior_excluded"], "infrastructure": tk["infra_size"]}
                         for tk in train + [cal]},
               "training_rows": int(len(y)), "training_positives": int(y.sum()), "detectors": {}}
        for name, make in detectors().items():
            m = make().fit(X, y.astype(int))
            tau, rate = strict_tau(scores(m, Xc))
            rep["detectors"][name] = {"tau": tau, "realised_calibration_alert_rate": rate,
                                      "degenerate": bool(rate == 0.0)}
        out[str(c)] = rep
        print(c, json.dumps({k: rep[k] for k in ("training_rows", "training_positives")}), flush=True)
    Path("results").mkdir(exist_ok=True)
    Path("results/tornado_dry_run.json").write_text(json.dumps(out, indent=1, default=str))
    return out


def build_registry() -> None:
    """As-of contract evidence for every address in the study's feature weeks, plus the 38 OFAC addresses."""
    from gffs.tornado_aux import run_contracts
    addrs = set(ofac_addresses())
    for f in sorted((STUDY / "edges").glob("*.parquet")):
        t = pq.read_table(f, columns=["src", "dst"])
        addrs |= set(pd.unique(t["src"].to_pandas())) | set(pd.unique(t["dst"].to_pandas().dropna()))
    print("addresses", len(addrs), flush=True)
    pq.write_table(run_contracts(addrs), REGISTRY)


def _stress_sets() -> dict:
    from gffs.e3e4 import ALL_PAIRS
    from gffs.motifs import MOTIFS
    lit = json.loads(Path("results/literature_graph_v2.json").read_text())
    s4 = json.loads(Path("results/s4_alien.json").read_text())["s4"]["S4"]
    return {"S1": [tuple(x["pair"]) for x in lit["scenarios"]][:10],
            "S2": [ALL_PAIRS[i] for i in np.random.default_rng(0).choice(len(ALL_PAIRS), 10, replace=False)],
            "S3": [(m,) for m in MOTIFS], "S4": [tuple(x) for x in s4]}


def run() -> dict:
    """The single frozen run (design + A1 + A2). Post-cutoff labels only behind the approval gate."""
    from gffs.scenarios import size_sampler_from
    from gffs.tornado_study_data import EVAL_CUTOFFS, HISTORY_START
    registry, sets, results = load_registry(), _stress_sets(), {}
    for c in EVAL_CUTOFFS:
        td = task_dates(c); weeks = WEEKS
        history = load_history(HISTORY_START, c + timedelta(weeks=WEEKS))
        ev = build_task(c, history, registry, keep_edges=True)
        if c == CUTOFF:                                              # power rule (s7): a count, before any score
            n8 = len(ev["positives"]); rule = {"positives_8w": n8}
            if n8 < 100:
                history = load_history(HISTORY_START, c + timedelta(weeks=26)); weeks = 26
                ev["positives"] = labels_for_task(history, ev["eligible"], c, weeks=26); rule["positives_26w"] = len(ev["positives"])
                if len(ev["positives"]) < 100:
                    results[str(c)] = {"underpowered": rule}; continue
            Path("results").mkdir(exist_ok=True)
            Path("results/tornado_power_rule.json").write_text(json.dumps({**rule, "horizon_weeks": weeks}, indent=1))
        train = [build_task(t, history, registry) for t in td["train"]]
        cal = build_task(td["calibration"], history, registry)
        X, y = training_set(train)
        act = pd.concat([X_for(tk, [a for a in tk["positives"] if a in tk["features"].index]) for tk in train])
        sampler = size_sampler_from(act.rename(columns={"in_W": "in_deg", "out_W": "out_deg", "peel_run_W": "peel_run"}),
                                    pd.Series(1, index=act.index))
        syn_X = synthetic_accounts(ev, sets, sampler)
        names = sorted(detectors())
        pos0, posh = sorted(cal["positives"]), sorted(ev["positives"])
        X0, Xh, Xc = X_for(cal, pos0), X_for(ev, posh), X_for(cal, calibration_sample(cal))
        S0, H = np.zeros((len(pos0), len(names))), np.zeros((len(posh), len(names)))
        syn = {k: (np.zeros((len(v[0]), len(names))), v[1]) for k, v in syn_X.items()}
        model_ids, taus = {}, {}
        for j, name in enumerate(names):
            m = detectors()[name]().fit(X, y.astype(int))           # fitted ONCE; scores every arm and the holdout (A1)
            tau, rate = strict_tau(scores(m, Xc)); taus[name] = {"tau": tau, "calibration_alert_rate": rate}
            model_ids[name] = __import__("hashlib").sha256(__import__("pickle").dumps(m)).hexdigest()[:16]
            S0[:, j] = scores(m, X0) > tau; H[:, j] = scores(m, Xh) > tau
            for k in syn:
                syn[k][0][:, j] = scores(m, syn_X[k][0]) > tau
        r = evaluate(names, S0, np.array([cal["positives"][a] for a in pos0]), syn, H,
                     np.array([ev["positives"][a] for a in posh]), h_n_weeks=weeks)
        r.update({"horizon_weeks": weeks, "thresholds": taus, "model_hash": model_ids,
                  "sizes": {"eligible": len(ev["eligible"]), "holdout_positives": len(posh), "s0_positives": len(pos0)}})
        results[str(c)] = r
    ok = [str(c) for c in EVAL_CUTOFFS if "metrics" in results.get(str(c), {})]
    if len(ok) == 3:
        ev_, p1, p2 = (results[str(c)] for c in EVAL_CUTOFFS)
        dc = shift_contrast(np.array(ev_["syn_minus_s0_block_draws"]), np.array(p1["syn_minus_s0_block_draws"]),
                            np.array(p2["syn_minus_s0_block_draws"]))
        dc["D"] = ev_["contrasts"]["SYN-S0"]["e4_diff"] - (p1["contrasts"]["SYN-S0"]["e4_diff"] + p2["contrasts"]["SYN-S0"]["e4_diff"]) / 2
        results["shift_contrast_D"] = dc
    Path("results/tornado_stage2.json").write_text(json.dumps(results, indent=1, default=str))
    return results


if __name__ == "__main__":
    import sys
    step = sys.argv[1] if len(sys.argv) > 1 else "dry-run"
    {"dry-run": dry_run, "registry": build_registry, "run": run}[step]()


# ---------------------------------------------------------------- synthetic accounts and metrics (design s6, s8; A1, A2)

def synthetic_accounts(task: dict, sets: dict[str, list[tuple]], sampler, per: int = 200, seed: int = 0):
    """Each instance = Elliptic's motif shapes with accounts as nodes and S (payment) edges, attached by one S edge from
    a distinct active eligible account of the evaluation week (contexts never shared, so instances never interact).
    Returns {set: (features of its synthetic accounts, instance id per row)}."""
    from gffs.scenarios import scenario
    rng = np.random.default_rng(seed)
    active = np.array(sorted(task["features"].index))
    total = sum(len(p) for p in sets.values()) * per
    ctx = rng.choice(active, total, replace=False)
    rows, owner, k = [], {}, 0
    for sname, pairs in sets.items():
        for pair in pairs:
            for _ in range(per):
                kk, L = sampler(rng)
                nodes, es, entry = scenario(tuple(pair), kk, L, prefix=f"syn:{sname}:{k}")
                rows += [(a, b, "simple_transfer") for a, b in es] + [(ctx[k], entry, "simple_transfer")]
                for n in nodes:
                    owner[n] = (sname, k)
                k += 1
    syn = pd.DataFrame(rows, columns=["src", "dst", "category"])
    combined = pd.concat([task["clean_edges"][["src", "dst", "category"]], syn], ignore_index=True)
    senders = set(syn["src"])
    classes = {**task["classes"], **{n: ("eoa" if n in senders else "unknown") for n in owner}}
    feats = account_features(combined, classes, targets=pd.Index(sorted(owner)))
    out = {}
    for sname in sets:
        idx = [n for n in feats.index if owner[n][0] == sname]
        out[sname] = (feats.loc[idx, FEATURES].astype(float), np.array([owner[n][1] for n in idx]))
    return out


def _arm_recalls(names, S0, syn, idx0=None, inst_draw=None):
    rec = {"S0": (S0 if idx0 is None else S0[idx0]).mean(0)}
    for s, (F, inst) in syn.items():
        if inst_draw is None:
            rec[s] = F.mean(0)
        else:
            ids, inv = np.unique(inst, return_inverse=True)
            hits = np.zeros((len(ids), F.shape[1])); np.add.at(hits, inv, F)
            size = np.bincount(inv, minlength=len(ids)).astype(float)
            d = inst_draw[s]
            rec[s] = hits[d].sum(0) / size[d].sum()
    rec["SYN"] = np.mean([rec[s] for s in ("S1", "S2", "S3") if s in rec], axis=0)
    m = rec["S0"].mean()
    rec["B_const"] = np.full(len(names), m); rec["B_shrink"] = 0.5 * rec["S0"] + 0.5 * m; rec["B_zero"] = np.zeros(len(names))
    return rec


def _rho(a, b):
    from scipy.stats import spearmanr
    return float("nan") if np.std(a) == 0 or np.std(b) == 0 else float(spearmanr(a, b)[0])


CONTRASTS = [("SYN", "S0"), ("S1", "S0"), ("S2", "S0"), ("S3", "S0"), ("S1", "S2"), ("SYN", "B_shrink"), ("SYN", "B_const"),
             ("S4", "S0"), ("S4", "S1"), ("S4", "S2")]


def evaluate(names, S0, s0_weeks, syn, H, h_weeks, boots: int = 1000, seed: int = 0, h_n_weeks: int = WEEKS) -> dict:
    """Arms' recalls vs holdout recall across detectors. S0/H: positives x detectors flag matrices with deposit weeks;
    syn: {set: (flags nodes x detectors, instance id per node)}. Primary interval (A2): weeks resampled for real
    positives, whole instances for synthetic ones; secondary: positives i.i.d. Same draws for every arm and detector."""
    rng = np.random.default_rng(seed)
    hold = H.mean(0)
    rec = _arm_recalls(names, S0, syn)
    metrics = {a: {"e4": float(np.abs(r - hold).mean()), "signed": float((r - hold).mean()), "rho": _rho(r, hold)}
               for a, r in rec.items()}
    pairs = [(a, b) for a, b in CONTRASTS if a in rec and b in rec]
    draws = {"block": {p: [] for p in pairs}, "iid": {p: [] for p in pairs}, "D_block": []}
    wk_h = [np.flatnonzero(h_weeks == w) for w in range(h_n_weeks)]; wk_0 = [np.flatnonzero(s0_weeks == w) for w in range(WEEKS)]
    for _ in range(boots):
        inst = {s: (lambda ids: ids[rng.integers(0, len(ids), len(ids))])(np.unique(i)) for s, (_, i) in syn.items()}
        ih = np.concatenate([wk_h[w] for w in rng.integers(0, h_n_weeks, h_n_weeks)]); i0 = np.concatenate([wk_0[w] for w in rng.integers(0, WEEKS, WEEKS)])
        jh, j0 = rng.integers(0, len(H), len(H)), rng.integers(0, len(S0), len(S0))
        for kind, (a_idx, h_idx) in (("block", (i0, ih)), ("iid", (j0, jh))):
            r = _arm_recalls(names, S0, syn, a_idx, inst); h = H[h_idx].mean(0)
            for a, b in pairs:
                draws[kind][(a, b)].append(np.abs(r[a] - h).mean() - np.abs(r[b] - h).mean())
    pct = lambda x: [float(v) for v in np.percentile(x, [2.5, 97.5])]
    contrasts = {f"{a}-{b}": {"e4_diff": metrics[a]["e4"] - metrics[b]["e4"], "ci_block": pct(draws["block"][(a, b)]),
                              "ci_iid": pct(draws["iid"][(a, b)]), "rho_diff": metrics[a]["rho"] - metrics[b]["rho"]}
                 for a, b in pairs}
    return {"recall_holdout": dict(zip(names, hold.tolist())), "recall_arms": {a: dict(zip(names, r.tolist())) for a, r in rec.items()},
            "metrics": metrics, "contrasts": contrasts, "syn_minus_s0_block_draws": draws["block"][("SYN", "S0")],
            "n_holdout": int(len(H)), "n_s0": int(len(S0))}


def shift_contrast(d_event: np.ndarray, d_p1: np.ndarray, d_p2: np.ndarray) -> dict:
    """A1 item 4: D = Delta_C - (Delta_P1 + Delta_P2)/2 from independent per-cutoff bootstrap draws (index-paired)."""
    n = min(len(d_event), len(d_p1), len(d_p2))
    d = np.asarray(d_event[:n]) - (np.asarray(d_p1[:n]) + np.asarray(d_p2[:n])) / 2
    return {"D": float(np.mean(d_event) - (np.mean(d_p1) + np.mean(d_p2)) / 2), "ci": [float(v) for v in np.percentile(d, [2.5, 97.5])]}
