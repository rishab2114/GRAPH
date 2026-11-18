"""Download versioned ATT&CK Enterprise releases from the mitre/cti repo."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import requests

RAW = "https://raw.githubusercontent.com/mitre/cti/{tag}/enterprise-attack/enterprise-attack.json"


def release_url(tag: str) -> str:
    return RAW.format(tag=quote(tag, safe=""))


def fetch_release(tag: str, cache_dir: Path = Path("data/attack")) -> Path:
    """Return the local path of release `tag`, downloading it once."""
    cache_dir = Path(cache_dir)
    path = cache_dir / f"{tag}.json"
    if path.exists():
        return path
    cache_dir.mkdir(parents=True, exist_ok=True)
    resp = requests.get(release_url(tag), timeout=60)
    resp.raise_for_status()
    tmp = path.with_suffix(".part")
    tmp.write_bytes(resp.content)
    tmp.rename(path)
    return path
