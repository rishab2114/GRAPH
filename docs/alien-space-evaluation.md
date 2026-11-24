# "The Alien Space of Science": read, evaluated, and **not adopted now**

**Paper:** A. H. Artiles, M. Weiss, L. Brinkmann, I. Rahwan, B. Schölkopf, C. Pal, H. Larochelle, A. Goyal,
N. Rahaman. *The Alien Space of Science: Sampling Coherent but Cognitively Unavailable Research Directions.*
arXiv:2603.01092v3 (21 Oct 2026), NeurIPS 2026. Code: github.com/alejandrohdez00/alien-space-of-science.

**Evaluated 2026-11-24**, at the owner's request.
- **Read:** the main text, pages 1–11 (method, validation, results, limitations, ethics).
- **Not read:** the 48 appendix pages. Where an appendix is mentioned below, it is cited from the main text, not
  checked.

## What it does, briefly

1. **Idea atoms.** An LLM distils 16,068 LLM-research papers into short "conceptual units", which are clustered into
   **273 idea atoms**. Each paper becomes a sparse set of atoms (3.38 per paper on average).
2. **Coherence model.** An autoregressive transformer over atom sequences. C(S) asks: do these atoms plausibly occur
   together in one paper?
3. **Availability model.** A two-encoder contrastive model trained on the atom repertoires of 39,791 authors. A(S) is
   the median similarity of the top-m authors, and unavailability is U(S) = −A(S).
4. **Alien sampling.** All 3.35 million atom triples are ranked by F_β = (1 − β)·z_C + β·z_U, with β = 0.7 for the main
   portfolio.

**Key evidence**, with everything built from pre-2025 data:
- Coherence alone (β = 0), keeping 0.875% of candidates, recovers 2025 combinations at **35.9× chance**.
- Adding unavailability (β = 0.4) lowers overall recovery (21.4×) but raises recovery of *strictly novel* combinations
  (3.24× against 2.35×).
- Portfolios are more diverse than those of frontier LLMs (Vendi 225 against 198 for the best LLM baseline), with
  comparable rated quality.

## How it relates to this project

| This project | Alien Space |
|---|---|
| Concept graph from the literature; shared-neighbour link prediction ranks pairs **likely to be linked next** (SciMuse/Impact4Cast style) | Coherence model = "plausible"; availability model = "likely to be produced by the current community" |
| S1 = forecast's top pairs, i.e. what the field will **probably** write about next | That is the **available** region. Alien sampling deliberately moves *away* from it (β > 0) |
| ATT&CK study: on a dense graph, popularity beat structure. The physics control: structure wins on a sparse graph | Their main text reports that hypergraph-distance methods "largely collapse" in a dense field where nearly every pair is within two hops (their Appendix A.9, not checked). **Independent, consistent evidence** about density, though not a test of our claim |
| Elliptic: forecast-chosen pairs (S1) were no better stress tests than random pairs (S2) | One possible reading: forecasting the defenders' *next likely* topics targets the available region, while detector blind spots may lie elsewhere. **This is a hypothesis, not evidence** |

## Their code, inspected 2026-11-24

Repository `alejandrohdez00/alien-space-of-science`, commit `a55d660` (2026-11-02), MIT licence. It was cloned
read-only and never executed.

**What it does:**
- **Coherence** (`generation/scoring.py`): a causal transformer over atom tokens. The score is the mean per-atom
  negative log-likelihood, averaged over orderings of the set.
- **Availability** (`generation/two_tower_model.py`, `generation/scoring.py`):
  - an author tower (mean-pool, then an MLP) and a set tower (a transformer), with shared atom embeddings;
  - availability is the **median of the top-10** author cosine scores, and unavailability is its negative.
- **Training** (`generation/train_availability.py`): a CLIP-style symmetric InfoNCE loss. Pairs from the same author
  are masked out as negatives. Each author's repertoire is split into a query subset of 2–4 atoms and its complement
  (`generation/make_availability.py`).
- **Fusion** (`generation/sample.py`): (1 − β)·z(coherence) + β·z(unavailability), z-scored over the candidate pool,
  with default β = 0.7.

**What we can and cannot reuse:**

| Item | Verdict |
|---|---|
| Scoring formulas and the fusion rule | **Reused** (re-implemented in `gffs.alien_s4`, with attribution) |
| Vendi diversity score | **Reused** (re-implemented, Jaccard similarity on atom sets) |
| Trained models and author bank | **Not usable:** fitted on 273 atoms from LLM-research papers, a different domain |
| Training stack (PyTorch transformers; the availability model was trained on 4 A100 GPUs) | **Not used:** too heavy for a 28-pair space and our small corpus |
| LLM atomisation and decoding (paid API calls) | **Not used:** our concepts already exist, and we want no prose scenarios (dual-use) |

**Competing interest, disclosed in the paper:** two authors co-founded Tiptree Systems, which sells a production
version (Lacuna).

## Decision: **not adopted into the frozen work; an S4 prototype is built separately**

1. **Stage 2 is frozen** (`docs/tornado-design.md`, commit `5f8757c`). It replicates the Elliptic lead with the
   *identical* scenario sets. Adding a new selector now would change what is tested, add comparisons, and require a
   deviation. That would be exactly the kind of moving target the owner asked us to avoid.
2. **Our search space is too small for it to matter.** Graph-expressible motifs are 8, so there are 28 pairs. The
   paper's value comes from searching millions of combinations. Over 28 pairs, a coherence-minus-availability ranking
   barely differs from what S2 already samples (10 of the 28).
3. **Availability needs author histories at scale.** The paper uses about 40,000 authors. Our AML literature for the
   target motifs is thin (0–73 pre-2017 works per motif), so an availability model would be poorly identified.
4. **Dual use.** The paper's own ethics section warns that in dual-use fields, low-availability combinations can be
   exactly the ones a community avoids for safety reasons, and it applies the method only to low-risk literatures.
   Fraud and money laundering are dual-use. Our motif-level scenarios are abstract graph shapes used to *test
   detectors*, which is low risk. But a richer "alien" generator over laundering typologies would need a safety review
   before it is built.

## Where it fits (the owner chose: inspect the code *and* build an S4 prototype)

**Now built as an exploratory prototype** (`gffs.alien_s4`, pre-registered in `docs/s4-alien-prereg.md`). A full,
confirmatory version would still need:
- **a richer vocabulary:** account-level motifs × AML typologies, at least ~30 atoms, so the search space is large
  enough;
- **an availability model** built from OpenAlex author histories in the AML/fraud literature, dated before the cutoff;
- **one confirmatory test:** across a shift, does S4 predict detectors' post-shift recall better than S1 (forecast) and
  S2 (random)? The Elliptic and Tornado pipelines can be reused unchanged;
- **a safety screen** of generated scenarios before any is written out in detail.

**Also useful now, without adopting anything:** their portfolio-diversity measure (the Vendi score) could describe how
different our stress sets S1, S2 and S3 are from one another. It would be descriptive only, and would not change any
frozen test.
