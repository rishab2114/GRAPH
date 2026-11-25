"""Pre-cutoff data for the frozen Stage 2 design (docs/tornado-design.md, sections 2-4 and 10).

One chronological pass over 2019-12-16 .. 2022-08-07 reads each day's transactions once (and the ETH-pool payment
traces) and writes:
  history/{day}.json      Tornado participation: successful transactions to the 38 OFAC-listed addresses (deposit if the
                          value equals a pool denomination) and ETH-pool withdrawals (recipient, fee payee, tx sender)
  frames/{YYYY-MM}.parquet senders of successful transactions in each reference month M(t)
  edges/{day}.parquet     typed top-level edges for the 15 feature weeks
Every date read is before 2022-08-08 (asserted).

    python -m gffs.tornado_study_data          # resumable
"""
from __future__ import annotations

import json
from collections import OrderedDict
from datetime import date, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from gffs import ethereum as eth
from gffs.tornado_aux import categorize
from gffs.tornado_pilot import CUTOFF

STUDY = Path("data/ethereum/study")
HISTORY_START = date(2019, 12, 16)              # first ETH pools deployed (pilot P3 registry)
EVAL_CUTOFFS = [date(2022, 8, 8), date(2022, 6, 8), date(2022, 4, 8)]
DENOMS = (1e17, 1e18, 1e19, 1e20)
TOL = 1e6
OFAC_FILE = Path("config/ofac/20220808_eth_addresses.txt")


def ofac_addresses() -> set[str]:
    return {l.strip().lower() for l in OFAC_FILE.read_text().splitlines() if l.strip().startswith("0x")}


def task_dates(c: date) -> dict:
    return {"train": [c - timedelta(weeks=w) for w in (32, 24, 16)], "calibration": c - timedelta(weeks=8), "evaluation": c}


def all_tasks() -> list[date]:
    out = set()
    for c in EVAL_CUTOFFS:
        t = task_dates(c); out |= set(t["train"]) | {t["calibration"], t["evaluation"]}
    return sorted(out)


def reference_month(t: date) -> tuple[date, date]:
    """Last full calendar month ending at least 8 days before t."""
    last = t - timedelta(days=8)
    end = date(last.year, last.month, 1) - timedelta(days=1)           # end of the month before `last`'s month
    nxt = date(last.year + (last.month == 12), last.month % 12 + 1, 1)
    if nxt - timedelta(days=1) <= last:                                   # `last` is itself a month end
        end = last
    return date(end.year, end.month, 1), end


def feature_days() -> set[date]:
    return {t - timedelta(days=k) for t in all_tasks() for k in range(1, 8)}


def months() -> dict[str, tuple[date, date]]:
    return {f"{a:%Y-%m}": (a, b) for a, b in sorted({reference_month(t) for t in all_tasks()})}


def tornado_rows(txs, ofac: set[str]) -> list[dict]:
    out = []
    for h, frm, to, value, status in txs:
        if status != 1 or to not in ofac:
            continue
        out.append({"tx": h, "sender": frm, "to": to, "value": value})
    return out


def pool_deposits(inflows: list[dict]) -> list[dict]:
    """ETH-pool deposits = calls paying a pool exactly its denomination (whatever contract the user entered through)."""
    return [{"tx": x["tx"], "pool": x["pool"]} for x in inflows
            if abs(x["value"] - eth.POOL_DENOMINATION_WEI[x["pool"]]) <= TOL]


def _order(a: str) -> tuple:
    return tuple(int(x) for x in a.split(",")) if a else ()


def effective_ok(traces: list[dict]) -> set[tuple]:
    """(tx, trace_address) of calls that took effect: neither the call nor any ancestor in its transaction has an error.
    The traces' `status` column is not used: it was wrong in both directions in the pilot (49 + 1 cases)."""
    err = {(t["tx"], _order(t["order"] or "")): bool(t["error"]) for t in traces}
    ok = set()
    for (tx, o), e in err.items():
        if not e and not any(err.get((tx, o[:i]), False) for i in range(len(o))):
            ok.add((tx, ",".join(map(str, o)) if o else None))
    return ok


