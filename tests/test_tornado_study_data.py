from datetime import date

from gffs.tornado_study_data import (DENOMS, pool_deposits, reference_month, split_payments, task_dates,
                                     tornado_rows)

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
    out = split_payments(pays)
    assert out == [{"tx": "0x1", "pool": P01, "recipient": "0xr", "fee_payee": "0xl", "payments": 2},
                   {"tx": "0x2", "pool": POOL1, "recipient": "0xs", "fee_payee": None, "payments": 1}]
