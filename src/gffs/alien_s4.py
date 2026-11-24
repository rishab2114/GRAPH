"""S4 "alien scenarios": an exploratory, lightweight adaptation of Artiles et al. (2026), *The Alien Space of Science*.

Kept separate from the frozen Stage 2 (docs/tornado-design.md); see docs/s4-alien-prereg.md. Uses only literature
dated up to 2016 (the same cutoff as S1).

The paper's models, replaced by count/embedding versions that fit our small AML corpus:
  coherence     their autoregressive transformer over idea atoms -> cosine of PPMI-SVD concept embeddings
                (generalises to pairs that never co-occurred, which is what candidates are)
  availability  their author-idea dual encoder (median of top-10 authors) -> number of authors whose pre-cutoff
                repertoire already holds every concept of the set (the "bridging community"), log1p-scaled
  ranking       F_beta = (1 - beta) z(coherence) + beta z(unavailability), z-scored within the candidate pool (as theirs)

    python -m gffs.alien_s4 fetch       # authorships for the cached corpus (OpenAlex; resumable)
    python -m gffs.alien_s4 run         # pre-2017 temporal validation + S4 selection -> results/s4_alien.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import sparse

from gffs import aml_vocab
from gffs import literature as lit
from gffs import literature_v2 as l2

AUTH_DIR = Path("data/openalex/v2_authors")
CONFIG = Path("config/aml_vocabulary_v2.toml")
BETA_S4 = 0.7          # the paper's default portfolio setting, fixed before any score is seen
N_S4 = 10              # same size as S1 and S2
VALID = {"t0": 2013, "t1": 2016, "k_share": 0.01, "betas": [round(0.1 * i, 1) for i in range(11)]}


# ---------- pure functions (tested) ----------

def repertoires(works: dict, authors: dict, upto: int) -> dict[str, set]:
    reps: dict[str, set] = {}
    for wid, w in works.items():
        if w["year"] > upto:
            continue
        for a in authors.get(wid, []):
            reps.setdefault(a, set()).update(w["concepts"])
    return reps


def bridging_counts(reps: dict[str, set], pairs: list[tuple]) -> list[int]:
    """How many authors already hold every concept of each set in their repertoire (in any of their papers)."""
    concepts = sorted({c for p in pairs for c in p} | {c for r in reps.values() for c in r})
    idx = {c: i for i, c in enumerate(concepts)}
    rows, cols = [], []
    for i, r in enumerate(reps.values()):
        for c in r:
            rows.append(i); cols.append(idx[c])
    m = sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(reps), len(concepts)))
    co = (m.T @ m).tocsr()
    return [int(co[idx[a], idx[b]]) for a, b in pairs]


def coherence(works: dict, upto: int, pairs: list[tuple], dim: int = 64) -> np.ndarray:
    """Cosine similarity of concepts in a PPMI-SVD embedding of paper-level co-occurrence up to `upto`."""
    concepts = sorted({c for w in works.values() if w["year"] <= upto for c in w["concepts"]})
    idx = {c: i for i, c in enumerate(concepts)}
    n = len(concepts)
    cnt = np.zeros((n, n))
    for w in works.values():
        if w["year"] > upto:
            continue
        ids = [idx[c] for c in w["concepts"]]
        for i in ids:
            for j in ids:
                if i != j:
                    cnt[i, j] += 1
    tot = cnt.sum()
    row = cnt.sum(1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        pmi = np.log(cnt * tot / (row @ row.T))
    ppmi = np.where(np.isfinite(pmi) & (pmi > 0), pmi, 0.0)
    u, s, _ = np.linalg.svd(ppmi, full_matrices=False)
    k = min(dim, n)
    emb = u[:, :k] * np.sqrt(s[:k])
    norm = np.linalg.norm(emb, axis=1, keepdims=True)
    emb = np.divide(emb, norm, out=np.zeros_like(emb), where=norm > 0)
    out = np.zeros(len(pairs))
    for t, (a, b) in enumerate(pairs):
        if a in idx and b in idx:
            out[t] = float(emb[idx[a]] @ emb[idx[b]])
    return out


def _z(x: np.ndarray) -> np.ndarray:
    s = x.std()
    return (x - x.mean()) / s if s > 0 else np.zeros_like(x, dtype=float)


def fuse(coh: np.ndarray, unavail: np.ndarray, beta: float) -> np.ndarray:
    return (1 - beta) * _z(np.asarray(coh, float)) + beta * _z(np.asarray(unavail, float))


def recovery(scores: np.ndarray, hit: np.ndarray, k: int) -> dict:
    top = np.argsort(-scores, kind="stable")[:k]
    hits = int(hit[top].sum())
    expected = k * hit.sum() / len(hit)
    return {"k": k, "hits": hits, "expected": float(expected), "enrichment": float(hits / expected) if expected else None}


def vendi_pairs(pairs: list[tuple]) -> float:
    """Vendi score (effective number of distinct items) with Jaccard similarity between atom sets, as in the paper."""
    sets = [set(p) for p in pairs]
    n = len(sets)
    k = np.array([[len(a & b) / len(a | b) for b in sets] for a in sets]) / n
    lam = np.linalg.eigvalsh(k)
    lam = lam[lam > 1e-12]
    return float(np.exp(-(lam * np.log(lam)).sum()))


# ---------- data ----------

def load_works() -> tuple[dict, aml_vocab.Vocabulary]:
    """The v2 literature graph's works (same construction as gffs.literature_v2.main), from the local cache."""
    import tomllib
    cfg = tomllib.loads(CONFIG.read_text())
    v = aml_vocab.load(Path(cfg["base_vocabulary"]))
    client = lit.Client(lit.api_key())
    v1_works = lit.works_from_records(lit.fetch_vocabulary(v, client, Path(f"data/openalex/v{v.version}")))
    raw = l2.fetch_corpus(client, lit.anchor_filter(v.anchor_terms, cfg["cutoff"]), Path("data/openalex/v2"))
    ctx = cfg["context"]
    first = json.loads(Path("data/openalex/v2/corpus/page_00000.json").read_text())
    source = l2.choose_source(first, ctx["source_preference"])
    corpus = l2.corpus_from_raw(raw, source, ctx["min_score"], ctx["min_level"])
    nodes = l2.context_nodes(corpus, ctx["min_works"], ctx["max_nodes"], int(cfg["cutoff"][:4]))
    return l2.merge_works(v1_works, corpus, nodes, ctx["node_prefix"]), v