def withdrawals_from_payments(pays: list[dict]) -> list[dict]:
    """One withdrawal per pool call frame (a batch makes several frames). In a frame the pool pays the recipient first,
    then the relayer (ETHTornado._processWithdraw). Frames that do not fit that pattern are kept as `ambiguous`, with
    every payee listed, instead of being given roles."""
    by: OrderedDict = OrderedDict()
    for p in pays:
        o = _order(p.get("order") or "")
        by.setdefault((p["tx"], p["pool"], o[:-1]), []).append((o, p))
    out = []
    for (tx, pool, _), ps in by.items():
        ps = [p for _, p in sorted(ps, key=lambda x: x[0])]
        denom = eth.POOL_DENOMINATION_WEI[pool]
        total = sum(p["value"] for p in ps)
        fits = len(ps) in (1, 2) and abs(total - denom) <= TOL
        out.append({"tx": tx, "pool": pool, "recipient": ps[0]["to"] if fits else None,
                    "fee_payee": ps[1]["to"] if fits and len(ps) == 2 else None,
                    "payees": [p["to"] for p in ps], "ambiguous": not fits, "payments": len(ps)})
    return out


def study_day(fs, d: date, ofac: set[str], write_edges: bool) -> tuple[dict, set[str]]:
    assert d < CUTOFF
    tx = eth.read_day(fs, "transactions", d.isoformat(),
                      ["hash", "from_address", "to_address", "value", "receipt_gas_used", "receipt_status"])
    h = pc.utf8_lower(tx["hash"]); frm = pc.utf8_lower(tx["from_address"]); to = pc.utf8_lower(tx["to_address"])
    st = tx["receipt_status"]
    m = pc.is_in(to, value_set=pa.array(sorted(ofac)))
    sub = [c.filter(m).to_pylist() for c in (h, frm, to, tx["value"], st)]
    rows = tornado_rows(zip(*sub), ofac)
    ok = pc.equal(st, 1)
    senders = set(pc.unique(frm.filter(ok)).to_pylist())
    if write_edges:
        cats = [categorize(g or 0, v or 0.0, s if s is not None else 0) for g, v, s in
                zip(tx["receipt_gas_used"].to_pylist(), tx["value"].to_pylist(), st.to_pylist())]
        (STUDY / "edges").mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.table({"src": frm, "dst": to, "category": pa.array(cats).dictionary_encode()}),
                       STUDY / "edges" / f"{d}.parquet")
    tr = eth.read_day(fs, "traces", d.isoformat(),
                      ["transaction_hash", "from_address", "to_address", "value", "call_type", "trace_address", "error"])
    pools = pa.array(list(eth.POOL_DENOMINATION_WEI))
    real = pc.and_(pc.equal(tr["call_type"], "call"), pc.greater(tr["value"], 0))
    tf, tt = pc.utf8_lower(tr["from_address"]), pc.utf8_lower(tr["to_address"])
    out_t = tr.filter(pc.and_(real, pc.is_in(tf, value_set=pools)))         # pool payments (withdrawals)
    in_t = tr.filter(pc.and_(real, pc.is_in(tt, value_set=pools)))          # pool inflows (deposits)
    oh, ih = pc.utf8_lower(out_t["transaction_hash"]), pc.utf8_lower(in_t["transaction_hash"])
    # G04: every trace of the pool-touching transactions, to drop calls whose own frame or an ancestor failed
    th = pc.utf8_lower(tr["transaction_hash"])
    anc = tr.filter(pc.is_in(th, value_set=pc.unique(pa.concat_arrays([oh.combine_chunks(), ih.combine_chunks()]))))
    took_effect = effective_ok([{"tx": a.lower(), "order": o, "error": e} for a, o, e in
                                zip(anc["transaction_hash"].to_pylist(), anc["trace_address"].to_pylist(),
                                    anc["error"].to_pylist())])
    # receipt status and sender of every transaction touching a pool (only successful ones count)
    sel = pc.is_in(h, value_set=pc.unique(pa.concat_arrays([oh.combine_chunks(), ih.combine_chunks()])))
    info = {a: (b, c) for a, b, c in zip(h.filter(sel).to_pylist(), frm.filter(sel).to_pylist(), st.filter(sel).to_pylist())}
    ok_tx = lambda a: info.get(a, (None, 0))[1] == 1
    pays = [{"tx": a, "pool": b, "to": (c or "").lower(), "value": v, "order": o}
            for a, b, c, v, o in zip(oh.to_pylist(), pc.utf8_lower(out_t["from_address"]).to_pylist(),
                                     out_t["to_address"].to_pylist(), out_t["value"].to_pylist(),
                                     out_t["trace_address"].to_pylist()) if ok_tx(a)]
    n_pay = len(pays)
    pays = [p for p in pays if (p["tx"], p["order"]) in took_effect]
    wds = withdrawals_from_payments(pays)
    for w in wds:
        w["tx_sender"] = info[w["tx"]][0]
    ins = [{"tx": a, "pool": b, "value": v, "order": o} for a, b, v, o in
           zip(ih.to_pylist(), pc.utf8_lower(in_t["to_address"]).to_pylist(), in_t["value"].to_pylist(),
               in_t["trace_address"].to_pylist()) if ok_tx(a)]
    n_in = len(ins)
    ins = [x for x in ins if (x["tx"], x["order"]) in took_effect]
    deps = pool_deposits(ins)
    for x in deps:
        x["depositor"] = info[x["tx"]][0]
    stats = {"n_tx": tx.num_rows, "tornado_txs": len(rows), "deposits": len(deps), "pool_inflows_not_denomination":
             len(ins) - len(deps), "withdrawals": len(wds), "ambiguous_withdrawal_frames": sum(w["ambiguous"] for w in wds),
             "pool_calls_dropped_by_ancestry": (n_pay - len(pays)) + (n_in - len(ins)),
             "payments_in_failed_or_missing_tx": int(out_t.num_rows) - len(pays), "senders": len(senders)}
    return {"day": d.isoformat(), "tornado_txs": rows, "deposits": deps, "withdrawals": wds, "stats": stats}, senders


