from gffs.tornado_aux import categorize, match_withdrawals

POOL = "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936"   # 1 ETH


def test_categorize_is_exclusive_and_excludes_failed():
    assert categorize(21000, 5.0, 1) == "simple_transfer"
    assert categorize(60000, 5.0, 1) == "value_call"
    assert categorize(21000, 0.0, 1) == "call"
    assert categorize(90000, 0.0, 1) == "call"
    assert categorize(21000, 5.0, 0) == "failed"


def _t(tx, to, value, status=1, call_type="call"):
    return {"tx": tx, "from": POOL, "to": to, "value": value, "status": status, "call_type": call_type}


def test_match_withdrawals_both_directions_and_ignores_delegatecalls():
    fee = 2 * 10**15
    w = [{"tx": "0xa", "pool": POOL, "recipient": "0xr", "relayer": "0xl", "fee_wei": fee},
         {"tx": "0xb", "pool": POOL, "recipient": "0xs", "relayer": "0x" + "0" * 40, "fee_wei": 0},
         {"tx": "0xd", "pool": POOL, "recipient": "0xu", "relayer": "0xl", "fee_wei": fee}]
    traces = [_t("0xa", "0xr", float(10**18 - fee)), _t("0xa", "0xl", float(fee)),
              _t("0xb", "0xs", 1e18),
              _t("0xb", "0xhasher", 1e18, call_type="delegatecall"),       # context value, no ETH moves: ignored
              _t("0xc", "0xq", 1e18),                                       # real outflow, no decoded event: a missed event
              _t("0xd", "0xu", float(10**18 - fee), status=0), _t("0xd", "0xl", float(fee))]   # status anomaly
    m = match_withdrawals(w, traces)
    assert m["withdrawals"] == 3 and m["exact_match"] == 2 and m["status_anomaly"] == 1
    assert m["events_without_outflow"] == 0
    assert m["outflow_tx_without_event"] == 1          # the completeness check: should be 0 on real data
    assert m["self_withdrawals"] == 1


def test_outflows_inside_reverted_transactions_are_not_missed_events():
    # Observed 2022-02-08 (tx 0x232b84...): the root call reverted (out of gas) but the traces table still marks the
    # pool's child call status=1. No ETH moved and no event exists, so it must not count as a missed withdrawal.
    traces = [_t("0xe", "0xv", 1e19)]
    r = match_withdrawals([], traces, tx_ok=set())
    assert r["outflow_tx_without_event"] == 0 and r["outflows_in_reverted_tx"] == 1
    r = match_withdrawals([], traces, tx_ok={"0xe"})
    assert r["outflow_tx_without_event"] == 1 and r["outflows_in_reverted_tx"] == 0
