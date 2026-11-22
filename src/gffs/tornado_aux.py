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


def match_withdrawals(withdrawals: list[dict], traces: list[dict], tx_ok: set | None = None) -> dict:
    """Independent withdrawal completeness from traces, in both directions.

    Only real value-moving calls count (`call_type == "call"`): delegatecalls carry the context value but move no ETH.
    - events -> traces: each decoded Withdrawal should have pool outflows `denomination - fee` to the recipient and
      `fee` to the relayer (exact_match); a match where a trace is marked failed is a `status_anomaly`.
    - traces -> events: a transaction with a successful real pool outflow but no decoded Withdrawal would be a
      missed event (`outflow_tx_without_event`, should be 0). `tx_ok` is the set of transactions whose receipt
      succeeded: the traces table can mark a child call status=1 inside a reverted transaction (seen 2022-02-08), where
      no ETH moved. Those are counted as `outflows_in_reverted_tx`, not as missed events.
    - A matched withdrawal whose trace says status=0 in a successful transaction (`status_anomaly`) cannot be a failed
      payment: the ETH instance `require`s both payments (tornado-core ETHTornado.sol `_processWithdraw`), so the event
      would not exist. It is a status-field inconsistency in the traces table.
    """
    real = [t for t in traces if t.get("call_type", "call") == "call" and t["from"] in eth.POOL_DENOMINATION_WEI
            and t["value"] > 0]
    by_tx: dict = {}
    for i, t in enumerate(real):
        by_tx.setdefault(t["tx"], []).append(i)
    used, exact, anomaly, no_outflow = set(), 0, 0, 0
    for w in withdrawals:
        idx = by_tx.get(w["tx"], [])
        if not idx:
            no_outflow += 1
            continue
        denom = eth.POOL_DENOMINATION_WEI[w["pool"]]
        expected = [(w["recipient"], denom - w["fee_wei"])] + ([(w["relayer"], w["fee_wei"])] if w["fee_wei"] > 0 else [])
        found = []
        for to, amount in expected:
            hit = next((i for i in idx if i not in used and i not in found and real[i]["from"] == w["pool"]
                        and real[i]["to"] == to and abs(real[i]["value"] - amount) <= WEI_TOL), None)
            if hit is None:
                break
            found.append(hit)
        if len(found) == len(expected):
            used.update(found)
            if all(real[i]["status"] == 1 for i in found):
                exact += 1
            else:
                anomaly += 1
    event_tx = {w["tx"] for w in withdrawals}
    ok_tx = {t["tx"] for t in real if t["status"] == 1}
    reverted = {h for h in ok_tx if tx_ok is not None and h not in tx_ok}
    ok_tx -= reverted
    return {"withdrawals": len(withdrawals), "exact_match": exact, "status_anomaly": anomaly,
            "amount_mismatch": len(withdrawals) - exact - anomaly - no_outflow, "events_without_outflow": no_outflow,
            "real_pool_outflows": sum(1 for t in real if t["status"] == 1),
            "outflow_tx_without_event": len(ok_tx - event_tx), "outflows_in_reverted_tx": len(reverted),
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
    tr = eth.read_day(fs, "traces", d.isoformat(), ["transaction_hash", "from_address", "to_address", "value", "status", "call_type"])
    frm = pc.utf8_lower(tr["from_address"])
    m = pc.is_in(frm, value_set=pa.array(list(eth.POOL_DENOMINATION_WEI)))
    ptr = tr.filter(m)
    traces = [{"tx": h.lower(), "from": f.lower(), "to": (t or "").lower(), "value": v or 0.0, "status": s, "call_type": ct}
              for h, f, t, v, s, ct in zip(*(ptr[c].to_pylist() for c in
                                             ("transaction_hash", "from_address", "to_address", "value", "status", "call_type")))]
    from collections import Counter
    return {"day": d.isoformat(), "category_counts": dict(Counter(cats)),
            "event_tx_status": {"n": len(event_tx), "found": len(st), "success": sum(1 for s in st.values() if s == 1)},
            "withdrawal_check": match_withdrawals(main["withdrawals"], traces,
                                                  tx_ok={h for h, s in zip(hashes, status) if s == 1})}


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
    import pyarrow.fs as pafs
    fs = fs or eth.filesystem(); addresses = set(addresses); found = []
    present = {i.base_name.split("=", 1)[1] for i in fs.get_file_info(pafs.FileSelector(f"{eth.BUCKET}/contracts"))
               if i.base_name.startswith("date=")}
    wanted = [start + timedelta(days=k) for k in range((end - start).days)]
    missing = [x.isoformat() for x in wanted if x.isoformat() not in present]
    print(f"contracts partitions: {len(wanted) - len(missing)} present, {len(missing)} missing in [{start}, {end}):",
          missing[:20], flush=True)
    for d in wanted:
        if d.isoformat() not in present:
            continue
        t = eth.read_day(fs, "contracts", d.isoformat(), ["address", "block_timestamp"])
        if t is not None and t.num_rows:
            a = pc.utf8_lower(t["address"])
            m = pa.array([x in addresses for x in a.to_pylist()])   # a Python set: millions of addresses, built once
            if pc.any(m).as_py():
                found.append(pa.table({"address": a.filter(m), "created": pc.cast(t["block_timestamp"].filter(m), pa.string())}))
        if d.day == 1:
            print("contracts scanned through", d, "found so far", sum(f.num_rows for f in found), flush=True)
    if not found:
        return pa.table({"address": pa.array([], pa.string()), "created": pa.array([], pa.string())})
    # Some addresses appear more than once (e.g. redeployed at the same address): keep the earliest creation.
    reg = pa.concat_tables(found).group_by("address").aggregate([("created", "min")])
    return reg.rename_columns(["address", "created"])


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("step", choices=["days", "contracts"]); a = ap.parse_args(argv)
    if a.step == "days":
        run_days()
    else:
        import pandas as pd
        addrs = set()
        for f in (AUX / "edges").glob("*.parquet"):
            t = pq.read_table(f, columns=["src", "dst"])
            addrs |= set(pd.unique(t["src"].to_pandas())) | set(pd.unique(t["dst"].to_pandas().dropna()))
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
