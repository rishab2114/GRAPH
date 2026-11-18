"""AML literature graph, vocabulary v2: the 14 v1 target concepts plus context nodes taken from
OpenAlex's own tags on the pre-2017 AML / crypto / fraud corpus (config/aml_vocabulary_v2.toml,
docs/vocabulary-v2.md). Frozen rules; nothing here is tuned on results.

    python -m gffs.literature_v2 --out results/

The corpus download is resumable: every page is cached under data/openalex/v2/ with the next cursor,
so a run that hits OpenAlex's allowance continues where it stopped on the next run.
"""
from __future__ import annotations

import argparse
import json
import tomllib
from collections import Counter
from pathlib import Path

import numpy as np

from gffs import aml_vocab
from gffs import literature as lit

CORPUS_SELECT = "id,publication_year,concepts,topics"
DEFAULT_CONFIG = Path("config/aml_vocabulary_v2.toml")


def _short(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def choose_source(first_page: list[dict], preference: list[str]) -> str:
    """The first tag field, in preference order, that any work on the first corpus page carries."""
    for field in preference:
        if any(w.get(field) for w in first_page):
            return field
    raise ValueError(f"no work on the first page carries any of {preference}")


def work_tags(w: dict, source: str, min_score: float, min_level: int) -> list[str]:
    out = []
    for t in w.get(source) or []:
        if (t.get("score") or 0) < min_score:
            continue
        if source == "concepts" and (t.get("level") or 0) < min_level:
            continue
        out.append(_short(t["id"]))
    return sorted(set(out))


def context_nodes(corpus: dict[str, dict], min_works: int, max_nodes: int, cutoff_year: int) -> list[str]:
    counts = Counter(t for w in corpus.values() if w["year"] <= cutoff_year for t in w["tags"])
    kept = sorted((t for t, n in counts.items() if n >= min_works), key=lambda t: (-counts[t], t))
    return kept[:max_nodes]


def merge_works(v1_works: dict, corpus: dict[str, dict], nodes: list[str], prefix: str) -> dict:
    keep = set(nodes)
    out: dict[str, dict] = {}
    for wid, w in v1_works.items():
        out[wid] = {"year": w["year"], "concepts": list(w["concepts"])}
    for wid, w in corpus.items():
        tags = [prefix + t for t in w["tags"] if t in keep]
        if not tags:
            continue
        rec = out.setdefault(wid, {"year": w["year"], "concepts": []})
        rec["concepts"].extend(tags)
    for rec in out.values():
        rec["concepts"] = sorted(set(rec["concepts"]))
    return {k: v for k, v in out.items() if v["concepts"]}


def fetch_corpus(client: lit.Client, filt: str, cache_dir: Path, select: str = CORPUS_SELECT) -> list[dict]:
    """All works matching `filt`, page by page, resumable. Returns the raw work records."""
    pages_dir = cache_dir / "corpus"
    pages_dir.mkdir(parents=True, exist_ok=True)
    state_path = cache_dir / "corpus_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else \
        {"filter": filt, "select": select, "next_cursor": "*", "pages": 0, "done": False}
    if state["filter"] != filt or state["select"] != select:
        raise RuntimeError(f"{state_path} was built with a different query; delete {cache_dir} to refetch")
    while not state["done"]:
        page = client._get({"filter": filt, "per_page": lit.PER_PAGE, "cursor": state["next_cursor"], "select": select})
        (pages_dir / f"page_{state['pages']:05d}.json").write_text(json.dumps(page["results"]))
        state["pages"] += 1
        state["reported_count"] = page["meta"].get("count")
        nxt = page["meta"].get("next_cursor") if page["results"] else None
        state["next_cursor"], state["done"] = nxt, nxt is None
        tmp = state_path.with_suffix(".part"); tmp.write_text(json.dumps(state)); tmp.rename(state_path)
    raw = []
    for i in range(state["pages"]):
        raw.extend(json.loads((pages_dir / f"page_{i:05d}.json").read_text()))
    return raw


def corpus_from_raw(raw: list[dict], source: str, min_score: float, min_level: int) -> dict[str, dict]:
    return {_short(w["id"]): {"year": int(w["publication_year"]), "tags": work_tags(w, source, min_score, min_level)}
            for w in raw if w.get("publication_year") is not None}


def rank_scenarios(works: dict, v: aml_vocab.Vocabulary, method: str, train: tuple[int, int], t: int) -> list[dict]:
    """Rank unlinked Elliptic-expressible target pairs at year `t` with the pre-chosen method."""
    from gffs.baselines import frequency_scores
    from gffs.features import pair_features
    from gffs.graph import candidate_pairs, new_edges
    from gffs.models import fit_model

    g_t = lit.graph_at(works, t, v.ids)
    targets = [p for p in candidate_pairs(g_t) if p[0] in v.ids and p[1] in v.ids and v.expressible(*p)]
    if not targets:
        return []
    if method == "frequency":
        scores = frequency_scores(g_t, targets)
    else:
        g_a, g_b = lit.graph_at(works, train[0], v.ids), lit.graph_at(works, train[1], v.ids)
        tp = candidate_pairs(g_a)
        y = np.array([p in new_edges(g_a, g_b) for p in tp], dtype=int)
        scorer = fit_model(method, pair_features(g_a, tp).reset_index(drop=True), y)
        scores = scorer(pair_features(g_t, targets).reset_index(drop=True))
    order = np.argsort(-np.asarray(scores), kind="stable")
    return [{"pair": list(targets[i]), "score": float(scores[i]), "rank": r + 1} for r, i in enumerate(order)]


def main(argv: list[str] | None = None) -> None:
    from gffs.study import run_split

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--n-boot", type=int, default=1000)
    args = ap.parse_args(argv)
    cfg = tomllib.loads(args.config.read_text())
    v = aml_vocab.load(Path(cfg["base_vocabulary"]))
    client = lit.Client(lit.api_key())

    v1_records = lit.fetch_vocabulary(v, client, Path(f"data/openalex/v{v.version}"))
    v1_works = lit.works_from_records(v1_records)
    raw = fetch_corpus(client, lit.anchor_filter(v.anchor_terms, cfg["cutoff"]), Path("data/openalex/v2"))
    ctx = cfg["context"]
    first_page = json.loads((Path("data/openalex/v2/corpus/page_00000.json")).read_text())
    source = choose_source(first_page, ctx["source_preference"])
    corpus = corpus_from_raw(raw, source, ctx["min_score"], ctx["min_level"])
    cutoff_year = int(cfg["cutoff"][:4])
    nodes = context_nodes(corpus, ctx["min_works"], ctx["max_nodes"], cutoff_year)
    works = merge_works(v1_works, corpus, nodes, ctx["node_prefix"])

    (a, b), (_, c) = cfg["evaluation"]["train"], cfg["evaluation"]["test"]
    targets = set(v.ids)
    ell = {x.id for x in v.concepts if x.elliptic}
    r = run_split(lit.concept_sets(works, a), lit.concept_sets(works, b), lit.concept_sets(works, c),
                  n_boot=args.n_boot, focus=lambda u, w: u in ell or w in ell)
    lr = r["methods"]["logreg_all"]["vs_frequency"]
    sr = r["methods"]["structural_rank_mean"]["vs_frequency"]
    primary = bool(lr["lo"] > 0 and sr["lo"] > 0)
    method = "logreg_all" if lr["lo"] > 0 else "frequency"
    scenarios = rank_scenarios(works, v, method, (b, c), cutoff_year)
    names = {}
    for w in raw:
        for t in w.get(source) or []:
            names[_short(t["id"])] = t.get("display_name")
    out = {"config": str(args.config), "source": source, "corpus_works": len(corpus), "n_context_nodes": len(nodes),
           "context_nodes": [{"id": n, "name": names.get(n)} for n in nodes],
           "graph_works": len(works), "evaluation": r, "primary_holds": primary,
           "scenario_method": method, "scenarios": scenarios}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "literature_graph_v2.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("source", "corpus_works", "n_context_nodes", "graph_works",
                                          "primary_holds", "scenario_method")}, indent=1))


if __name__ == "__main__":
    main()
