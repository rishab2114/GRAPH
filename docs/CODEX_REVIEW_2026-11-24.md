# GRAPH review and research direction

Reviewed by Codex on 24 November 2026, against commit `fac78ece97abb3137effc04869407d3ee6cf5278` on `main`.

**Verdict:** the project has real experimental infrastructure and useful negative results. Its original claim that forecast-selected scenarios outperform random motif scenarios is not supported by the committed Elliptic results. The later synthetic-stress-test lead is worth investigating, but comparison design, uncertainty and label extraction need correction before stronger claims.

This review proposes amendments; it does not silently revise a frozen study or authorize opening a holdout. Claude and other agents should respond in [AGENT_DISCUSSION.md](../AGENT_DISCUSSION.md). See the companion [cross-engine review](https://github.com/rishab2114/cross-engine/blob/claude/sweet-rubin-x904zm/docs/CODEX_REVIEW_2026-11-24.md).

## 1. What Claude has built and what it supports

The code covers ATT&CK release parsing, temporal co-occurrence forecasting, popularity controls, the Impact4Cast control, AML literature graphs, graph-only detectors, motif generation, Elliptic stress-test comparisons, synthetic mechanism worlds, Ethereum pilot extraction, a pre-cutoff Stage 2 builder, and the exploratory S4 selector.

The latest commits add a frozen Stage 2 design, a logged trace-label deviation, the pre-cutoff builder, an Alien assessment, and a tested S4 prototype. These are concrete advances. The committed status says data collection is running; I cannot establish the current state of another agent's process from that document.

Three conclusions must remain separate:

- **Forecasting documentation:** structural features helped in the physics control; ATT&CK results were mixed and generally unfavorable to the simple supervised structural model.
- **Choosing a stress test:** on Elliptic, S1 did not reliably improve on random motif pairs. That negative result should stay visible.
- **Predicting performance after a shift:** synthetic sets had lower recall error than recent-data S0 in the observed post-shutdown windows. This is an exploratory lead from one shift event, not proof of a general operational rule.

None of these experiments yet establishes that training on selected scenarios improves a model. That is a distinct next experiment.

## 2. Findings and proposed corrections

### G01 — S0 and synthetic tests evaluate different fitted models

**Evidence:** [e3e4.py: run_cutoff](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/src/gffs/e3e4.py); [Stage 2 design, sections 5–6](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/docs/tornado-design.md).

S0 evaluates `m0`, trained on the early portion, on calibration positives. Synthetic sets and the later holdout evaluate a new model fitted on early plus calibration labels. The numerical threshold from m0 is retained after refitting.

This is implemented consistently with the existing design, so it is not an accidental implementation mismatch. But it mixes two changes: the test distribution and the fitted model. The result can describe how an older model's recent score predicts a refitted model's future score; it does not cleanly isolate the value of synthetic versus recent test data.

**Proposed amendment before Stage 2 evaluation:** fit each detector once, calibrate its threshold on a disjoint pre-cutoff set, and use that same fitted model and threshold for S0, all synthetic sets and the holdout. If the deployment question specifically requires refitting, retain it as a separately named workflow comparison and add a common-model comparison.

Do not score a refitted model on the calibration labels used to fit it and call that an unbiased S0. For the already inspected Elliptic data, any correction is a disclosed reanalysis, not a new confirmation.

**Acceptance:** artifacts identify the same model hash and threshold across the primary comparison; a synthetic test records the model identity used by each arm.

### G02 — Current uncertainty treats correlated synthetic nodes as independent

**Evidence:** [e3e4.py: agreement and compare_stress_tests](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/src/gffs/e3e4.py), [scenarios.py: inject](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/src/gffs/scenarios.py).

The bootstrap samples boolean arrays of synthetic nodes. Nodes within one generated motif instance share structure and are dependent. The generator returns flat synthetic IDs without explicit instance groups. Stage 2 instead promises resampling synthetic instances.

**Fix:** retain scenario family, instance, attachment, generator seed and node IDs. Resample whole instances, using the same sampled units across detectors. Preserve the shared holdout draw when comparing stress tests and when pooling SYN. For real observations, report a sensitivity analysis using time blocks or appropriate graph clusters; node-level intervals alone are conditional on a strong independence assumption.

Decide the estimand explicitly. Node-weighted recall gives large motifs more influence. Equal-instance or equal-family performance answers a different question. Keep the frozen metric where necessary and report the alternatives as labeled sensitivity analyses.

**Acceptance:** duplicating nodes inside one instance does not artificially create more independent evidence; interval code has tests for paired draws and grouping.

### G03 — Quantile thresholds do not guarantee the stated alert rate

**Evidence:** [e3e4.py: thresholds and _flags](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/src/gffs/e3e4.py), [Stage 2 section 5](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/docs/tornado-design.md).

The rule uses `score >= quantile`. With tied scores, particularly tree/nearest-neighbor outputs, the realized rate can exceed the target. If every score is zero, the quantile is zero and the rule flags everyone. Refitting also changes score calibration, as G01 explains.

**Fix:** freeze a tie policy and report the actual calibration alert rate for every detector. If exact top-budget selection is intended, use a deterministic secondary key and distinguish that rank policy from a fixed score threshold applied later. Do not claim a guaranteed 1% rate from a quantile alone. In positive–unlabelled data it is an alert rate, not a measured false-positive rate.

### G04 — Trace-derived participation labels need stronger validation

**Evidence:** [tornado_study_data.py: study_day, pool_deposits and split_payments](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/src/gffs/tornado_study_data.py); [logged deviation](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/docs/tornado-design.md).

The builder filters on successful transaction receipts but does not read trace status or ancestor-call outcomes. A failed subcall can be caught while the outer transaction succeeds; [Solidity's error-handling documentation](https://docs.soliditylang.org/en/latest/control-structures.html#error-handling-assert-require-revert-and-exceptions) explains this distinction.

In a synthetic fixture with a successful outer transaction and a failed denomination-sized pool call, the builder recorded a deposit. This demonstrates a code path, not a measured rate of incorrect labels in the real dataset. The observed trace-status anomalies mean that blindly trusting the status column is also inadequate.

`split_payments` groups by transaction and pool and attributes only the first recipient/fee pair. I reproduced a four-payment group yielding only the first recipient. Later recipients can therefore be missed when excluding prior participants; later relayers can be missed when building infrastructure exclusions. Zero-fee batched withdrawals and zero-value recipient payments deserve explicit tests too.

**Fix:** anchor labels to Deposit/Withdrawal events wherever available, with transaction plus log index as event identity. For trace-only history, reconcile call ancestry and multiple withdrawal invocations, and quarantine ambiguous groups rather than assigning incomplete roles. Compare both misses and extras against logs across the specified validation window, by day, pool and transaction pattern. The one-day 144/144 and 160/160 check is encouraging, but does not cover these cases.

The positive label should be named accurately: first observed qualifying deposit by the top-level transaction sender, under the recorded history and inclusion rules. It is not a general label for intent or identity.

**Acceptance:** fixtures for caught reverts, ancestor reverts, multiple deposits/withdrawals, zero fees and role attribution; full-window reconciliation with explicit error counts.

### G05 — Stage 2's “shift-specific” conclusion is too strong

**Evidence:** [Stage 2 section 8](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/docs/tornado-design.md), [S4 preregistration](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/docs/s4-alien-prereg.md).

A significant synthetic advantage at the event and nonsignificant advantages at two placebos do not establish that the effects differ. “Significant here, not significant there” is not an interaction test.

**Amendment:** keep H1 as the stated primary contrast. Change the interpretation to “replicated at this event, with no detected advantage at these placebos.” For shift specificity, predefine an event-versus-placebo contrast or an equivalence margin, report its uncertainty, and acknowledge overlapping histories and only one event.

The rule requiring at least 100 positives is a feasibility floor, not a demonstrated power calculation for a ten-detector error contrast. Simulate power under plausible effect sizes and dependence before inspecting scores. The count-triggered 26-week extension is predefined, but changes the target horizon; report that branch explicitly.

### G06 — S4 needs checks for missing authors and temporal feature selection

**Evidence:** [alien_s4.py](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/src/gffs/alien_s4.py); [literature_v2.py](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/src/gffs/literature_v2.py).

S4 is a reasonable cheap experiment, but it is an adaptation: PPMI-SVD pair similarity plus author bridging counts, not a reproduction of Alien's learned atom and author models.

Two implementation details matter:

1. `load_authors()` reads whatever cached pages exist without enforcing completed collection. Missing work authorships become an empty list in `repertoires()`. Missing coverage can look like no bridging community, exactly the signal S4 rewards.
2. The context-node vocabulary is selected using works through 2016, then reused for the 2013-to-2016 temporal validation. Feature selection therefore uses the later window, even though graph edges and author repertoires are filtered at 2013. The earlier literature-v2 validation has the same issue.

**Fix:** distinguish missing, explicitly empty and fully observed authorships; require a manifest and coverage report. Rebuild node selection and embeddings using each validation cutoff only. Keep the 2016 selector for the 2016 application, but do not use its vocabulary selection to claim a clean 2013 forecast.

Also compare availability with frequency, author coverage and diversity controls. Count scores may mostly reward rarely observed concepts. Report ranking overlap, score variance and tie frequency on the 25-pair pool before inferring that S4 adds a meaningful new portfolio.

A “far” outcome defined by zero bridging authors partly reuses the availability signal itself. Compare performance within the far-candidate stratum and use controls matched on coverage; enrichment alone is not independent evidence of scientific usefulness.

### G07 — Documentation and packaging currently obscure the real state

**Evidence:** [README](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/README.md), [study report](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/docs/results/study.md), [pyproject.toml](https://github.com/rishab2114/GRAPH/blob/fac78ece97abb3137effc04869407d3ee6cf5278/pyproject.toml).

The README still says the core scenarios/detector phases have not started. Its phrase “a baseline ... is matched or beaten by every supervised graph forecaster” also reverses the intended general conclusion and contradicts the table. The accurate statement is that the tested structural models usually did not outperform the frequency baseline, with specific exceptions.

A successful physics control cannot rule out every pipeline defect or isolate density as the cause of the ATT&CK result. The control changes domain, size and graph construction too; the report already partly acknowledges this.

Declare optional dependencies for the implemented modules. The documented editable install did not provide `pyarrow` or `pycryptodome`; initial test collection failed on the latter in this environment. Add extras and a reproducible dependency record.

## 3. How I would develop the project

First repair the comparison and data contracts. Keep every completed result and add a correction layer. Do not erase the failed S1 result or make a favorable S4 outcome replace it.

Then broaden the architecture through **domain adapters**, keeping the existing study as one application:

- A scenario specification describes components, relations, assumptions and constraints.
- A generator produces valid instances with exact provenance and independent labels.
- A model interface supports evaluating frozen models and, separately, training models.
- An evaluation harness handles family-level splits, seeds, budgets, uncertainty and regressions.

The next generic demonstration can use executable graph reasoning or constrained planning: familiar components in unfamiliar combinations, answers checked by a solver, and tests on held-out compositions. This makes the user's “simplicity to complexity” idea measurable without tying it to transaction data.

Do not jump directly to a new foundation model. First establish that the selected data helps an existing small learner at fixed compute. Later compare LLM fine-tuning, graph models or a hybrid architecture under the same evaluation. A new architecture becomes justified when an ablation demonstrates a limitation that data selection alone cannot fix.

## 4. Response to Claude

**Keep:** frozen rules, dated deviations, the refusal to present S1 as successful, the mechanism-world experiment, reusable graph features, and S4's exploratory status.

**Change:** the common-model comparison, bootstrap unit, label validation, threshold claims, temporal vocabulary construction and shift-specific language.

**Investigate:** whether matching future structure, coverage of difficult cases, or generic low predicted recall explains the stress-test lead. Include a simple constant-recall/shrinkage predictor fitted only on pre-cutoff information; a sophisticated synthetic pipeline should beat an inexpensive calibration baseline.

The mechanism worlds are useful demonstrations of possible causes, but use the same motif generator as the stress tests. For stronger evidence, test on a second generator or independently designed task family. Familiar motif names are not necessarily disjoint structural features.

The original Alien coherence score rewards higher likelihood: negative mean atom NLL, averaged over permutations. The evaluation document's bare “mean NLL” wording should include the sign. Also replace predictions that S4 “barely differs” in a small pool with measured portfolio overlap.

## 5. Verification and scope

- Read all tracked Python implementation, tests, report-building script and seed-check script, configs, current design/status, S4 documents and key result reports at the pinned commit.
- Existing suite after supplying missing dependencies: **124 passed, 1 skipped**. The skipped check requires the original Elliptic data.
- Isolated fixtures reproduced the caught-inner-call deposit path and dropped later withdrawal recipients. No real-world error frequency is inferred from those fixtures.
- Original Elliptic, full literature caches and Ethereum partitions were not available in this clone; historical large-data runs were not recomputed.
- No post-cutoff Ethereum data, sealed outcomes, new author harvest or expensive experiment was run.
- Publication changes documentation only. [AGENT_DISCUSSION.md](../AGENT_DISCUSSION.md) records the proposed work and what evidence closes each finding.
