# Mechanism check design: why do synthetic motif stress tests predict post-shift detector performance?

**Frozen 2026-11-21, before any generator code exists.** This is stage 1 of 3 chosen by the owner (then the Tornado Cash
sanctions dataset, then later crypto events). Changes after this commit go in a dated "Deviations" section.

## What is being explained

On Elliptic (`docs/results/e3e4.md`), every synthetic motif stress test predicted detectors' recall **after** the
dark-market shutdown better than recent data did (mean error 0.047 vs 0.120). It did worse than recent data before the
shutdown. This was seen once, on one shift.

## Two explanations to tell apart

- **H-gen (generalisation):** unfamiliar transaction shapes expose detectors that over-fit the training-period shapes.
  A shift exposes the same weakness, so any unfamiliar scenario set predicts post-shift performance, **even if it shares
  no shapes with the new attacks**.
- **H-match (matching):** the scenarios predict post-shift performance only because some of them **resemble** the new attacks.

## Synthetic world

A generator modelled on Elliptic's structure (time steps of transaction graphs, mostly unlabelled, 2% illicit):

- **Steps:** 40. Each step is a background of licit flows: random trees and chains, with degrees drawn to match
  Elliptic's training-period licit distribution (`results/motifs_elliptic.json` and `gffs.motifs` features).
- **Illicit activity:** injected motif instances, with sizes drawn as in `gffs.scenarios`, plus random noise edges.
- **Motif families:** the 8 drawable motifs are split once, with a fixed seed of 0, into three disjoint families: **A**
  (3 motifs), **B** (3 motifs) and **C** (the remaining 2), plus 2-motif pairs within each family.
- **Periods:**
  - Steps 1–24 (training): illicit uses family **A** only.
  - Steps 25–40 (holdout): one of three worlds.

| World | Illicit in steps 25–40 | Purpose |
|---|---|---|
| W0 no shift | family A | control: recent data should win |
| W1 shift | family B | the shift |
| W2 shift + mimicry | family B, plus licit-looking camouflage edges | a harder shift |

## Stress tests (same harness as E3/E4: `gffs.e3e4.agreement` / `compare_stress_tests`)

| Name | Content | Shares shapes with the post-shift attacks? |
|---|---|---|
| S0 recent data | real illicit transactions in steps 19–24 | no (family A) |
| **SC unfamiliar** | instances of family **C** only | **no**, so this tests H-gen |
| SB matching | instances of family **B** | **yes**, the upper bound for H-match |
| SA familiar | instances of family A | no; same shapes as training |

- **Detectors:** the 10 graph-only detectors of `gffs.e3e4`. Thresholds and training exactly as in E3/E4 (cutoff 24,
  validation steps 19–24).
- **Replication:** **20 independently generated worlds** per world type (seeds 0–19), so results come with a spread
  instead of a single event.

## Predictions, fixed now

- **In W0 (no shift),** S0 should beat SC in ranking (ρ) and in error, as on Elliptic.
- **If H-gen holds,** in W1, **SC beats S0** on recall error and ranking, in a majority of worlds (≥ 14 of 20).
- **If only H-match holds,** in W1, SB beats S0 but **SC does not** (SC wins in ≤ 10 of 20).
- **SA**, the familiar shapes, should not beat S0 in W1. Otherwise the effect comes from *any* synthetic set, which
  would point to an artefact of injection rather than to generalisation.

## Metrics

Per world: Spearman ρ (stress-test recall vs holdout recall across detectors), and the mean absolute recall error.
Across the 20 worlds: the number of worlds where each stress test beats S0, and the median difference with a 95%
interval over worlds.

## Limits, stated in advance

- **The world is synthetic and built from the same motif generators** as the stress tests. It can show a *mechanism*,
  not that the mechanism is what happened on Elliptic or will happen elsewhere.
- **The family split is one fixed random split.** If the result depends heavily on which motifs land in C, that is a
  weakness. A second split (seed 1) is run as a robustness check and reported regardless.
