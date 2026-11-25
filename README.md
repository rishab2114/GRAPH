# Graph-Forecast Fraud Scenarios

Forecast attack-technique combinations that have not been documented yet, using a time-sliced
technique co-occurrence graph. Turn the forecasts into a stress test for detectors, then check
whether the stress test predicts how detectors perform on a later period nobody has touched.

## Status

The current state is in [`STATUS.md`](STATUS.md). The full reasoning is in [`docs/RESEARCH_LOG.md`](docs/RESEARCH_LOG.md).
Open review items and agent responses are in [`AGENT_DISCUSSION.md`](AGENT_DISCUSSION.md).

**Results so far, as they stand:**
- **ATT&CK** ([`docs/results/study.md`](docs/results/study.md)): every supervised graph forecaster is matched or
  beaten by a baseline that uses only technique popularity. Shared-neighbour structure adds a small signal only
  *within* popularity bands.
- **Physics control** ([`docs/results/control.md`](docs/results/control.md)): structure helps on a sparse concept graph.
  This does not by itself isolate density as the cause of the ATT&CK result; domain, size and construction differ.
- **Elliptic** ([`docs/results/e3e4.md`](docs/results/e3e4.md)): the pre-registered hypothesis (forecast-selected
  scenarios beat random ones) is **not supported**. An exploratory lead (synthetic stress tests predicted post-shift
  recall better than recent data) has open confounds; see `AGENT_DISCUSSION.md`, G01–G02.
- **Tornado Cash** (Stage 2): pilot done; design frozen with dated deviations; pre-cutoff data being built; no
  post-cutoff data read.

## Layout

```
src/gffs/attack.py      ATT&CK STIX release -> entity -> technique sets (sub-techniques collapsed)
src/gffs/fetch.py       download and cache versioned releases from mitre/cti
src/gffs/graph.py       co-occurrence graph, candidate pairs, newly-documented-pair labels
src/gffs/features.py    shared-neighbour pair features
src/gffs/baselines.py   frequency-matched and random baselines
src/gffs/models.py      pre-registered model variants (plus one labelled exploratory)
src/gffs/stats.py       popularity-stratified AUC, paired bootstrap CIs
src/gffs/e1.py          single-split E1 runner
src/gffs/study.py       multi-split study runner
src/gffs/elliptic.py, phase0.py, motifs.py, scenarios.py, e3e4.py, mechanism.py, synthworld.py
                        Elliptic detectors, motif library, scenario injection, E3/E4/E5 and mechanism worlds
src/gffs/literature*.py, aml_vocab.py, concept_control.py
                        OpenAlex literature graphs (v1, v2) and the Impact4Cast physics control
src/gffs/ethereum.py, tornado_*.py
                        Tornado Cash pilot (P1-P8), feasibility, Stage 2 pre-cutoff data builder
src/gffs/alien_s4.py    exploratory S4 selector adapted from Artiles et al. (2026)
config/                 release tags and study design
docs/spec.md            project plan (source spec)
docs/review-notes.md    problems found in the spec
docs/results/           E1 and multi-split study write-ups
```

## Reproduce

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev,ethereum]"
```

```bash
.venv/bin/pytest -q
```

```bash
.venv/bin/python -m gffs.study --config config/study.toml --out results/
```

The study takes about 5 minutes on a laptop. ATT&CK releases are downloaded once into `data/attack/`.

Dual-use note: this repo stores technique IDs, scores and metrics only. It contains no exploit
code and no step-by-step attack procedures.
