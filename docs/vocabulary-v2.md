# Why vocabulary v2

**Decision:** the owner chose this on 2026-11-18, after the Impact4Cast control and before any literature data had been fetched.

**Reason:** the control (`docs/results/control.md`) showed that the shared-neighbour forecaster works on a
large, sparse graph (37,901 concepts, 3% of pairs linked: structure beats popularity by +0.049 AUC). It fails on a
small, dense one (ATT&CK, about 190 nodes, 49–66% of pairs linked). Vocabulary v1 has 14 concepts, which gives 91 pairs, and it
would very likely be denser still. Structure would have nothing to work with.

**What changes:**
- **Nodes:** the 14 v1 concepts stay, unchanged, as the *targets*. They are the only concepts that can
  become Elliptic scenarios. Up to 500 *context* concepts are added around them. These provide the shared
  neighbours that give structure its signal.
- **Choosing context concepts:** the context concepts are OpenAlex's own machine-assigned tags on the pre-2017
  AML, crypto and fraud literature. They are filtered by fixed thresholds (`config/aml_vocabulary_v2.toml`),
  not hand-picked, so nobody can choose concepts that flatter the result.
- **Evaluation:** forecaster quality is measured on 2010→2013 (train) and 2013→2016 (test). That uses literature
  only, all before the cutoff.
- **Picking scenarios:** the rule for which ranking picks the scenario pairs is fixed in advance. Use the trained
  model if it beats popularity on the test window, otherwise popularity.

**What does not change:**
- The v1 file, its 14 concepts and synonyms, and its scope anchors.
- The cutoff (2016-12-31).
- The 8 Elliptic-expressible concepts and the 28 expressible target pairs.

**Known limits:**
- With only 28 target pairs, the forecasting skill is measured on the whole graph. The 28 are only ranked for
  scenario choice; they are too few to evaluate on their own.
- The context source (`concepts` or `topics`) depends on what OpenAlex returns. The order of preference is fixed in advance.
- A larger corpus needs many more OpenAlex requests, so an API key is required.
