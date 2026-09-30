"""Shared helpers for handlers: peer statistics, ranks and chart blocks."""
from __future__ import annotations

from ..analytics import median, quantile
from . import metrics as M
from .fmt import CO2, compact, num, ordinal, pct, short_name, tile


class Ctx:
    def __init__(self, kb, plan, index, answer):
        self.kb = kb
        self.plan = plan
        self.index = index
        self.a = answer

    def co(self, cid):
        return self.kb.by_id[cid]

    def sector(self, sid):
        return self.kb.sector_by_id[sid]


def eligible(metric: M.Metric, companies, by: str = "value"):
    """(company, value) pairs that can be compared on this metric."""
    out = []
    for c in companies:
        if by == "yoy":
            # A ratio is unit-invariant, so scaled-unit filings still compare on change;
            # only the report's own exclusions are removed.
            v = metric.yoy(c) if metric.yoy else None
            if v is not None and metric.kind == "abs" and any(
                    f["type"] == "report_exclusion" and set(f["qids"]) & set(metric.qids) for f in c["flags"]):
                v = None
        else:
            v = metric.value(c)
            if v is not None and metric.level_ok is not None and not metric.level_ok(c):
                v = None
        if v is not None:
            out.append((c, v))
    return out


def rank_of(c, pairs, descending: bool):
    """1-based rank with ties broken by name, as in analytics.ranked."""
    ordered = sorted(pairs, key=lambda cv: (-cv[1] if descending else cv[1], cv[0]["name"].lower()))
    for i, (x, _) in enumerate(ordered, start=1):
        if x["id"] == c["id"]:
            return i, len(ordered), ordered
    return None, len(ordered), ordered


def beat_share(value, pairs, c, better: str):
    """How many peers the company does better than on this metric."""
    others = [v for x, v in pairs if x["id"] != c["id"]]
    if not others:
        return 0, 0
    if better == "lower":
        beat = sum(1 for v in others if v > value)
    else:
        beat = sum(1 for v in others if v < value)
    return beat, len(others)


def rank_phrase(r: int, n: int, word_high: str = "highest", word_low: str = "lowest") -> str:
    if r == 1:
        return f"the {word_high} of {n}"
    if r == n:
        return f"the {word_low} of {n}"
    return f"{ordinal(r)} {word_high} of {n}"


def fmt_value(metric: M.Metric, v):
    if v is None:
        return "not reported"
    if metric.kind == "abs":
        return f"{num(v)} {CO2}"
    if metric.kind == "intensity":
        return f"{num(v)} {metric.unit}" if metric.comparable_levels else f"{num(v)} ({metric.unit})"
    if metric.kind == "score":
        return f"{num(v)}/100" if metric.id != "index" else f"{v:.1f}/100"
    return num(v)


def fmt_short(metric: M.Metric, v):
    if v is None:
        return "n/a"
    if metric.kind == "abs":
        return tile(v)
    if metric.kind == "score":
        return f"{v:.0f}" if metric.id != "index" else f"{v:.1f}"
    return num(v)


def bars(title, pairs, metric: M.Metric, focus_ids=(), median_v=None, subtitle=None, log=False, limit=None,
         show_rank=True, value_kind="value"):
    rows = []
    for i, (c, v) in enumerate(pairs[:limit] if limit else pairs, start=1):
        rows.append({"id": c["id"], "label": short_name(c["name"]), "value": v,
                     "display": pct(v) if value_kind == "yoy" else fmt_short(metric, v),
                     "full": pct(v, digits=2) if value_kind == "yoy" else fmt_value(metric, v),
                     "rank": i if show_rank else None, "highlight": c["id"] in focus_ids})
    blk = {"type": "bars", "title": title, "subtitle": subtitle, "rows": rows,
           "unit": "% change" if value_kind == "yoy" else metric.unit, "log": log,
           "diverging": value_kind == "yoy", "better": metric.better}
    if median_v is not None:
        blk["median"] = {"value": median_v, "label": "Sector median", "display": pct(median_v) if value_kind == "yoy"
                         else fmt_short(metric, median_v)}
    return blk


def strip(title, pairs, metric: M.Metric, focus_ids=(), subtitle=None, value_kind="value"):
    vals = [v for _, v in pairs]
    pts = [{"id": c["id"], "label": short_name(c["name"]), "value": v,
            "display": pct(v, digits=2) if value_kind == "yoy" else fmt_value(metric, v),
            "highlight": c["id"] in focus_ids} for c, v in pairs]
    return {"type": "strip", "title": title, "subtitle": subtitle, "points": pts,
            "log": value_kind != "yoy" and metric.kind in ("abs", "intensity") and min((v for v in vals if v > 0), default=1) > 0
                   and len(vals) > 3 and max(vals) / max(min((v for v in vals if v > 0), default=1), 1e-12) > 200,
            "median": median(vals), "q1": quantile(vals, 0.25), "q3": quantile(vals, 0.75),
            "median_display": (pct(median(vals)) if value_kind == "yoy" else fmt_short(metric, median(vals))) if vals else None,
            "unit": "% change" if value_kind == "yoy" else metric.unit, "better": metric.better,
            "diverging": value_kind == "yoy"}


def yes_rate(companies, qid):
    y = sum(1 for c in companies if c["ratings"].get(qid) == 100)
    return y, len(companies)


def kpi(label, value, sub=None, delta=None, tone="neutral", cite=None, big=False):
    d = {"label": label, "value": value}
    if sub:
        d["sub"] = sub
    if delta is not None:
        d["delta"] = {"text": delta, "tone": tone}
    if cite:
        d["cite"] = cite
    if big:
        d["big"] = True
    return d


def change_tone(v, better="lower"):
    if v is None or abs(v) < 0.05:
        return "neutral"
    good = v < 0 if better == "lower" else v > 0
    return "good" if good else "bad"


def compact_value(metric: M.Metric, v):
    if metric.kind == "abs":
        return f"{compact(v)} {CO2}"
    return fmt_value(metric, v)
