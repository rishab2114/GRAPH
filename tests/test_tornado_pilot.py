import pyarrow as pa

from gffs import ethereum as eth
from gffs.tornado_pilot import process_day

POOL1 = "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936"


def _w(h): return h.rjust(64, "0")


def test_process_day_links_deposits_to_senders_and_decodes_withdrawals():
    tx = pa.table({
        "hash": ["0xd1", "0xw1", "0xp1", "0xc1"],
        "from_address": ["0xAlice", "0xrelayer", "0xbob", "0xbob"],
        "to_address": [eth.ROUTER, eth.ROUTER, "0xCarol", "0xdex"],
        "value": [1e18, 0.0, 5.0, 0.0],   # AWS stores value as double
        "receipt_gas_used": [900000, 400000, 21000, 120000],
        "block_timestamp": ["2022-07-01 00:00:00"] * 4,
    })
    logs = pa.table({
        "address": [POOL1, POOL1, "0xother"],
        "topics": [[eth.DEPOSIT_TOPIC, "0x" + "aa" * 32], [eth.WITHDRAWAL_TOPIC, "0x" + _w("ee" * 20)], ["0xdead"]],
        "data": ["0x" + _w("1") + _w("1656633600"), "0x" + _w("dd" * 20) + _w("11" * 32) + _w("0"), "0x"],
        "transaction_hash": ["0xd1", "0xw1", "0xc1"],
    })
    r = process_day("2022-07-01", tx, logs)
    assert [d["depositor"] for d in r["deposits"]] == ["0xalice"] and r["deposits"][0]["pool"] == POOL1
    assert r["withdrawals"][0]["recipient"] == "0x" + "dd" * 20 and r["withdrawals"][0]["tx_sender"] == "0xrelayer"
    assert r["stats"]["n_tx"] == 4 and r["stats"]["n_value_transfer"] == 1 and r["stats"]["n_tornado_tx"] == 2
    assert r["stats"]["undecoded_pool_events"] == 0
    assert "0xdex" in r["contract_callees"] and "0xcarol" not in r["contract_callees"]
