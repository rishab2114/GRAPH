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

## Next steps

1. ~~Write the vocabulary~~ **Done** (v1). Do not edit it: any change goes in a new versioned file,
   with a note saying why. Risk: with only 14 nodes, the 2016 graph may already be nearly complete,
   leaving few unseen pairs to forecast. If so, report that as a result; don't add concepts to fix it.
2. **Build the literature graph:** query the OpenAlex API (`api.openalex.org/works`, filtered by
   `to_publication_date`) for works mentioning each concept. Nodes are concepts. An edge means the two
   concepts appear in the same work, dated by publication year. Freeze the graph at end of 2016.
   OpenAlex needs a free API key once the shared allowance is used up. Add it as
   `?api_key=` or `Authorization: Bearer`. Never commit it.
3. **Forecast unseen concept pairs** with the existing models and the popularity baseline.
4. **Write scenarios as transaction-subgraph motifs** on `elliptic_txs_edgelist.csv`. Do not use the anonymised features.
5. **Run E3/E4 against the Phase 0 baseline:** detectors use graph features computed the same way for real and synthetic transactions.

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
