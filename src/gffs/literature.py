"""Literature co-occurrence graph of AML red-flag concepts from OpenAlex (Option 1, graph source A).

For each concept in the frozen vocabulary, fetch every work published up to the cutoff whose title or
abstract matches one of its synonyms AND one of the scope anchor terms. A work then "mentions" the set
of concepts whose queries returned it. Nodes = concepts; edge (a, b) = works mentioning both, dated by
the earliest such work. The graph can be rewound to any year <= cutoff.

    OPENALEX_API_KEY=... python -m gffs.literature --out results/

The key is read from OPENALEX_API_KEY or the git-ignored file .openalex_key, and sent only as an Authorization header: never in a URL, a log
or a cache file. Raw per-concept results are cached under data/openalex/v<version>/ (git-ignored).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from datetime import date
from itertools import combinations
from pathlib import Path

import networkx as nx
import requests

from gffs import aml_vocab
from gffs.graph import build_graph

API = "https://api.openalex.org/works"
USER_AGENT = "gffs-research-client"
PER_PAGE = 200

Works = dict[str, dict]  # work id -> {"year": int, "concepts": list[str]}


def _or_group(terms) -> str:
    for t in terms:
        if any(ch in t for ch in ',"()'):
            raise ValueError(f"term {t!r} contains a character that breaks the OpenAlex filter")
    return "(" + " OR ".join(f'"{t}"' for t in terms) + ")"


def concept_filter(synonyms, anchors, cutoff: str) -> str:
    """OpenAlex `filter` value: (any synonym) AND (any anchor) in title/abstract, published <= cutoff."""
    return (f"title_and_abstract.search:({_or_group(synonyms)} AND {_or_group(anchors)}),"
            f"to_publication_date:{cutoff}")


def anchor_filter(anchors, cutoff: str) -> str:
    return f"title_and_abstract.search:{_or_group(anchors)},to_publication_date:{cutoff}"


KEY_FILE = Path(".openalex_key")  # git-ignored


def api_key() -> str | None:
    """OPENALEX_API_KEY from the environment, else the first line of the git-ignored .openalex_key."""
    key = os.environ.get("OPENALEX_API_KEY")
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text().strip().splitlines()[0] if KEY_FILE.read_text().strip() else None
    return key or None


class Client:
    def __init__(self, api_key: str | None, session: requests.Session | None = None, pause: float = 0.1):
        self.s = session or requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        if api_key:
            self.s.headers["Authorization"] = f"Bearer {api_key}"
        self.pause = pause

    def _get(self, params: dict) -> dict:
        for attempt in range(12):
            r = self.s.get(API, params=params, timeout=60)
            if r.status_code == 200:
                time.sleep(self.pause)
                return r.json()
            if r.status_code == 503 and "temporarily unavailable" in r.text.lower() and attempt < 11:
                time.sleep(min(60 * (attempt + 1), 300))   # search cluster outage: wait minutes, up to ~25 min in all
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 5:
                if r.status_code == 429 and "budget" in r.text.lower():
                    raise RuntimeError("OpenAlex budget exhausted: set OPENALEX_API_KEY (free key) or wait for reset")
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"OpenAlex {r.status_code}: {r.text[:300]}")
        raise AssertionError("unreachable")

    def count(self, filt: str) -> int:
        return int(self._get({"filter": filt, "per_page": 1, "select": "id"})["meta"]["count"])

    def fetch_years(self, filt: str) -> tuple[dict[str, int], int]:
        """All works matching `filt` as {short id: publication year}, plus the API's reported count."""
        out: dict[str, int] = {}
        cursor, reported = "*", None
        while cursor:
            page = self._get({"filter": filt, "per_page": PER_PAGE, "cursor": cursor,
                              "select": "id,publication_year"})
            reported = page["meta"]["count"] if reported is None else reported
            for w in page["results"]:
                if w.get("publication_year") is not None:
                    out[w["id"].rsplit("/", 1)[-1]] = int(w["publication_year"])
            cursor = page["meta"].get("next_cursor") if page["results"] else None
        return out, int(reported or 0)


