"""Summarise the pre-sanction pilot extracts into answers for P1-P6, P8 (docs/tornado-pilot-plan.md)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq

from gffs import ethereum as eth
from gffs.tornado_pilot import OUT, SAMPLE_WEEKS, pilot_days


def leaf_gaps(deposits: list[dict]) -> dict:
    by = defaultdict(list)
    for d in deposits:
        by[d["pool"]].append(d["leaf_index"])
    out = {}
    for pool, idx in by.items():
        u = sorted(set(idx))
        out[pool] = {"first": u[0], "last": u[-1], "count": len(idx),
                     "missing": (u[-1] - u[0] + 1) - len(u), "duplicates": len(idx) - len(u)}
    return out


def summarise(out_path: Path = Path("results/tornado_pilot.json")) -> dict:
    days = [json.loads((OUT / "days" / f"{d}.json").read_text()) for d in pilot_days() if (OUT / "days" / f"{d}.json").exists()]
    deps = [x for d in days for x in d["deposits"]]; wds = [x for d in days for x in d["withdrawals"]]
    stats = [d["stats"] for d in days]
    depositors = {d["depositor"] for d in deps if d["depositor"]}
    recipients = {w["recipient"] for w in wds}
    relayers = {w["tx_sender"] for w in wds if w["tx_sender"] and w["tx_sender"] != w["recipient"]} | {w["relayer"] for w in wds}
    callees = set()
    for d in pilot_days():
        p = OUT / "days" / f"{d}.callees.parquet"
        if p.exists():
            callees |= set(pq.read_table(p)["address"].to_pylist())
    frame = set(pq.read_table(OUT / "frame_senders.parquet")["address"].to_pylist())
    tornado_infra = set(eth.TORNADO_ADDRESSES) | relayers

    p4, p6 = {}, {}
    for a, b in SAMPLE_WEEKS:
        files = sorted(p for p in (OUT / "edges").glob("*.parquet") if a.isoformat() <= p.stem <= b.isoformat())
        src, dst, vt = [], [], []
        for f in files:
            t = pq.read_table(f); src += t["src"].to_pylist(); dst += t["dst"].to_pylist(); vt += t["value_transfer"].to_pylist()
        inter = {(s, t) for s, t in zip(src, dst) if t}
        value = {(s, t) for s, t, v in zip(src, dst, vt) if t and v}
        def size(E):
            n = {x for e in E for x in e}
            return {"nodes": len(n), "edges": len(E), "density": len(E) / (len(n) * (len(n) - 1)) if len(n) > 1 else 0}
        key = f"{a}..{b}"
        p4[key] = {"interaction": size(inter), "value_transfer": size(value)}
        pos = (depositors | recipients) & frame
        deg_all, deg_clean = Counter(), Counter()
        for s, t in inter:
            for x, other in ((s, t), (t, s)):
                if x in pos:
                    deg_all[x] += 1
                    if other not in tornado_infra:
                        deg_clean[x] += 1
        active = [x for x in pos if deg_all[x] > 0]
        p6[key] = {"positives_in_frame_active_this_week": len(active),
                   "isolated_after_removing_tornado_edges": sum(1 for x in active if deg_clean[x] == 0),
                   "median_degree_before": sorted(deg_all[x] for x in active)[len(active) // 2] if active else None,
                   "median_degree_after": sorted(deg_clean[x] for x in active)[len(active) // 2] if active else None}
    res = {
        "days_extracted": len(days),
        "P1": {"deposits": len(deps), "withdrawals": len(wds), "undecoded_pool_events": sum(s["undecoded_pool_events"] for s in stats),
               "deposits_without_sender": sum(s["deposits_without_sender"] for s in stats),
               "per_pool": {p: {"deposits": c} for p, c in Counter(d["pool"] for d in deps).items()},
               "withdrawals_per_pool": dict(Counter(w["pool"] for w in wds)), "leaf_index_gaps": leaf_gaps(deps)},
        "P2": {"unique_depositors": len(depositors), "unique_recipients": len(recipients),
               "both_roles": len(depositors & recipients),
               "traceable_share": (sum(1 for d in deps if d["depositor"] and d["tx"]) + len(wds)) / max(1, len(deps) + len(wds))},
        "P3": {"contract_callees_seen": len(callees), "relayers": len(relayers),
               "depositors_that_are_contract_callees": len(depositors & callees),
               "recipients_that_are_contract_callees": len(recipients & callees)},
        "P4": p4,
        "P5": {"frame_size": len(frame), "depositors_in_frame": len(depositors & frame), "recipients_in_frame": len(recipients & frame),
               "expected_at_sampling": {f: {"depositors": round(len(depositors & frame) * f), "recipients": round(len(recipients & frame) * f)}
                                        for f in (0.01, 0.05, 0.10, 0.25)}},
        "P6": p6,
        "P8": {"placebo_cutoffs": ["2022-05-08", "2022-06-08"],
               "data_present": all((OUT / "days" / f"{d}.json").exists() for d in ("2022-05-08", "2022-06-08"))},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:4000])
    return res
