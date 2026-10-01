"""Company-level answers: emissions, a single figure, a short profile, yes/no, narrative, what-if.

Answers are kept to the point: the figure asked for, the previous year for
context, and nothing the question did not ask about. Comparisons and charts
are offered as follow-ups instead of being added unasked.
"""
from __future__ import annotations

import re

from . import metrics as M
from .common import change_tone, export, fmt_short, fmt_value, kpi, prev_cite, value_cite, yes
from .evidence import highlight
from .fmt import CO2, exact, join, lc, num, pct, short_name, tile
from .public import FLAG_NOTE, TOPIC, item

BOOL_PHRASE = {
    "232": ("has a policy covering Principle 6 (environment)", "does not report a policy covering Principle 6 (environment)",
            "have a policy covering Principle 6 (environment)"),
    "241": ("has had this policy approved by its Board", "does not report Board approval of this policy",
            "report Board approval of the policy"),
    "250": ("provides a public web link to its policies", "does not provide a public web link to its policies",
            "provide a public web link to their policies"),
    "259": ("has translated the policy into procedures", "does not report translating the policy into procedures",
            "have translated the policy into procedures"),
    "268": ("extends its policies to value chain partners", "does not extend its policies to value chain partners",
            "extend their policies to value chain partners"),
    "344": ("has had the working of its policies independently assessed by an external agency",
            "does not report an independent assessment of the working of its policies",
            "report an independent assessment of their policies"),
    "1329": ("treats the GHG emissions disclosure as applicable", "marks the GHG emissions disclosure as not applicable",
             "treat the GHG emissions disclosure as applicable"),
    "1340": ("has had its GHG emissions independently assessed or assured by an external agency",
             "does not report independent assessment or assurance of its GHG emissions",
             "report independent assurance of their GHG emissions"),
    "1341": ("has projects to reduce GHG emissions", "does not report projects to reduce GHG emissions",
             "report projects to reduce GHG emissions"),
    "1387": ("reports Scope 3 emissions", "does not report Scope 3 emissions", "report Scope 3 emissions"),
    "1560": ("has had its Scope 3 emissions independently assured", "does not report independent assurance of its Scope 3 emissions",
             "report independent assurance of their Scope 3 emissions"),
}
BOOL_TITLE = {"232": "Environment policy", "241": "Board approval of the policy", "250": "Public link to policies",
              "259": "Policy translated into procedures", "268": "Policy coverage of value chain partners",
              "344": "Independent assessment of policies", "1329": "GHG emissions disclosure",
              "1340": "Independent assurance of GHG emissions", "1341": "Projects to reduce GHG emissions",
              "1387": "Scope 3 emissions disclosure", "1560": "Independent assurance of Scope 3 emissions"}
TEXT_TITLE = {"286": "Commitments, goals and targets", "295": "Performance against targets",
              "1342": "Projects to reduce GHG emissions", "277": "Codes, certifications and standards"}
SIM_METRICS = ("scope1", "scope2", "scope12", "scope3", "intensity", "scope3_intensity")


def kicker(ctx, c) -> str:
    s = ctx.kb.sector_of(c)["name"]
    mine = ctx.plan.used_context.get("lens") == c["id"]
    return f"{'Your company · ' if mine else ''}{short_name(c['name'])} · {s}"


def vs_prev(y: float | None, prev_text: str) -> str:
    """'3.9% lower than in FY 2023-24 (410.06 tCO₂e)'."""
    if y is None:
        return f"FY 2023-24: {prev_text}"
    if round(y, 1) == 0:
        return f"unchanged from FY 2023-24 ({prev_text})"
    return f"{abs(y):.1f}% {'higher' if y > 0 else 'lower'} than in FY 2023-24 ({prev_text})"


def _delta(y):
    return (pct(y) + " vs FY 2023-24") if y is not None else None


def _tile(metric: M.Metric, c, label: str, cite: str | None = None):
    v, y = metric.value(c), metric.yoy(c) if metric.yoy else None
    if v is None:
        return kpi(label, "Not disclosed", sub="FY 2024-25")
    if metric.kind == "intensity" and metric.level_ok is not None and not metric.level_ok(c):
        return kpi(label, "See note", sub="unit differs from most filings", cite=cite)
    shown = tile(v) if metric.kind == "abs" else num(v)
    return kpi(label, shown, sub=metric.unit if metric.comparable_levels else "unit as disclosed", delta=_delta(y),
               tone=change_tone(y, metric.better), cite=cite)


