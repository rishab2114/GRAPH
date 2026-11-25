# Project status

*Updated 2026-11-25. The detailed reasoning is in `docs/RESEARCH_LOG.md`; review items and agent responses are in
`AGENT_DISCUSSION.md`.*

## Where we are

| Stage | State | Main document |
|---|---|---|
| Stage 1: Elliptic (E3/E4) | Pre-registered S1 hypothesis **failed**. The after-shift lead was **weakened by a disclosed reanalysis**: the point estimate survives one common model, but the time-block interval includes 0, and the ranking advantage is not robust | `docs/results/e3e4.md`, `docs/results/e3e4-reanalysis.md` |
| Literature forecaster (AML, 2013→2016) | Structure beats popularity by **+0.212** [+0.203, +0.219] after the vocabulary-leak correction (was +0.241) | `results/literature_graph_v2_reanalysis.json` |
| Stage 2: Tornado Cash | Pilot done. Design frozen, with deviations and **Amendments A1–A2** (common model, instance and week-block intervals, tie policy, baselines, power). Labels **verified** against the logs (44,293/44,293 deposits; 42,334/42,334 withdrawals). Pre-cutoff history being built (569 days done, through 2021-01-06) | `docs/tornado-design.md`, `docs/tornado-pilot.md` |
| Stage 2 run (reads post-2022-08-08 data) | **Waiting for owner approval** | — |
| S4 "alien scenarios" (exploratory) | Selection degenerate in the motif space (24 of 25 pairs have zero bridging). Literature validation: coherence 3.4×; unavailability is distinct from rarity | `docs/results/s4.md` |
| Codex review G01–G07 | **All implemented with evidence;** awaiting Codex verification (G04 and G07 verified) | `AGENT_DISCUSSION.md` |
| General direction (E01, beyond finance) | Proposed: constrained **project scheduling** (RCPSP family) with an exact solver, verified sources and a solver contract. **The owner decides when to start** | `AGENT_DISCUSSION.md` (L01–L06 response) |

## Rules in force

- No Ethereum data dated on or after 2022-08-08 is read until the owner approves the frozen design.
- No detector comparison before the single pre-registered run.
- Every change to a frozen design is logged as a dated deviation or amendment. Earlier results are kept and corrected
  by reanalysis, never overwritten.
