# Graph-Forecast Fraud Scenarios

Forecast attack-technique combinations that have not been documented yet, using a time-sliced
technique co-occurrence graph. Turn the forecasts into a stress test for detectors, then check
whether the stress test predicts how detectors perform on a later period nobody has touched.

## Status (2026-11-18)

| Part of the plan | State |
|---|---|
| Phase 0: holdout dataset and domain decision | **Open.** Needs dataset downloads and the owner's choice |
| Phase 1: technique graph, forecaster, baselines, E1 | **Done.** See below |
| Phases 2–4: scenarios, detectors, E2–E5 (the core research question) | Not started. Blocked on Phase 0 |
| Prospective confirmation | Pre-registered in [`PREREGISTRATION.md`](PREREGISTRATION.md). Resolves with the first ATT&CK release on or after 2027-10 |

**Main result so far** ([`docs/results/study.md`](docs/results/study.md)): on MITRE ATT&CK, the
setting is 3 rolling 2-year splits × 3 edge definitions. A baseline that uses only technique
popularity is matched or beaten by every supervised graph forecaster. Shared-neighbour structure
adds a small signal only *within* popularity bands.

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
config/                 release tags and study design
docs/spec.md            project plan (source spec)
docs/review-notes.md    problems found in the spec
docs/results/           E1 and multi-split study write-ups
```

## Reproduce

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
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
