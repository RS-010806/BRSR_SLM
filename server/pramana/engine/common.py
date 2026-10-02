"""Shared helpers for handlers: peer statistics, chart blocks and exports."""
from __future__ import annotations

from ..analytics import median, quantile
from . import metrics as M
from .fmt import CO2, ascii_unit, compact, num, pct, short_name, tile


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


def yes(c: dict, qid: str) -> bool:
    """Whether the company answered Yes to a yes/no disclosure."""
    return c["ratings"].get(qid) == 100 if qid in c["ratings"] else c["values"].get(qid) is True


def yes_count(companies, qid: str) -> tuple[int, int]:
    return sum(1 for c in companies if yes(c, qid)), len(companies)


def eligible(metric: M.Metric, companies, by: str = "value"):
    """(company, value) pairs that can be compared on this metric."""
    out = []
    for c in companies:
        if by == "yoy":
            # A ratio does not depend on the unit, so filings in a different unit still compare on change.
            v = metric.yoy(c) if metric.yoy else None
            # more than tenfold up or down between two years is a change of unit or reporting boundary, not of operations
            if v is not None and (v > 900 or v < -90):
                v = None
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


def ordered(pairs, descending: bool = True):
    return sorted(pairs, key=lambda cv: (-cv[1] if descending else cv[1], cv[0]["name"].lower()))


def fmt_value(metric: M.Metric, v):
    if v is None:
        return "not disclosed"
    if metric.kind == "abs":
        return f"{num(v)} {CO2}"
    if metric.kind == "intensity":
        return f"{num(v)} {metric.unit}" if metric.comparable_levels else f"{num(v)} (unit as disclosed)"
    return num(v)


def fmt_short(metric: M.Metric, v):
    if v is None:
        return "n/a"
    if metric.kind == "abs":
        return tile(v)
    return num(v)


def export(title: str, columns: list[str], rows: list[list], note: str | None = None) -> dict:
    """Spreadsheet-ready copy of a table or chart: plain headers with units, raw numbers in cells."""
    return {"title": title, "columns": [ascii_unit(c) for c in columns],
            "rows": [[ascii_unit(x) if isinstance(x, str) else x for x in r] for r in rows], "note": note}


def bars(title, pairs, metric: M.Metric, focus_ids=(), median_v=None, median_label="Median", subtitle=None, log=False,
         limit=None, show_rank=True, value_kind="value"):
    rows = []
    for i, (c, v) in enumerate(pairs[:limit] if limit else pairs, start=1):
        row = {"id": c["id"], "label": short_name(c["name"]), "value": v,
               "display": pct(v) if value_kind == "yoy" else fmt_short(metric, v),
               "full": pct(v, digits=2) if value_kind == "yoy" else fmt_value(metric, v),
               "highlight": c["id"] in focus_ids}
        if show_rank:
            row["rank"] = i                     # numbered only when the question asked for a ranking
        rows.append(row)
    unit = "% change" if value_kind == "yoy" else metric.unit
    blk = {"type": "bars", "title": title, "subtitle": subtitle, "rows": rows, "unit": unit, "log": log,
           "diverging": value_kind == "yoy", "better": metric.better,
           "export": export(title, ["Company", f"{metric.label} ({unit})"], [[c["name"], v] for c, v in
                                                                              (pairs[:limit] if limit else pairs)])}
    if median_v is not None:
        blk["median"] = {"value": median_v, "label": median_label, "display": pct(median_v) if value_kind == "yoy"
                         else fmt_short(metric, median_v)}
    return blk


def strip(title, pairs, metric: M.Metric, focus_ids=(), subtitle=None, value_kind="value"):
    vals = [v for _, v in pairs]
    pts = [{"id": c["id"], "label": short_name(c["name"]), "value": v,
            "display": pct(v, digits=2) if value_kind == "yoy" else fmt_value(metric, v),
            "highlight": c["id"] in focus_ids} for c, v in pairs]
    unit = "% change" if value_kind == "yoy" else metric.unit
    return {"type": "strip", "title": title, "subtitle": subtitle, "points": pts,
            "log": value_kind != "yoy" and metric.kind in ("abs", "intensity") and min((v for v in vals if v > 0), default=1) > 0
                   and len(vals) > 3 and max(vals) / max(min((v for v in vals if v > 0), default=1), 1e-12) > 200,
            "median": median(vals), "q1": quantile(vals, 0.25), "q3": quantile(vals, 0.75),
            "median_display": (pct(median(vals)) if value_kind == "yoy" else fmt_short(metric, median(vals))) if vals else None,
            "unit": unit, "better": metric.better, "diverging": value_kind == "yoy",
            "export": export(title, ["Company", f"{metric.label} ({unit})"],
                             [[c["name"], v] for c, v in ordered(pairs)])}


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


