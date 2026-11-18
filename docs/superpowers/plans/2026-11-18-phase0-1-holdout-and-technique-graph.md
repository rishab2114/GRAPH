# Phase 0–1: Holdout Decision and Technique-Graph Forecaster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Settle the holdout dataset and domain (Phase 0). Then build the time-sliced technique graph, the shared-neighbour forecaster, the two baselines, and the E1 forecasting experiment (Phase 1).

**Architecture:** This is a small Python package, `gffs`. A loader turns one versioned ATT&CK STIX release into a mapping from each entity to the set of techniques it uses. A builder then turns that mapping into a weighted technique co-occurrence graph. The forecaster is trained with the time-travel set-up from the spec. It learns from the graph at release T−k and the edges that release T added, then scores the graph at T against the edges that release T+k added. All code depends only on the "entity to technique set" mapping. A FATF or other typology loader can therefore replace the ATT&CK loader if Phase 0 picks the fraud route.

**Tech Stack:** Python 3.11+, networkx, pandas, numpy, scikit-learn, pytest, requests.

**Spec:** [`docs/spec.md`](../../spec.md). Read it together with [`docs/review-notes.md`](../../review-notes.md).

**Scope:** This plan covers Phases 0 and 1 only. Phases 2–4 (scenario generator, detectors, core experiment) depend on the holdout chosen in Task 0. Each of them gets its own plan once that decision is recorded.

## Global Constraints

- One domain only. One graph method in the core build. No disk embedding or multi-node growth (spec: "Later extensions").
- Leakage rule: every stage uses only information that existed at cutoff T. **Use the data source's release at T, not today's version filtered by date.**
- Outcomes are worded as "newly documented together", never "happened".
- E1 metrics: **AUC** and **precision at top 100**, reported against a **frequency-matched** baseline and a **uniform random** baseline.
- Sub-techniques collapse to their parent ID (`T1059.001 → T1059`) at load time (review note 4). Training cutoffs are ATT&CK v8 or later.
- Revoked objects and objects with `x_mitre_deprecated: true` are ignored. This applies to techniques, entities and relationships.
- Dual-use guardrail: the repo stores technique IDs, scores and metrics only. It holds no exploit code and no step-by-step procedures.
- Everything runs on a laptop. Expect about 200–700 parent techniques, so ≤ about 250k candidate pairs, all scored in memory.

## Review Focus

1. **Revoked or deprecated STIX objects.** Real releases contain them. A technique or relationship marked revoked or deprecated must not create nodes or edges. *Pinned in Task 1 (`test_ignores_revoked_and_deprecated`).*
2. **A technique that appears only after T.** It cannot be a candidate at T. If it were counted as a positive, E1 would score pairs the forecaster could never have seen. *Pinned in Task 3 (`test_new_edges_excludes_nodes_absent_at_t`).*
3. **The same entity using a technique through several sub-techniques.** This must count once. Otherwise frequencies and edge weights are inflated. *Pinned in Task 1 (`test_subtechniques_collapse_to_parent_once`).*
4. **A test window with zero new edges.** This can happen if two releases are too close together. AUC is then undefined, so the program must stop with a clear error and not report NaN. *Pinned in Task 5 (`test_evaluate_rejects_no_positives`).*
5. **Pair order.** `(a, b)` and `(b, a)` must be the same candidate in features, labels and baselines. Otherwise labels misalign with scores without any visible error. *Pinned in Task 3 (`test_candidate_pairs_are_canonical`).*

---

### Task 0: Phase 0 holdout decision and prior-work note

No code. This task gates the rest of the project (spec §4, Phase 0). Record facts that you have checked against the dataset files or papers, not from memory.

**Files:**
- Create: `docs/phase0-decision.md`

- [ ] **Step 1: Check Elliptic.** Download from Kaggle (`ellipticco/elliptic-data-set`). Record the number of rows and time steps, the label counts (illicit/licit/unknown), whether the features are anonymised, and whether detectors are reported to fail after the dark-market shutdown (around time step 43 in published work).
- [ ] **Step 2: Check IEEE-CIS.** Download from Kaggle (`ieee-fraud-detection`). Record the units of `TransactionDT`, the label rate, and how many columns are masked (`V*`, `C*`, `D*`, `M*`) and how many are readable.
- [ ] **Step 3: Check one cyber holdout candidate** (LANL unified host and network, or DARPA OpTC). Record whether it has timestamps, labels, benign cases, and whether its events map to ATT&CK techniques.
- [ ] **Step 4: Expressibility test.** For each dataset, take 3 hand-picked technique pairs and write down which real columns could express each one. Record the share that is expressible.
- [ ] **Step 5: Prior-work search** (one page): SynthAML (did its generator use test-period alerts?), studies of stress-test-to-future transfer, hyperbolic embeddings for forecasting combinations.
- [ ] **Step 6: Record the decision** in `docs/phase0-decision.md` under these headings: *Chosen domain*, *Graph source* (it must match the domain, see review note 1), *Holdout dataset*, *Cutoff T*, *Expressible share*, *Fallback: simulation benchmark? (yes/no)*, *Open questions*. Also record the remaining spec §8 decisions: LLM, output target, weekly hours.
- [ ] **Step 7: Commit**

