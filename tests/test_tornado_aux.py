from gffs.tornado_aux import categorize, match_withdrawals

POOL = "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936"   # 1 ETH


def test_categorize_is_exclusive_and_excludes_failed():
    assert categorize(21000, 5.0, 1) == "simple_transfer"
    assert categorize(60000, 5.0, 1) == "value_call"
    assert categorize(21000, 0.0, 1) == "call"           # zero-value, no code: still not a value transfer
    assert categorize(90000, 0.0, 1) == "call"
    assert categorize(21000, 5.0, 0) == "failed"


def test_match_withdrawals_accounts_for_recipient_and_relayer_transfers():
    fee = 2 * 10**15
    w = [{"tx": "0xa", "pool": POOL, "recipient": "0xr", "relayer": "0xl", "fee_wei": fee},
         {"tx": "0xb", "pool": POOL, "recipient": "0xs", "relayer": "0x" + "0" * 40, "fee_wei": 0}]
    traces = [{"tx": "0xa", "from": POOL, "to": "0xr", "value": float(10**18 - fee), "status": 1},
              {"tx": "0xa", "from": POOL, "to": "0xl", "value": float(fee), "status": 1},
              {"tx": "0xb", "from": POOL, "to": "0xs", "value": 1e18, "status": 1},
              {"tx": "0xc", "from": POOL, "to": "0xq", "value": 1e18, "status": 1}]   # outflow with no event
    m = match_withdrawals(w, traces)
    assert m == {"withdrawals": 2, "matched": 2, "unmatched": 0, "pool_outflows": 4,
                 "explained_outflows": 3, "orphan_outflows": 1, "self_withdrawals": 1}