def _compact(results: list[dict]) -> dict:
    return {l2._short(w["id"]): [l2._short(a["author"]["id"]) for a in (w.get("authorships") or [])
                                  if a.get("author") and a["author"].get("id")] for w in results}


def fetch_authorships() -> dict[str, list[str]]:
    """Author ids for every work of the v2 graph: the corpus by cursor (same filter), then leftover ids in batches."""
    import tomllib
    cfg = tomllib.loads(CONFIG.read_text())
    v = aml_vocab.load(Path(cfg["base_vocabulary"]))
    client = lit.Client(lit.api_key())
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    state_p = AUTH_DIR / "state.json"
    st = json.loads(state_p.read_text()) if state_p.exists() else {"next_cursor": "*", "pages": 0, "done": False}
    filt = lit.anchor_filter(v.anchor_terms, cfg["cutoff"])
    while not st["done"]:
        page = client._get({"filter": filt, "per_page": lit.PER_PAGE, "cursor": st["next_cursor"], "select": "id,authorships"})
        (AUTH_DIR / f"page_{st['pages']:05d}.json").write_text(json.dumps(_compact(page["results"])))
        st["pages"] += 1
        nxt = page["meta"].get("next_cursor") if page["results"] else None
        st["next_cursor"], st["done"] = nxt, nxt is None
        state_p.write_text(json.dumps(st))
        if st["pages"] % 50 == 0:
            print("authorship pages", st["pages"], flush=True)
    authors: dict = {}
    for i in range(st["pages"]):
        authors.update(json.loads((AUTH_DIR / f"page_{i:05d}.json").read_text()))
    works, _ = load_works()
    missing = sorted(set(works) - set(authors))
    extra_p = AUTH_DIR / "extra.json"
    extra = json.loads(extra_p.read_text()) if extra_p.exists() else {}
    todo = [w for w in missing if w not in extra]
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        page = client._get({"filter": "openalex:" + "|".join(chunk), "per_page": 50, "select": "id,authorships"})
        got = _compact(page["results"])
        for w in chunk:
            extra[w] = got.get(w, [])
        extra_p.write_text(json.dumps(extra))
    authors.update(extra)
    print("works", len(works), "with authorship records", sum(1 for w in works if authors.get(w)), flush=True)
    return authors