```bash
git add docs/phase0-decision.md
git commit -m "docs: record Phase 0 holdout and domain decision"
```

> If Task 0 picks the **fraud route**, Tasks 1–2 still go ahead, but only as a tested reference loader. Add a typology loader with the same output type (`dict[str, frozenset[str]]`) before Task 6, and run E1 on it.

---

### Task 1: Scaffold and ATT&CK bundle parser

**Files:**
- Create: `pyproject.toml`, `src/gffs/__init__.py`, `src/gffs/attack.py`
- Test: `tests/conftest.py`, `tests/test_attack.py`

**Interfaces:**
- Produces:
  - `parent_id(external_id: str) -> str`
  - `technique_sets(bundle: dict) -> dict[str, frozenset[str]]`: maps the STIX id of each `intrusion-set`, `malware`, `tool` or `campaign` to the set of parent technique IDs it `uses`. Entities with an empty set are left out.
  - `load_bundle(path: Path) -> dict`
  - Test helper `make_bundle(uses: dict[str, list[str]], *, revoked: set[str] = frozenset(), deprecated_rels: set[tuple[str, str]] = frozenset()) -> dict` in `conftest.py`. It builds a minimal STIX bundle in which each key is an intrusion-set name and each value is a list of technique external IDs. Technique IDs listed in `revoked` get `"revoked": true`. `(entity, technique)` pairs listed in `deprecated_rels` get relationships with `"x_mitre_deprecated": true`.

- [ ] **Step 1: Write `pyproject.toml`.** Use a `src/` layout, package `gffs`, and Python `>=3.11`. Dependencies: `networkx`, `pandas`, `numpy`, `scikit-learn`, `requests`. Dev dependency: `pytest`. Set `[tool.pytest.ini_options] testpaths = ["tests"]`.

- [ ] **Step 2: Write the failing tests**

```python
def test_parent_id():
    assert parent_id("T1059.001") == "T1059"
    assert parent_id("T1059") == "T1059"

def test_technique_sets_basic(make_bundle):
    b = make_bundle({"APT-A": ["T1059", "T1078"], "APT-B": ["T1078"]})
    sets = technique_sets(b)
    assert sorted(sets.values(), key=len) == [frozenset({"T1078"}), frozenset({"T1059", "T1078"})]

def test_subtechniques_collapse_to_parent_once(make_bundle):
    b = make_bundle({"APT-A": ["T1059.001", "T1059.003", "T1078"]})
    assert list(technique_sets(b).values()) == [frozenset({"T1059", "T1078"})]

def test_ignores_revoked_and_deprecated(make_bundle):
    b = make_bundle({"APT-A": ["T1059", "T1078", "T1003"]},
                    revoked={"T1003"}, deprecated_rels={("APT-A", "T1078")})
    assert list(technique_sets(b).values()) == [frozenset({"T1059"})]
```

- [ ] **Step 3: Run the tests and check they fail.** Run `pytest tests/test_attack.py -v`. Expected: FAIL with `ImportError`.

- [ ] **Step 4: Implement `src/gffs/attack.py`.** Index `attack-pattern` objects by STIX id and read their `external_references` entry where `source_name == "mitre-attack"`. Keep `relationship` objects with `relationship_type == "uses"` whose target is an attack-pattern. Drop any object or relationship where `revoked` or `x_mitre_deprecated` is true.

- [ ] **Step 5: Run the tests and check they pass.** Run `pytest -v`. Expected: 4 passed.

- [ ] **Step 6: Commit** with `git add pyproject.toml src tests` and then `git commit -m "feat: parse ATT&CK bundle into entity technique sets"`.

---

### Task 2: Versioned release fetcher

