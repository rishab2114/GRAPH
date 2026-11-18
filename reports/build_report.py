"""Fill reports/template.html from results/study.json -> reports/study-report.html.

    python -m reports.build_report
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent


def summary(results: list[dict]) -> dict[str, str]:
    def wins(key):
        return sum(r["methods"][key]["vs_frequency"]["lo"] > 0 for r in results)

    freq = [r["methods"]["frequency"]["auc"] for r in results]
    dens = [r["graph"]["density_t"] for r in results]
    return {
        "FREQ_RANGE": f"{min(freq):.2f}–{max(freq):.2f}",
        "DENSITY_RANGE": f"{min(dens):.0%}–{max(dens):.0%}",
        "LOGREG_WINS": str(wins("logreg_all")),
        "HGB_WINS": str(wins("hgb_all")),
        "STRAT_WINS": str(sum(r["methods"]["structural_rank_mean"]["strat_auc"] > r["methods"]["frequency"]["strat_auc"]
                              for r in results)),
        "HY_MAX": f"{max(r['methods']['hybrid_rank_exploratory']['vs_frequency']['diff'] for r in results):+.3f}",
        "HY_P100_LOSE": str(sum(r["methods"]["hybrid_rank_exploratory"]["precision_at_k"]
                                < r["methods"]["frequency"]["precision_at_k"] for r in results)),
    }


def build(results_path: Path = Path("results/study.json"), out: Path = HERE / "study-report.html") -> Path:
    results = json.loads(results_path.read_text())
    html = (HERE / "template.html").read_text()
    fills = summary(results)
    fills["DATE"] = date.today().isoformat()
    fills["NMETHODS"] = str(len(results[0]["methods"]))
    seen, rows = set(), []
    for r in results:
        if r["split"] in seen:
            continue
        seen.add(r["split"])
        rel = r["releases"]
        rows.append(f"<tr><td>{r['split']}</td><td>{rel['train_from']}</td><td>{rel['t']}</td><td>{rel['test_to']}</td></tr>")
    fills["SPLIT_ROWS"] = "".join(rows).replace("&", "&amp;")
    slim = [{"split": r["split"], "edges": r["edges"], "graph": r["graph"], "methods": r["methods"]} for r in results]
    fills["DATA"] = json.dumps(slim, separators=(",", ":"))
    for k, v in fills.items():
        html = html.replace(f"__{k}__", v)
    assert "__" not in html.replace("__init__", ""), "unfilled placeholder"
    out.write_text(html)
    return out


if __name__ == "__main__":
    print(build())