def quote_item(ctx, c, qid, k: int = 3) -> dict:
    """A passage exactly as the company disclosed it, with its most specific sentences marked."""
    a = ctx.a
    segs = ctx.index.by_cell.get((c["id"], qid), [])
    return {"key": f"{c['id']}:{qid}", "company": c["name"], "company_id": c["id"], "short": short_name(c["name"]),
            "sector": ctx.kb.sector_of(c)["name"], "topic": item(qid)[0], "text": c["values"][qid],
            "segments": [{"start": s["start"], "end": s["end"], "highlight": s["highlight"]} for s in highlight(segs, k=k)],
            "themes": ctx.kb.themes(c["id"], qid), "cite": a.c_filing(c, qid)}


# --------------------------------------------------------------------------- emissions (Scope 1 and Scope 2, side by side)

def company_emissions(ctx, c, generic: bool = True):
    """Scope 1 and Scope 2 as two separate figures, with the combined total alongside."""
    a = ctx.a
    a.company_ref(c)
    m1, m2, m12, m3 = (M.NUMERIC[k] for k in ("scope1", "scope2", "scope12", "scope3"))
    v1, v2, v3 = m1.value(c), m2.value(c), m3.value(c)
    a.kicker = kicker(ctx, c)
    a.title = "GHG emissions" if generic else "Scope 1 and Scope 2 emissions"
    short = short_name(c["name"])
    if v1 is None and v2 is None:
        a.status = "partial"
        a.p(f"**{c['name']}** has not disclosed Scope 1 or Scope 2 emissions for FY 2024-25 {a.c_filing(c, '1330')}.")
        a.follow(f"Tell me about {short}", f"What are {short}'s targets?")
        return
    parts = []
    c1 = c2 = None
    if v1 is not None:
        c1 = a.c_filing(c, "1330")
        parts.append(f"**Scope 1 emissions of {num(v1)} {CO2}** {c1}")
    if v2 is not None:
        c2 = a.c_filing(c, "1332")
        parts.append(f"**Scope 2 emissions of {num(v2)} {CO2}** {c2}")
    s = f"**{c['name']}** reported {join(parts)} for FY 2024-25"
    both = v1 is not None and v2 is not None
    c12 = value_cite(a, c, m12) if both else None
    if both:
        s += f", a combined {num(m12.value(c))} {CO2} {c12}"
    a.p(s + ".")
    if both and m12.prev(c) is not None and m12.yoy(c) is not None:
        a.p(f"The combined figure is {vs_prev(m12.yoy(c), num(m12.prev(c)) + ' ' + CO2)} {prev_cite(a, c, m12)}.")
    elif not both:
        a.p(f"Scope {'2' if v2 is None else '1'} emissions were not disclosed {a.c_filing(c, '1332' if v2 is None else '1330')}.")
    c3 = None
    if generic and v3 is not None:
        c3 = a.c_filing(c, "1388")
        a.p(f"It also reported Scope 3 emissions of {num(v3)} {CO2} {c3}.")
    tiles = [_tile(m1, c, "Scope 1", c1), _tile(m2, c, "Scope 2", c2)]
    if both:
        tiles.append(_tile(m12, c, "Scope 1 + Scope 2", c12))
    if generic and v3 is not None:
        tiles.append(_tile(m3, c, "Scope 3", c3))
    a.block("kpis", items=tiles, export=_emissions_export(c, generic))
    a.flag_notes(c, ["1330", "1331", "1332", "1333"])
    a.context.update({"metric": "scope12"})
    a.follow(f"How does {short} compare with its peers?", f"What is {short}'s emission intensity?",
             f"What are {short}'s targets?", f"Make an infographic for {short}")


def _emissions_export(c, with_scope3: bool):
    rows = []
    for mid in ("scope1", "scope2", "scope12") + (("scope3",) if with_scope3 else ()):
        m = M.NUMERIC[mid]
        rows.append([m.label, m.value(c), m.prev(c), None if m.yoy(c) is None else round(m.yoy(c), 2)])
    return export(f"{c['name']}: GHG emissions", ["Measure", "FY 2024-25 (tCO2e)", "FY 2023-24 (tCO2e)", "Change (%)"], rows)


