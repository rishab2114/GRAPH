"""Seed check for the Impact4Cast control's random baseline (AUC 0.530 with seed 0).

Rebuilds the exact test pairs and labels of gffs.concept_control.run_control (same rng draw order),
confirms seed 0 reproduces the logged AUC, then scores 20 more random-score seeds against the same labels.
"""
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

from gffs.baselines import random_scores
from gffs.concept_control import adjacencies_from_parquet, pair_labels, sample_unconnected

adj = adjacencies_from_parquet(Path("data/zenodo/impact4cast/data_concept_graph/full_dynamic_graph.parquet"),
                               [2016, 2019, 2022], 37_960)
rng = np.random.default_rng(0)
sample_unconnected(adj[2016], 200_000, rng)          # training draw, made first in run_control
u, v = sample_unconnected(adj[2019], 200_000, rng)  # test draw
y = pair_labels(adj[2022], u, v)
pairs = list(zip(u, v))
aucs = {s: float(roc_auc_score(y, random_scores(pairs, s))) for s in range(21)}
vals = np.array([aucs[s] for s in range(1, 21)])
n1, n0 = int(y.sum()), int(len(y) - y.sum())
se = float(np.sqrt((n1 + n0 + 1) / (12 * n1 * n0)))   # null SE of AUC for random scores (Mann-Whitney)
out = {"positives": n1, "negatives": n0, "seed0_auc": aucs[0], "seeds1_20": aucs,
       "mean_1_20": float(vals.mean()), "sd_1_20": float(vals.std(ddof=1)), "null_se": se,
       "seed0_z": (aucs[0] - 0.5) / se}
Path("results/control_seed_check.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("positives", "seed0_auc", "mean_1_20", "sd_1_20", "null_se", "seed0_z")}, indent=1))
