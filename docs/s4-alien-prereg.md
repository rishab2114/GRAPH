# S4 "alien scenarios": exploratory pre-registration

**Written 2026-11-24, before any S4 score is computed and before any Ethereum data on or after 2022-08-08 is read.**
- **Origin:** the owner asked to inspect the code of Artiles et al. (2026, arXiv:2603.01092, NeurIPS 2026) and build an
  S4 prototype, kept separate from the frozen Stage 2 (`docs/tornado-design.md`).
- **Status: exploratory, non-confirmatory.** It does not change Stage 2's H1, the definition of SYN (S1–S3), or any
  Stage 2 criterion.
- **Changes after this commit** go in the Deviations section below.

## Question

The Elliptic stress test built from the literature *forecast* (S1) did no better than random pairs (S2). The paper
suggests one reason: a forecast picks combinations the community is **likely to produce next** (the "available"
region). S4 instead picks combinations that are **coherent but unavailable**: plausible given the literature, yet held
by no existing author community. Does such a set predict detectors' post-shift behaviour any differently from S1 and S2?

## Construction (rules fixed now)

| Item | Rule |
|---|---|
| Literature | The v2 AML literature graph (`gffs.literature_v2`), works published **up to 2016**: the same cutoff and works as S1 |
| Candidate pool | The **25** unlinked expressible motif pairs ranked for S1 (`results/literature_graph_v2.json`, `scenarios`) |
| Coherence | Cosine similarity of the two concepts in a PPMI-SVD embedding (64 dimensions) of paper-level co-occurrence among all graph nodes, works ≤ 2016. This stands in for the paper's transformer over idea atoms; it scores pairs that never co-occurred |
| Availability | The number of authors whose works ≤ 2016 already carry **both** concepts, in any of their papers, log1p-scaled. Unavailability is its negative. This stands in for the paper's author–idea dual encoder (the median of the top-10 authors) |
| Ranking | F_β = (1 − β)·z(coherence) + β·z(unavailability), z-scored within the 25-pair pool, with **β = 0.7** (the paper's default). Ties are broken by S1's rank |
| S4 | The **top 10** pairs, the same size as S1 and S2 |
| Not used | LLM atomisation, LLM decoding into prose, the paper's trained models (they are fitted on LLM-research atoms, a different domain) |

**Descriptive validation on pre-2017 data**, the analogue of the paper's §5.2:
- **Scores:** from works ≤ 2013.
- **Candidates:** all unlinked node pairs at 2013.
- **Targets:** pairs first linked in 2014–2016.
- **"Far" targets:** targets with no bridging author at 2013.
- **Measures:** recovery at K = 1% of candidates, relative to chance, for β = 0, 0.1, …, 1; and the share of far targets
  among recovered pairs.
- **Paper's pattern, for comparison:** coherence alone recovers far above chance, and raising β shifts recovery toward
  far targets. Whatever we find is reported.

## Test

S4 is evaluated **only on the Stage 2 Tornado data**, inside the single Stage 2 run. It uses the frozen detectors,
thresholds and injection procedure, with 200 instances per pair (seed 0) and accounts as nodes.

| Exploratory comparison | Where |
|---|---|
| E4(S4) − E4(S1), E4(S4) − E4(S2), E4(S4) − E4(S0), with 95% bootstrap intervals | At C (2022-08-08) and at P1 and P2 |
| Δρ for the same pairs | Same |

**Reading:**
- Only if S4 beats **both** S1 and S2 at C (intervals excluding 0) and **not** at the placebos would S4 merit a
  confirmatory test on a third dataset or shift.
- Anything else is reported as it is.
- None of this can confirm or refute Stage 2's H1.

**Elliptic:** its holdout has already been seen, so any Elliptic S4 run would be post hoc and descriptive, never
evidence.

## Safety

S4 selects among the same 8 abstract graph motifs as S1, S2 and S3. It creates no new laundering typologies and
produces no prose. This follows the paper's own caution about low-availability search in dual-use fields.

## Deviations

(none yet)
