# Stage 2 design: does the after-shift lead replicate on the Tornado Cash sanctions?

**Frozen 2026-11-24, before any Ethereum data dated on or after 2022-08-08 is read, and before any detector is fitted
on Ethereum data.**
- **Basis:** the pilot (`docs/tornado-pilot.md`) and the owner's acceptance of redesign R1–R7 (2026-11-24).
- **Changes after this commit** go in a dated **Deviations** section at the end, with the reason.
- **Approval gate:** the study's code reads post-cutoff data only behind an explicit approval switch, and the owner
  approves this frozen design before that switch is used.

## 1. What is being tested

The Elliptic core result (`docs/results/e3e4.md`) left one lead. It was **not** the pre-registered hypothesis, and it
rests on one shift event and 169 positives:

> Across a real shift (the dark-market shutdown), synthetic motif stress tests (S1, S2 and S3 alike) predicted detectors'
> post-shift catch rates **better than recent real data (S0)**. Without a shift, recent data was better.

Stage 2 tests this **prospectively on a second dataset with a different, dated shift**: the OFAC designation of Tornado
Cash on **2022-08-08** (C). After it, the population of new mixer users changes.

**The target is mixer participation, not criminality** (pilot P2; review 2026-11-22). Claims are limited to that.

| | Hypothesis | Test | Role |
|---|---|---|---|
| **H1 (primary, the lead)** | Across the shift at C, the pooled synthetic stress test predicts each detector's post-shift recall with a **smaller error than S0** | E4 error of SYN minus E4 error of S0 at C; **success if the 95% bootstrap interval lies entirely below 0** | The only confirmatory test |
| H2 | SYN also *ranks* detectors better than S0 across the shift | Δρ (SYN − S0) at C, 95% interval above 0 | Secondary |
| H3 | Each of S1, S2, S3 separately beats S0 (E4 and ρ) at C | Intervals reported | Secondary, exploratory |
| H4 | The literature forecast adds something: S1 beats S2 | Δ at C | Secondary. Expected null, since it failed on Elliptic |
| **P (shift specificity)** | At placebo cutoffs (no shift), SYN does **not** beat S0 | The H1 statistic at P1 and P2 | Interpretation check (§8) |

**SYN** = for each detector, the mean of its S1, S2 and S3 recalls. This makes one pre-specified number out of the
three synthetic sets, which behaved alike on Elliptic.

## 2. Cutoffs and tasks

**Evaluation cutoffs:**
- **C = 2022-08-08**, the shift.
- Placebos **P1 = 2022-04-08** and **P2 = 2022-06-08** (R7: their 8-week horizons, ending 06-03 and 08-03, do not
  overlap).

**A task at date t** has:
- a frame and features from before t;
- labels from the horizon [t, t + 8 weeks).

Each evaluated cutoff c uses five tasks, mirroring Elliptic's 1–28 / 29–34 / holdout split:

| Task | Date | Use |
|---|---|---|
| Training | c − 16w, c − 24w, c − 32w (horizons do not overlap) | Fit detectors |
| Calibration (S0) | c − 8w (horizon [c − 8w, c)) | Set thresholds; S0 recall |
| Evaluation | c | Holdout recall |

| c | Training tasks | Calibration task | Evaluation horizon |
|---|---|---|---|
| 2022-08-08 | 2021-12-27, 2022-02-21, 2022-04-18 | 2022-06-13 | [08-08, 10-03); see §7 for the extension |
| 2022-06-08 | 2021-10-27, 2021-12-22, 2022-02-16 | 2022-04-13 | [06-08, 08-03) |
| 2022-04-08 | 2021-08-27, 2021-10-22, 2021-12-17 | 2022-02-11 | [04-08, 06-03) |

Every input used for c's thresholds, training or stress tests is dated before c. At C, every one is dated before
2022-08-08.

## 3. Population, labels, removal (R1–R4), all as of each task date t

- **Frame F(t)** (R2, label-independent, fixed before labels are attached) is the union of:
  - every address that sent a successful transaction in **M(t)**, the last full calendar month ending at least 8 days
    before t;
  - every address that sent one in the feature week [t − 7d, t − 1d].

  *Why a rolling month rather than "January":* training tasks and P1 begin before or around January 2022, and a fixed
  January frame would use information from after their own dates. For the pilot's window, M(t) was January. At
  C, M = July 2022.
