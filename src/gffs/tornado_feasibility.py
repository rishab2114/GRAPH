"""Pilot P1-P8 report on pre-sanction data (docs/tornado-pilot-plan.md, corrections in RESEARCH_LOG 2026-11-22).

Everything at a placebo cutoff c uses only information dated before c for features, relayer exclusion, contract
classification and sampling; outcomes are first Tornado participation in the horizon after c. No model is fitted.

    python -m gffs.tornado_feasibility      # writes results/tornado_pilot.json
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from gffs import ethereum as eth
from gffs.tornado_aux import AUX, HORIZON_WEEKS, PLACEBO_CUTOFFS, ZERO, feature_days
from gffs.tornado_pilot import CUTOFF, OUT, pilot_days
from gffs.tornado_pilot_summary import leaf_gaps


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def prospective_labels(deposits, withdrawals, frame: set, cutoff: date, horizon_days: int) -> dict:
    end = cutoff + timedelta(days=horizon_days)
    assert end <= CUTOFF, "outcome horizon must end before the real cutoff"
    out = {}
    for role, events, key in (("depositor", deposits, "depositor"), ("recipient", withdrawals, "recipient")):
        prior = {e[key] for e in events if e.get(key) and _d(e["day"]) < cutoff}
        after = {e[key] for e in events if e.get(key) and cutoff <= _d(e["day"]) < end}
        first_after = after - prior
        out[role] = {"positives": (first_after & frame) - prior, "prior_participants_excluded": (prior & frame),
                     "participants_outside_frame": len(first_after - frame), "first_time_participants": len(first_after)}
    return out


def as_of_relayers(withdrawals, cutoff: date) -> set:
    return {w["relayer"] for w in withdrawals if w.get("relayer") and w["relayer"] != ZERO and _d(w["day"]) < cutoff}


def classify_as_of(addresses, registry: dict, eoa_evidence: set, cutoff: date) -> dict:
    out = {}
    for a in addresses:
        created = registry.get(a)
        if created is not None and _d(created) < cutoff:
            out[a] = "contract"
        elif a in eoa_evidence:
            out[a] = "eoa"
        else:
            out[a] = "unknown"
    return out


def _auc(scores: np.ndarray, y: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, scores)) if 0 < y.sum() < len(y) else float("nan")


def feasibility_at(cutoff: date, deps, wds, frame: set, registry: dict) -> dict:
    days = feature_days()[cutoff]
    frames = [pq.read_table(AUX / "edges" / f"{d}.parquet").to_pandas() for d in days]
    e = pd.concat(frames, ignore_index=True)
    e["category"] = e["category"].astype(str)
    sizes = {}
    for cat, g in e.groupby("category"):
        gg = g.dropna(subset=["dst"]).drop_duplicates(["src", "dst"])
        n = pd.unique(pd.concat([gg["src"], gg["dst"]]))
        sizes[cat] = {"transactions": int(len(g)), "distinct_edges": int(len(gg)), "nodes": int(len(n))}
    tornado = set(eth.TORNADO_ADDRESSES) | as_of_relayers(wds, cutoff)
    ok = e[(e["category"] != "failed") & e["dst"].notna()]
    clean = ok[~ok["src"].isin(tornado) & ~ok["dst"].isin(tornado)].drop_duplicates(["src", "dst", "category"])
    removed = len(ok.drop_duplicates(["src", "dst", "category"])) - len(clean)
    # distinct non-Tornado counterparties per frame address, all successful categories and per category
    und = pd.concat([clean[["src", "dst", "category"]].rename(columns={"src": "a", "dst": "b"}),
                     clean[["dst", "src", "category"]].rename(columns={"dst": "a", "src": "b"})])
    und = und[und["a"].isin(frame)]
    deg = und.drop_duplicates(["a", "b"]).groupby("a").size()
    deg_cat = und.drop_duplicates(["a", "b", "category"]).groupby(["a", "category"]).size().unstack(fill_value=0)
    eoa_evidence = frame | set(ok["src"].unique())
    neighbours = pd.unique(und["b"])
    cls = Counter(classify_as_of(neighbours, registry, eoa_evidence, cutoff).values())
    labels = prospective_labels(deps, wds, frame, cutoff, HORIZON_WEEKS * 7)
    frame_list = np.array(sorted(frame))
    d_all = deg.reindex(frame_list, fill_value=0).to_numpy()
    roles = {}
    for role, lab in labels.items():
        eligible = ~np.isin(frame_list, list(lab["prior_participants_excluded"]))
        y = np.isin(frame_list, list(lab["positives"])).astype(int)
        pos = (y == 1) & eligible
        neg = (y == 0) & eligible
        roles[role] = {
            "positives": int(pos.sum()), "eligible_frame": int(eligible.sum()),
            "prior_participants_excluded": len(lab["prior_participants_excluded"]),
            "first_time_participants_total": lab["first_time_participants"],
            "participants_outside_frame": lab["participants_outside_frame"],
            "frame_coverage": (int(pos.sum()) / lab["first_time_participants"]) if lab["first_time_participants"] else None,
            "positives_with_non_tornado_activity": int(((d_all > 0) & pos).sum()),
            "share_active_positives": float((d_all[pos] > 0).mean()) if pos.any() else None,
            "share_active_others": float((d_all[neg] > 0).mean()),
            "median_degree_active_positives": float(np.median(d_all[pos & (d_all > 0)])) if ((d_all > 0) & pos).any() else None,
            "median_degree_active_others": float(np.median(d_all[neg & (d_all > 0)])) if ((d_all > 0) & neg).any() else None,
            "auc_degree_descriptive": _auc(d_all[eligible], y[eligible]),
        }
        cats = {}
        for c in deg_cat.columns:
            v = deg_cat[c].reindex(frame_list, fill_value=0).to_numpy()
            cats[c] = {"share_positives_with_edges": float((v[pos] > 0).mean()) if pos.any() else None,
                       "share_others_with_edges": float((v[neg] > 0).mean())}
        roles[role]["by_category"] = cats
    return {"cutoff": cutoff.isoformat(), "feature_days": [d.isoformat() for d in days],
            "horizon_end": (cutoff + timedelta(weeks=HORIZON_WEEKS)).isoformat(),
            "P4_graph_sizes_by_category": sizes, "P6_edges_removed_touching_tornado": int(removed),
            "tornado_addresses_excluded": len(tornado), "P3_neighbour_classes": dict(cls), "roles": roles}


def report(out_path: Path = Path("results/tornado_pilot.json")) -> dict:
    days = [d for d in pilot_days() if (OUT / "days" / f"{d}.json").exists()]
    main = [json.loads((OUT / "days" / f"{d}.json").read_text()) for d in days]
    aux = [json.loads((AUX / f"{d}.json").read_text()) for d in days if (AUX / f"{d}.json").exists()]
    deps = [x for m in main for x in m["deposits"]]; wds = [x for m in main for x in m["withdrawals"]]
    wc = Counter(); [wc.update(a["withdrawal_check"]) for a in aux]
    ets = Counter(); [ets.update(a["event_tx_status"]) for a in aux]
    cats = Counter(); [cats.update(a["category_counts"]) for a in aux]
    nulls = Counter(w["nullifier"] for w in wds)
    frame = set(pq.read_table(OUT / "frame_senders.parquet")["address"].to_pylist())
    reg_path = AUX / "contracts_registry.parquet"
    registry = dict(zip(*pq.read_table(reg_path).to_pydict().values())) if reg_path.exists() else {}
    depositors = {d["depositor"] for d in deps if d["depositor"]}
    recipients = {w["recipient"] for w in wds}
    relayers = {w["relayer"] for w in wds if w["relayer"] != ZERO}
    res = {
        "coverage": {"days_main": len(days), "days_aux": len(aux), "window": [str(min(days)), str(max(days))] if days else None,
                     "contracts_registry_rows": len(registry)},
        "P1": {"deposits": len(deps), "withdrawals": len(wds),
               "undecoded_pool_events": sum(m["stats"]["undecoded_pool_events"] for m in main),
               "deposits_without_sender": sum(m["stats"]["deposits_without_sender"] for m in main),
               "leaf_index_gaps": leaf_gaps(deps), "duplicate_nullifiers": sum(1 for n, c in nulls.items() if c > 1),
               "withdrawal_trace_check": dict(wc), "event_tx_status": dict(ets)},
        "P2": {"depositors": len(depositors), "recipients": len(recipients), "relayers_nonzero": len(relayers),
               "self_withdrawals": sum(1 for w in wds if w["relayer"] == ZERO),
               "depositor_and_recipient": len(depositors & recipients), "recipients_that_are_relayers": len(recipients & relayers),
               "depositors_that_are_relayers": len(depositors & relayers),
               "recipients_that_are_contracts_by_cutoff": sum(1 for r in recipients if r in registry)},
        "P4_transaction_categories_all_days": dict(cats),
        "P5_frame": {"frame_size": len(frame), "definition": "senders of any transaction 2022-01-01..2022-01-31"},
        "placebo_cutoffs": {},
    }
    for c in PLACEBO_CUTOFFS:
        if all((AUX / "edges" / f"{d}.parquet").exists() for d in feature_days()[c]):
            res["placebo_cutoffs"][c.isoformat()] = feasibility_at(c, deps, wds, frame, registry)
    res["P8_pipeline_ran_at"] = sorted(res["placebo_cutoffs"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    r = report()
    print(json.dumps({k: v for k, v in r.items() if k != "placebo_cutoffs"}, indent=1, default=str)[:3000])
    for c, v in r["placebo_cutoffs"].items():
        print(c, json.dumps(v["roles"], default=str)[:1500])
