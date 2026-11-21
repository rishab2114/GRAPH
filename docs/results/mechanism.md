# Mechanism check: why did synthetic motif stress tests predict post-shift performance?

Design frozen beforehand: `docs/mechanism-design.md`. Run once: `python -m gffs.mechanism` (120 synthetic worlds:
20 seeds × {W0 no shift, W1 shift, W2 shift + camouflage} × 2 family splits). Raw output: `results/mechanism.json`.

**Family splits** (training attacks = A, post-shift attacks = B, never used by attackers = C):

| Split | A | B | C |
|---|---|---|---|
| 0 | fan_out, layering, mixing | coinjoin, pass_through, peel_chain | fan_in, smurfing |
| 1 | coinjoin, fan_in, pass_through | fan_out, mixing, peel_chain | layering, smurfing |

## Results

Worlds (of 20) where each stress test beats recent data (S0). The median difference is in brackets: error (lower is
better), and ρ (higher is better).

| World | SA familiar | SB matching | SC unfamiliar |
|---|---|---|---|
| W0 no shift, split 0 | err 16, ρ 11 (Δerr −0.013) | err 0, ρ 0 | err 0, ρ 0 |
| W0 no shift, split 1 | err 19, ρ 19 (Δerr −0.018) | err 0, ρ 0 | err 0, ρ 0 |
| W1 shift, split 0 | err 15, ρ 11 (≈ tie) | **err 20, ρ 20** (Δerr −0.30, Δρ +1.20) | err 8, ρ 2 (Δρ −0.39) |
| W1 shift, split 1 | err 9, ρ 11 (≈ tie) | **err 20, ρ 20** (Δerr −0.39, Δρ +0.98) | err 20, ρ 6 (Δerr −0.24, Δρ −0.20) |
| W2 shift + camouflage, split 0 | err 14, ρ 8 | err 20, ρ 10 (Δρ −0.09) | **err 20, ρ 18** (Δerr −0.27, Δρ +0.66) |
| W2 shift + camouflage, split 1 | err 9, ρ 12 | err 20, ρ 5 (Δρ −0.24) | **err 20, ρ 20** (Δerr −0.30, Δρ +0.70) |

## Against the frozen predictions

1. **No shift → recent data wins: confirmed.** Neither SB nor SC beats recent data in any of the 40 worlds.
2. **H-match: confirmed, strongly.** After a plain shift, scenarios that share shapes with the new attacks beat recent
   data in all 40 worlds, on both error and ranking.
3. **H-gen: not supported for a plain shift.** Unfamiliar scenarios rank detectors worse than recent data
   (wins 2/20 and 6/20). In one split they help calibration (error, 20/20), but not in the other (8/20).
4. **Familiar scenarios ≈ recent data: confirmed.** SA ties S0, so the effect is not an artefact of injection.

**Not predicted, and the strongest pattern:** when the shifted attacks also **camouflage** themselves (licit-looking
outflows), unfamiliar scenarios (SC) beat recent data on both error and ranking in 38–40 of 40 worlds. They also rank
detectors better than the *matching* scenarios do. A plausible reading: camouflage makes success depend on robustness to
unfamiliar structure, which is what unfamiliar scenarios measure. Matching shapes alone don't capture that.

## What it means for the Elliptic lead

- **The Elliptic effect has two candidate sources, and they predict different things.** If the post-shutdown illicit
  activity used shapes that the stress tests happened to contain, that is H-match, and it works only when the scenarios
  cover the future attacks. If it mixed new shapes with camouflage-like behaviour, unfamiliar scenarios help regardless.
- **This check cannot say which happened on Elliptic** (its illicit typologies are unlabelled). It does say that
  *"any synthetic scenarios beat recent data after a shift"* is **too strong**: in a plain shift with no camouflage,
  unfamiliar scenarios did not.
- **For practice:** the stress test should *cover* plausible future shapes (H-match), which is what a good forecast is
  for. Unfamiliar shapes are additionally useful when adversaries are expected to camouflage.

## Limits

- **The worlds are synthetic,** built from the same motif generators as the stress tests, with a simple licit background.
  This shows mechanisms that *can* produce the Elliptic pattern, not which one did.
- **Camouflage (W2) is one particular form,** licit-looking outflows. Other evasion styles may behave differently.
- **Two family splits.** Results agree across them on every confirmed prediction. The plain-shift calibration result for
  SC differs between splits (8/20 vs 20/20), so it depends on which motifs are unfamiliar.