# --------------------------------------------------------------------------- one figure

def company_numeric(ctx, c, metric: M.Metric):
    a = ctx.a
    a.company_ref(c)
    a.kicker = kicker(ctx, c)
    a.title = metric.label
    short = short_name(c["name"])
    v, pv, y = metric.value(c), metric.prev(c), metric.yoy(c) if metric.yoy else None
    if v is None:
        a.status = "partial"
        a.p(f"**{c['name']}** has not disclosed {lc(metric.label)} for FY 2024-25 {a.c_filing(c, metric.cy_q)}.")
        a.follow(f"What are {short}'s GHG emissions?", f"Tell me about {short}")
        return
    if metric.kind == "intensity" and metric.comparable_levels and not metric.level_ok(c):
        return _intensity_as_disclosed(ctx, c, metric)
    cy = value_cite(a, c, metric)
    s = f"**{c['name']}** reported **{lc(metric.label)} of {fmt_value(metric, v)}** for FY 2024-25 {cy}"
    py = None
    if pv is not None:
        py = prev_cite(a, c, metric)
        s += f", {vs_prev(y, fmt_value(metric, pv))} {py}"
    a.p(s + ".")
    unit = metric.unit if metric.comparable_levels else "unit as disclosed"
    tiles = [kpi("FY 2024-25", fmt_short(metric, v), sub=unit, cite=cy)]
    if pv is not None:
        tiles.append(kpi("FY 2023-24", fmt_short(metric, pv), sub=unit, cite=py))
    if y is not None:
        tiles.append(kpi("Change", pct(y), sub="vs FY 2023-24", tone=change_tone(y, metric.better),
                         delta="lower" if y < 0 else "higher" if y > 0 else "unchanged"))
    a.block("kpis", items=tiles, export=export(
        f"{c['name']}: {metric.label}", ["Measure", f"FY 2024-25 ({unit})", f"FY 2023-24 ({unit})", "Change (%)"],
        [[metric.label, v, pv, None if y is None else round(y, 2)]]))
    if metric.note:
        a.note("method", metric.note)
    a.flag_notes(c, metric.qids)
    a.context.update({"metric": metric.id})
    a.follow(f"How does {short} compare with its peers on {lc(metric.label)}?",
             f"What are {short}'s GHG emissions?" if metric.id not in ("scope1", "scope2") else
             f"What are {short}'s Scope {'2' if metric.id == 'scope1' else '1'} emissions?",
             f"What if {short} cuts {lc(metric.label)} by 10%?" if metric.id in SIM_METRICS else None)


def _intensity_as_disclosed(ctx, c, metric):
    """An intensity that seems to use a different unit: show the disclosed number untouched, and say so."""
    a = ctx.a
    short = short_name(c["name"])
    raw, raw_p, y = c["values"].get(metric.cy_q), c["values"].get(metric.py_q), metric.yoy(c) if metric.yoy else None
    s = (f"**{c['name']}** disclosed **{lc(metric.label)} of {exact(raw)}** per rupee of turnover for FY 2024-25 "
         f"{a.c_filing(c, metric.cy_q)}")
    if raw_p is not None:
        s += f", {vs_prev(y, exact(raw_p))} {a.c_filing(c, metric.py_q)}"
    a.p(s + ".")
    a.p("This figure appears to use a different unit from most filings, so it is shown exactly as disclosed and is "
        "not converted or compared with other companies.")
    tiles = [kpi("FY 2024-25", exact(raw), sub="as disclosed")]
    if raw_p is not None:
        tiles.append(kpi("FY 2023-24", exact(raw_p), sub="as disclosed"))
    if y is not None:
        tiles.append(kpi("Change", pct(y), sub="vs FY 2023-24", tone=change_tone(y, metric.better),
                         delta="lower" if y < 0 else "higher" if y > 0 else "unchanged"))
    a.block("kpis", items=tiles, export=export(f"{c['name']}: {metric.label}",
                                                ["Measure", "FY 2024-25 (as disclosed)", "FY 2023-24 (as disclosed)", "Change (%)"],
                                                [[metric.label, raw, raw_p, None if y is None else round(y, 2)]]))
    a.context.update({"metric": metric.id})
    a.follow(f"What are {short}'s GHG emissions?", f"Tell me about {short}")


