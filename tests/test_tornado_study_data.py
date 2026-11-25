from datetime import date

from gffs.tornado_study_data import (DENOMS, pool_deposits, reference_month, task_dates, tornado_rows,
                                     withdrawals_from_payments)

POOL1 = "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936"   # 1 ETH


def test_task_dates_match_the_frozen_design():
    assert task_dates(date(2022, 8, 8)) == {"train": [date(2021, 12, 27), date(2022, 2, 21), date(2022, 4, 18)],
                                            "calibration": date(2022, 6, 13), "evaluation": date(2022, 8, 8)}
    assert task_dates(date(2022, 4, 8))["train"][0] == date(2021, 8, 27)


def test_reference_month_is_last_full_month_ending_8_days_before():
    assert reference_month(date(2022, 8, 8)) == (date(2022, 7, 1), date(2022, 7, 31))
    assert reference_month(date(2022, 4, 8)) == (date(2022, 3, 1), date(2022, 3, 31))
    assert reference_month(date(2022, 4, 7)) == (date(2022, 2, 1), date(2022, 2, 28))   # March ends after t-8d
    assert reference_month(date(2022, 2, 11)) == (date(2022, 1, 1), date(2022, 1, 31))


def test_tornado_rows_keeps_successful_calls_to_listed_addresses():
    ofac = {POOL1, "0xrouter"}
    txs = [("0xh1", "0xa", POOL1, 1e18, 1), ("0xh3", "0xc", "0xrouter", 0.0, 1),
           ("0xh4", "0xd", "0xrouter", 1e18, 0), ("0xh5", "0xe", "0xother", 1e18, 1)]
    assert [x["sender"] for x in tornado_rows(txs, ofac)] == ["0xa", "0xc"]
    assert DENOMS == (1e17, 1e18, 1e19, 1e20)


def test_pool_deposits_are_inflows_of_exactly_the_denomination():
    # Seen 2022-02-21: 0.1 and 1 ETH sent to another listed Tornado contract are not ETH-pool deposits.
    ins = [{"tx": "0x1", "pool": POOL1, "value": 1e18}, {"tx": "0x2", "pool": POOL1, "value": 5e17}]
    assert pool_deposits(ins) == [{"tx": "0x1", "pool": POOL1}]


def test_split_payments_uses_call_order_recipient_first():
    # ETHTornado._processWithdraw pays the recipient first, then the relayer. Seen 2022-02-21: fees above half of a
    # 0.1 ETH denomination, so "the larger payment is the recipient" is wrong.
    P01 = "0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc"
    pays = [{"tx": "0x1", "pool": P01, "to": "0xl", "value": 6e16, "order": "0,2"},
            {"tx": "0x1", "pool": P01, "to": "0xr", "value": 4e16, "order": "0,1"},
            {"tx": "0x2", "pool": POOL1, "to": "0xs", "value": 1e18, "order": "0,10"}]
    out = withdrawals_from_payments(pays)
    assert [(w["tx"], w["recipient"], w["fee_payee"], w["ambiguous"]) for w in out] == \
        [("0x1", "0xr", "0xl", False), ("0x2", "0xs", None, False)]


# ---- G04 (Codex review 2026-11-24): call ancestry, batches, zero fees ----
from gffs.tornado_study_data import effective_ok, withdrawals_from_payments  # noqa: E402

P10 = "0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc"   # 0.1 ETH


def test_a_call_counts_only_if_it_and_every_ancestor_has_no_error():
    tr = [{"tx": "0x1", "order": None, "error": None}, {"tx": "0x1", "order": "0", "error": "Reverted"},
          {"tx": "0x1", "order": "0,0", "error": None},                 # caught revert: parent failed, outer tx fine
          {"tx": "0x1", "order": "1", "error": None}, {"tx": "0x1", "order": "1,0", "error": None},
          {"tx": "0x2", "order": "0", "error": "Out of gas"}]
    ok = effective_ok(tr)
    assert ("0x1", "0,0") not in ok and ("0x1", "0") not in ok and ("0x2", "0") not in ok
    assert ("0x1", "1,0") in ok and ("0x1", "1") in ok


def test_batched_withdrawals_are_split_by_their_pool_call_frame():
    pays = [{"tx": "0x1", "pool": POOL1, "to": "0xl", "value": 3e15, "order": "0,2"},
            {"tx": "0x1", "pool": POOL1, "to": "0xr1", "value": 1e18 - 3e15, "order": "0,1"},
            {"tx": "0x1", "pool": POOL1, "to": "0xr2", "value": 1e18 - 3e15, "order": "1,1"},
            {"tx": "0x1", "pool": POOL1, "to": "0xl", "value": 3e15, "order": "1,2"}]
    out = withdrawals_from_payments(pays)
    assert [(w["recipient"], w["fee_payee"], w["ambiguous"]) for w in out] == [("0xr1", "0xl", False), ("0xr2", "0xl", False)]


def test_zero_fee_single_payment_is_recipient_and_fee_equal_to_denomination_is_ambiguous():
    pays = [{"tx": "0x1", "pool": P10, "to": "0xs", "value": 1e17, "order": "0,1"},      # zero fee
            {"tx": "0x2", "pool": P10, "to": "0xl", "value": 1e17 - 1e14, "order": "0,1"}]  # recipient got 0: unseen
    out = withdrawals_from_payments(pays)
    assert (out[0]["recipient"], out[0]["fee_payee"], out[0]["ambiguous"]) == ("0xs", None, False)
    assert out[1]["ambiguous"] and out[1]["payees"] == ["0xl"]


def test_reconcile_counts_misses_and_extras_as_multisets():
    from gffs.tornado_study_data import reconcile_day
    logs = {"deposits": [{"tx": "0x1", "pool": POOL1, "depositor": "0xa"}, {"tx": "0x1", "pool": POOL1, "depositor": "0xa"},
                         {"tx": "0x2", "pool": POOL1, "depositor": "0xb"}],
            "withdrawals": [{"tx": "0x3", "pool": POOL1, "recipient": "0xr", "relayer": "0xl", "fee_wei": 5},
                            {"tx": "0x4", "pool": POOL1, "recipient": "0xs", "relayer": "0xl", "fee_wei": 0}]}
    hist = {"deposits": [{"tx": "0x1", "pool": POOL1, "depositor": "0xa"}, {"tx": "0x9", "pool": POOL1, "depositor": "0xz"}],
            "withdrawals": [{"tx": "0x3", "pool": POOL1, "recipient": "0xr", "fee_payee": "0xl", "ambiguous": False},
                            {"tx": "0x4", "pool": POOL1, "recipient": "0xs", "fee_payee": None, "ambiguous": False}]}
    r = reconcile_day(logs, hist)
    assert r["deposits"] == {"logs": 3, "traces": 2, "missed": 2, "extra": 1}
    assert r["withdrawals"] == {"logs": 2, "traces": 2, "missed": 0, "extra": 0, "ambiguous": 0}


def test_root_trace_address_stored_as_the_string_none_is_the_root():
    # Real data: the root call's trace_address is the string "None" (seen 2022-02-08 after the G04 change).
    tr = [{"tx": "0x1", "order": "None", "error": "Reverted"}, {"tx": "0x1", "order": "0", "error": None},
          {"tx": "0x2", "order": "None", "error": None}, {"tx": "0x2", "order": "0,1", "error": None}]
    ok = effective_ok(tr)
    assert ("0x1", "0") not in ok and ("0x2", "0,1") in ok
