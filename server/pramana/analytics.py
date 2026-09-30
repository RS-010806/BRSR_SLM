"""Deterministic statistics that reproduce the IIMB E1 report tables.

Conventions verified against the report (see tests/test_reconciliation.py):
  * Yes/No questions count "Yes" when the Rating-sheet score is 100 and
    group everything else as "No / NA / Blank".
  * Absolute Scope 1/2 sums apply the two report exclusions.
  * Year-on-year change is (CY - PY) / PY, undefined when PY is 0 or missing.
  * Company-wise direction treats CY == PY as "increased" (Table 3.3).
  * Change bands: < -10, [-10, -5), [-5, +5], (+5, +10], > +10 (percent).
"""
from __future__ import annotations

from typing import Callable, Iterable

BANDS = ["< -10%", "-10% to -5%", "-5% to +5%", "+5% to +10%", "> +10%"]


def median(values: Iterable[float]) -> float | None:
    xs = sorted(v for v in values if v is not None)
    n = len(xs)
    if n == 0:
        return None
    mid = n // 2
    return xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2.0


def mean(values: Iterable[float]) -> float | None:
    xs = [v for v in values if v is not None]
    return sum(xs) / len(xs) if xs else None


def quantile(values: Iterable[float], q: float) -> float | None:
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return None
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def band_of(v: float) -> int:
    if v < -10:
        return 0
    if v < -5:
        return 1
    if v <= 5:
        return 2
    if v <= 10:
        return 3
    return 4


def band_counts(values: Iterable[float]) -> list[int]:
    counts = [0] * 5
    for v in values:
        if v is not None:
            counts[band_of(v)] += 1
    return counts


def is_yes(c: dict, qid: str) -> bool:
    """Report convention: Yes only when the rating is 100."""
    return c["ratings"].get(qid) == 100


def yes_count(companies, qid: str) -> tuple[int, int]:
    y = sum(1 for c in companies if is_yes(c, qid))
    return y, len(companies) - y


def agg_value(c: dict, qid: str):
    """Value used in sector aggregates (report exclusions applied)."""
    if qid in ("1330", "1331", "1332", "1333"):
        return c["derived"]["agg"][qid]
    return c["values"].get(qid)


def sector_sum(companies, qid: str) -> float:
    return sum(agg_value(c, qid) or 0.0 for c in companies)


def category_counts(companies, qid: str, order: list[str]) -> dict[str, int]:
    out = {k: 0 for k in order}
    out["Blank"] = 0
    for c in companies:
        v = c["values"].get(qid)
        if v in out:
            out[v] += 1
        else:
            out["Blank"] += 1
    return out


def rating_distribution(companies, qid: str) -> dict[str, int]:
    out = {"0": 0, "25": 0, "50": 0, "75": 0, "100": 0, "none": 0}
    for c in companies:
        r = c["ratings"].get(qid)
        out["none" if r is None else str(r)] += 1
    return out


def ranked(companies, key: Callable[[dict], float | None], descending: bool) -> list[tuple[dict, float]]:
    """Stable, deterministic ranking. Ties are broken by company name."""
    rows = [(c, key(c)) for c in companies]
    rows = [(c, v) for c, v in rows if v is not None]
    rows.sort(key=lambda cv: (-cv[1] if descending else cv[1], cv[0]["name"].lower()))
    return rows


def percentile_rank(value: float, population: list[float], higher_is_better: bool) -> float | None:
    """Share of peers the value beats (0-100). Ties count half."""
    pop = [p for p in population if p is not None]
    if value is None or not pop:
        return None
    better = sum(1 for p in pop if (value > p if higher_is_better else value < p))
    ties = sum(1 for p in pop if p == value) - 1  # exclude self
    others = len(pop) - 1
    if others <= 0:
        return None
    return round(100.0 * (better + 0.5 * max(ties, 0)) / others, 1)