# --------------------------------------------------------------------------- yes / no

def company_bool(ctx, c, qid):
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    a.kicker = kicker(ctx, c)
    a.title = BOOL_TITLE.get(qid, item(qid)[0])
    short = short_name(c["name"])
    is_yes = yes(c, qid)
    pos, neg, _ = BOOL_PHRASE[qid]
    a.p(f"**{'Yes' if is_yes else 'No'}.** {c['name']} {pos if is_yes else neg} {a.c_filing(c, qid)}.")
    raw = c["values"].get(qid)
    if qid == "250" and isinstance(raw, str):
        urls = re.findall(r"https?://\S+", raw)
        if urls:
            a.block("links", items=[u.rstrip(".,;)") for u in urls[:4]], title="Links as disclosed")
    comp = M.COMPANION_TEXT.get(qid)
    if is_yes and comp in ("1561", "353") and c["values"].get(comp):
        agency = str(c["values"][comp]).strip()
        if len(agency) <= 160:
            a.p(f"The agency named is {agency.rstrip('.')} {a.c_filing(c, comp)}.")
        else:
            a.block("quotes", items=[quote_item(ctx, c, comp, k=1)], title="As disclosed")
    sname = kb.sector_of(c)["name"]
    a.context.update({"metric": ctx.plan.metric})
    a.follow(f"Show {short}'s projects to reduce GHG emissions" if qid == "1341" and is_yes else None,
             f"How many {sname} companies {BOOL_PHRASE[qid][2]}?", f"Tell me about {short}")


# --------------------------------------------------------------------------- narrative

def company_text(ctx, c, qid):
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    a.kicker = kicker(ctx, c)
    a.title = TEXT_TITLE.get(qid, item(qid)[0])
    short = short_name(c["name"])
    topic = TOPIC.get(qid, lc(item(qid)[0]))
    text = c["values"].get(qid)
    if not text:
        a.status = "partial"
        if qid == "1342" and not yes(c, "1341"):
            a.p(f"**{c['name']}** does not report projects to reduce GHG emissions for FY 2024-25 {a.c_filing(c, '1341')}.")
        else:
            a.p(f"**{c['name']}** has not disclosed {topic} for FY 2024-25 {a.c_filing(c, qid)}.")
        a.follow(f"Examples of {_examples_topic(qid)} from {kb.sector_of(c)['name']} companies", f"Tell me about {short}")
        return
    it = quote_item(ctx, c, qid)
    n_hl = sum(1 for s in it["segments"] if s["highlight"])
    a.p(f"This is what **{c['name']}** disclosed on {topic} for FY 2024-25 {it['cite']}"
        + (". The most specific points are highlighted." if n_hl else "."))
    a.block("quotes", items=[it])
    a.context.update({"metric": ctx.plan.metric})
    a.follow(f"Examples of {_examples_topic(qid)} from {kb.sector_of(c)['name']} companies",
             f"What are {short}'s GHG emissions?", f"Make an infographic for {short}")


def _examples_topic(qid):
    return {"286": "targets", "295": "progress against targets", "1342": "GHG reduction projects",
            "277": "certifications"}.get(qid, "disclosures")


def company_category(ctx, c, qids):
    a = ctx.a
    a.company_ref(c)
    a.kicker = kicker(ctx, c)
    a.title = "Review of performance" if qids[0] == "308" else "Review frequency"
    for q in qids:
        v = c["values"].get(q)
        label = item(q)[0]
        a.p(f"{label}: **{v}** {a.c_filing(c, q)}." if v else f"{label}: not disclosed {a.c_filing(c, q)}.")
    a.follow(f"Tell me about {short_name(c['name'])}")


