# Project status

*Updated 2026-11-24. The detailed reasoning is in `docs/RESEARCH_LOG.md`; this page is the short version.*

## Where we are

| Stage | State | Main document |
|---|---|---|
| Stage 1: Elliptic (E3/E4) | Done. The pre-registered S1 hypothesis failed. **Lead:** across a shift, synthetic stress tests predicted detectors better than recent data | `docs/results/e3e4.md` |
| Mechanism check | Done | `docs/results/mechanism.md` |
| Stage 2 pilot: Tornado Cash (pre-sanction only) | Done. Events reliable; depositors sufficient; recipients unreachable. **Decision: Redesign (R1–R7), accepted by the owner** | `docs/tornado-pilot.md` |
| Stage 2 design | **Frozen** 2026-11-24 (commit `5f8757c`), with one dated deviation (label source) | `docs/tornado-design.md` |
| Stage 2 data build (pre-cutoff only) | **Running**: history from 2019-12-16, 7 monthly frames, 15 feature weeks | `src/gffs/tornado_study_data.py` |
| Stage 2 run (reads post-2022-08-08 data) | **Waiting for owner approval** of the frozen design | — |
| Stage 3: recent crypto events (e.g. the 2025-03-21 delisting) | Not started; to confirm with the owner | — |

## Recent decisions

- **"The Alien Space of Science" (NeurIPS 2026): read, not adopted now.** Stage 2 is frozen. Our space has only 28
  motif pairs. There is a dual-use caution. It is proposed as a later, separately pre-registered "S4" experiment.
  See `docs/alien-space-evaluation.md`.

## Rules in force

- No Ethereum data dated on or after 2022-08-08 is read until the owner approves the frozen design.
- No detector is fitted on evaluation data, and no detector comparison is run, before the single pre-registered run.
- Every change to a frozen design is logged under its **Deviations** section with a date and a reason.
