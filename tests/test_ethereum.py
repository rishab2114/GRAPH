import pytest

from gffs import ethereum as eth


def test_event_signatures_are_keccak_of_the_event_definitions():
    # Literal topic0 values observed in the 2022-07-01 pool logs (336 and 350 events): the computed hashes must match them.
    assert eth.DEPOSIT_TOPIC == "0xa945e51eec50ab98c161376f0db4cf2aeba3ec92755fe2fcd388bdbbb80ff196"
    assert eth.WITHDRAWAL_TOPIC == "0xe9e508bad6d4c3227e881ca19068f099da81b5164dd6d62b2eaf1e8bc6c34931"


def _word(hex_body: str) -> str:
    return hex_body.rjust(64, "0")


def test_decode_withdrawal():
    to = "ab" * 20; relayer = "cd" * 20
    data = "0x" + _word(to) + _word("11" * 32) + _word(hex(10**15)[2:])
    topics = [eth.WITHDRAWAL_TOPIC, "0x" + _word(relayer)]
    w = eth.decode_withdrawal(topics, data)
    assert w == {"recipient": "0x" + to, "relayer": "0x" + relayer, "fee_wei": 10**15, "nullifier": "0x" + "11" * 32}


def test_decode_deposit():
    data = "0x" + _word(hex(42)[2:]) + _word(hex(1656633600)[2:])
    d = eth.decode_deposit([eth.DEPOSIT_TOPIC, "0x" + "22" * 32], data)
    assert d == {"commitment": "0x" + "22" * 32, "leaf_index": 42, "timestamp": 1656633600}


def test_value_transfer_rule():
    assert eth.is_value_transfer(21000, 5)            # plain ETH transfer between accounts
    assert not eth.is_value_transfer(21000, 0)        # zero-value
    assert not eth.is_value_transfer(52000, 5)        # contract call carrying ETH


def test_pool_denominations():
    assert eth.POOL_DENOMINATION_WEI["0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936"] == 10**18
    assert set(eth.TORNADO_ADDRESSES) >= set(eth.POOL_DENOMINATION_WEI) | {eth.ROUTER}