def company_metric(ctx, c, mid, generic: bool = True):
    if mid == "scope12":
        return company_emissions(ctx, c, generic)
    if mid in M.NUMERIC:
        return company_numeric(ctx, c, M.NUMERIC[mid])
    if mid in M.TEXT_Q:
        return company_text(ctx, c, M.TEXT_Q[mid])
    if mid in M.CATEGORY_Q:
        return company_category(ctx, c, M.CATEGORY_Q[mid])
    if mid in M.BOOL_Q:
        return company_bool(ctx, c, M.BOOL_Q[mid])
    if mid == "green_credits":
        a = ctx.a
        a.company_ref(c)
        a.status = "partial"
        a.kicker = kicker(ctx, c)
        a.title = "Green credits"
        a.p(f"Green credit figures are not available for {c['name']}. I can share its emissions, targets and projects "
            f"to reduce GHG emissions.")
        a.follow(f"Show {short_name(c['name'])}'s projects to reduce GHG emissions", f"What are {short_name(c['name'])}'s targets?")
        return
    return company_profile(ctx, c)


# --------------------------------------------------------------------------- profile

CHECKS = [("1340", "GHG emissions independently assured"), ("1387", "Scope 3 emissions reported"),
          ("1341", "Projects to reduce GHG emissions"), ("286", "Targets with timelines disclosed"),
          ("241", "Environment policy approved by the Board"), ("268", "Policy extends to value chain partners")]


def company_profile(ctx, c):
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    sname = kb.sector_of(c)["name"]
    short = short_name(c["name"])
    a.kicker = kicker(ctx, c)
    a.title = c["name"]
    m1, m2, m3, mi = (M.NUMERIC[k] for k in ("scope1", "scope2", "scope3", "intensity"))
    v1, v2 = m1.value(c), m2.value(c)
    c1 = a.c_filing(c, "1330") if v1 is not None else None
    c2 = a.c_filing(c, "1332") if v2 is not None else None
    if v1 is not None and v2 is not None:
        a.p(f"**{c['name']}** ({sname}) reported Scope 1 emissions of **{num(v1)} {CO2}** {c1} and Scope 2 emissions "
            f"of **{num(v2)} {CO2}** {c2} for FY 2024-25.")
    elif v1 is not None or v2 is not None:
        which, v, cc = ("Scope 1", v1, c1) if v1 is not None else ("Scope 2", v2, c2)
        a.p(f"**{c['name']}** ({sname}) reported {which} emissions of **{num(v)} {CO2}** {cc} for FY 2024-25.")
    else:
        a.p(f"**{c['name']}** ({sname}) has not disclosed Scope 1 or Scope 2 emissions for FY 2024-25 {a.c_filing(c, '1330')}.")
    c3 = a.c_filing(c, "1388") if m3.value(c) is not None else None
    ci = value_cite(a, c, mi) if mi.value(c) is not None else None
    a.block("kpis", items=[_tile(m1, c, "Scope 1", c1), _tile(m2, c, "Scope 2", c2), _tile(m3, c, "Scope 3", c3),
                           _tile(mi, c, "Emission intensity", ci)], export=_profile_export(c))
    checks = []
    for q, label in CHECKS:
        val = bool(c["values"].get(q)) if q == "286" else yes(c, q)
        checks.append({"label": label, "value": val, "cite": a.c_filing(c, q)})
    a.block("checklist", title="Climate disclosures at a glance", items=checks)
    a.flag_notes(c, ["1330", "1331", "1332", "1333"])
    if mi.value(c) is not None and not mi.level_ok(c):
        a.note("data", FLAG_NOTE["unit_check"])
    a.follow(f"What are {short}'s targets?", f"Show {short}'s projects to reduce GHG emissions",
             f"How does {short} compare with its peers?", f"Make an infographic for {short}")


def _profile_export(c):
    rows = []
    for mid in ("scope1", "scope2", "scope3", "intensity"):
        m = M.NUMERIC[mid]
        ok = m.kind != "intensity" or m.level_ok(c)
        rows.append([f"{m.label} ({m.unit})", m.value(c) if ok else None, m.prev(c) if ok else None,
                     None if m.yoy(c) is None else round(m.yoy(c), 2)])
    for q, label in CHECKS:
        val = bool(c["values"].get(q)) if q == "286" else yes(c, q)
        rows.append([label, "Yes" if val else "No", None, None])
    return export(f"{c['name']}: summary", ["Item", "FY 2024-25", "FY 2023-24", "Change (%)"], rows)


# --------------------------------------------------------------------------- your company

