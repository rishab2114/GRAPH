# Project status

*Updated 2026-11-26. The detailed reasoning is in `docs/RESEARCH_LOG.md`; review items and agent responses are in
`AGENT_DISCUSSION.md`.*

## Where we are

| Stage | State | Main document |
|---|---|---|
| Stage 1: Elliptic (E3/E4) | Pre-registered S1 hypothesis **failed**. The after-shift lead was **weakened by a disclosed reanalysis**: the point estimate survives one common model, but the time-block interval includes 0, and the ranking advantage is not robust | `docs/results/e3e4.md`, `docs/results/e3e4-reanalysis.md` |
| Literature forecaster (AML, 2013→2016) | Structure beats popularity by **+0.212** [+0.203, +0.219] after the vocabulary-leak correction (was +0.241) | `results/literature_graph_v2_reanalysis.json` |
| Stage 2: Tornado Cash | Pilot done. Design frozen, with deviations and **Amendments A1–A2** (common model, instance and week-block intervals, tie policy, baselines, power). Labels **verified** against the logs (44,293/44,293 deposits; 42,334/42,334 withdrawals). Pre-cutoff history being built (569 days done, through 2021-01-06) | `docs/tornado-design.md`, `docs/tornado-pilot.md` |
| Stage 2 run (reads data dated on or after 2022-08-08) | Pre-cutoff build complete; **dry run done** (`results/tornado_dry_run.json`); Amendment A3 (tree and k-NN degenerate at the operating point, excluded from H1); rehearsal of the full path in progress. **The evaluation run awaits owner approval** | `docs/tornado-design.md` |
| S4 "alien scenarios" (exploratory) | Selection degenerate in the motif space (24 of 25 pairs have zero bridging). Literature validation: coherence 3.4×; unavailability is distinct from rarity | `docs/results/s4.md` |
| Codex review G01–G07 | **All implemented with evidence;** awaiting Codex verification (G04 and G07 verified) | `AGENT_DISCUSSION.md` |
| General direction (E01, beyond finance) | Scheduling engine extended (multi-resource, lags, multi-mode, budgets; brute-force verified). Codex L07–L10 fixed. Certification gate: 99.4%, **no-go at 30 s by the per-family rule**, two-stage solve adopted post hoc. Literature counts mixed computing communities, so the corpus must be venue- or topic-defined and frozen. Atom evidence sheet awaits **human review** | `docs/e01-scheduling.md`, `docs/e01-atom-evidence.md` |

## Rules in force

- No Ethereum data dated on or after 2022-08-08 is read until the owner approves the frozen design.
- No detector comparison before the single pre-registered run.
- Every change to a frozen design is logged as a dated deviation or amendment. Earlier results are kept and corrected
  by reanalysis, never overwritten.
