# Handoff: where the project stands (2026-11-18)

Read this first if you are a new Claude Code session, local or cloud. Then read `docs/spec.md`,
`docs/review-notes.md`, `docs/phase0-decision.md` and `docs/design-option1.md`.

## Done

| Work | Where | Result |
|---|---|---|
| ATT&CK technique graph, forecaster, baselines, E1 | `src/gffs/{attack,fetch,graph,features,baselines,forecaster,evaluate,e1}.py` | The forecaster loses to popularity on v8→v12→v16 |
| Multi-split study (3 splits × 3 edge sets × 8 methods) | `src/gffs/study.py`, `docs/results/study.md` | Popularity wins. Structure adds a small signal only within popularity bands |
| Pre-registration (resolves with the first ATT&CK release on or after 2027-10-01) | `PREREGISTRATION.md` | Do not edit |
| Phase 0: Elliptic check | `src/gffs/{elliptic,phase0}.py`, `docs/phase0-decision.md` | Facts verified; dark-market collapse reproduced; recent-window stress test: recall ρ ≈ 0, +24 pt error across the shift |
| AML vocabulary v1, frozen before counting | `config/aml_vocabulary.toml`, `src/gffs/aml_vocab.py` | 14 concepts (8 expressible as Elliptic motifs), 91 pairs (28 expressible). Scope anchor terms filter out other senses |
| Impact4Cast control (sparse concept graph) | `src/gffs/concept_control.py`, `docs/results/control.md` | Prediction committed; **check whether the result section is filled in** |

## Decisions made by the owner

- Domain: **Option 1**, the Elliptic holdout plus an AML typology graph.
- Graph source: **research literature**, meaning how often a fixed set of AML and crypto-crime concepts
  co-occur in pre-2017 paper titles and abstracts via OpenAlex. See `docs/design-option1.md`.

## Next steps (updated 2026-11-19 03:15 UTC)

Read `docs/RESEARCH_LOG.md` (the full decision record) before acting.

1. **Literature graph v2:** `python -m gffs.literature_v2 --out results/` (frozen design: `config/aml_vocabulary_v2.toml`).
   - **Progress:** 135 of 528 corpus pages cached in `data/openalex/v2/` (git-ignored, 79 MB). The OpenAlex key's
     daily *search* allowance is about 155 pages, so about 3 nights remain.
   - **Scheduled:** a stored reminder resumes it at 00:10 UTC each night until done (by 2026-11-25).
   - **If the container was replaced,** the cache is gone and the run restarts from page 0. That costs one extra
     night; nothing else is lost.
   - **The key** is a network secret on the cloud environment, injected by the proxy for api.openalex.org. Nothing to set.
2. **Core experiment, once `results/literature_graph_v2.json` exists:**
   `python -m gffs.e3e4 --data data/elliptic --literature results/literature_graph_v2.json --out results/`.
   It runs the main result (cutoff 34) plus the robustness cutoffs 24, 29 and 39, as frozen in `docs/e3e4-design.md`.
   Run it **once**, then log and report.
3. **Write-up:** `docs/paper/draft.md`. Fill §4.5 and the abstract from the core result.
4. **Dashboard:** https://claude.ai/artifact/QFnriSAbKFtGtcaYWdmFaV. Add the core result when it exists
   (source CSVs are in `reports/dashboard/`).

## Set-up on a Mac

```bash
git clone https://github.com/rishab2114/graph.git
```

```bash
cd graph && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" pyarrow && .venv/bin/pytest -q
```

The data is not in git. Re-create it with these commands. They download into `data/`, which is ignored.

```bash
mkdir -p data/elliptic && cd data/elliptic && for f in features classes edgelist; do curl -fLO https://data.pyg.org/datasets/elliptic/elliptic_txs_$f.csv.zip && unzip -o elliptic_txs_$f.csv.zip; done
```

ATT&CK releases download automatically on first use. The Impact4Cast graph (1.25 GB) is only needed to
rerun the control:

```bash
mkdir -p data/zenodo/impact4cast && curl -fL -o data/zenodo/impact4cast/data_concept_graph.zip "https://zenodo.org/api/records/10692137/files/data_concept_graph.zip/content"
```