def run(fs=None, start: date = HISTORY_START, end: date = CUTOFF) -> None:
    assert end <= CUTOFF
    fs = fs or eth.filesystem(); ofac = ofac_addresses()
    for sub in ("history", "frames", "senders"):
        (STUDY / sub).mkdir(parents=True, exist_ok=True)
    fdays = feature_days(); mon = months()
    in_month = {d: k for k, (a, b) in mon.items() for d in (a + timedelta(days=i) for i in range((b - a).days + 1))}
    d = start
    while d < end:
        out = STUDY / "history" / f"{d}.json"
        month = in_month.get(d)
        need_edges = d in fdays and not (STUDY / "edges" / f"{d}.parquet").exists()
        need_senders = month is not None and not (STUDY / "frames" / f"{month}.parquet").exists() \
            and not (STUDY / "senders" / f"{d}.parquet").exists()
        if not out.exists() or need_edges or need_senders:
            rec, senders = study_day(fs, d, ofac, write_edges=d in fdays)
            if need_senders:
                pq.write_table(pa.table({"address": sorted(senders)}), STUDY / "senders" / f"{d}.parquet")
            tmp = out.with_suffix(".part"); tmp.write_text(json.dumps(rec)); tmp.rename(out)
            print(d, rec["stats"], flush=True)
        if month is not None and d == mon[month][1] and not (STUDY / "frames" / f"{month}.parquet").exists():
            a, b = mon[month]
            files = [STUDY / "senders" / f"{a + timedelta(days=i)}.parquet" for i in range((b - a).days + 1)]
            allm = pa.concat_tables([pq.read_table(f) for f in files])
            frame = pc.unique(allm["address"])
            pq.write_table(pa.table({"address": frame}), STUDY / "frames" / f"{month}.parquet")
            for f in files:
                f.unlink()
            print("frame", month, len(frame), flush=True)
        d += timedelta(days=1)


if __name__ == "__main__":
    run()
