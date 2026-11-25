"""Disclosed reanalysis of the literature-v2 forecaster validation (results/literature_graph_v2.json), Codex G06.

The published validation (graph 2013 -> pairs linked by 2016, trained on 2010 -> 2013) selected the ~500 context
nodes using works up to 2016, i.e. with knowledge of the evaluation window. Here the context vocabulary is selected
from works up to 2013 (the evaluation graph's date) and everything else is unchanged.

    python -m gffs.literature_v2_reanalysis     # -> results/literature_graph_v2_reanalysis.json
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

from gffs import literature as lit
from gffs.alien_s4 import CONFIG, load_works
from gffs.study import run_split


def main() -> None:
    cfg = tomllib.loads(CONFIG.read_text())
    (a, b), (_, c) = cfg["evaluation"]["train"], cfg["evaluation"]["test"]
    works, v = load_works(vocab_year=b)                      # b = 2013: vocabulary chosen with data up to 2013 only
    ell = {x.id for x in v.concepts if x.elliptic}
    r = run_split(lit.concept_sets(works, a), lit.concept_sets(works, b), lit.concept_sets(works, c),
                  n_boot=1000, focus=lambda u, w: u in ell or w in ell)
    pub = json.loads(Path("results/literature_graph_v2.json").read_text())["evaluation"]
    out = {"what": "literature-v2 validation with the context vocabulary selected up to 2013 (G06); disclosed reanalysis",
           "vocab_year": b, "graph_works": len(works), "reanalysis": r,
           "compare": {m: {"published_auc": pub["methods"][m].get("auc"), "reanalysis_auc": r["methods"][m].get("auc"),
                           "published_vs_frequency": pub["methods"][m].get("vs_frequency"),
                           "reanalysis_vs_frequency": r["methods"][m].get("vs_frequency")} for m in r["methods"]}}
    Path("results/literature_graph_v2_reanalysis.json").write_text(json.dumps(out, indent=1, default=str))
    for m, x in out["compare"].items():
        print(f"{m:26s} AUC published {x['published_auc']}  reanalysis {x['reanalysis_auc']}  vs freq {x['reanalysis_vs_frequency']}")


if __name__ == "__main__":
    main()
