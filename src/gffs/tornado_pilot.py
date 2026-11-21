"""Tornado Cash pilot extractor: pre-sanction data only (docs/tornado-pilot-plan.md).

    python -m gffs.tornado_pilot extract      # resumable; writes data/ethereum/pilot/
    python -m gffs.tornado_pilot summarise    # writes results/tornado_pilot.json

Never reads any date on or after 2022-08-08 (CUTOFF); this is enforced by `pilot_days()`.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from gffs import ethereum as eth

CUTOFF = date(2022, 8, 8)
WINDOW_START = date(2022, 2, 8)
FRAME_DAYS = (date(2022, 1, 1), date(2022, 1, 31))           # sampling frame reference period (before the window)
SAMPLE_WEEKS = [(date(2022, 3, 7), date(2022, 3, 13)), (date(2022, 6, 6), date(2022, 6, 12))]
OUT = Path("data/ethereum/pilot")
TX_COLS = ["hash", "from_address", "to_address", "value", "receipt_gas_used", "block_timestamp"]
LOG_COLS = ["address", "topics", "data", "transaction_hash"]


def _days(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def pilot_days() -> list[date]:
    days = list(_days(WINDOW_START, CUTOFF - timedelta(days=1)))
    assert max(days) < CUTOFF
    return days


def process_day(day: str, tx: pa.Table, logs: pa.Table) -> dict:
    frm = pc.utf8_lower(tx["from_address"]); to = pc.utf8_lower(tx["to_address"])
    gas = tx["receipt_gas_used"].to_pylist(); val = [int(v) if v is not None else 0 for v in tx["value"].to_pylist()]
    hashes = pc.utf8_lower(tx["hash"]).to_pylist(); frm_l = frm.to_pylist(); to_l = to.to_pylist()
    sender = dict(zip(hashes, frm_l))
    vt = [eth.is_value_transfer(g or 0, v) for g, v in zip(gas, val)]
    callees = {t for t, g in zip(to_l, gas) if t and (g or 0) > eth.PLAIN_TRANSFER_GAS}
    tornado_tx = sum(1 for t in to_l if t in eth.TORNADO_ADDRESSES)

    addr = pc.utf8_lower(logs["address"]).to_pylist()
    deposits, withdrawals, undecoded = [], [], 0
    for a, topics, data, th in zip(addr, logs["topics"].to_pylist(), logs["data"].to_pylist(),
                                   pc.utf8_lower(logs["transaction_hash"]).to_pylist()):
        if a not in eth.POOL_DENOMINATION_WEI or not topics:
            continue
        try:
            if topics[0] == eth.DEPOSIT_TOPIC:
                d = eth.decode_deposit(topics, data)
                deposits.append({"day": day, "pool": a, "tx": th, "depositor": sender.get(th), **d})
            elif topics[0] == eth.WITHDRAWAL_TOPIC:
                w = eth.decode_withdrawal(topics, data)
                withdrawals.append({"day": day, "pool": a, "tx": th, "tx_sender": sender.get(th), **w})
            else:
                undecoded += 1
        except (IndexError, ValueError):
            undecoded += 1
    return {"day": day, "deposits": deposits, "withdrawals": withdrawals, "contract_callees": callees,
            "stats": {"n_tx": tx.num_rows, "n_value_transfer": int(sum(vt)), "n_tornado_tx": tornado_tx,
                      "n_unique_senders": len(set(frm_l)), "undecoded_pool_events": undecoded,
                      "deposits_without_sender": sum(1 for d in deposits if d["depositor"] is None)}}


def _in_sample_week(d: date) -> bool:
    return any(a <= d <= b for a, b in SAMPLE_WEEKS)


def extract(fs=None) -> None:
    fs = fs or eth.filesystem()
    (OUT / "days").mkdir(parents=True, exist_ok=True); (OUT / "edges").mkdir(exist_ok=True)
    frame_path = OUT / "frame_senders.parquet"
    if not frame_path.exists():
        senders = set()
        for d in _days(*FRAME_DAYS):
            t = eth.read_day(fs, "transactions", d.isoformat(), ["from_address"])
            senders |= set(pc.utf8_lower(t["from_address"]).to_pylist())
            print("frame", d, len(senders), flush=True)
        pq.write_table(pa.table({"address": sorted(senders)}), frame_path)
    for d in pilot_days():
        out = OUT / "days" / f"{d}.json"
        if out.exists():
            continue
        tx = eth.read_day(fs, "transactions", d.isoformat(), TX_COLS)
        logs = eth.read_day(fs, "logs", d.isoformat(), LOG_COLS)
        r = process_day(d.isoformat(), tx, logs)
        pq.write_table(pa.table({"address": sorted(r.pop("contract_callees"))}), OUT / "days" / f"{d}.callees.parquet")
        if _in_sample_week(d):
            g = pa.compute.cast(tx["receipt_gas_used"], pa.int64())
            vt = pc.and_(pc.equal(g, eth.PLAIN_TRANSFER_GAS), pc.not_equal(tx["value"], "0"))
            pq.write_table(pa.table({"src": pc.utf8_lower(tx["from_address"]), "dst": pc.utf8_lower(tx["to_address"]),
                                     "value_transfer": vt}), OUT / "edges" / f"{d}.parquet")
        tmp = out.with_suffix(".part"); tmp.write_text(json.dumps(r)); tmp.rename(out)
        s = r["stats"]; print(d, "deposits", len(r["deposits"]), "withdrawals", len(r["withdrawals"]), s, flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("step", choices=["extract", "summarise"]); a = ap.parse_args(argv)
    if a.step == "extract":
        extract()
    else:
        from gffs.tornado_pilot_summary import summarise
        summarise()


if __name__ == "__main__":
    main()