def set_lens(ctx, c):
    a = ctx.a
    a.company_ref(c)
    sname = ctx.kb.sector_of(c)["name"]
    a.kicker = "Your company"
    a.title = short_name(c["name"])
    a.p(f"Done. I will answer as **{c['name']}** ({sname}) from here on, so you can ask about “our emissions” or "
        f"“our peers” without naming the company.")
    a.context["lens"] = c["id"]
    a.follow("What are our GHG emissions?", "Who are our peers?", "How do we compare with our peers?",
             "Make an infographic of our emissions")


def clear_lens(ctx):
    a = ctx.a
    a.kicker = "Your company"
    a.title = "Company cleared"
    a.p("Done. I am no longer answering as a specific company. Name a company in your question, or set one again "
        "at any time.")
    a.context["lens"] = ""
    a.follow("What are NTPC's GHG emissions?", "Top 10 emitters")


def need_company(ctx):
    a = ctx.a
    a.status = "clarify"
    a.kicker = "One detail needed"
    a.title = "Which company?"
    a.p("Tell me which company you mean. You can name it in the question, or set your company once and then ask "
        "about “our emissions” or “our peers”.")
    a.block("action", action="set_company", label="Set your company")
    a.follow("What are UltraTech's GHG emissions?", "My company is Infosys", "How does Tata Power compare with its peers?")


# --------------------------------------------------------------------------- what-if

def simulate(ctx, c, mid, pct_cut):
    a = ctx.a
    a.company_ref(c)
    if mid not in SIM_METRICS:
        mid = "scope12"
    metric = M.NUMERIC[mid]
    short = short_name(c["name"])
    v, pv = metric.value(c), metric.prev(c)
    a.kicker = kicker(ctx, c)
    a.title = f"What if: lower {lc(metric.label)}"
    if v is None:
        a.status = "partial"
        a.p(f"A what-if needs a disclosed figure, and {c['name']} has not disclosed {lc(metric.label)} for FY 2024-25 "
            f"{a.c_filing(c, metric.cy_q or '1330')}.")
        a.follow(f"Tell me about {short}")
        return
    p = max(0.0, min(pct_cut if pct_cut is not None else 10.0, 100.0))
    new = v * (1 - p / 100)
    base = value_cite(a, c, metric)
    a.p(f"If {c['name']}'s FY 2024-25 {lc(metric.label)} had been **{p:g}% lower**, the figure would be "
        f"**{fmt_value(metric, new)}** instead of {fmt_value(metric, v)} {base}.")
    if pv:
        y1 = (new - pv) / pv * 100
        calc = a.c_calc("What-if arithmetic", f"{num(v)} × (1 − {p:g}%) = {num(new)}; ({num(new)} − {num(pv)}) ÷ {num(pv)} = {pct(y1, digits=2)}",
                        [base, prev_cite(a, c, metric)])
        a.p(f"That would be {vs_prev(y1, fmt_value(metric, pv))} {calc}.")
    if re.search(r"\b(median|average|peers?|sector|industry|typical)\b", ctx.plan.query.lower()) and metric.comparable_levels:
        from ..analytics import median
        from .common import eligible
        others = [m for m in ctx.kb.members(c["sector"]) if m["id"] != c["id"]]
        vals = [x for _, x in eligible(metric, others)]
        if vals and (metric.level_ok is None or metric.level_ok(c)):
            med = median(vals)
            sname = ctx.kb.sector_of(c)["name"]
            mc = a.c_calc(f"Peer median: {lc(metric.label)}", f"Median of the {len(vals)} other {sname} companies that disclosed "
                          f"this figure = {fmt_value(metric, med)}")
            if v > med:
                a.p(f"To match the peer median of {fmt_value(metric, med)} {mc}, it would need a cut of about "
                    f"**{(1 - med / v) * 100:.1f}%**.")
            else:
                a.p(f"It is already at or below the peer median of {fmt_value(metric, med)} {mc}.")
    a.note("method", "This is arithmetic on the disclosed figure, not a forecast.")
    a.block("simulator", company=short, metric=metric.label, unit=metric.unit, cy=v, py=pv, pct=p)
    a.flag_notes(c, metric.qids)
    a.context.update({"metric": mid})
    a.follow(f"What if {short} cuts it by {int(min(p * 2, 50))}%?",
             f"Show {short}'s projects to reduce GHG emissions", f"How does {short} compare with its peers?")
