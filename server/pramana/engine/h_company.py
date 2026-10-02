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
from .fmt import CO2, clip, exact, join, lc, num, pct, short_name, tile
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


RE_CHART = re.compile(r"\b(charts?|graphs?|plot|plots|visuali[sz]e|visuali[sz]ation|visual|diagram|pie)\b")


def _years_chart(a, c, rows):
    """Both years side by side, one group per scope."""
    rows = [(lab, m) for lab, m in rows if m.value(c) is not None or m.prev(c) is not None]
    if not rows:
        return
    short = short_name(c["name"])
    vals = [x for _, m in rows for x in (m.prev(c), m.value(c)) if x and x > 0]
    a.block("grouped", title="FY 2023-24 and FY 2024-25", subtitle=f"{short}, {CO2}", series=["FY 2023-24", "FY 2024-25"],
            groups=[{"label": lab, "values": [m.prev(c), m.value(c)],
                     "displays": [tile(m.prev(c)) if m.prev(c) is not None else "n/a", tile(m.value(c)) if m.value(c) is not None else "n/a"]}
                    for lab, m in rows],
            log=len(vals) > 1 and max(vals) / min(vals) > 50,
            export=export(f"{c['name']}: emissions in both years",
                          ["Scope", "FY 2023-24 (tCO2e)", "FY 2024-25 (tCO2e)", "Change (%)"],
                          [[lab, m.prev(c), m.value(c), None if m.yoy(c) is None else round(m.yoy(c), 2)] for lab, m in rows]))


