"""Ethereum data access (AWS Public Blockchain Data, anonymous) and Tornado Cash event decoding.

Stage 2 pilot (docs/tornado-pilot-plan.md). Read only what each question needs; keep filtered extracts.
"""
from __future__ import annotations

import os
import urllib.parse

from Crypto.Hash import keccak

BUCKET = "aws-public-blockchain/v1.0/eth"
ROUTER = "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b"
POOL_DENOMINATION_WEI = {
    "0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc": 10**17,      # 0.1 ETH
    "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936": 10**18,      # 1 ETH
    "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf": 10**19,      # 10 ETH
    "0xa160cdab225685da1d56aa342ad8841c3b53f291": 10**20,      # 100 ETH
}
TORNADO_ADDRESSES = frozenset(POOL_DENOMINATION_WEI) | {ROUTER}
PLAIN_TRANSFER_GAS = 21000


def event_topic(signature: str) -> str:
    return "0x" + keccak.new(digest_bits=256, data=signature.encode()).hexdigest()


DEPOSIT_TOPIC = event_topic("Deposit(bytes32,uint32,uint256)")
WITHDRAWAL_TOPIC = event_topic("Withdrawal(address,bytes32,address,uint256)")


def _words(data: str) -> list[str]:
    body = data[2:] if data.startswith("0x") else data
    return [body[i:i + 64] for i in range(0, len(body), 64)]


def _addr(word: str) -> str:
    return "0x" + word[-40:].lower()


def decode_withdrawal(topics: list[str], data: str) -> dict:
    """Withdrawal(address to, bytes32 nullifierHash, address indexed relayer, uint256 fee)."""
    w = _words(data)
    return {"recipient": _addr(w[0]), "relayer": _addr(topics[1][2:]), "fee_wei": int(w[2], 16), "nullifier": "0x" + w[1]}


def decode_deposit(topics: list[str], data: str) -> dict:
    """Deposit(bytes32 indexed commitment, uint32 leafIndex, uint256 timestamp)."""
    w = _words(data)
    return {"commitment": topics[1].lower(), "leaf_index": int(w[0], 16), "timestamp": int(w[1], 16)}


def is_value_transfer(gas_used: int, value: int) -> bool:
    """A plain ETH transfer between externally owned accounts uses exactly 21,000 gas and moves value."""
    return gas_used == PLAIN_TRANSFER_GAS and value > 0


def filesystem():
    import pyarrow.fs as pafs
    proxy = urllib.parse.urlparse(os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "")
    kw = {"proxy_options": {"scheme": "http", "host": proxy.hostname, "port": proxy.port}} if proxy.hostname else {}
    return pafs.S3FileSystem(anonymous=True, region="us-east-2", **kw)


def day_files(fs, table: str, day: str) -> list[str]:
    import pyarrow.fs as pafs
    infos = fs.get_file_info(pafs.FileSelector(f"{BUCKET}/{table}/date={day}"))
    return sorted(i.path for i in infos if i.path.endswith(".parquet"))


def read_day(fs, table: str, day: str, columns: list[str]):
    import pyarrow as pa
    import pyarrow.parquet as pq
    parts = [pq.read_table(p, filesystem=fs, columns=columns) for p in day_files(fs, table, day)]
    return pa.concat_tables(parts) if parts else None
