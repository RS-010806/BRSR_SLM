"""Infographics: a one-page, shareable summary of a company, a sector or the whole market.

The handler only prepares the facts. The page draws them, so the same data
always produces the same picture, and every figure on it is cited in the
answer text.
"""
from __future__ import annotations

from ..analytics import sector_sum
from . import metrics as M
from .common import change_tone, eligible, ordered, value_cite, yes, yes_count
from .evidence import highlight
from .fmt import CO2, compact, join, num, pct, short_name, tile
from .h_company import kicker

SOURCE = "Source: company BRSR disclosures, FY 2024-25"


def _big(v: float) -> tuple[str, str]:
    """(number, unit) sized for a headline."""
    if v >= 1e9:
        return f"{v / 1e9:.2f}", f"billion {CO2}"
    if v >= 1e6:
        return f"{v / 1e6:.2f}", f"million {CO2}"
    return num(v), CO2


def _delta(y):
    if y is None:
        return None
    return {"text": f"{pct(y)} vs FY 2023-24", "tone": change_tone(y)}


def _key_sentence(ctx, c, qid, limit=210):
    """The most specific sentence of a disclosure, exactly as written (shortened with an ellipsis if long)."""
    text = c["values"].get(qid)
    if not text:
        return None
    segs = ctx.index.by_cell.get((c["id"], qid), [])
    top = [s for s in highlight(segs, k=1) if s["highlight"]]
    if not top:
        return None
    s = " ".join(text[top[0]["start"]:top[0]["end"]].split())
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return s


def infographic(ctx, c=None, sid=None):
    if c is not None:
        return _company(ctx, c)
    if sid is not None:
        return _sector(ctx, sid)
    return _market(ctx)


def _company(ctx, c):
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    short = short_name(c["name"])
    sname = kb.sector_of(c)["name"]
    m1, m2, m12, m3, mi = (M.NUMERIC[k] for k in ("scope1", "scope2", "scope12", "scope3", "intensity"))
    v1, v2, v3 = m1.value(c), m2.value(c), m3.value(c)
    a.kicker = kicker(ctx, c)
    a.title = f"Infographic: {short}"
    if v1 is None and v2 is None:
        a.status = "partial"
        a.p(f"An infographic needs emission figures, and {c['name']} has not disclosed Scope 1 or Scope 2 emissions for "
            f"FY 2024-25 {a.c_filing(c, '1330')}.")
        a.follow(f"Tell me about {short}")
        return
    bits = []
    if v1 is not None:
        bits.append(f"Scope 1 emissions of {num(v1)} {CO2} {a.c_filing(c, '1330')}")
    if v2 is not None:
        bits.append(f"Scope 2 emissions of {num(v2)} {CO2} {a.c_filing(c, '1332')}")
    if v3 is not None:
        bits.append(f"Scope 3 emissions of {num(v3)} {CO2} {a.c_filing(c, '1388')}")
    a.p(f"Here is an infographic for **{c['name']}**, built from its BRSR disclosures for FY 2024-25: {join(bits)}. "
        f"You can download it as an image.")
    total = m12.value(c) if (v1 is not None and v2 is not None) else (v1 if v1 is not None else v2)
    hv, hu = _big(total)
    stats = []
    for m, label in ((m1, "Scope 1"), (m2, "Scope 2"), (m3, "Scope 3")):
        v = m.value(c)
        stats.append({"label": label, "value": tile(v) if v is not None else "Not disclosed",
                      "unit": CO2 if v is not None else "", "delta": _delta(m.yoy(c)) if v is not None else None})
    if mi.value(c) is not None and mi.level_ok(c):
        stats.append({"label": "Emission intensity", "value": num(mi.value(c)), "unit": f"{CO2} per ₹ crore",
                      "delta": _delta(mi.yoy(c))})
        value_cite(a, c, mi)
    quote = _key_sentence(ctx, c, "286")
    qlabel = "On targets, in the company's words"
    if quote:
        a.c_filing(c, "286")
    else:
        quote = _key_sentence(ctx, c, "1342")
        qlabel = "On reducing emissions, in the company's words"
        if quote:
            a.c_filing(c, "1342")
    a.block("infographic", kind="company", eyebrow="GHG emissions snapshot", period="FY 2024-25", title=short,
            subtitle=sname, filename=f"{short} GHG snapshot FY2024-25",
            hero={"label": "Scope 1 + Scope 2 emissions" if (v1 is not None and v2 is not None) else
                  ("Scope 1 emissions" if v1 is not None else "Scope 2 emissions"),
                  "value": hv, "unit": hu, "delta": _delta(m12.yoy(c)) if (v1 is not None and v2 is not None) else None},
            stats=stats,
            split=[{"label": lab, "value": v} for lab, v in (("Scope 1", v1), ("Scope 2", v2), ("Scope 3", v3)) if v],
            trend=[{"label": lab, "py": m.prev(c), "cy": m.value(c)} for m, lab in ((m1, "Scope 1"), (m2, "Scope 2"))
                   if m.prev(c) is not None and m.value(c) is not None],
            checks=[{"label": lab, "value": yes(c, q)} for q, lab in (("1340", "Emissions independently assured"),
                                                                      ("1387", "Scope 3 emissions reported"),
                                                                      ("1341", "Projects to reduce GHG emissions"),
                                                                      ("241", "Board-approved environment policy"))],
            quote={"label": qlabel, "text": quote} if quote else None, source=SOURCE)
    a.flag_notes(c, ["1330", "1331", "1332", "1333"])
    a.context.update({"companies": [c["id"]], "intent": "infographic"})
    a.follow(f"How does {short} compare with its peers?", f"What are {short}'s targets?",
             f"Make an infographic for the {sname} sector")