def _tidy(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().rstrip(".").replace(" :", ":")


def _looks_like_name(text: str) -> bool:
    """'Deloitte Haskins & Sells LLP' is a name; 'Yes, independent assurance was carried out by ...' is a sentence."""
    t = _tidy(text)
    return len(t.split()) <= 9 and not re.match(r"(?i)(yes|no|not|the|this|our|we|it|independent|assurance|na\b|n/a)", t) \
        and not re.search(r"(?i)\b(was|were|is|are|has|have|been|carried|conducted|obtained|done|by)\b", t)


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


def _share(p: float) -> str:
    return "<0.1%" if 0 < p < 0.1 else f"{p:.1f}%" if p < 10 else f"{p:.0f}%"


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
    if ctx.plan.period == "PY" and (m1.prev(c) is not None or m2.prev(c) is not None):
        return _emissions_prev(ctx, c, generic)
    if ctx.plan.period == "PY":
        a.p(f"**{c['name']}** has not disclosed Scope 1 or Scope 2 emissions for FY 2023-24 {a.c_filing(c, '1331')}. "
            f"The FY 2024-25 figures are shown instead.")
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
    if RE_CHART.search(ctx.plan.query.lower()):
        _years_chart(a, c, [(lab, m) for lab, m in (("Scope 1", m1), ("Scope 2", m2)) + ((("Scope 3", m3),) if generic else ())
                            if m.value(c) is not None])
    a.flag_notes(c, ["1330", "1331", "1332", "1333"])
    a.context.update({"metric": "scope12"})
    a.follow(f"How does {short} compare with its peers?", f"What is {short}'s emission intensity?",
             f"What are {short}'s targets?", f"Make an infographic for {short}")


def _emissions_prev(ctx, c, generic: bool):
    """The same answer for the previous year, when the question asks for FY 2023-24."""
    a = ctx.a
    m1, m2, m12, m3 = (M.NUMERIC[k] for k in ("scope1", "scope2", "scope12", "scope3"))
    p1, p2, p3 = m1.prev(c), m2.prev(c), m3.prev(c)
    short = short_name(c["name"])
    a.title += ", FY 2023-24"
    parts, c1, c2 = [], None, None
    if p1 is not None:
        c1 = a.c_filing(c, "1331")
        parts.append(f"**Scope 1 emissions of {num(p1)} {CO2}** {c1}")
    if p2 is not None:
        c2 = a.c_filing(c, "1333")
        parts.append(f"**Scope 2 emissions of {num(p2)} {CO2}** {c2}")
    both = p1 is not None and p2 is not None
    line = f"**{c['name']}** reported {join(parts)} for FY 2023-24"
    c12 = prev_cite(a, c, m12) if both and m12.prev(c) is not None else None
    if c12:
        line += f", a combined {num(m12.prev(c))} {CO2} {c12}"
    a.p(line + ".")
    tiles = []
    if p1 is not None:
        tiles.append(kpi("Scope 1 · FY 2023-24", tile(p1), sub=CO2, cite=c1))
    if p2 is not None:
        tiles.append(kpi("Scope 2 · FY 2023-24", tile(p2), sub=CO2, cite=c2))
    if c12:
        tiles.append(kpi("Scope 1 + Scope 2 · FY 2023-24", tile(m12.prev(c)), sub=CO2, cite=c12))
    y = m12.yoy(c)
    if c12 and m12.value(c) is not None and y is not None:
        cy = value_cite(a, c, m12)
        how = "unchanged" if round(y, 1) == 0 else f"{abs(y):.1f}% {'higher' if y > 0 else 'lower'}"
        a.p(f"For FY 2024-25 the combined figure was {num(m12.value(c))} {CO2} {cy}, {how}.")
        tiles.append(kpi("Scope 1 + Scope 2 · FY 2024-25", tile(m12.value(c)), sub=CO2, delta=_delta(y),
                         tone=change_tone(y), cite=cy))
    if generic and p3 is not None:
        c3 = a.c_filing(c, "1389")
        a.p(f"It also reported Scope 3 emissions of {num(p3)} {CO2} for FY 2023-24 {c3}.")
        tiles.append(kpi("Scope 3 · FY 2023-24", tile(p3), sub=CO2, cite=c3))
    a.block("kpis", items=tiles, export=_emissions_export(c, generic))
    a.flag_notes(c, ["1330", "1331", "1332", "1333"])
    a.context.update({"metric": "scope12"})
    a.follow(f"How did {short}'s emissions change?", f"What are {short}'s GHG emissions for FY 2024-25?",
             f"How does {short} compare with its peers?")


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
        if pv is not None and metric.py_q:
            a.p(f"**{c['name']}** has not disclosed {lc(metric.label)} for FY 2024-25 {a.c_filing(c, metric.cy_q)}. For "
                f"FY 2023-24 it reported {fmt_value(metric, pv)} {a.c_filing(c, metric.py_q)}.")
        elif ctx.plan.period == "PY":
            a.p(f"**{c['name']}** has not disclosed {lc(metric.label)} for FY 2023-24 or FY 2024-25 {a.c_filing(c, metric.cy_q)}.")
        else:
            a.p(f"**{c['name']}** has not disclosed {lc(metric.label)} for FY 2024-25 {a.c_filing(c, metric.cy_q)}.")
        a.follow(f"What are {short}'s GHG emissions?", f"Tell me about {short}")
        return
    if metric.kind == "intensity" and metric.comparable_levels and not metric.level_ok(c):
        return _intensity_as_disclosed(ctx, c, metric)
    cy = value_cite(a, c, metric)
    py = prev_cite(a, c, metric) if pv is not None else None
    prev_first = ctx.plan.period == "PY"
    if prev_first and pv is not None:
        a.title += ", FY 2023-24"
        s = f"**{c['name']}** reported **{lc(metric.label)} of {fmt_value(metric, pv)}** for FY 2023-24 {py}"
        if y is not None:
            how = "unchanged" if round(y, 1) == 0 else f"{abs(y):.1f}% {'higher' if y > 0 else 'lower'}"
            s += f". The FY 2024-25 figure is {fmt_value(metric, v)} {cy}, {how}"
        else:
            s += f". The FY 2024-25 figure is {fmt_value(metric, v)} {cy}"
    else:
        if prev_first:
            a.p(f"**{c['name']}** has not disclosed {lc(metric.label)} for FY 2023-24 {a.c_filing(c, metric.py_q)}."
                if metric.py_q else f"A FY 2023-24 figure is not available for {c['name']}.")
        s = f"**{c['name']}** reported **{lc(metric.label)} of {fmt_value(metric, v)}** for FY 2024-25 {cy}"
        if pv is not None:
            s += f", {vs_prev(y, fmt_value(metric, pv))} {py}"
    a.p(s + ".")
    unit = metric.unit if metric.comparable_levels else "unit as disclosed"
    tiles = [kpi("FY 2024-25", fmt_short(metric, v), sub=unit, cite=cy)]
    if pv is not None:
        tiles.insert(0 if prev_first else 1, kpi("FY 2023-24", fmt_short(metric, pv), sub=unit, cite=py))
    if y is not None:
        tiles.append(kpi("Change", pct(y), sub="vs FY 2023-24", tone=change_tone(y, metric.better),
                         delta="lower" if y < 0 else "higher" if y > 0 else "unchanged"))
    a.block("kpis", items=tiles, export=export(
        f"{c['name']}: {metric.label}", ["Measure", f"FY 2024-25 ({unit})", f"FY 2023-24 ({unit})", "Change (%)"],
        [[metric.label, v, pv, None if y is None else round(y, 2)]]))
    if metric.note:
        a.note("method", metric.note)
    if re.search(r"\b(breakdown|break up|categor\w+|split|by source|sources)\b", ctx.plan.query.lower()) and metric.kind == "abs":
        a.note("scope", f"A breakdown of {lc(metric.label)} by category or source is not available, so the total is shown.")
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
    raw = c["values"].get(qid)
    if ctx.plan.who and qid in ("1340", "1560", "344"):
        # "who assured our emissions": the answer is a name, or a plain statement that none is given
        a.p(f"**{c['name']}** {pos if is_yes else neg} {a.c_filing(c, qid)}.")
        comp = M.COMPANION_TEXT.get(qid)
        agency = str(c["values"].get(comp) or "").strip() if comp else ""
        if is_yes and agency and len(agency) <= 160 and _looks_like_name(agency):
            a.p(f"The agency named is **{_tidy(agency)}** {a.c_filing(c, comp)}.")
        elif is_yes and agency and len(agency) <= 260:
            a.p(f"Its disclosure states: “{_tidy(agency)}” {a.c_filing(c, comp)}.")
        elif is_yes and agency:
            a.block("quotes", items=[quote_item(ctx, c, comp, k=1)], title="As disclosed")
        elif not is_yes:
            a.p("No agency is named.")
        else:
            a.p("The name of the agency is not part of this disclosure.")
            s3 = str(c["values"].get("1561") or "").strip()
            if qid == "1340" and yes(c, "1560") and s3 and len(s3) <= 160 and _looks_like_name(s3):
                a.p(f"For its Scope 3 emissions, the agency named is **{_tidy(s3)}** {a.c_filing(c, '1561')}.")
            elif qid == "1340" and yes(c, "1560") and s3 and len(s3) <= 260:
                a.p(f"On its Scope 3 emissions, the disclosure states: “{_tidy(s3)}” {a.c_filing(c, '1561')}.")
        a.context.update({"metric": ctx.plan.metric})
        a.follow(f"Tell me about {short}", f"How many {kb.sector_of(c)['name']} companies {BOOL_PHRASE[qid][2]}?")
        return
    low = (ctx.plan.resolved_query or ctx.plan.query).lower()
    if qid == "232" and is_yes and re.search(r"\b(say|says|state|states|contain\w*|covers?|text|read|content)\b", low):
        a.p(f"**{c['name']}** {pos} {a.c_filing(c, qid)}. The text of the policy is not part of its BRSR disclosure.")
        link = c["values"].get("250")
        urls = re.findall(r"https?://\S+", link) if isinstance(link, str) else []
        if urls:
            a.p(f"It gives a public link to its policies {a.c_filing(c, '250')}.")
            a.block("links", items=[u.rstrip(".,;)") for u in urls[:4]], title="Links as disclosed")
        a.follow(f"Is {short}'s policy approved by the Board?", f"Tell me about {short}")
        return
    a.p(f"**{'Yes' if is_yes else 'No'}.** {c['name']} {pos if is_yes else neg} {a.c_filing(c, qid)}.")
    if qid == "1387" and is_yes and c["values"].get("1388") is not None:
        m3 = M.NUMERIC["scope3"]
        line = f"It reported Scope 3 emissions of **{num(m3.value(c))} {CO2}** for FY 2024-25 {a.c_filing(c, '1388')}"
        if m3.prev(c) is not None and m3.yoy(c) is not None:
            line += f", {vs_prev(m3.yoy(c), num(m3.prev(c)) + ' ' + CO2)} {a.c_filing(c, '1389')}"
        a.p(line + ".")
    if qid == "250" and isinstance(raw, str):
        urls = re.findall(r"https?://\S+", raw)
        if urls:
            a.block("links", items=[u.rstrip(".,;)") for u in urls[:4]], title="Links as disclosed")
    comp = M.COMPANION_TEXT.get(qid)
    if is_yes and comp in ("1561", "353") and c["values"].get(comp):
        agency = str(c["values"][comp]).strip()
        if len(agency) <= 160 and _looks_like_name(agency):
            a.p(f"The agency named is {_tidy(agency)} {a.c_filing(c, comp)}.")
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
        no = "**No.** " if ctx.plan.yesno and not ctx.plan.negated else ""
        who = c["name"] if no else f"**{c['name']}**"
        if qid == "1342" and not yes(c, "1341"):
            a.p(f"{no}{who} does not report projects to reduce GHG emissions for FY 2024-25 {a.c_filing(c, '1341')}.")
        else:
            a.p(f"{no}{who} has not disclosed {topic} for FY 2024-25 {a.c_filing(c, qid)}.")
        a.follow(f"Examples of {_examples_topic(qid)} from {kb.sector_of(c)['name']} companies", f"Tell me about {short}")
        return
    it = quote_item(ctx, c, qid)
    n_hl = sum(1 for s in it["segments"] if s["highlight"])
    asks_exists = ctx.plan.yesno and not ctx.plan.negated and qid != "295" and not re.search(
        r"\b(met|meet|meeting|achiev\w*|on track|hit|reach\w*|deliver\w*|progress\w*|enough|ambitious|good)\b",
        (ctx.plan.resolved_query or ctx.plan.query).lower())
    # a long disclosure: its most specific sentences first, as points; the full text one click away
    keys = [clip(text[s["start"]:s["end"]], 230) for s in it["segments"] if s["highlight"]][:4]
    focus_note = ""
    fs = ctx.plan.focus_scope
    if fs:
        from .h_practice import FOCUS
        rx = FOCUS[fs][0] if fs in FOCUS else None
        on = [s for s in it["segments"] if rx and rx.search(text[s["start"]:s["end"]])]
        label = {"scope1": "Scope 1", "scope2": "Scope 2", "scope3": "Scope 3"}[fs]
        if on:
            keep = {id(s) for s in on[:4]}
            for s in it["segments"]:
                s["highlight"] = id(s) in keep
            keys = [clip(text[s["start"]:s["end"]], 230) for s in on[:4]]
            focus_note = f" The points below are the ones that concern {label}."
        else:
            focus_note = f" It does not mention {label} specifically; its key points are below."
    summarised = (len(text) > 700 and len(keys) >= 2) or (bool(fs) and len(keys) >= 1)
    tail = ("The key points are below, in the company's own words." if summarised else
            "The most specific points are highlighted." if n_hl else "")
    if focus_note:
        tail = focus_note.strip()
    if asks_exists:
        a.p(f"**Yes.** {c['name']} has disclosed {topic} for FY 2024-25 {it['cite']}. " + (tail or "The disclosure is shown below."))
    else:
        a.p(f"This is what **{c['name']}** disclosed on {topic} for FY 2024-25 {it['cite']}." + (f" {tail}" if tail else ""))
    if summarised:
        a.block("points", title="Key points", items=[], verbatim=keys)
        a.block("quotes", items=[it], collapsed=True, summary="View the full disclosure")
    else:
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
    scopes = [(lab, m.value(c)) for lab, m in (("Scope 1", m1), ("Scope 2", m2), ("Scope 3", m3)) if (m.value(c) or 0) > 0]
    if len(scopes) >= 2:
        total = sum(v for _, v in scopes)
        a.block("stack", title="Emissions by scope", subtitle="Share of disclosed emissions, FY 2024-25", categorical=True,
                rows=[{"label": short, "segments": [{"label": f"{lab} {_share(100 * v / total)}", "value": v,
                                                      "display": f"{num(v)} {CO2}"} for lab, v in scopes]}],
                export=export(f"{c['name']}: emissions by scope", ["Scope", "Emissions (tCO2e)", "Share (%)"],
                              [[lab, v, round(100 * v / total, 2)] for lab, v in scopes]))
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
    base = value_cite(a, c, metric)
    if v == 0:
        a.p(f"{c['name']} reported {lc(metric.label)} of zero for FY 2024-25 {base}, so a what-if on this figure would "
            f"not change it.")
        a.follow(f"What are {short}'s GHG emissions?", f"Tell me about {short}")
        return
    low = (ctx.plan.resolved_query or ctx.plan.query).lower()
    if re.search(r"\b(rise|rises|rose|rising|increas\w*|grow|grows|grew|growth|higher|go(?:es)? up|went up|up by|more)\b", low) \
            and not re.search(r"\b(cut|cuts|reduc\w*|lower\w*|decreas\w*|less|halv\w*)\b", low):
        # an increase: plain arithmetic, shown as figures (the slider is for cuts)
        p = max(0.0, min(pct_cut if pct_cut is not None else 10.0, 500.0))
        new = v * (1 + p / 100)
        a.title = f"What if: higher {lc(metric.label)}"
        a.p(f"If {c['name']}'s FY 2024-25 {lc(metric.label)} had been **{p:g}% higher**, the figure would be "
            f"**{fmt_value(metric, new)}** instead of {fmt_value(metric, v)} {base}.")
        tiles = [kpi("FY 2024-25, as disclosed", fmt_short(metric, v), sub=metric.unit, cite=base),
                 kpi(f"With a {p:g}% rise", fmt_short(metric, new), sub=metric.unit)]
        if pv:
            y1 = (new - pv) / pv * 100
            calc = a.c_calc("What-if arithmetic", f"{num(v)} × (1 + {p:g}%) = {num(new)}; ({num(new)} − {num(pv)}) ÷ {num(pv)} = {pct(y1, digits=2)}",
                            [base, prev_cite(a, c, metric)])
            a.p(f"That would be {vs_prev(y1, fmt_value(metric, pv))} {calc}.")
            tiles.insert(0, kpi("FY 2023-24, as disclosed", fmt_short(metric, pv), sub=metric.unit))
        a.block("kpis", items=tiles)
        a.note("method", "This is arithmetic on the disclosed figure, not a forecast.")
        a.flag_notes(c, metric.qids)
        a.context.update({"metric": mid})
        a.follow(f"What if {short} cuts {lc(metric.label)} by {p:g}%?", f"How did {short}'s emissions change?")
        return
    target = None
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
                target = (1 - med / v) * 100
                a.p(f"To match the peer median of {fmt_value(metric, med)} {mc}, {c['name']} would need to cut its "
                    f"{lc(metric.label)} of {fmt_value(metric, v)} {base} by about **{target:.1f}%**.")
            else:
                a.p(f"{c['name']}'s {lc(metric.label)} of {fmt_value(metric, v)} {base} is already at or below the peer "
                    f"median of {fmt_value(metric, med)} {mc}, so no cut is needed to match it.")
    p = max(0.0, min(pct_cut if pct_cut is not None else (round(target) if target and 1 <= target <= 60 else 10.0), 100.0))
    new = v * (1 - p / 100)
    a.p(f"If {c['name']}'s FY 2024-25 {lc(metric.label)} had been **{p:g}% lower**, the figure would be "
        f"**{fmt_value(metric, new)}** instead of {fmt_value(metric, v)} {base}.")
    if pv:
        y1 = (new - pv) / pv * 100
        calc = a.c_calc("What-if arithmetic", f"{num(v)} × (1 − {p:g}%) = {num(new)}; ({num(new)} − {num(pv)}) ÷ {num(pv)} = {pct(y1, digits=2)}",
                        [base, prev_cite(a, c, metric)])
        a.p(f"That would be {vs_prev(y1, fmt_value(metric, pv))} {calc}.")
    a.note("method", "This is arithmetic on the disclosed figure, not a forecast.")
    a.block("simulator", company=short, metric=metric.label, unit=metric.unit, cy=v, py=pv, pct=p)
    a.flag_notes(c, metric.qids)
    a.context.update({"metric": mid})
    a.follow(f"What if {short} cuts it by {int(min(p * 2, 50))}%?",
             f"Show {short}'s projects to reduce GHG emissions", f"How does {short} compare with its peers?")


# --------------------------------------------------------------------------- how a figure moved between the two years

RE_ASKS_DOWN = re.compile(r"\b(reduc\w*|cut|cuts|cutting|lower\w*|decreas\w*|declin\w*|fall\w*|fell|drop\w*|down|improv\w*)\b")
RE_ASKS_UP = re.compile(r"\b(increas\w*|rise|risen|rising|rose|grow\w*|grew|up|higher|worsen\w*)\b")


def _moved(y: float, plural: bool = True) -> str:
    if round(y, 1) == 0:
        return "were unchanged" if plural else "was unchanged"
    return f"{'rose' if y > 0 else 'fell'} **{abs(y):.1f}%**"


def _yes_no(ctx, y: float) -> str:
    """'Yes.' or 'No.' when the question was 'did emissions go down?' or 'did they go up?'."""
    plan = ctx.plan
    if not plan.yesno or round(y, 1) == 0:
        return ""
    low = (plan.resolved_query or plan.query).lower()
    if RE_ASKS_DOWN.search(low) and RE_ASKS_UP.search(low):
        return ""                                     # "did it go up or down" is not a yes/no question
    if RE_ASKS_DOWN.search(low):
        return "**Yes.** " if y < 0 else "**No.** "
    if RE_ASKS_UP.search(low):
        return "**Yes.** " if y > 0 else "**No.** "
    return ""


def company_change(ctx, c, mid, generic: bool = True):
    """Leads with the direction and size of the change, then shows both years."""
    a = ctx.a
    a.company_ref(c)
    a.kicker = kicker(ctx, c)
    short = short_name(c["name"])
    if mid in M.NUMERIC and mid != "scope12":
        metric = M.NUMERIC[mid]
        a.title = f"Change in {lc(metric.label)}"
        v, pv, y = metric.value(c), metric.prev(c), metric.yoy(c) if metric.yoy else None
        if v is None or pv is None or y is None:
            a.status = "partial"
            fy, q = ("FY 2024-25", metric.cy_q) if v is None else ("FY 2023-24", metric.py_q)
            a.p(f"The change cannot be worked out, because **{c['name']}** has not disclosed {lc(metric.label)} for "
                f"{fy} {a.c_filing(c, q)}.")
            if v is not None:
                a.p(f"For FY 2024-25 it reported {fmt_value(metric, v)} {value_cite(a, c, metric)}.")
            a.follow(f"What are {short}'s GHG emissions?", f"Tell me about {short}")
            return
        if metric.kind == "intensity" and metric.comparable_levels and not metric.level_ok(c):
            return _intensity_as_disclosed(ctx, c, metric)
        cy, py = value_cite(a, c, metric), prev_cite(a, c, metric)
        if round(y, 1) == 0:
            a.p(f"**{c['name']}**'s {lc(metric.label)} was unchanged at {fmt_value(metric, v)} {cy} between FY 2023-24 "
                f"and FY 2024-25 {py}.")
        else:
            a.p(f"{_yes_no(ctx, y)}**{c['name']}**'s {lc(metric.label)} {'rose' if y > 0 else 'fell'} **{abs(y):.1f}%**, "
                f"from {fmt_value(metric, pv)} in FY 2023-24 {py} to {fmt_value(metric, v)} in FY 2024-25 {cy}.")
        unit = metric.unit if metric.comparable_levels else "unit as disclosed"
        a.block("kpis", items=[
            kpi("FY 2023-24", fmt_short(metric, pv), sub=unit, cite=py),
            kpi("FY 2024-25", fmt_short(metric, v), sub=unit, cite=cy),
            kpi("Change", pct(y), sub="vs FY 2023-24", tone=change_tone(y, metric.better),
                delta="lower" if y < 0 else "higher" if y > 0 else "unchanged")],
            export=export(f"{c['name']}: {metric.label}", ["Measure", f"FY 2023-24 ({unit})", f"FY 2024-25 ({unit})", "Change (%)"],
                          [[metric.label, pv, v, round(y, 2)]]))
        if metric.note:
            a.note("method", metric.note)
        a.flag_notes(c, metric.qids)
        a.context.update({"metric": metric.id})
        a.follow(f"How did {short}'s emissions change?" if mid != "intensity" else f"What are {short}'s GHG emissions?",
                 f"How does {short} compare with its peers on {lc(metric.label)}?",
                 f"Show {short}'s projects to reduce GHG emissions")
        return

    m1, m2, m12, m3 = (M.NUMERIC[k] for k in ("scope1", "scope2", "scope12", "scope3"))
    a.title = "Change in GHG emissions"
    y12 = m12.yoy(c) if m12.value(c) is not None and m12.prev(c) is not None else None
    rows = [(lab, m) for lab, m in (("Scope 1", m1), ("Scope 2", m2)) if m.value(c) is not None and m.prev(c) is not None
            and m.yoy(c) is not None]
    if y12 is None and not rows:
        a.status = "partial"
        a.p(f"The change cannot be worked out, because **{c['name']}** has not disclosed Scope 1 and Scope 2 emissions "
            f"for both FY 2023-24 and FY 2024-25 {a.c_filing(c, '1331')}.")
        if m1.value(c) is not None or m2.value(c) is not None:
            a.follow(f"What are {short}'s GHG emissions?")
        a.follow(f"Tell me about {short}")
        return
    if y12 is not None:
        cy, py = value_cite(a, c, m12), prev_cite(a, c, m12)
        if round(y12, 1) == 0:
            a.p(f"**{c['name']}**'s combined Scope 1 and Scope 2 emissions were unchanged at {num(m12.value(c))} {CO2} {cy} "
                f"between FY 2023-24 and FY 2024-25 {py}.")
        else:
            a.p(f"{_yes_no(ctx, y12)}**{c['name']}**'s combined Scope 1 and Scope 2 emissions {'rose' if y12 > 0 else 'fell'} "
                f"**{abs(y12):.1f}%**, from {num(m12.prev(c))} {CO2} in FY 2023-24 {py} to {num(m12.value(c))} {CO2} in "
                f"FY 2024-25 {cy}.")
    parts = [f"{lab} emissions {_moved(m.yoy(c)).replace('**', '')} {value_cite(a, c, m, 'yoy')}" for lab, m in rows]
    if generic and m3.value(c) is not None and m3.prev(c) is not None and m3.yoy(c) is not None:
        rows.append(("Scope 3", m3))
        parts.append(f"Scope 3 emissions {_moved(m3.yoy(c)).replace('**', '')} {value_cite(a, c, m3, 'yoy')}")
    if parts:
        a.p("By scope: " + join(parts) + ".")
    tiles = [_tile(m, c, lab, a.c_filing(c, m.cy_q)) for lab, m in rows]
    if y12 is not None:
        tiles.insert(min(2, len(tiles)), _tile(m12, c, "Scope 1 + Scope 2"))
    a.block("kpis", items=tiles, export=_emissions_export(c, generic))
    _years_chart(a, c, rows)
    a.flag_notes(c, ["1330", "1331", "1332", "1333"])
    a.context.update({"metric": "scope12"})
    a.follow(f"Show {short}'s projects to reduce GHG emissions", f"How does {short} compare with its peers?",
             f"What are {short}'s targets?")


# --------------------------------------------------------------------------- the scopes within one company

SCOPE_LABEL = {"scope1": "Scope 1", "scope2": "Scope 2", "scope3": "Scope 3"}
SCOPE_Q = {"scope1": "1330", "scope2": "1332", "scope3": "1388"}


def _times(r: float) -> str:
    return f"{r:,.0f}" if r >= 20 else f"{r:.1f}"


def company_scopes(ctx, c):
    """Which scope is largest, or how two scopes compare, for one company."""
    a = ctx.a
    a.company_ref(c)
    a.kicker = kicker(ctx, c)
    a.title = "Emissions by scope"
    short = short_name(c["name"])
    have = [(k, M.NUMERIC[k].value(c)) for k in ("scope1", "scope2", "scope3") if (M.NUMERIC[k].value(c) or 0) > 0]
    if len(have) < 2:
        return company_emissions(ctx, c, True)
    total = sum(v for _, v in have)
    cites = {k: a.c_filing(c, SCOPE_Q[k]) for k, _ in have}
    vals = dict(have)
    named = [k for k in ctx.plan.raw_metrics if k in vals]
    labels = join([SCOPE_LABEL[k] for k, _ in have])
    calc = a.c_calc(f"Share of each scope ({short})", f"Each scope ÷ total of {labels} ({num(total)} {CO2})")
    if len(named) >= 2:
        x, y = named[0], named[1]
        vx, vy = vals[x], vals[y]
        big, small = (x, y) if vx >= vy else (y, x)
        r = vals[big] / vals[small]
        rc = a.c_calc(f"{SCOPE_LABEL[big]} relative to {SCOPE_LABEL[small]} ({short})",
                      f"{num(vals[big])} ÷ {num(vals[small])} = {r:,.2f}", [cites[big], cites[small]])
        rel = "the same as" if r == 1 else (f"about {_times(r)} times" if r >= 1.5 else f"{(r - 1) * 100:.0f}% higher than")
        a.p(f"**{c['name']}** reported {SCOPE_LABEL[x]} emissions of **{num(vx)} {CO2}** {cites[x]} and {SCOPE_LABEL[y]} "
            f"emissions of **{num(vy)} {CO2}** {cites[y]} for FY 2024-25. {SCOPE_LABEL[big]} is {rel} "
            f"{SCOPE_LABEL[small]} {rc}.")
    else:
        k, v = max(have, key=lambda t: t[1])
        a.p(f"**{SCOPE_LABEL[k]}** is the largest part of {c['name']}'s disclosed emissions for FY 2024-25: "
            f"**{num(v)} {CO2}** {cites[k]}, {_share(100 * v / total)} of the total across {labels} {calc}.")
    a.block("kpis", items=[kpi(SCOPE_LABEL[k], tile(v), sub=f"{_share(100 * v / total)} of the total", cite=cites[k])
                           for k, v in have])
    a.block("stack", title="Emissions by scope", subtitle="Share of disclosed emissions, FY 2024-25", categorical=True,
            rows=[{"label": short, "segments": [{"label": f"{SCOPE_LABEL[k]} {_share(100 * v / total)}", "value": v,
                                                  "display": f"{num(v)} {CO2}"} for k, v in have]}],
            export=export(f"{c['name']}: emissions by scope", ["Scope", "Emissions (tCO2e)", "Share (%)"],
                          [[SCOPE_LABEL[k], v, round(100 * v / total, 2)] for k, v in have]))
    if "scope3" not in vals:
        a.note("data", f"{short} has not disclosed Scope 3 emissions, so the split covers Scope 1 and Scope 2 only.")
    a.flag_notes(c, ["1330", "1331", "1332", "1333"])
    a.context.update({"metric": "scope12"})
    a.follow(f"How did {short}'s emissions change?", f"How does {short} compare with its peers?",
             f"Show {short}'s projects to reduce GHG emissions")


# --------------------------------------------------------------------------- a company's share of its sector

def company_share(ctx, c, mid):
    from .h_sector import _total
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    a.kicker = kicker(ctx, c)
    mid = mid if mid in ("scope1", "scope2", "scope3") else "scope12"
    metric = M.NUMERIC[mid]
    short = short_name(c["name"])
    sname = kb.sector_of(c)["name"]
    a.title = f"Share of {lc(metric.label)}"
    v = metric.value(c)
    if v is None:
        a.status = "partial"
        a.p(f"**{c['name']}** has not disclosed {lc(metric.label)} for FY 2024-25 {a.c_filing(c, metric.cy_q or '1330')}, "
            f"so its share cannot be worked out.")
        a.follow(f"Tell me about {short}")
        return
    if metric.level_ok is not None and not metric.level_ok(c):
        a.status = "partial"
        a.p(f"**{c['name']}** disclosed {lc(metric.label)} of {fmt_value(metric, v)} {value_cite(a, c, metric)}. The figure "
            f"appears to use a different unit from most filings, so it is left out of sector totals and a share is not shown.")
        a.flag_notes(c, metric.qids)
        return
    members = kb.members(c["sector"])
    st, gt = _total(members, mid), _total(kb.companies, mid)
    sp, gp = 100 * v / st, 100 * v / gt
    calc = a.c_calc(f"{short}'s share of {lc(metric.label)}",
                    f"{num(v)} ÷ {num(st)} ({sname}) = {sp:.2f}%; {num(v)} ÷ {num(gt)} (all companies) = {gp:.2f}%",
                    [value_cite(a, c, metric)], note="Totals are the sum of what companies disclosed for FY 2024-25.")
    a.p(f"**{c['name']}** accounts for **{_share(sp)}** of the {lc(metric.label)} disclosed by the {len(members)} {sname} "
        f"companies for FY 2024-25, and {_share(gp)} of the total across all {len(kb.companies)} companies {calc}.")
    a.block("stack", title=f"{short}'s share of {lc(metric.label)}", subtitle="FY 2024-25", categorical=True, rows=[
        {"label": sname, "segments": [{"label": short, "value": v, "display": f"{num(v)} {CO2}"},
                                      {"label": "Other companies", "value": max(st - v, 0), "display": f"{num(st - v)} {CO2}"}]},
        {"label": "All sectors", "segments": [{"label": short, "value": v, "display": f"{num(v)} {CO2}"},
                                              {"label": "Other companies", "value": max(gt - v, 0), "display": f"{num(gt - v)} {CO2}"}]}],
        export=export(f"{c['name']}: share of {lc(metric.label)}", ["Group", f"{short} (tCO2e)", "Group total (tCO2e)", "Share (%)"],
                      [[sname, v, st, round(sp, 2)], ["All companies", v, gt, round(gp, 2)]]))
    a.context.update({"metric": mid})
    a.follow(f"How does {short} compare with its peers?", f"Give me an overview of the {sname} sector",
             f"Top 10 {sname} companies by emissions")


# --------------------------------------------------------------------------- what a company has not disclosed yet

GAP_ITEMS = [("1330", "Scope 1 emissions", "num"), ("1332", "Scope 2 emissions", "num"), ("1388", "Scope 3 emissions", "num"),
             ("1334", "Emission intensity per rupee of turnover", "num"),
             ("1340", "Independent assurance of GHG emissions", "bool"), ("286", "Targets with timelines", "text"),
             ("295", "Performance against targets", "text"), ("1341", "Projects to reduce GHG emissions", "bool"),
             ("277", "Codes, certifications and standards", "text"), ("241", "Board approval of the environment policy", "bool"),
             ("268", "Policy extended to value chain partners", "bool")]


def _has(c, qid, kind) -> bool:
    if kind == "bool":
        return yes(c, qid)
    v = c["values"].get(qid)
    return v is not None and v != ""


def company_gaps(ctx, c):
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    a.kicker = kicker(ctx, c)
    a.title = "Disclosure checklist"
    short = short_name(c["name"])
    sname = kb.sector_of(c)["name"]
    peers = [m for m in kb.members(c["sector"]) if m["id"] != c["id"]]
    rows = [(q, label, _has(c, q, kind), sum(1 for o in peers if _has(o, q, kind))) for q, label, kind in GAP_ITEMS]
    done = [r for r in rows if r[2]]
    missing = sorted([r for r in rows if not r[2]], key=lambda r: (-r[3], r[1]))
    note = a.c_note("Disclosure checklist", "Eleven climate items from the BRSR: emissions by scope, intensity, assurance, "
                    "targets and progress, reduction projects, certifications and policy governance. An item counts as "
                    "disclosed when the company gave a figure, a description or a Yes.")
    if not missing:
        a.p(f"**{c['name']}** has disclosed all of the climate items checked for FY 2024-25 {note}.")
    else:
        cc = a.c_calc(f"Peers disclosing each item ({sname})", f"Count among the other {len(peers)} {sname} companies")
        a.p(f"**{c['name']}** has disclosed **{len(done)} of the {len(rows)}** climate items checked for FY 2024-25 {note}.")
        bits = [f"{lc(label)} ({k} of {len(peers)} peers disclose it)" for _, label, _, k in missing[:4]]
        a.p(f"Not yet disclosed: {join(bits)} {cc}." + (f" {len(missing) - 4} more are listed below." if len(missing) > 4 else ""))
    a.block("checklist", title=f"What {short} has disclosed", items=[
        {"label": label, "value": ok, "sub": f"{k} of {len(peers)} peers", "cite": a.c_filing(c, q)} for q, label, ok, k in rows],
        export=export(f"{c['name']}: disclosure checklist", ["Item", "Disclosed", f"{sname} peers disclosing", "Peers in sector"],
                      [[label, "Yes" if ok else "No", k, len(peers)] for _, label, ok, k in rows]))
    first = missing[0][0] if missing else None
    a.follow(f"Examples of targets from {sname} companies" if first in ("286", "295") else
             f"Which {sname} companies have independent assurance of GHG emissions?" if first == "1340" else
             f"Examples of GHG reduction projects from {sname} companies",
             f"How does {short} compare with its peers?", f"Which {sname} companies report Scope 3 emissions?" if first == "1388" else None,
             f"Make an infographic for {short}")


# --------------------------------------------------------------------------- a pledge or technology, for one company

def company_mentions(ctx, c):
    """Where one company's disclosures mention net zero, SBTi, a technology or a quoted phrase."""
    from .h_practice import SEARCH_QIDS, TECH_LABEL
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    a.company_ref(c)
    a.kicker = kicker(ctx, c)
    short = short_name(c["name"])
    labels = [TECH_LABEL.get(t, t) for t in plan.tech] + [f"“{k}”" for k in plan.keywords]
    what = join(labels, "or")
    a.title = f"{short}: {what}"
    hits = ctx.index.search(plan.tech, plan.keywords, SEARCH_QIDS, {c["id"]}).get(c["id"], [])
    how = a.c_note("How the search works",
                   "An exact, case-insensitive match in what the company disclosed on targets, progress against targets, "
                   "projects to reduce GHG emissions and certifications. A mention is not a verified commitment.")
    if not hits:
        a.p(f"**{c['name']}** does not mention {what} in its disclosures on targets, progress against targets, projects to "
            f"reduce GHG emissions or certifications for FY 2024-25 {how}. The search is literal, so the company may "
            f"describe the same thing in other words.")
        # show the disclosure the term would normally appear in, so the user can read it for themselves
        q = M.TEXT_Q.get(plan.metric) or ("286" if set(plan.tech) & {"net zero", "sbti"} else "1342")
        q = q if c["values"].get(q) else next((x for x in ("286", "1342") if c["values"].get(x)), None)
        if q:
            it = quote_item(ctx, c, q)
            a.p(f"Its disclosure on {TOPIC.get(q, lc(item(q)[0]))} is shown below {it['cite']}.")
            a.block("quotes", items=[it])
        else:
            a.status = "partial"
        a.follow(f"What are {short}'s targets?" if c["values"].get("286") and q != "286" else None,
                 f"Show {short}'s projects to reduce GHG emissions" if c["values"].get("1342") else None,
                 f"Which {kb.sector_of(c)['name']} companies mention {labels[0]}?", f"Tell me about {short}")
        return
    by_q: dict[str, list] = {}
    for d, spans in hits:
        by_q.setdefault(d["qid"], []).append((d, spans))
    order = sorted(by_q, key=lambda q: (q != M.TEXT_Q.get(plan.metric), -sum(len(sp) for _, sp in by_q[q]), q))
    items = []
    for q in order[:3]:
        segs = [{"start": d["start"], "end": d["end"], "highlight": True,
                 "marks": [[d["start"] + s0, d["start"] + s1] for s0, s1 in spans]} for d, spans in by_q[q][:4]]
        items.append({"key": f"{c['id']}:{q}", "company": c["name"], "company_id": c["id"], "short": short,
                      "sector": kb.sector_of(c)["name"], "topic": item(q)[0], "text": c["values"][q], "segments": segs,
                      "mentions": sum(len(sp) for _, sp in by_q[q]), "cite": a.c_filing(c, q)})
    topics = join([lc(TOPIC.get(q, item(q)[0])) for q in order[:3]])
    a.p(f"**{c['name']}** mentions {what} in its disclosure{'s' if len(order[:3]) > 1 else ''} on {topics} for FY 2024-25 "
        f"{items[0]['cite']}. The passages are "
        f"shown below, exactly as disclosed {how}.")
    a.block("quotes", items=items, excerpt=True)
    a.context.update({"tech": plan.tech, "metric": plan.metric})
    a.follow(f"What are {short}'s targets?",
             f"Which {kb.sector_of(c)['name']} companies mention {labels[0]}?",
             f"Show {short}'s projects to reduce GHG emissions")