- **Prior participation before t** (R4, history from the pools' deployment on 2019-12-16) means any of:
  - a successful transaction to any of the 38 Tornado addresses on OFAC's 2022-08-08 list;
  - an ETH-pool deposit;
  - receiving an ETH-pool withdrawal payment.
- **Infrastructure I(t)** (R3) is the union of:
  - the 38 listed addresses that were created before t;
  - relayers (the Withdrawal `relayer` field, or fee payees) seen before t;
  - senders of relayed withdrawals seen before t.
- **Eligible E(t)** = F(t) minus prior participants minus I(t).
- **Positive at t** (R1) = an eligible address whose **first ETH-pool deposit** (the depositor being the deposit
  transaction's sender) falls in [t, t + 8w). Recipients are reported descriptively only.

**Label sources:**
- **Deposit events (logs)** from 2022-02-08 on. Pre-cutoff extraction is done; post-cutoff extraction happens only
  after approval.
- **Before 2022-02-08: transactions table.** A successful transaction to a pool, the proxy or the router whose value
  equals a pool denomination counts as a deposit by its sender.
  - *Check:* this rule is first compared with the logs on 2022-02-08..08-07.
  - *Fallback:* if it misses more than 1% of logged deposits, Deposit logs are read for the pre-2022 horizons instead.
- **Prior recipients:** ETH-pool payment traces (`call_type = call`, from a pool, in a successful transaction).

## 4. Graph and features (R5)

**Graph.** Each task's graph is the successful top-level transactions in [t − 7d, t − 1d], in three typed layers that
are never merged:
- **S** = `simple_transfer`;
- **V** = `value_call`;
- **K** = `call` (value 0).

Every edge touching I(t) is removed before features are computed.

**Features.** The function below is identical for real and synthetic accounts (an account translation of the Elliptic
graph-only features). With W = S ∪ V, the value layers:
- distinct counterparties in and out for each layer: in_S, out_S, in_V, out_V, in_K, out_K; plus in_W and out_W;
- `peel_run_W`: peel accounts have in_W = 1 and out_W ≤ 2; the value is the longest path through the account inside
  the peel subgraph, capped at 10;
- `depth_W`: the longest chain of W-predecessors, capped at 3, since account graphs have cycles;
- `max_neighbour_min_io_W`;
- `reconverges_W`: two distinct W-successors reach a common account within 2 hops. For accounts with more than 50
  successors, the 50 with the lowest address hash are used;
- mean and max of W-predecessors' in_W and out_W, and of W-successors' in_W and out_W;
- the share of all counterparties classified, as of t, as **contract**, and the share classified **unknown** (pilot P3
  rule; `gas_used` is never used).

**Eligible addresses with no edge in the week** get the all-zero feature vector. Their score is computed once.

## 5. Detectors, thresholds, scores (mirrors the Elliptic E3/E4 procedure)

- **Detectors:** the same **10** graph-only detectors as Elliptic E3/E4 (`gffs.e3e4.GRAPH_DETECTORS`), unchanged.
- **Training data:** all positives of the three training tasks, plus **50,000 unlabelled eligible addresses** sampled
  uniformly across those tasks (seed 0). This is positive–unlabelled learning: unlabelled counts as 0.
- **m0:** each detector is fitted on the training tasks.
- **Threshold:** the score at the **99th percentile** over a uniform sample of **200,000 eligible addresses** of the
  calibration task (seed 0), so that the **alert rate is 1%**. There are no licit labels, so a false-positive rate is
  never claimed (review 2026-11-22).
- **S0 recall:** m0's recall on the calibration task's positives, at that threshold.
- **Final model:** refit on training plus calibration tasks, keeping the threshold fixed. This is exactly the Elliptic
  procedure.
- **Holdout recall:** the final model's recall on the evaluation task's positives, at the fixed threshold.
- **E5′:** the realised alert rate on a 200,000-address sample of E(c), reported, with no criterion.

## 6. Stress tests: the same scenario sets as Elliptic, written as accounts

| Name | Content |
|---|---|
| **S0** recent data | The calibration task's real positives, scored by m0 |
| **S1** forecast | The **same 10 motif pairs** as Elliptic S1 (v2 literature graph at 2016; `results/literature_graph_v2.json`). The forecast date is before C, so nothing leaks |
| **S2** uniform pairs | The **same 10 pairs** as Elliptic S2 (uniform over the 28 expressible pairs, seed 0) |
| **S3** single motifs | The 8 motifs on their own |

**Writing a scenario as accounts:**
- **Shapes and generator:** identical to Elliptic (`gffs.scenarios.motif_subgraph`, motif A's output feeds motif B's
  input). Every synthetic node becomes a new account, and every synthetic edge becomes an **S** (EOA-to-EOA payment)
  edge.
- **Sizes:** k and L come from the training tasks' **active positives** (`size_sampler_from`, chain-once weighting as
  in the Elliptic deviation of 2026-11-18), with W-layer in- and out-degree and `peel_run_W`.
- **Context:** each instance gets one S edge from a different real active eligible address of the evaluation task's
  week. The addresses are sampled without replacement, so instances never share a neighbour.
- **Scale:** 200 instances per scenario, seed 0. Every synthetic account is a positive. Stress-test recall is the share
  of synthetic accounts flagged by the final model at the fixed threshold.

## 7. Power rule (R6), fixed now

At C, before any score is computed, **count only** |positives in E(C)| over [C, C + 8w):
- if it is **≥ 100**, use 8 weeks;
- otherwise, extend the horizon **once**, to [C, C + 26w);
- if it is still **< 100**, **stop**. The report says "underpowered"; no detector score on post-cutoff data is
  computed or looked at.

The count and the decision are logged before scoring. The placebo and calibration tasks also need ≥ 100 positives; the
pilot suggests about 900.

## 8. Metrics, success, interpretation

**Metrics:**
- **E3:** Spearman ρ across the 10 detectors between stress-test recall and holdout recall.
- **E4:** mean absolute recall error across detectors, with its signed version.
- **Intervals:** 1,000 bootstrap resamples (seed 0) of holdout positives, S0 positives and synthetic instances.

**H1 success:** the 95% interval of E4(SYN) − E4(S0) at C lies entirely below 0. One test; no other result can
substitute for it.

| H1 at C | SYN beats S0 at a placebo (same criterion) | Conclusion written in the report |
|---|---|---|
| Met | Neither placebo | **The lead replicates on a second dataset and is shift-specific.** Still one shift each in two datasets |
| Met | P1 or P2 | Synthetic stress tests beat recent data here, but **not specifically under a shift**. The Elliptic interpretation is not supported |
| Not met | Any | **The lead does not replicate.** Negative result, reported as such |
| Underpowered (§7) | — | No conclusion; reported as underpowered |

**Also reported (descriptive, not criteria):**
- H2–H4;
- per-detector recalls, including the linear-versus-tree pattern seen on Elliptic;
- active-only positives;
- alert rates of 0.5% and 2%;
- per-motif recalls;
- recipients, descriptively.

## 9. Known weaknesses, stated in advance

- **Synthetic accounts have only S edges, with no contract (K) activity.** Real positives do call contracts. Detectors
  that lean on K features may flag synthetic accounts rarely, everywhere. That would make SYN recall near 0 and E4
  favour whichever set has recalls near 0. This is a real property of these scenarios, as on Elliptic, and will be
  shown per detector.
- **Positive–unlabelled labels:** unlabelled addresses include future and ERC-20-pool participants. Recall is
  unaffected; the scores' meaning as probabilities is not claimed.
- **One shift at C.** The placebos test specificity, not generality.
- **Top-level transactions only:** internal and ERC-20 transfers are absent (pilot limitation 3).
- **The 2026-11-22 dry run** showed a coverage contrast at the old placebo dates (05-08, 06-08): positives ≈ 50% active
  against ≈ 10% for others. It is disclosed in the log and is not evidence here.
- **Multiplicity:** only H1 is confirmatory. Everything else carries unadjusted intervals and is labelled exploratory.

## 10. Order of work

1. **Pre-cutoff, before approval:**
   - Tornado history from 2019-12-16 (transactions and traces);
   - monthly sender frames M(t) (7 distinct months);
   - the 15 feature weeks;
   - the transactions-versus-logs label check (§3);
   - code, test-first;
   - a dry run on **training and calibration tasks only** (no evaluation-task scores), as on Elliptic.
2. **The owner approves.**
3. **Run once:** post-cutoff Deposit logs for the horizon, the §7 count, then everything in §8, including the placebos.

## Deviations

- **2026-11-24: deposit labels before 2022-02-08 come from pool-inflow traces, not the transactions-table rule.**
  - *What happened.* A one-day smoke test (2022-02-21, inside the window where logs exist, before the full data pass)
    found two errors in my first implementation:
    - it applied the value rule to all 38 OFAC addresses, so it labelled 29 payments to another listed Tornado contract
      as deposits;
    - it assigned withdrawal roles by "the larger payment is the recipient", which fails when a relayer fee exceeds half
      of the 0.1 ETH denomination (4 cases that day).
  - *Why the trace rule.* Even when restricted to pool, proxy and router as §3 says, the transactions rule would miss
    deposits made through other entry contracts.
  - *New rules.*
    - **Deposit:** a successful-transaction `call` paying an ETH pool exactly its denomination; the depositor is the
      transaction's sender.
    - **Withdrawal roles:** by call order (the pool pays the recipient first, then the relayer).
  - *Check.* Both rules match the logs exactly on that day: 144/144 deposits and 160/160 withdrawals, with 0 extra.
    The §3 check (≤ 1% of logged deposits missed, on 2022-02-08..08-07) now applies to the trace rule, and extras are
    reported too.
  - *Data read.* No evaluation data was read.
- **2026-11-24: one extra stress set is scored in the same run, outside every Stage 2 criterion.**
  - *What.* The owner asked for an S4 "alien scenarios" prototype, pre-registered separately in
    `docs/s4-alien-prereg.md` before any post-cutoff read.
  - *How.* It is scored with the same frozen detectors, thresholds and injection procedure, and reported in a separate
    section.
  - *Unchanged.* It is **not** part of SYN. H1, H2–H4, the placebo rule and the power rule are unchanged.


## Amendment A1 (2026-11-25): Codex review G01–G05

Adopted **before any evaluation data exists**: no Stage 2 detector has been fitted, and no post-cutoff data has been
read. The original sections stay as written; where they conflict, this amendment governs. Each item is discussed in
`AGENT_DISCUSSION.md`.

1. **One model for every arm (G01).**
   - **Primary:** each detector is fitted **once**, on the training tasks (m0). Its threshold τ is set once, on the
     calibration task's unlabelled sample. That same model and τ score S0 (the calibration positives, which m0 never
     saw), S1–S3, SYN, S4, the baselines and the holdout.
   - Each arm records its model's hash and τ.
   - The §5 refit procedure is kept as a named **secondary "refit workflow"** comparison.