def _totals(members):
    t1, t2 = sector_sum(members, "1330"), sector_sum(members, "1332")
    p = sector_sum(members, "1331") + sector_sum(members, "1333")
    return t1, t2, ((t1 + t2 - p) / p * 100 if p else None)


def _shares(members):
    n = len(members)
    out = []
    for q, lab in (("1387", "Report Scope 3 emissions"), ("1340", "Emissions independently assured"),
                   ("1341", "Projects to reduce GHG emissions")):
        y, _ = yes_count(members, q)
        out.append({"label": lab, "value": round(100 * y / n, 1) if n else 0, "text": f"{y} of {n}"})
    return out


def _sector(ctx, sid):
    a, kb = ctx.a, ctx.kb
    s = kb.sector_by_id[sid]
    members = kb.members(sid)
    t1, t2, yoy = _totals(members)
    a.kicker = "Sector"
    a.title = f"Infographic: {s['name']}"
    cite = a.c_calc(f"Sector totals, {s['name']}", f"Sum of disclosed Scope 1 ({num(t1)} {CO2}) and Scope 2 ({num(t2)} {CO2}) "
                    f"across {len(members)} companies")
    a.p(f"Here is an infographic for the **{s['name']}** sector: {len(members)} companies with combined Scope 1 and "
        f"Scope 2 emissions of {compact(t1 + t2)} {CO2} for FY 2024-25 {cite}. You can download it as an image.")
    hv, hu = _big(t1 + t2)
    top = ordered(eligible(M.NUMERIC["scope12"], members))[:5]
    a.block("infographic", kind="sector", eyebrow="Sector GHG snapshot", period="FY 2024-25", title=s["name"],
            subtitle=f"{len(members)} companies", filename=f"{s['name']} GHG snapshot FY2024-25",
            hero={"label": "Scope 1 + Scope 2 emissions", "value": hv, "unit": hu, "delta": _delta(yoy)},
            stats=[{"label": "Scope 1", "value": tile(t1), "unit": CO2}, {"label": "Scope 2", "value": tile(t2), "unit": CO2},
                   {"label": "Companies", "value": str(len(members)), "unit": ""}],
            split=[{"label": "Scope 1", "value": t1}, {"label": "Scope 2", "value": t2}],
            bars={"label": "Largest emitters (Scope 1 + Scope 2)",
                  "items": [{"label": short_name(c["name"]), "value": v, "display": tile(v)} for c, v in top]},
            shares=_shares(members), source=SOURCE)
    if any(f["type"] == "report_exclusion" for c in members for f in c["flags"]):
        a.note("data", "Totals leave out disclosed values that are clearly in a different unit.")
    a.context.update({"sector": sid, "intent": "infographic"})
    a.follow(f"Give me an overview of the {s['name']} sector", f"List all {s['name']} companies",
             f"Examples of GHG reduction projects from {s['name']} companies")


def _market(ctx):
    a, kb = ctx.a, ctx.kb
    cos = kb.companies
    t1, t2, yoy = _totals(cos)
    a.kicker = "All companies"
    a.title = "Infographic: emissions across all companies"
    cite = a.c_calc("Totals across all companies", f"Sum of disclosed Scope 1 ({num(t1)} {CO2}) and Scope 2 ({num(t2)} {CO2}) "
                    f"across {len(cos)} companies")
    a.p(f"Here is an infographic covering all {len(cos)} companies: combined Scope 1 and Scope 2 emissions of "
        f"{compact(t1 + t2)} {CO2} for FY 2024-25 {cite}. You can download it as an image.")
    hv, hu = _big(t1 + t2)
    tot = sorted(((s, sector_sum(kb.members(s["id"]), "1330") + sector_sum(kb.members(s["id"]), "1332")) for s in kb.sectors),
                 key=lambda t: (-t[1], t[0]["name"]))[:5]
    a.block("infographic", kind="market", eyebrow="GHG emissions snapshot", period="FY 2024-25",
            title="Listed companies in India", subtitle=f"{len(cos)} companies, {len(kb.sectors)} sectors",
            filename="GHG snapshot FY2024-25",
            hero={"label": "Scope 1 + Scope 2 emissions", "value": hv, "unit": hu, "delta": _delta(yoy)},
            stats=[{"label": "Scope 1", "value": tile(t1), "unit": CO2}, {"label": "Scope 2", "value": tile(t2), "unit": CO2},
                   {"label": "Companies", "value": str(len(cos)), "unit": ""}],
            split=[{"label": "Scope 1", "value": t1}, {"label": "Scope 2", "value": t2}],
            bars={"label": "Largest emitting sectors (Scope 1 + Scope 2)",
                  "items": [{"label": s["name"], "value": v, "display": tile(v)} for s, v in tot]},
            shares=_shares(cos), source=SOURCE)
    a.note("data", "Totals leave out disclosed values that are clearly in a different unit.")
    a.follow("Which sector emits the most?", "Top 10 emitters", "Make an infographic for NTPC")