**Files:**
- Create: `src/gffs/fetch.py`, `config/releases.toml`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Produces:
  - `release_url(tag: str) -> str`, which returns `https://raw.githubusercontent.com/mitre/cti/<url-quoted tag>/enterprise-attack/enterprise-attack.json`
  - `fetch_release(tag: str, cache_dir: Path = Path("data/attack")) -> Path`, which downloads the release once and reuses the cached file after that
  - `config/releases.toml`, with keys `train_from`, `train_to` (= T), `test_to` and their tag strings

- [ ] **Step 1: Write the failing test**

```python
def test_release_url_quotes_ampersand():
    assert release_url("ATT&CK-v12.1") == (
        "https://raw.githubusercontent.com/mitre/cti/ATT%26CK-v12.1/enterprise-attack/enterprise-attack.json")

def test_fetch_uses_cache(tmp_path, monkeypatch):
    (tmp_path / "ATT&CK-v12.1.json").write_text("{}")
    monkeypatch.setattr("gffs.fetch.requests.get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    assert fetch_release("ATT&CK-v12.1", tmp_path) == tmp_path / "ATT&CK-v12.1.json"
```

- [ ] **Step 2: Run the tests and check they fail.** Run `pytest tests/test_fetch.py -v`. Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement `release_url` and `fetch_release`.** Use `urllib.parse.quote(tag, safe="")`. Call `requests.get(..., timeout=60)` and then `raise_for_status()`.
- [ ] **Step 4: Run the tests and check they pass.** Run `pytest -v`. Expected: all pass.
- [ ] **Step 5: Check the real tags and pick cutoffs.** Run `git ls-remote --tags https://github.com/mitre/cti | grep -o 'ATT&CK-v[0-9.]*' | sort -uV`. Pick three tags about 2 years apart, all v8 or later. A starting suggestion is `train_from = v8.x`, `train_to = T = v12.x`, `test_to = v16.x`, but confirm the release dates against the tag dates. Write the tags and their dates into `config/releases.toml`, and add `data/` to `.gitignore`.
- [ ] **Step 6: Commit** with `git add src/gffs/fetch.py tests/test_fetch.py config/releases.toml .gitignore` and then `git commit -m "feat: fetch versioned ATT&CK releases"`.

---

### Task 3: Co-occurrence graph, candidates and new-edge labels

**Files:**
- Create: `src/gffs/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: `technique_sets` output (`dict[str, frozenset[str]]`)
- Produces:
  - `build_graph(sets: dict[str, frozenset[str]]) -> nx.Graph`. The nodes are all techniques used by at least one entity, and each node has a `freq` attribute (the number of entities that use it). Edge weight is the number of entities that use both techniques.
  - `Pair = tuple[str, str]`, always ordered with `u < v`
  - `candidate_pairs(g: nx.Graph) -> list[Pair]`: all non-edges among the nodes of `g`, sorted
  - `new_edges(g_t: nx.Graph, g_later: nx.Graph) -> set[Pair]`: edges of `g_later` whose two endpoints are both nodes of `g_t` and that are not edges in `g_t`

- [ ] **Step 1: Write the failing tests**

```python
SETS = {"a": frozenset({"T1", "T2"}), "b": frozenset({"T2", "T3"}), "c": frozenset({"T2", "T3"})}

def test_build_graph_weights_and_freq():
    g = build_graph(SETS)
    assert g["T2"]["T3"]["weight"] == 2 and g.nodes["T2"]["freq"] == 3
    assert not g.has_edge("T1", "T3")

def test_candidate_pairs_are_canonical():
    assert candidate_pairs(build_graph(SETS)) == [("T1", "T3")]

def test_new_edges_excludes_nodes_absent_at_t():
    later = build_graph({**SETS, "d": frozenset({"T1", "T3", "T9"})})
    assert new_edges(build_graph(SETS), later) == {("T1", "T3")}
