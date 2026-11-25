# Elliptic E3/E4: disclosed reanalysis under the Codex review (G01–G03)

**Run 2026-11-25.**
- **Command:** `python -m gffs.e3e4_reanalysis`. Raw output: `results/e3e4_reanalysis.json`.
- **Not a confirmation:** the Elliptic holdout was already seen. This asks whether the exploratory lead in
  `docs/results/e3e4.md` survives the corrections Codex identified. The original result and document are kept
  unchanged.

## Workflows compared

| Workflow | Model scoring the synthetic sets and the holdout | Threshold rule | Purpose |
|---|---|---|---|
| `as_published` | Refit on steps 1–cutoff | score ≥ 95th-percentile quantile | Reproduction check |
| `common_model_m0` | **m0**, the same model that scores S0 (G01) | **score > τ**, with at most 5% of validation licit strictly above (G03) | Corrected primary |
| `refit_strict` | Refit | Strict rule | Separates G03 from G01 |

**Intervals:**
- a **cluster bootstrap over whole synthetic instances**, paired across detectors with one shared holdout draw (G02);
- a **time-block** sensitivity that resamples whole time steps of real positives;
- an equal-instance-weighted sensitivity.

**Baselines:**
- **B_const:** the mean S0 recall;
- **B_shrink:** ½ × S0 + ½ × that mean;
- **B_zero:** predict 0.

## Reproduction check

- Every holdout recall and every synthetic-arm recall matches the published run **exactly**.
- One number differs: the S0 recall of `rf_balanced` (+0.0152).
- **Cause, verified:**
  - Parallel random-forest prediction (`n_jobs=-1`) sums tree outputs in varying order, so two predictions of the same
    model differ by up to 3.3×10⁻¹⁶, and so does the quantile threshold.
  - 14 of the 920 S0 positives score within 10⁻¹² of the threshold, and 14/920 = 0.0152 exactly.
  - This is threshold ties (G03) in practice.
- The published S1 − S0 error difference of −0.0732 reproduces as −0.0747.

**Ties also distorted a published operating point.** Under the published `≥ quantile` rule, `knn` flagged **9.2%** of
validation licit transactions, not 5% (`lr` 5.1%, `rf_balanced` 5.2%). The strict rule gives 4.9%.

## Results

ΔE4 = E4(SYN) − E4(S0); negative means the synthetic tests predicted holdout recall better. SYN is the mean of the S1,
S2 and S3 recalls.

| Run, window | Workflow | ΔE4 (SYN − S0) | 95% CI, instance bootstrap | 95% CI, time blocks | ρ SYN / ρ S0 | E4 SYN / B_zero |
|---|---|---|---|---|---|---|
| cutoff 34, steps 43–49 (after) | as published | −0.077 | [−0.089, −0.058] | [−0.145, −0.006] | 0.92 / 0.77 | 0.045 / 0.104 |
| cutoff 34, steps 43–49 (after) | **common model** | **−0.061** | [−0.076, −0.030] | **[−0.122, +0.014]** | **0.43 / 0.52** | 0.032 / 0.090 |
| cutoff 39, steps 43–49 (after) | as published | −0.064 | [−0.076, −0.044] | [−0.083, +0.013] | 0.52 / 0.31 | **0.026 / 0.030** |
| cutoff 39, steps 43–49 (after) | **common model** | **−0.057** | [−0.079, −0.030] | **[−0.098, +0.059]** | 0.90 / −0.15 | 0.044 / 0.094 |
| cutoff 34, steps 35–42 (before) | common model | +0.083 | [+0.063, +0.095] | [+0.006, +0.105] | 0.62 / 0.78 | 0.107 / 0.153 |
| cutoff 24, steps 25–34 | common model | +0.098 | [+0.075, +0.115] | [+0.005, +0.140] | −0.43 / 0.62 | 0.136 / 0.178 |
| cutoff 29, steps 30–39 | common model | +0.084 | [+0.063, +0.104] | [+0.014, +0.116] | 0.03 / 0.87 | 0.143 / 0.199 |

**SYN against the baselines**, cutoff 34, after the shift:
- **Common model:** SYN − B_const = −0.077 [−0.089, −0.043]. Equal-instance E4: SYN 0.059 against S0 0.092.
- **As published:** SYN − B_const = −0.091 [−0.099, −0.074].

**S1 − S2** (forecast against random pairs) is still about 0 everywhere. Where its interval excludes 0, S1 is
*worse* (cutoff 24, and cutoff 39 after the shift, under the common model).

## What changes in the conclusions

1. **After the shift, calibration (E4).** The point estimate survives one common model (G01) and instance resampling
   (G02). **When the 7 post-shift time steps are resampled as blocks, the interval includes 0** under the common
   model, at both cutoffs. The lead is a **suggestive point estimate, not an established effect.**
2. **After the shift, ranking (E3).** **Not robust.** Under the common model, synthetic ranks worse than recent data at
   cutoff 34 and better at cutoff 39.
3. **"Generic low predicted recall"** does not explain most windows: SYN beats B_zero, B_const and B_shrink. The
   exception is cutoff 39 as published, where predicting zero is about as good.
4. **Without a shift, recent data is better.** **Robust:** intervals exclude 0 even with time blocks.
5. **The pre-registered S1 hypothesis still fails** (S1 ≈ S2).

**Consequences for Stage 2:**
- The Tornado test is more necessary, because the Elliptic lead is weaker than reported.
- Its power matters more: time dependence widens intervals.
- Amendment A1's power simulation must include block-level dependence.
- Scores are rounded before any threshold comparison (A1 clarification), so threshold ties cannot depend on
  floating-point jitter.
