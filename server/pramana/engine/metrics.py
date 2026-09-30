"""Runtime metric definitions used for values, rankings and peer statistics."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .fmt import CO2


@dataclass
class Metric:
    id: str
    label: str
    unit: str
    kind: str                     # abs | intensity | score | bool | text | category
    better: str = "lower"         # lower | higher
    cy_q: str | None = None
    py_q: str | None = None
    rating_q: list = field(default_factory=list)
    value: Callable | None = None
    prev: Callable | None = None
    yoy: Callable | None = None
    level_ok: Callable | None = None
    comparable_levels: bool = True
    qids: list = field(default_factory=list)
    note: str | None = None


def _v(q):
    return lambda c: c["values"].get(q)


def _d(k):
    return lambda c: c["derived"].get(k)


def _excluded(c, qids):
    return any(f["type"] == "report_exclusion" and set(f["qids"]) & set(qids) for f in c["flags"])


def _abs_ok(qids):
    return lambda c: not _excluded(c, qids) and c["derived"].get("abs_level_ok", True)


def _pos(getter):
    return lambda c: (getter(c) or 0) > 0


NUMERIC: dict[str, Metric] = {
    "scope1": Metric("scope1", "Scope 1 emissions", CO2, "abs", cy_q="1330", py_q="1331", rating_q=["1330"],
                     value=_v("1330"), prev=_v("1331"), yoy=_d("scope1_yoy_pct"), level_ok=_abs_ok(["1330", "1331"]),
                     qids=["1330", "1331"]),
    "scope2": Metric("scope2", "Scope 2 emissions", CO2, "abs", cy_q="1332", py_q="1333", rating_q=["1332"],
                     value=_v("1332"), prev=_v("1333"), yoy=_d("scope2_yoy_pct"), level_ok=_abs_ok(["1332", "1333"]),
                     qids=["1332", "1333"]),
    "scope12": Metric("scope12", "Scope 1+2 emissions", CO2, "abs", rating_q=["1330", "1332"],
                      value=_d("scope12_cy"), prev=_d("scope12_py"), yoy=_d("scope12_yoy_pct"),
                      level_ok=_abs_ok(["1330", "1331", "1332", "1333"]), qids=["1330", "1331", "1332", "1333"]),
    "scope3": Metric("scope3", "Scope 3 emissions", CO2, "abs", cy_q="1388", py_q="1389", rating_q=["1388"],
                     value=_v("1388"), prev=_v("1389"), yoy=_d("scope3_yoy_pct"), level_ok=lambda c: True,
                     qids=["1388", "1389"]),
    "intensity": Metric("intensity", "Scope 1+2 intensity", f"{CO2} per ₹ crore", "intensity",
                        cy_q="1334", py_q="1335", rating_q=["1334", "1335"], value=_d("intensity_cr_cy"),
                        prev=_d("intensity_cr_py"), yoy=_d("intensity_yoy_pct"), level_ok=_d("intensity_level_ok"),
                        qids=["1334", "1335"],
                        note="Reported per rupee of turnover; shown per ₹ crore (x 10,000,000) as in Report Table 3.5."),
    "scope3_intensity": Metric("scope3_intensity", "Scope 3 intensity", f"{CO2} per ₹ crore", "intensity",
                               cy_q="1390", py_q="1391", rating_q=["1390", "1391"], value=_d("scope3_intensity_cr_cy"),
                               prev=_d("scope3_intensity_cr_py"), yoy=_d("scope3_intensity_yoy_pct"),
                               level_ok=_d("scope3_intensity_level_ok"), qids=["1390", "1391"],
                               note="Reported per rupee of turnover; shown per ₹ crore."),
    "intensity_phys": Metric("intensity_phys", "Scope 1+2 intensity per unit of physical output",
                             "company-specific unit", "intensity", cy_q="1338", py_q="1339", rating_q=["1338", "1339"],
                             value=_v("1338"), prev=_v("1339"), yoy=_d("intensity_phys_yoy_pct"),
                             level_ok=lambda c: False, comparable_levels=False, qids=["1338", "1339"],
                             note="Each company chooses its own physical unit (per tonne, per MWh, per unit and so on), "
                                  "so levels are not comparable across companies. Only the year-on-year change is compared."),
    "intensity_ppp": Metric("intensity_ppp", "Scope 1+2 intensity (PPP adjusted)", "as reported", "intensity",
                            cy_q="1336", py_q="1337", rating_q=["1336", "1337"], value=_v("1336"), prev=_v("1337"),
                            yoy=_d("intensity_ppp_yoy_pct"), level_ok=lambda c: False, comparable_levels=False,
                            qids=["1336", "1337"],
                            note="PPP-adjusted intensities are reported in inconsistent units across companies, "
                                 "so only the year-on-year change is compared."),
    "index": Metric("index", "E1 index (derived)", "/100", "score", better="higher",
                    value=lambda c: c["derived"]["index"]["overall"], level_ok=lambda c: True,
                    note="Equal-weighted mean of the Governance, Action and Performance pillar averages of "
                         "Rating-sheet scores. Derived by Pramana for navigation; not an official IIMB score."),
}

# Narrative / yes-no questions expressed as their Rating-sheet score (0-100).
SCORE_Q = {"targets": "286", "target_performance": "295", "projects": "1342", "certifications": "277",
           "ghg_assurance": "1340", "scope3_reported": "1387", "scope3_assurance": "1560", "policy": "232",
           "board_approval": "241", "policy_link": "250", "procedures": "259", "value_chain": "268",
           "policy_assessment": "344", "review_level": "308", "review_frequency": "326", "ghg_applicable": "1329"}

BOOL_Q = {"ghg_assurance": "1340", "scope3_reported": "1387", "scope3_assurance": "1560", "policy": "232",
          "board_approval": "241", "policy_link": "250", "procedures": "259", "value_chain": "268",
          "policy_assessment": "344", "ghg_applicable": "1329", "projects": "1341"}

# Companion narrative question for a yes/no question.
COMPANION_TEXT = {"1560": "1561", "344": "353", "1341": "1342", "250": "250"}

TEXT_Q = {"targets": "286", "target_performance": "295", "projects": "1342", "certifications": "277"}
CATEGORY_Q = {"review_level": ["308", "317"], "review_frequency": ["326", "335"]}


def score_metric(mid: str, kb) -> Metric:
    q = SCORE_Q[mid]
    qq = kb.q(q)
    return Metric(mid, f"{qq['label']} (score)", "/100", "score", better="higher",
                  value=lambda c, q=q: c["ratings"].get(q), level_ok=lambda c: True, rating_q=[q], qids=[q])


def get(mid: str, kb) -> Metric | None:
    if mid in NUMERIC:
        return NUMERIC[mid]
    if mid in SCORE_Q:
        return score_metric(mid, kb)
    return None