def value_cite(a, c, metric: M.Metric, by: str = "value") -> str:
    """Citation for a company's value on a metric: the filing itself, or the arithmetic over filed values."""
    v = c["values"]
    name = short_name(c["name"])
    if by == "yoy":
        if metric.id == "scope12":
            return a.c_calc(f"Change in Scope 1 + Scope 2 emissions ({name})",
                            f"({num(metric.value(c))} − {num(metric.prev(c))}) ÷ {num(metric.prev(c))} = {pct(metric.yoy(c), digits=2)}",
                            [a.c_filing(c, q) for q in ("1330", "1332", "1331", "1333")])
        if metric.cy_q and metric.py_q:
            return a.c_calc(f"Change in {metric.label[0].lower() + metric.label[1:]} ({name})",
                            f"({num(v.get(metric.cy_q))} − {num(v.get(metric.py_q))}) ÷ {num(v.get(metric.py_q))} = "
                            f"{pct(metric.yoy(c), digits=2)}", [a.c_filing(c, metric.cy_q), a.c_filing(c, metric.py_q)])
    if metric.id == "scope12":
        return a.c_calc(f"Scope 1 + Scope 2, FY 2024-25 ({name})",
                        f"{num(v.get('1330'))} + {num(v.get('1332'))} = {num(metric.value(c))} {CO2}",
                        [a.c_filing(c, "1330"), a.c_filing(c, "1332")])
    if metric.kind == "intensity" and metric.comparable_levels and metric.cy_q:
        return a.c_calc(f"{metric.label} per ₹ crore ({name})",
                        f"{num(v.get(metric.cy_q))} {CO2} per rupee × 1 crore (10,000,000) = {num(metric.value(c))} "
                        f"{CO2} per ₹ crore", [a.c_filing(c, metric.cy_q)])
    if metric.cy_q:
        return a.c_filing(c, metric.cy_q)
    return ""


def prev_cite(a, c, metric: M.Metric) -> str:
    """Citation for the previous-year value."""
    v = c["values"]
    name = short_name(c["name"])
    if metric.id == "scope12":
        return a.c_calc(f"Scope 1 + Scope 2, FY 2023-24 ({name})",
                        f"{num(v.get('1331'))} + {num(v.get('1333'))} = {num(metric.prev(c))} {CO2}",
                        [a.c_filing(c, "1331"), a.c_filing(c, "1333")])
    if metric.kind == "intensity" and metric.comparable_levels and metric.py_q:
        return a.c_calc(f"{metric.label} per ₹ crore, FY 2023-24 ({name})",
                        f"{num(v.get(metric.py_q))} {CO2} per rupee × 1 crore (10,000,000) = {num(metric.prev(c))} "
                        f"{CO2} per ₹ crore", [a.c_filing(c, metric.py_q)])
    return a.c_filing(c, metric.py_q) if metric.py_q else ""


# --------------------------------------------------------------------------- suggested questions
def example_company(ctx, mid: str = "scope12"):
    """(company, is it the user's own): the user's company, else the one being discussed, else the largest discloser of
    the measure in the sector being discussed, else across all companies. Suggestions follow the conversation."""
    plan, kb = ctx.plan, ctx.kb
    cid = plan.lens or next(iter(plan.about), None) or next(iter(plan.companies), None)
    if cid in kb.by_id:
        return kb.by_id[cid], cid == plan.lens
    sid = plan.sector if plan.sector in kb.sector_by_id else plan.about_sector
    pool = kb.members(sid) if sid in kb.sector_by_id else kb.companies
    pairs = eligible(M.NUMERIC.get(mid) or M.NUMERIC["scope12"], pool) or eligible(M.NUMERIC["scope12"], kb.companies)
    return max(pairs, key=lambda t: (t[1], t[0]["name"]))[0], False


ASK = {"emissions": ("What are our GHG emissions?", "What are {s}'s GHG emissions?"),
       "scope1": ("What are our Scope 1 emissions?", "What are {s}'s Scope 1 emissions?"),
       "scope2": ("What are our Scope 2 emissions?", "What are {s}'s Scope 2 emissions?"),
       "scope12": ("What are our Scope 1 and Scope 2 emissions?", "What are {s}'s Scope 1 and Scope 2 emissions?"),
       "scope3": ("What are our Scope 3 emissions?", "What are {s}'s Scope 3 emissions?"),
       "intensity": ("What is our emission intensity?", "What is {s}'s emission intensity?"),
       "targets": ("What are our targets?", "What are {s}'s targets?"),
       "projects": ("Show our projects to reduce GHG emissions", "Show {s}'s projects to reduce GHG emissions"),
       "peers": ("How do we compare with our peers?", "How does {s} compare with its peers?"),
       "peer_list": ("Who are our peers?", "Who are {s}'s peers?"),
       "infographic": ("Make an infographic of our emissions", "Make an infographic for {s}"),
       "whatif": ("What if we cut Scope 1 by 10%?", "What if {s} cuts Scope 1 by 10%?"),
       "change": ("How did our emissions change?", "How did {s}'s emissions change?")}


def ask(ctx, kind: str, mid: str | None = None) -> str:
    c, own = example_company(ctx, mid or (kind if kind in M.NUMERIC else "scope12"))
    mine, theirs = ASK[kind]
    return mine if own else theirs.format(s=short_name(c["name"]))