2. **Resampling unit (G02).**
   - Every synthetic instance keeps its scenario, instance ID, attachment address, seed and node IDs.
   - Intervals come from a **cluster bootstrap over whole instances** (within each scenario), plus holdout and S0
     positives, with 1,000 draws (seed 0).
   - The same draw is used for every detector (paired) and every arm (one shared holdout draw).
   - **Estimand:** node-weighted recall, as frozen. Equal-instance-weighted recall is reported as a labelled
     sensitivity, and so is a bootstrap of real positives in blocks by deposit day.
3. **Threshold ties (G03).**
   - τ = the smallest score such that **at most 1%** of the calibration sample scores strictly above it; an address is
     flagged iff its score > τ.
   - The realised calibration alert rate is reported per detector. With ties it can be well below 1%.
   - If every score is equal, the detector flags nothing and is reported as degenerate.
   - The language stays "alert rate", never a false-positive rate.
4. **Shift specificity and power (G05).**
   - **H1 wording if met:** "replicated at this event; no detected advantage at these placebos".
   - **Shift-specific contrast**, pre-specified: Δ = E4(SYN) − E4(S0) at each cutoff, and
     **D = Δ_C − (Δ_P1 + Δ_P2)/2**, with independent bootstraps per cutoff. "Shift-specific" may be claimed only if D's
     95% interval lies below 0. Caveats stated with it: one event, overlapping training histories, and P2's horizon ends
     5 days before C.
   - **Power:** "≥ 100 positives" is a **feasibility floor**, not a power calculation. A power simulation (binomial
     noise around plausible per-detector recalls, n ∈ {50, 100, 200, 500}, 200 instances per scenario, instance-level
     clustering) is run and committed **before any score is computed**.
   - The 26-week branch is reported as a **different estimand**.
