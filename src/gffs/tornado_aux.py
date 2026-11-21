"""Add-on pilot passes (corrections in RESEARCH_LOG 2026-11-22): transaction status and exclusive edge categories,
independent withdrawal completeness via traces, and as-of-date contract evidence. Pre-sanction dates only.

    python -m gffs.tornado_aux days        # resumable; needs the main extractor's day JSON for each day
    python -m gffs.tornado_aux contracts   # contract creation evidence for addresses used by the pilot graphs
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from gffs import ethereum as eth
from gffs.tornado_pilot import CUTOFF, OUT, pilot_days

ZERO = "0x" + "0" * 40
PLACEBO_CUTOFFS = [date(2022, 5, 8), date(2022, 6, 8)]
FEATURE_DAYS = 7
HORIZON_WEEKS = 8
AUX = OUT / "aux"
WEI_TOL = 1e6     # doubles near 1e18-1e20 wei have spacing far below this


def categorize(gas: int, value: float, status: int) -> str:
    """Exactly one category per transaction. Contract calls and value transfers are never mixed."""
    if status != 1:
        return "failed"
    if value > 0:
        return "simple_transfer" if gas == eth.PLAIN_TRANSFER_GAS else "value_call"
    return "call"


def match_withdrawals(withdrawals: list[dict], traces: list[dict]) -> dict:
    out = [t for t in traces if t["status"] == 1 and t["from"] in eth.POOL_DENOMINATION_WEI and t["value"] > 0]
    by_tx: dict = {}
    for i, t in enumerate(out):
        by_tx.setdefault(t["tx"], []).append(i)
    used, matched = set(), 0
    for w in withdrawals:
        denom = eth.POOL_DENOMINATION_WEI[w["pool"]]
        expected = [(w["recipient"], denom - w["fee_wei"])] + ([(w["relayer"], w["fee_wei"])] if w["fee_wei"] > 0 else [])
        found = []
        for to, amount in expected:
            hit = next((i for i in by_tx.get(w["tx"], []) if i not in used and i not in found
                        and out[i]["from"] == w["pool"] and out[i]["to"] == to and abs(out[i]["value"] - amount) <= WEI_TOL), None)
            if hit is None:
                break
            found.append(hit)
        if len(found) == len(expected):
            matched += 1; used.update(found)
    return {"withdrawals": len(withdrawals), "matched": matched, "unmatched": len(withdrawals) - matched,
            "pool_outflows": len(out), "explained_outflows": len(used), "orphan_outflows": len(out) - len(used),
            "self_withdrawals": sum(1 for w in withdrawals if w["relayer"] == ZERO)}


def feature_days() -> dict[date, list[date]]:
    return {c: [c - timedelta(days=k) for k in range(FEATURE_DAYS, 0, -1)] for c in PLACEBO_CUTOFFS}


def aux_day(fs, d: date) -> dict:
    assert d < CUTOFF
    main = json.loads((OUT / "days" / f"{d}.json").read_text())
    event_tx = {x["tx"] for x in main["deposits"]} | {x["tx"] for x in main["withdrawals"]}
    tx = eth.read_day(fs, "transactions", d.isoformat(), ["hash", "from_address", "to_address", "value", "receipt_gas_used", "receipt_status"])
    hashes = pc.utf8_lower(tx["hash"]).to_pylist(); status = tx["receipt_status"].to_pylist()
    gas = tx["receipt_gas_used"].to_pylist(); val = tx["value"].to_pylist()
    cats = [categorize(g or 0, v or 0.0, s if s is not None else 0) for g, v, s in zip(gas, val, status)]
    st = {h: s for h, s in zip(hashes, status) if h in event_tx}
    if any(d in days for days in feature_days().values()):
        (AUX / "edges").mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.table({"src": pc.utf8_lower(tx["from_address"]), "dst": pc.utf8_lower(tx["to_address"]),
                                 "category": pa.array(cats).dictionary_encode()}), AUX / "edges" / f"{d}.parquet")
    tr = eth.read_day(fs, "traces", d.isoformat(), ["transaction_hash", "from_address", "to_address", "value", "status"])
    frm = pc.utf8_lower(tr["from_address"])
    m = pc.is_in(frm, value_set=pa.array(list(eth.POOL_DENOMINATION_WEI)))
    ptr = tr.filter(m)
    traces = [{"tx": h.lower(), "from": f.lower(), "to": (t or "").lower(), "value": v or 0.0, "status": s}
              for h, f, t, v, s in zip(*(ptr[c].to_pylist() for c in ("transaction_hash", "from_address", "to_address", "value", "status")))]
    from collections import Counter
    return {"day": d.isoformat(), "category_counts": dict(Counter(cats)),
            "event_tx_status": {"n": len(event_tx), "found": len(st), "success": sum(1 for s in st.values() if s == 1)},
            "withdrawal_check": match_withdrawals(main["withdrawals"], traces)}


def run_days(fs=None) -> None:
    fs = fs or eth.filesystem(); AUX.mkdir(parents=True, exist_ok=True)
    for d in pilot_days():
        out = AUX / f"{d}.json"
        if out.exists() or not (OUT / "days" / f"{d}.json").exists():
            continue
        r = aux_day(fs, d)
        tmp = out.with_suffix(".part"); tmp.write_text(json.dumps(r)); tmp.rename(out)
        print(d, r["event_tx_status"], r["withdrawal_check"], flush=True)


def run_contracts(addresses: set[str], end: date = CUTOFF, fs=None, start: date = date(2015, 7, 30)) -> pa.Table:
    """Creation evidence for `addresses`, from contracts created strictly before `end` (never after the cutoff)."""
    assert end <= CUTOFF
    fs = fs or eth.filesystem(); vs = pa.array(sorted(addresses)); found = []
    d = start
    while d < end:
        t = eth.read_day(fs, "contracts", d.isoformat(), ["address", "block_timestamp"])
        if t is not None and t.num_rows:
            a = pc.utf8_lower(t["address"]); m = pc.is_in(a, value_set=vs)
            if pc.any(m).as_py():
                found.append(pa.table({"address": a.filter(m), "created": pc.cast(t["block_timestamp"].filter(m), pa.string())}))
        d += timedelta(days=1)
    return pa.concat_tables(found) if found else pa.table({"address": pa.array([], pa.string()), "created": pa.array([], pa.string())})


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("step", choices=["days", "contracts"]); a = ap.parse_args(argv)
    if a.step == "days":
        run_days()
    else:
        import pandas as pd
        addrs = set()
        for f in (AUX / "edges").glob("*.parquet"):
            t = pq.read_table(f, columns=["src", "dst"])
            addrs |= set(pd.unique(t["src"].to_pandas())) | set(pd.unique(t["dst"].dropna().to_pandas()))
        for f in (OUT / "days").glob("*.json"):
            j = json.loads(f.read_text())
            addrs |= {x["depositor"] for x in j["deposits"] if x["depositor"]} | {x["recipient"] for x in j["withdrawals"]} \
                | {x["relayer"] for x in j["withdrawals"]} | {x["tx_sender"] for x in j["withdrawals"] if x["tx_sender"]}
        addrs.discard(None)
        print("addresses of interest:", len(addrs), flush=True)
        reg = run_contracts(addrs)
        pq.write_table(reg, AUX / "contracts_registry.parquet")
        print("contracts found:", reg.num_rows)


if __name__ == "__main__":
    main()