def fetch_vocabulary(v: aml_vocab.Vocabulary, client: Client, cache_dir: Path) -> dict[str, dict]:
    """Fetch (or load from cache) every concept's matching works. Returns {concept id: cache record}."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    records = {}
    for c in v.concepts:
        path = cache_dir / f"{c.id}.json"
        filt = concept_filter(c.synonyms, v.anchor_terms, v.cutoff)
        if path.exists():
            rec = json.loads(path.read_text())
            if rec["filter"] != filt:
                raise RuntimeError(f"cache {path} was built with a different query; delete it to refetch")
        else:
            works, reported = client.fetch_years(filt)
            rec = {"concept": c.id, "filter": filt, "retrieved": date.today().isoformat(),
                   "reported_count": reported, "works": works}
            tmp = path.with_suffix(".part")
            tmp.write_text(json.dumps(rec, sort_keys=True))
            tmp.rename(path)
        print(f"{c.id:16s} {len(rec['works']):6d} works (API reported {rec['reported_count']})")
        records[c.id] = rec
    return records


def works_from_records(records: dict[str, dict]) -> Works:
    works: Works = {}
    for cid, rec in records.items():
        for wid, year in rec["works"].items():
            w = works.setdefault(wid, {"year": year, "concepts": []})
            w["concepts"].append(cid)
    for w in works.values():
        w["concepts"].sort()
    return works


def concept_sets(works: Works, through_year: int) -> dict[str, frozenset[str]]:
    """Works published up to `through_year` -> concepts they mention (input to graph.build_graph)."""
    return {wid: frozenset(w["concepts"]) for wid, w in works.items() if w["year"] <= through_year}


def graph_at(works: Works, through_year: int, all_concepts: list[str]) -> nx.Graph:
    """Literature graph as of the end of `through_year`. Every vocabulary concept is a node, with
    freq 0 if no work mentions it yet, so candidate pairs are always over the full vocabulary."""
    g = build_graph(concept_sets(works, through_year))
    for c in all_concepts:
        if c not in g:
            g.add_node(c, freq=0)
    return g


def first_link_year(works: Works) -> dict[tuple[str, str], int]:
    first: dict[tuple[str, str], int] = {}
    for w in works.values():
        for pair in combinations(w["concepts"], 2):
            first[pair] = min(first.get(pair, w["year"]), w["year"])
    return first


def summarise(v: aml_vocab.Vocabulary, works: Works, years: list[int]) -> dict:
    ids = v.ids
    n_pairs = len(ids) * (len(ids) - 1) // 2
    expressible = {p for p in combinations(sorted(ids), 2) if v.expressible(*p)}
    by_year = []
    for y in years:
        g = graph_at(works, y, ids)
        edges = {tuple(sorted(e)) for e in g.edges}
        by_year.append({"year": y, "n_works": sum(w["year"] <= y for w in works.values()),
                        "n_edges": len(edges), "n_missing": n_pairs - len(edges),
                        "n_missing_expressible": len(expressible - edges)})
    g = graph_at(works, int(v.cutoff[:4]), ids)
    return {
        "vocabulary_version": v.version, "cutoff": v.cutoff, "n_concepts": len(ids), "n_pairs": n_pairs,
        "n_works": len(works), "n_works_multi_concept": sum(len(w["concepts"]) > 1 for w in works.values()),
        "concept_freq": {c: g.nodes[c]["freq"] for c in ids},
        "edges": sorted(([u, v_, g.edges[u, v_]["weight"]] for u, v_ in g.edges), key=lambda e: -e[2]),
        "first_link_year": {f"{a}|{b}": y for (a, b), y in sorted(first_link_year(works).items())},
        "by_year": by_year,
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vocab", type=Path, default=aml_vocab.DEFAULT_PATH)
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--first-year", type=int, default=2008)
    args = ap.parse_args(argv)

    v = aml_vocab.load(args.vocab)
    cache = args.cache or Path(f"data/openalex/v{v.version}")
    client = Client(api_key())
    records = fetch_vocabulary(v, client, cache)
    works = works_from_records(records)
    cutoff_year = int(v.cutoff[:4])
    summary = summarise(v, works, list(range(args.first_year, cutoff_year + 1)))
    summary["anchor_works_reported"] = client.count(anchor_filter(v.anchor_terms, v.cutoff))
    summary["retrieved"] = sorted({r["retrieved"] for r in records.values()})
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / f"literature_graph_v{v.version}.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"wrote {out}: {summary['n_works']} works, {len(summary['edges'])} of {summary['n_pairs']} pairs linked")


if __name__ == "__main__":
    main()