5. **Cheap baselines (the review's "Investigate" point)**, pre-registered secondary arms for E4. Each predicts every
   detector's holdout recall from pre-cutoff information only:
   - **B_const:** the mean S0 recall across detectors;
   - **B_shrink:** ½ × the detector's own S0 recall + ½ × that mean;
   - **B_zero:** 0, a descriptive floor only.

   If SYN does not beat B_shrink, the report says the lead **cannot be distinguished from generic shrinkage or low
   predicted recall**.
6. **Label name (G04).** A positive is the *first observed qualifying ETH-pool deposit by the top-level transaction
   sender, under the recorded history and inclusion rules*. It says nothing about intent or identity.
   - Trace labels count a call only when neither it nor any ancestor in the transaction has an error.
   - Batched withdrawals are split by pool call frame; frames that do not fit are quarantined.
   - Full-window reconciliation against the logs (2022-02-08..08-07), with misses and extras counted, precedes any use.

**A1 clarification (2026-11-25, still before any evaluation).** The Elliptic reanalysis verified that parallel
random-forest prediction changes scores by about 10⁻¹⁶ between calls. With scores tied at the threshold, that flipped
14 of 920 S0 positives (`docs/results/e3e4-reanalysis.md`). In Stage 2:
- every score is **rounded to 10 decimal places** before τ is computed and before any comparison with τ;
- detectors predict with `n_jobs=1`.

The power simulation in A1 item 4 **includes block dependence**: real positives resampled by deposit week, synthetic
positives by instance.


## Amendment A2 (2026-11-25): the H1 interval follows the power simulation

Made **before any Stage 2 score exists**, on the basis of the pre-registered power simulation (`gffs.tornado_power`,
`results/tornado_power.json`).
- **Simulation setup:** 10 detectors; Elliptic common-model recalls as the template; 8 weekly blocks with week effect
  τ on the logit scale; instance-clustered synthetic positives; 200 simulations × 200 bootstraps.

| Scenario | n holdout | τ = 0 | τ = 0.5 | τ = 1.0 |
|---|---|---|---|---|
| **Null** (SYN = S0): false-positive rate, i.i.d. interval | 50–500 | 0.00 | 0.02–0.035 | **0.19–0.32** |
| **Null**: false-positive rate, week-block interval | 50–500 | 0.00 | 0.00–0.01 | 0.005–0.04 |
| **Elliptic-size effect** (Δ ≈ −0.06): power, block interval | 50 / 100–500 | 0.98 / 1.00 | 0.93 / 1.00 | 0.77 / 0.88–0.93 |
| **Half effect** (Δ ≈ −0.03): power, block interval | 100–500 | — | 0.67–0.82 | **0.59–0.61** |

1. **H1's primary interval** resamples real positives (holdout and S0) **by deposit week**, and synthetic positives by
   whole instance. The i.i.d. interval from A1 is reported as secondary. Reason: under strong week dependence the
   i.i.d. interval rejects a true null in 19–32% of simulations.
2. **What a null result can say:** with 8 weekly blocks, power for an effect half the size of Elliptic's is about
   60–80%. Power is limited by the **number of weeks**, not the number of positives. A non-significant H1 therefore
   **does not rule out** effects of that size, and the report must say so.
3. **Open question** (for the owner and Codex, not adopted): more blocks would raise power more than more positives
   would. That suggests a pre-specified longer horizon as a secondary estimand. It would add post-cutoff reading and a
   comparison, so it is left undecided here.

- **2026-11-26, before any evaluation: listed accounts with no contract record.** The study's contract registry finds
  creation records for 37 of the 38 addresses on OFAC's 2022-08-08 list. The remaining one (`0x8589…fda16`) has no
  creation event, so it is an externally owned account. I believe it is the project's donation wallet, but that is
  not verified here.
  - *Why it matters.* Under §3 ("listed addresses created before t") an account with no creation date would never be
    excluded.
  - *Rule.* It is treated as infrastructure **at every task date**. Removing its edges can only remove interactions
    with a listed Tornado address.