```

- [ ] **Step 2: Run the tests and check they fail.** Run `pytest tests/test_graph.py -v`. Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement `build_graph`, `candidate_pairs` and `new_edges` in `src/gffs/graph.py`.** Use `itertools.combinations(sorted(s), 2)` for each entity.
- [ ] **Step 4: Run the tests and check they pass.** Run `pytest -v`. Expected: all pass.
- [ ] **Step 5: Commit** with `git add src/gffs/graph.py tests/test_graph.py` and then `git commit -m "feat: technique co-occurrence graph and new-edge labels"`.

---

### Task 4: Pair features and the two baselines

**Files:**
- Create: `src/gffs/features.py`, `src/gffs/baselines.py`
- Test: `tests/test_features.py`

**Interfaces:**
- Consumes: `build_graph`, `Pair`
- Produces:
  - `FEATURES = ["freq_min", "freq_max", "deg_min", "deg_max", "common_neighbours", "jaccard", "adamic_adar", "resource_allocation", "weighted_cn"]`
  - `pair_features(g: nx.Graph, pairs: list[Pair]) -> pd.DataFrame`. Columns are `FEATURES`, rows follow the order of `pairs`, and the index is a MultiIndex `(u, v)`. `weighted_cn` is the sum over common neighbours w of `min(weight(u,w), weight(v,w))`.
  - `frequency_scores(g: nx.Graph, pairs: list[Pair]) -> np.ndarray`, equal to `freq(u) * freq(v)` (the frequency-matched baseline as a ranker, see review note 6)
  - `random_scores(pairs: list[Pair], seed: int = 0) -> np.ndarray`, uniform on [0, 1)

- [ ] **Step 1: Write the failing tests**

```python
def test_shared_neighbour_features():
    g = build_graph({"a": frozenset({"T1", "T2"}), "b": frozenset({"T2", "T3"}), "c": frozenset({"T1", "T4"}), "d": frozenset({"T4", "T3"})})
    f = pair_features(g, [("T1", "T3")]).iloc[0]
    assert f.common_neighbours == 2          # T2 and T4
    assert f.jaccard == pytest.approx(2 / 2)  # N(T1)={T2,T4}, N(T3)={T2,T4}

def test_frequency_baseline_is_product_of_freq():
    g = build_graph({"a": frozenset({"T1", "T2"}), "b": frozenset({"T2"}), "c": frozenset({"T3"})})
    assert frequency_scores(g, [("T1", "T2"), ("T2", "T3")]).tolist() == [2, 2]

def test_random_scores_reproducible():
    p = [("T1", "T2"), ("T1", "T3")]
    assert (random_scores(p, 7) == random_scores(p, 7)).all()
```

> Note: in the third test, entity `c` uses only `T3`. `T3` is still a node, so `build_graph` must add nodes for single-technique entities even though they create no edges.

- [ ] **Step 2: Run the tests and check they fail.** Run `pytest tests/test_features.py -v`. Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement both modules.** Use networkx's `jaccard_coefficient`, `adamic_adar_index` and `resource_allocation_index` on the given pairs.
- [ ] **Step 4: Run the tests and check they pass.** Run `pytest -v`. Expected: all pass.
- [ ] **Step 5: Commit** with `git commit -m "feat: shared-neighbour pair features and baselines"`.

---

### Task 5: Time-travel forecaster and E1 metrics

**Files:**
- Create: `src/gffs/forecaster.py`, `src/gffs/evaluate.py`
- Test: `tests/test_forecaster.py`

**Interfaces:**
- Consumes: `candidate_pairs`, `new_edges`, `pair_features`, `FEATURES`
- Produces:
  - `fit_forecaster(g_before: nx.Graph, g_t: nx.Graph) -> Pipeline`. Its training rows are `candidate_pairs(g_before)` and its labels are `new_edges(g_before, g_t)`. The model is `StandardScaler` → `LogisticRegression(class_weight="balanced", max_iter=1000)`. **Its signature never takes a graph later than T.**
  - `forecast(model: Pipeline, g_t: nx.Graph) -> pd.Series`: scores for `candidate_pairs(g_t)`, indexed by `(u, v)` and sorted in descending order
  - `evaluate(scores: np.ndarray, labels: np.ndarray, k: int = 100) -> dict`, returning the keys `auc`, `precision_at_k`, `k`, `n_candidates`, `n_positive`. It raises `ValueError("no newly documented pairs in test window")` when `labels.sum() == 0`.

- [ ] **Step 1: Write the failing tests**

```python
def test_evaluate_perfect_ranking():
    r = evaluate(np.array([0.9, 0.8, 0.1, 0.0]), np.array([1, 1, 0, 0]), k=2)
    assert r["auc"] == 1.0 and r["precision_at_k"] == 1.0 and r["n_positive"] == 2

def test_evaluate_rejects_no_positives():
    with pytest.raises(ValueError, match="no newly documented pairs"):
        evaluate(np.array([0.5, 0.4]), np.array([0, 0]))