def load_authors() -> dict:
    authors: dict = {}
    for p in sorted(AUTH_DIR.glob("page_*.json")):
        authors.update(json.loads(p.read_text()))
    if (AUTH_DIR / "extra.json").exists():
        authors.update(json.loads((AUTH_DIR / "extra.json").read_text()))
    return authors


# ---------- analysis ----------

def _pairs_unlinked(works: dict, upto: int) -> tuple[list[tuple], set]:
    nodes = sorted({c for w in works.values() if w["year"] <= upto for c in w["concepts"]})
    linked = set()
    for w in works.values():
        if w["year"] <= upto:
            cs = sorted(w["concepts"])
            linked.update((a, b) for i, a in enumerate(cs) for b in cs[i + 1:])
    return [(a, b) for i, a in enumerate(nodes) for b in nodes[i + 1:] if (a, b) not in linked], linked


def temporal_validation(works: dict, authors: dict) -> dict:
    t0, t1 = VALID["t0"], VALID["t1"]
    cand, _ = _pairs_unlinked(works, t0)
    later = set()
    for w in works.values():
        if t0 < w["year"] <= t1:
            cs = sorted(w["concepts"])
            later.update((a, b) for i, a in enumerate(cs) for b in cs[i + 1:])
    hit = np.array([p in later for p in cand], dtype=int)
    coh = coherence(works, t0, cand)
    bridge = np.array(bridging_counts(repertoires(works, authors, t0), cand))
    unav = -np.log1p(bridge)
    far = (bridge == 0).astype(int) * hit
    k = max(1, int(round(VALID["k_share"] * len(cand))))
    rows = []
    for b in VALID["betas"]:
        s = fuse(coh, unav, b)
        r_all, r_far = recovery(s, hit, k), recovery(s, far, k)
        rows.append({"beta": b, "all": r_all, "far": r_far,
                     "far_share_of_hits": (r_far["hits"] / r_all["hits"]) if r_all["hits"] else None})
    from scipy.stats import spearmanr
    return {"t0": t0, "t1": t1, "candidates": len(cand), "targets": int(hit.sum()),
            "far_targets_no_bridging_author": int(far.sum()), "k": k,
            "spearman_coherence_vs_availability": float(spearmanr(coh, np.log1p(bridge)).statistic), "by_beta": rows}


def select_s4(works: dict, authors: dict, scenario_pairs: list[tuple], t: int = 2016) -> dict:
    coh = coherence(works, t, scenario_pairs)
    bridge = np.array(bridging_counts(repertoires(works, authors, t), scenario_pairs))
    s = fuse(coh, -np.log1p(bridge), BETA_S4)
    order = np.argsort(-s, kind="stable")
    table = [{"pair": list(scenario_pairs[i]), "coherence": float(coh[i]), "bridging_authors": int(bridge[i]),
              "F": float(s[i]), "rank": r + 1} for r, i in enumerate(order)]
    return {"t": t, "beta": BETA_S4, "pool": len(scenario_pairs), "ranking": table,
            "S4": [row["pair"] for row in table[:N_S4]]}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("step", choices=["fetch", "run"]); a = ap.parse_args(argv)
    if a.step == "fetch":
        fetch_authorships(); return
    works, _ = load_works(); authors = load_authors()
    lit_v2 = json.loads(Path("results/literature_graph_v2.json").read_text())
    pool = [tuple(s["pair"]) for s in lit_v2["scenarios"]]
    s1 = [tuple(s["pair"]) for s in lit_v2["scenarios"][:N_S4]]
    s4 = select_s4(works, authors, pool)
    from gffs.e3e4 import ALL_PAIRS  # S2 exactly as in Stage 1 (e3e4.run_cutoff)
    s2 = [tuple(ALL_PAIRS[i]) for i in np.random.default_rng(0).choice(len(ALL_PAIRS), 10, replace=False)]
    out = {"paper": "Artiles et al. 2026, arXiv:2603.01092 (NeurIPS 2026)", "validation": temporal_validation(works, authors),
           "s4": s4, "overlap_S4_S1": len({tuple(p) for p in s4["S4"]} & set(s1)),
           "vendi": {"S1": vendi_pairs(s1), "S2": vendi_pairs(s2), "S4": vendi_pairs([tuple(p) for p in s4["S4"]])}}
    Path("results").mkdir(exist_ok=True)
    Path("results/s4_alien.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("s4", "overlap_S4_S1", "vendi")}, indent=1)[:3000])


if __name__ == "__main__":
    main()
