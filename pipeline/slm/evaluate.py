"""Evaluate the full query-understanding stack on hand-written queries.

    python -m pipeline.slm.evaluate [--write]

Scores intent, company, sector and metric resolution separately. With
--write the report is saved next to the model so /api/meta can show it.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from pramana.kb import get_kb  # noqa: E402
from pramana.nlu.parser import ARTIFACTS, Parser  # noqa: E402


def main(write: bool = False):
    kb = get_kb()
    parser = Parser(kb)
    rows = [json.loads(l) for l in (Path(__file__).parent / "eval_queries.jsonl").read_text().splitlines() if l.strip()]
    stats = Counter()
    per_intent = Counter()
    per_intent_ok = Counter()
    model_only_ok = 0
    failures = []
    for r in rows:
        p = parser.parse(r["q"])
        ok_i = p.intent == r["intent"]
        model_only_ok += p.model["intent"] == r["intent"]
        per_intent[r["intent"]] += 1
        per_intent_ok[r["intent"]] += ok_i
        stats["intent"] += ok_i
        checks = {"intent": ok_i}
        if "companies" in r:
            stats["companies_n"] += 1
            ok = sorted(p.companies) == sorted(r["companies"])
            stats["companies"] += ok
            checks["companies"] = ok
        if "sector" in r:
            stats["sector_n"] += 1
            ok = p.sector == r["sector"]
            stats["sector"] += ok
            checks["sector"] = ok
        if "metric" in r:
            stats["metric_n"] += 1
            ok = p.metric == r["metric"]
            stats["metric"] += ok
            checks["metric"] = ok
        if not all(checks.values()):
            failures.append({"q": r["q"], "expected": r, "got": {"intent": p.intent, "p": p.confidence,
                                                                   "companies": p.companies, "sector": p.sector,
                                                                   "metric": p.metric, "rules": p.rules,
                                                                   "masked": p.masked}})
    n = len(rows)
    report = {
        "queries": n,
        "intent_accuracy": round(stats["intent"] / n, 4),
        "model_only_intent_accuracy": round(model_only_ok / n, 4),
        "company_accuracy": round(stats["companies"] / max(stats["companies_n"], 1), 4),
        "sector_accuracy": round(stats["sector"] / max(stats["sector_n"], 1), 4),
        "metric_accuracy": round(stats["metric"] / max(stats["metric_n"], 1), 4),
        "per_intent": {k: f"{per_intent_ok[k]}/{per_intent[k]}" for k in per_intent},
        "failures": failures,
    }
    for f in failures:
        print("FAIL", f["q"], "\n     expected", {k: v for k, v in f["expected"].items() if k != "q"},
              "\n     got     ", f["got"])
    print(json.dumps({k: v for k, v in report.items() if k != "failures"}, indent=1))
    if write:
        (ARTIFACTS / "eval_report.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main("--write" in sys.argv)