def test_forecaster_prefers_bridged_pair():
    # Training: A–C and B–D (two bridges each) get linked by T; pairs with E (no bridge) do not.
    # Scoring: T1–T3 has two bridges (T2, T4); T1–T5 has none.
    before = build_graph({"a": frozenset({"A", "B"}), "b": frozenset({"B", "C"}), "c": frozenset({"A", "D"}),
                          "d": frozenset({"D", "C"}), "e": frozenset({"E"})})
    t = build_graph({"a2": frozenset({"A", "B", "C", "D"}),
                     "z": frozenset({"E"}), "y": frozenset({"T1","T2"}), "x": frozenset({"T2","T3"}),
                     "w": frozenset({"T1","T4"}), "v": frozenset({"T4","T3"}), "u": frozenset({"T5"})})
    s = forecast(fit_forecaster(before, t), t)
    assert s[("T1", "T3")] > s[("T1", "T5")]
```

> The third test checks the direction of the effect only. It is not a precision claim. If logistic regression's fit on such a tiny graph makes it flaky, enlarge the fixture rather than loosen the assertion.

- [ ] **Step 2: Run the tests and check they fail.** Run `pytest tests/test_forecaster.py -v`. Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement both modules.** Use `sklearn.metrics.roc_auc_score`. Precision at k is the share of positives among the top-k scores.
- [ ] **Step 4: Run the tests and check they pass.** Run `pytest -v`. Expected: all pass.
- [ ] **Step 5: Commit** with `git commit -m "feat: time-travel forecaster and E1 metrics"`.

---

### Task 6: E1 runner and first real result

**Files:**
- Create: `src/gffs/e1.py`, `docs/results/e1.md`
- Test: `tests/test_e1.py`

**Interfaces:**
- Consumes: everything above, plus `config/releases.toml`
- Produces:
  - `run_e1(sets_before, sets_t, sets_after, k: int = 100, seed: int = 0) -> dict[str, dict]`, with keys `"forecaster"`, `"frequency"` and `"random"`, each holding an `evaluate` result
  - CLI `python -m gffs.e1 --config config/releases.toml --out results/`, which writes `results/e1.json` and `results/e1_top100.csv` (columns `u, v, score, newly_documented`)

- [ ] **Step 1: Write the failing test**

```python
def test_run_e1_reports_three_methods_on_same_candidates(make_bundle):
    before = technique_sets(make_bundle({"A": ["T1","T2"], "B": ["T2","T3"], "C": ["T3","T4"]}))
    t      = technique_sets(make_bundle({"A": ["T1","T2","T3"], "B": ["T2","T3"], "C": ["T3","T4"]}))
    after  = technique_sets(make_bundle({"A": ["T1","T2","T3"], "B": ["T2","T3","T4"], "C": ["T3","T4"]}))
    r = run_e1(before, t, after, k=2)
    assert set(r) == {"forecaster", "frequency", "random"}
    assert len({m["n_candidates"] for m in r.values()}) == 1
    assert r["forecaster"]["n_positive"] == 1   # only T2–T4 is new between T and after
```

- [ ] **Step 2: Run the test and check it fails.** Run `pytest tests/test_e1.py -v`. Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement `run_e1` and the `argparse` CLI in `src/gffs/e1.py`.** Score all three methods on `candidate_pairs(build_graph(sets_t))`. Labels come from `new_edges(g_t, g_after)`. The forecaster is fit with `fit_forecaster(g_before, g_t)` only.
- [ ] **Step 4: Run the tests and check they pass.** Run `pytest -v`. Expected: all pass.
- [ ] **Step 5: Run on the real releases.** Run `python -m gffs.e1 --config config/releases.toml --out results/`. Expected: `results/e1.json` exists with three method blocks. `n_positive` should be above 0 (if it is 0, widen the test window in `releases.toml`).
- [ ] **Step 6: Write `docs/results/e1.md`.** Include a table of AUC and P@100 for the three methods, the tags used and their dates, and the numbers of candidates and positives. Add one paragraph that answers spec sub-question 1. If the forecaster beats random but not frequency, say that common techniques may explain the gain (spec §5). Also state that positives are "newly documented together" by MITRE, which is often backfill (review note 5).
- [ ] **Step 7: Commit** with `git add src/gffs/e1.py tests/test_e1.py docs/results/e1.md` and then `git commit -m "feat: E1 forecasting experiment and first results"`. `results/` is data and stays git-ignored, except for `e1.json`, which you add with `git add -f results/e1.json`.

---

## After this plan

When Task 0's decision is recorded, write the next plan, `docs/superpowers/plans/<date>-phase2-4-<domain>.md`. It covers Stage 3 (plausibility filter), Stage 4 (writing scenarios in the holdout's features), detector variants (≥ 8, see review note 3), and E2–E5.
