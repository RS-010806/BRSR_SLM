"""Sector overviews, rankings, totals, counts and lists.

Everything is computed from what companies disclosed. Sector totals leave out
the few values that are clearly in a different unit, and say so.
"""
from __future__ import annotations

from ..analytics import band_counts, median, sector_sum
from . import metrics as M
from .common import bars, eligible, export, fmt_value, kpi, ordered, value_cite, yes, yes_count
from .fmt import CO2, compact, join, lc, num, pct, share, short_name
from .h_company import BOOL_PHRASE, BOOL_TITLE, TEXT_TITLE

CY_Q = {"scope1": ["1330"], "scope2": ["1332"], "scope12": ["1330", "1332"], "scope3": ["1388"]}
PY_Q = {"scope1": ["1331"], "scope2": ["1333"], "scope12": ["1331", "1333"], "scope3": ["1389"]}


def _in(scope: str | None) -> str:
    return f"in {scope}" if scope else "among the companies covered"


def _where(scope: str | None) -> str:
    """' in Power' for a sector, nothing for the whole market (the count already says how many)."""
    return f" in {scope}" if scope else ""


def _who(scope: str | None, n: int) -> str:
    return f"The {n} {scope} companies" if scope else f"The {n} companies covered"


def _total(members, mid, year="cy"):
    return sum(sector_sum(members, q) for q in (CY_Q if year == "cy" else PY_Q)[mid])


def _yoy(members, mid):
    cy, py = _total(members, mid), _total(members, mid, "py")
    return (cy - py) / py * 100 if py else None


def _excluded_note(a, members):
    if any(f["type"] == "report_exclusion" for c in members for f in c["flags"]):
        a.note("data", "Totals leave out disclosed values that are clearly in a different unit.")


def _total_cite(a, scope, mid, members, year="cy"):
    m = M.NUMERIC[mid]
    n = sum(1 for c in members if any(c["values"].get(q) is not None for q in (CY_Q if year == "cy" else PY_Q)[mid]))
    fy = "FY 2024-25" if year == "cy" else "FY 2023-24"
    return a.c_calc(f"Total {lc(m.label)}, {scope or 'all companies'}, {fy}",
                    f"Sum of the figures disclosed by {n} companies = {num(_total(members, mid, year))} {CO2}",
                    note="Each figure is the company's own BRSR disclosure for the year.")


# --------------------------------------------------------------------------- sector overview

def sector_overview(ctx, sid, mid=None):
    a, kb = ctx.a, ctx.kb
    if sid is None:
        return all_sectors(ctx, mid)
    s = kb.sector_by_id[sid]
    sname = s["name"]
    members = kb.members(sid)
    n = len(members)
    a.kicker = "Sector overview"
    a.title = sname
    t1, t2 = _total(members, "scope1"), _total(members, "scope2")
    yoy = _yoy(members, "scope12")
    asr, _ = yes_count(members, "1340")
    s3, _ = yes_count(members, "1387")
    proj, _ = yes_count(members, "1341")
    c1, c2 = _total_cite(a, sname, "scope1", members), _total_cite(a, sname, "scope2", members)
    line = (f"**{sname}** has {n} companies. Together they reported Scope 1 emissions of **{compact(t1)} {CO2}** {c1} "
            f"and Scope 2 emissions of **{compact(t2)} {CO2}** {c2} for FY 2024-25")
    if yoy is not None:
        yc = a.c_calc(f"Change in Scope 1 + Scope 2, {sname}", f"({num(t1 + t2)} − {num(_total(members, 'scope12', 'py'))}) ÷ "
                      f"{num(_total(members, 'scope12', 'py'))} = {pct(yoy, digits=2)}")
        line += f"; the combined total is {abs(yoy):.1f}% {'higher' if yoy > 0 else 'lower'} than in FY 2023-24 {yc}"
    a.p(line + ".")
    a.block("kpis", items=[
        kpi("Companies", str(n)),
        kpi("Scope 1", compact(t1).replace(" billion", "B").replace(" million", "M"), sub=CO2, cite=c1),
        kpi("Scope 2", compact(t2).replace(" billion", "B").replace(" million", "M"), sub=CO2, cite=c2),
        kpi("Report Scope 3", f"{s3} of {n}", sub="companies"),
        kpi("Independent assurance", f"{asr} of {n}", sub="companies"),
    ], export=export(f"{sname}: overview", ["Item", "Value"], [
        ["Companies", n], ["Scope 1 emissions, FY 2024-25 (tCO2e)", t1], ["Scope 2 emissions, FY 2024-25 (tCO2e)", t2],
        ["Change in Scope 1 + Scope 2 vs FY 2023-24 (%)", None if yoy is None else round(yoy, 2)],
        ["Companies reporting Scope 3 emissions", s3], ["Companies with independent assurance of GHG emissions", asr],
        ["Companies with projects to reduce GHG emissions", proj]]))
    m12 = M.NUMERIC["scope12"]
    pairs = ordered(eligible(m12, members))
    if pairs:
        a.blocks.append(bars(f"Largest emitters in {sname}", pairs, m12, limit=10, log=True,
                             subtitle="Scope 1 + Scope 2, FY 2024-25"))
    _excluded_note(a, members)
    a.context.update({"sector": sid})
    a.follow(f"List all {sname} companies", f"Examples of GHG reduction projects from {sname} companies",
             f"Which {sname} companies have independent assurance of GHG emissions?",
             f"Make an infographic for the {sname} sector")


def all_sectors(ctx, mid=None):
    a, kb = ctx.a, ctx.kb
    if mid in M.BOOL_Q and mid not in M.TEXT_Q:
        return _by_sector_bool(ctx, M.BOOL_Q[mid])
    if mid in ("scope1", "scope2", "scope3"):
        return _by_sector_total(ctx, mid)
    if mid in ("intensity", "scope3_intensity"):
        return _by_sector_intensity(ctx, mid)
    a.kicker = "All sectors"
    a.title = "Emissions by sector"
    tot = {s["id"]: _total(kb.members(s["id"]), "scope12") for s in kb.sectors}
    grand = sum(tot.values())
    order = sorted(kb.sectors, key=lambda s: (-tot[s["id"]], s["name"]))
    top = order[0]
    gc = _total_cite(a, None, "scope12", kb.companies)
    a.p(f"Across {len(kb.companies)} companies in {len(kb.sectors)} sectors, disclosed Scope 1 and Scope 2 emissions total "
        f"**{compact(grand)} {CO2}** for FY 2024-25 {gc}. **{top['name']}** accounts for the largest share, "
        f"{share(round(tot[top['id']]), round(grand))}, followed by {join([s['name'] for s in order[1:4]])}.")
    a.block("treemap", title="Share of Scope 1 + Scope 2 emissions by sector", subtitle="FY 2024-25",
            items=[{"label": s["name"], "short": s["short"], "value": tot[s["id"]], "display": f"{compact(tot[s['id']])} {CO2}",
                    "share": round(tot[s["id"]] / grand * 100, 1), "id": s["id"]} for s in order],
            export=export("Emissions by sector", ["Sector", "Companies", "Scope 1 (tCO2e)", "Scope 2 (tCO2e)",
                                                  "Scope 1 + Scope 2 (tCO2e)", "Share of total (%)"],
                          [[s["name"], s["n"], _total(kb.members(s["id"]), "scope1"), _total(kb.members(s["id"]), "scope2"),
                            tot[s["id"]], round(tot[s["id"]] / grand * 100, 2)] for s in order]))
    _excluded_note(a, kb.companies)
    a.follow(f"Give me an overview of the {top['name']} sector", "Top 10 emitters",
             "How many companies report Scope 3 emissions?")


def _by_sector_total(ctx, mid):
    a, kb = ctx.a, ctx.kb
    m = M.NUMERIC[mid]
    a.kicker = "All sectors"
    a.title = f"{m.label} by sector"
    rows = sorted(((s, _total(kb.members(s["id"]), mid)) for s in kb.sectors), key=lambda t: (-t[1], t[0]["name"]))
    grand = sum(v for _, v in rows)
    a.p(f"**{rows[0][0]['name']}** reported the highest total {lc(m.label)} for FY 2024-25, {compact(rows[0][1])} {CO2}, "
        f"out of {compact(grand)} {CO2} across all sectors {_total_cite(a, None, mid, kb.companies)}.")
    a.block("bars", title=f"{m.label} by sector", subtitle="FY 2024-25", unit=CO2, log=True,
            rows=[{"id": s["id"], "label": s["name"], "value": v, "display": compact(v).replace(" billion", "B").replace(" million", "M"),
                   "full": f"{num(v)} {CO2}"} for s, v in rows if v > 0],
            export=export(f"{m.label} by sector", ["Sector", f"{m.label} (tCO2e)"], [[s["name"], v] for s, v in rows]))
    _excluded_note(a, kb.companies)
    a.follow(f"Give me an overview of the {rows[0][0]['name']} sector", f"Top 10 companies by {lc(m.label)}")


def _by_sector_intensity(ctx, mid):
    a, kb = ctx.a, ctx.kb
    m = M.NUMERIC[mid]
    a.kicker = "All sectors"
    a.title = f"{m.label} by sector"
    rows = [(s, median(v for _, v in eligible(m, kb.members(s["id"])))) for s in kb.sectors]
    rows = sorted([r for r in rows if r[1]], key=lambda t: (-t[1], t[0]["name"]))
    cite = a.c_calc(f"Median {lc(m.label)} by sector", "Median of the comparable figures disclosed by companies in each sector")
    a.p(f"**{rows[0][0]['name']}** has the highest median {lc(m.label)}, {num(rows[0][1], 1)} {m.unit}, and "
        f"**{rows[-1][0]['name']}** the lowest, {num(rows[-1][1], 1)} {m.unit} {cite}.")
    a.block("bars", title=f"Median {lc(m.label)} by sector", subtitle=f"FY 2024-25, {m.unit}", unit=m.unit, log=True,
            rows=[{"id": s["id"], "label": s["name"], "value": v, "display": num(v, 1), "full": f"{num(v, 1)} {m.unit}"}
                  for s, v in rows],
            export=export(f"Median {lc(m.label)} by sector", ["Sector", f"Median {lc(m.label)} ({m.unit})"],
                          [[s["name"], round(v, 4)] for s, v in rows]))
    a.note("method", m.note)
    a.follow(f"Give me an overview of the {rows[0][0]['name']} sector", "Which companies have the lowest emission intensity?")


def _by_sector_bool(ctx, qid):
    a, kb = ctx.a, ctx.kb
    _, _, plural = BOOL_PHRASE[qid]
    a.kicker = "All sectors"
    a.title = f"{BOOL_TITLE.get(qid)} by sector"
    rows = []
    for s in kb.sectors:
        y, n = yes_count(kb.members(s["id"]), qid)
        rows.append((s, 100 * y / n, y, n))
    rows.sort(key=lambda r: (-r[1], r[0]["name"]))
    Y, N = yes_count(kb.companies, qid)
    cite = a.c_calc(f"{BOOL_TITLE.get(qid)} by sector", "Companies answering Yes ÷ companies in the sector")
    a.p(f"**{rows[0][0]['name']}** has the highest share of companies that {plural}, {rows[0][2]} of {rows[0][3]} "
        f"({rows[0][1]:.0f}%). Across all companies the figure is {Y} of {N} ({share(Y, N)}) {cite}.")
    a.block("bars", title=f"Share of companies that {plural}", unit="% of companies", max=100,
            median={"value": 100 * Y / N, "label": "All companies", "display": share(Y, N)},
            rows=[{"id": s["id"], "label": s["name"], "value": v, "display": f"{v:.0f}%", "full": f"{y} of {n} companies"}
                  for s, v, y, n in rows],
            export=export(f"{BOOL_TITLE.get(qid)} by sector", ["Sector", "Companies answering Yes", "Companies in sector", "Share (%)"],
                          [[s["name"], y, n, round(v, 1)] for s, v, y, n in rows]))
    a.follow(f"Which {rows[0][0]['name']} companies {plural}?", f"How many companies {plural}?")


# --------------------------------------------------------------------------- ranking

def ranking(ctx, mid, sid, n, extreme, quality, change):
    a, kb = ctx.a, ctx.kb
    if mid in M.TEXT_Q:
        from .h_practice import best_practice
        return best_practice(ctx, mid, sid, None)
    if mid in M.BOOL_Q:
        return screen(ctx, mid, sid, False, None)
    assumed = None
    if mid not in M.NUMERIC:
        if change:
            mid = "scope12"
        elif quality in ("best", "worst") and extreme != "high":
            mid, assumed = "intensity", "emission intensity, which allows for company size"
        else:
            mid = "scope12"
    metric = M.NUMERIC[mid]
    members = kb.members(sid) if sid else kb.companies
    scope = kb.sector_by_id[sid]["name"] if sid else None
    by = "yoy" if change or not metric.comparable_levels else "value"
    if by == "yoy":
        if change == "increased":
            desc = True
        elif change == "decreased":
            desc = False
        else:
            desc = quality == "worst"
    elif quality == "best":
        desc = False
    elif quality == "worst":
        desc = True
    else:
        desc = extreme != "low"
    pairs = eligible(metric, members, by=by)
    if by == "yoy" and change == "decreased":
        pairs = [(c, v) for c, v in pairs if v < 0]
    if by == "yoy" and change == "increased":
        pairs = [(c, v) for c, v in pairs if v > 0]
    ranked = ordered(pairs, desc)
    top = ranked[: (n or 10)]
    what = lc(metric.label)
    if by == "yoy":
        head = f"{'Largest increases' if desc else 'Largest reductions'} in {what}"
    else:
        head = f"{'Highest' if desc else 'Lowest'} {what}"
    a.kicker = scope or "All companies"
    a.title = head
    if not top:
        a.status = "partial"
        a.p(f"No company {_in(scope)} has disclosed a comparable figure for {what}.")
        return
    lead = top[0]
    val = (lambda v: pct(v)) if by == "yoy" else (lambda v: fmt_value(metric, v))
    lead_cite = value_cite(a, lead[0], metric, by)
    cite = a.c_calc(f"{head}, {scope or 'all companies'}",
                    f"{len(pairs)} companies with a comparable figure, sorted from {'high to low' if desc else 'low to high'}",
                    note="Figures that appear to use a different unit are left out. Ties are ordered alphabetically.")
    phrase = (f"the largest {'increase' if desc else 'reduction'} in {what}" if by == "yoy"
              else f"the {'highest' if desc else 'lowest'} {what}")
    a.p(f"{_in(scope)[0].upper() + _in(scope)[1:]}, **{short_name(lead[0]['name'])}** reported {phrase} "
        f"({val(lead[1])}) {lead_cite}"
        + (f", followed by {join([short_name(c['name']) + ' (' + val(v) + ')' for c, v in top[1:3]])}" if len(top) > 1 else "")
        + f" {cite}.")
    if assumed:
        a.note("method", f"No measure was named, so companies are ordered by {assumed}.")
    if by == "yoy" and metric.kind == "abs":
        a.note("method", "Percentage changes can be very large when the previous year's figure is small.")
    if metric.note and metric.kind == "intensity":
        a.note("method", metric.note)
    blk = bars(head, top, metric, value_kind=by, log=by == "value" and metric.kind == "abs",
               subtitle=f"{scope or 'All companies'}, FY 2024-25" + ("" if by == "value" else " vs FY 2023-24"))
    xcols = ["Position", "Company"] + ([] if sid else ["Sector"])
    if mid == "scope12":
        xcols += ["Scope 1 (tCO2e)", "Scope 2 (tCO2e)", "Scope 1 + Scope 2 (tCO2e)", "Change vs FY 2023-24 (%)"]
    else:
        unit = metric.unit if metric.comparable_levels else "unit as disclosed"
        xcols += [f"FY 2024-25 ({unit})", f"FY 2023-24 ({unit})", "Change vs FY 2023-24 (%)"]
    xrows = []
    for i, (c, v) in enumerate(top, 1):
        r = [i, c["name"]] + ([] if sid else [kb.sector_of(c)["name"]])
        y = metric.yoy(c) if metric.yoy else None
        if mid == "scope12":
            r += [c["values"].get("1330"), c["values"].get("1332"), metric.value(c), None if y is None else round(y, 2)]
        else:
            r += [metric.value(c), metric.prev(c), None if y is None else round(y, 2)]
        xrows.append(r)
    blk["export"] = export(head, xcols, xrows)
    a.blocks.append(blk)
    a.context.update({"metric": metric.id, "sector": sid})
    a.follow(f"Tell me about {short_name(lead[0]['name'])}",
             f"Compare {short_name(top[0][0]['name'])} and {short_name(top[1][0]['name'])}" if len(top) > 1 else None,
             f"Give me an overview of the {scope} sector" if sid else "Which sector emits the most?")


# --------------------------------------------------------------------------- totals and counts

def aggregate(ctx, mid, sid, change=None):
    a, kb = ctx.a, ctx.kb
    members = kb.members(sid) if sid else kb.companies
    sname = kb.sector_by_id[sid]["name"] if sid else None
    a.kicker = sname or "All companies"
    if mid is None and change in ("decreased", "increased"):
        return screen(ctx, None, sid, False, change)
    if mid is None:
        return coverage(ctx)

    if mid in M.TEXT_Q:
        qid = M.TEXT_Q[mid]
        a.title = TEXT_TITLE.get(qid)
        y = sum(1 for c in members if c["values"].get(qid))
        cite = a.c_calc(f"{TEXT_TITLE.get(qid)}: companies disclosing", f"{y} of {len(members)} companies provided this disclosure")
        a.p(f"**{y} of {len(members)} companies ({share(y, len(members))})**{_where(sname)} disclosed "
            f"{lc(TEXT_TITLE.get(qid))} for FY 2024-25 {cite}.")
        a.context.update({"metric": mid, "sector": sid})
        a.follow(f"Examples of {lc(TEXT_TITLE.get(qid))}" + (f" from {sname} companies" if sname else ""))
        return

    if mid in M.BOOL_Q:
        qid = M.BOOL_Q[mid]
        a.title = BOOL_TITLE.get(qid)
        _, _, plural = BOOL_PHRASE[qid]
        y, n = yes_count(members, qid)
        cite = a.c_calc(f"{BOOL_TITLE.get(qid)}: companies answering Yes", f"{y} of {n} companies answered Yes")
        line = f"**{y} of {n} companies ({share(y, n)})**{_where(sname)} {plural} {cite}."
        if sid:
            Y, N = yes_count(kb.companies, qid)
            line += f" Across all sectors the figure is {Y} of {N} ({share(Y, N)})."
        a.p(line)
        if qid == "1387":
            py = sum(1 for c in members if (c["values"].get("1389") or 0) > 0)
            a.p(f"In FY 2023-24, {py} of these companies disclosed a Scope 3 figure "
                f"{a.c_calc('Scope 3 figures disclosed for FY 2023-24', f'{py} of {n} companies')}.")
        a.context.update({"metric": mid, "sector": sid})
        a.follow(f"Which {sname + ' ' if sname else ''}companies {plural}?",
                 f"{BOOL_TITLE.get(qid)} by sector" if not sid else None,
                 f"Which {sname + ' ' if sname else ''}companies do not {plural}?" if sid else None)
        return

    if mid in M.CATEGORY_Q:
        qid = M.CATEGORY_Q[mid][0]
        a.title = "Review of performance" if qid == "308" else "Review frequency"
        cats: dict[str, int] = {}
        for c in members:
            k = c["values"].get(qid) or "Not disclosed"
            cats[k] = cats.get(k, 0) + 1
        rows = sorted(cats.items(), key=lambda t: (-t[1], t[0]))
        cite = a.c_calc(a.title, f"Count of each answer across {len(members)} companies")
        a.p(f"{_in(sname)[0].upper() + _in(sname)[1:]}: {join([f'{v} {k}' for k, v in rows])} {cite}.")
        a.block("bars", title=a.title, unit="companies", rows=[{"label": k, "value": v, "display": str(v), "full": f"{v} companies"} for k, v in rows],
                export=export(a.title, ["Answer", "Companies"], [[k, v] for k, v in rows]))
        return

    metric = M.NUMERIC.get(mid) or M.NUMERIC["scope12"]
    mid = metric.id
    a.title = f"Total {lc(metric.label)}" if metric.kind == "abs" else metric.label
    if metric.kind == "abs":
        if mid == "scope12":
            t1, t2 = _total(members, "scope1"), _total(members, "scope2")
            c1, c2 = _total_cite(a, sname, "scope1", members), _total_cite(a, sname, "scope2", members)
            yoy = _yoy(members, "scope12")
            a.p(f"{_who(sname, len(members))} reported total Scope 1 emissions of **{compact(t1)} {CO2}** {c1} and total Scope 2 "
                f"emissions of **{compact(t2)} {CO2}** {c2} for FY 2024-25, a combined {compact(t1 + t2)} {CO2}"
                + (f", {abs(yoy):.1f}% {'higher' if yoy > 0 else 'lower'} than in FY 2023-24 {_total_cite(a, sname, 'scope12', members, 'py')}" if yoy is not None else "")
                + ".")
            tiles = [kpi("Scope 1", compact(t1).replace(" billion", "B").replace(" million", "M"), sub=CO2, cite=c1),
                     kpi("Scope 2", compact(t2).replace(" billion", "B").replace(" million", "M"), sub=CO2, cite=c2),
                     kpi("Scope 1 + Scope 2", compact(t1 + t2).replace(" billion", "B").replace(" million", "M"), sub=CO2,
                         delta=(pct(yoy) + " vs FY 2023-24") if yoy is not None else None,
                         tone="good" if yoy is not None and yoy < 0 else "bad")]
            xrows = [["Scope 1 emissions (tCO2e)", t1, _total(members, "scope1", "py")],
                     ["Scope 2 emissions (tCO2e)", t2, _total(members, "scope2", "py")],
                     ["Scope 1 + Scope 2 emissions (tCO2e)", t1 + t2, _total(members, "scope12", "py")]]
        else:
            cy, py = _total(members, mid), _total(members, mid, "py")
            yoy = _yoy(members, mid)
            cc = _total_cite(a, sname, mid, members)
            n_rep = sum(1 for c in members if c["values"].get(CY_Q[mid][0]) is not None)
            a.p(f"{_who(sname, len(members))} reported total {lc(metric.label)} of **{compact(cy)} {CO2}** for FY 2024-25 {cc}"
                + (f", {abs(yoy):.1f}% {'higher' if yoy > 0 else 'lower'} than in FY 2023-24 {_total_cite(a, sname, mid, members, 'py')}" if yoy is not None else "")
                + f". {n_rep} of {len(members)} companies disclosed this figure.")
            tiles = [kpi("FY 2024-25", compact(cy).replace(" billion", "B").replace(" million", "M"), sub=CO2, cite=cc),
                     kpi("FY 2023-24", compact(py).replace(" billion", "B").replace(" million", "M"), sub=CO2),
                     kpi("Companies disclosing", f"{n_rep} of {len(members)}")]
            xrows = [[f"{metric.label} (tCO2e)", cy, py]]
        a.block("kpis", items=tiles, export=export(a.title + (f", {sname}" if sname else ""),
                                                   ["Measure", "FY 2024-25", "FY 2023-24"], xrows))
        _excluded_note(a, members)
    else:
        by = "value" if metric.comparable_levels else "yoy"
        vals = [v for _, v in eligible(metric, members, by=by)]
        ch = [v for _, v in eligible(metric, members, by="yoy")]
        if by == "value":
            cite = a.c_calc(f"Median {lc(metric.label)}", f"Median of the comparable figures disclosed by {len(vals)} companies")
            a.p(f"The median {lc(metric.label)} {_in(sname)} is **{num(median(vals), 1)} {metric.unit}** for FY 2024-25 {cite}. "
                f"{len(vals)} of {len(members)} companies disclosed a comparable figure.")
        if ch:
            bc = band_counts(ch)
            cc = a.c_calc(f"Change in {lc(metric.label)}", f"Year-on-year change for {len(ch)} companies")
            a.p(f"Compared with FY 2023-24, the median change is {pct(median(ch))}: {bc[0] + bc[1]} companies lowered it by "
                f"more than 5%, {bc[2]} stayed within 5%, and {bc[3] + bc[4]} raised it by more than 5% {cc}.")
        if metric.note:
            a.note("method", metric.note)
    a.context.update({"metric": metric.id, "sector": sid})
    a.follow(f"Top 10 {sname + ' ' if sid else ''}companies by {lc(metric.label)}",
             f"{metric.label} by sector" if not sid else f"Give me an overview of the {sname} sector")


def coverage(ctx):
    a, kb = ctx.a, ctx.kb
    a.kicker = "Coverage"
    a.title = "What is covered"
    a.p(f"I cover **{len(kb.companies)} listed companies** across **{len(kb.sectors)} sectors**, using what each company "
        f"disclosed in its BRSR for FY 2024-25, with FY 2023-24 figures for comparison "
        f"{a.c_note('Coverage', 'Listed companies whose BRSR filing for FY 2024-25 is included, grouped by sector.')}.")
    a.p("Topics: Scope 1, Scope 2 and Scope 3 emissions, emission intensity, targets, projects to reduce GHG emissions, "
        "independent assurance and environment policy.")
    a.block("bars", title="Companies per sector", unit="companies",
            rows=[{"id": s["id"], "label": s["name"], "value": s["n"], "display": str(s["n"]), "full": f"{s['n']} companies"}
                  for s in sorted(kb.sectors, key=lambda s: (-s["n"], s["name"]))],
            export=export("Companies per sector", ["Sector", "Companies"], [[s["name"], s["n"]] for s in kb.sectors]))
    a.follow("Which sector emits the most?", "Top 10 emitters", "How many companies report Scope 3 emissions?")


def highlights(ctx):
    """A short, computed summary of the market: no outside commentary."""
    a, kb = ctx.a, ctx.kb
    cos = kb.companies
    N = len(cos)
    a.kicker = "All companies"
    a.title = "Key highlights"
    t1, t2 = _total(cos, "scope1"), _total(cos, "scope2")
    yoy = _yoy(cos, "scope12")
    tot = {s["id"]: _total(kb.members(s["id"]), "scope12") for s in kb.sectors}
    top = max(kb.sectors, key=lambda s: (tot[s["id"]], s["name"]))
    dirs = [c["derived"]["scope12_direction"] for c in cos]
    s3, _ = yes_count(cos, "1387")
    asr, _ = yes_count(cos, "1340")
    proj, _ = yes_count(cos, "1341")
    tgt = sum(1 for c in cos if c["values"].get("286"))
    a.p("These are the main points across all companies covered, based on their BRSR disclosures for FY 2024-25.")
    a.block("points", items=[
        f"Total Scope 1 emissions were **{compact(t1)} {CO2}** {_total_cite(a, None, 'scope1', cos)} and total Scope 2 emissions "
        f"**{compact(t2)} {CO2}** {_total_cite(a, None, 'scope2', cos)}"
        + (f"; the combined total is {abs(yoy):.1f}% {'higher' if yoy > 0 else 'lower'} than in FY 2023-24." if yoy is not None else "."),
        f"**{top['name']}** is the largest emitting sector, with {share(round(tot[top['id']]), round(t1 + t2))} of combined "
        f"Scope 1 and Scope 2 emissions {a.c_calc('Sector share of emissions', 'Sector total ÷ total of all sectors')}.",
        f"**{dirs.count('decreased')} companies** lowered their combined Scope 1 and Scope 2 emissions compared with "
        f"FY 2023-24, while {dirs.count('increased')} reported an increase or no change "
        f"{a.c_calc('Direction of change', 'FY 2024-25 compared with FY 2023-24, company by company')}.",
        f"**{s3} of {N}** ({share(s3, N)}) report Scope 3 emissions {a.c_calc('Companies reporting Scope 3', f'{s3} of {N} answered Yes')}.",
        f"**{asr} of {N}** ({share(asr, N)}) have had their GHG emissions independently assured "
        f"{a.c_calc('Companies with independent assurance', f'{asr} of {N} answered Yes')}.",
        f"**{proj} of {N}** ({share(proj, N)}) report projects to reduce GHG emissions, and {tgt} disclose targets with "
        f"timelines {a.c_calc('Companies with projects and targets', f'{proj} answered Yes on projects; {tgt} provided a targets disclosure')}.",
    ])
    _excluded_note(a, cos)
    a.follow("Which sector emits the most?", "Top 10 emitters", "Examples of net zero targets")


# --------------------------------------------------------------------------- lists

def screen(ctx, mid, sid, negated, change):
    a, kb = ctx.a, ctx.kb
    members = kb.members(sid) if sid else kb.companies
    sname = kb.sector_by_id[sid]["name"] if sid else None
    a.kicker = sname or "All companies"
    if change in ("decreased", "increased") and (mid is None or mid in ("scope12", "scope1", "scope2")):
        m = M.NUMERIC["scope12"]
        hits = [c for c in members if c["derived"]["scope12_direction"] == change and m.yoy(c) is not None]
        word = "lowered" if change == "decreased" else "raised"
        a.title = f"Companies that {word} their emissions"
        cite = a.c_calc("Direction of change", "Scope 1 + Scope 2 for FY 2024-25 compared with FY 2023-24, company by company")
        a.p(f"**{len(hits)} of {len(members)}** companies{_where(sname)} {word} their combined Scope 1 and Scope 2 emissions "
            f"between FY 2023-24 and FY 2024-25 {cite}.")
        hits.sort(key=lambda c: ((m.yoy(c) or 0) * (1 if change == "decreased" else -1), c["name"].lower()))
        _list(ctx, hits, sid, extra=("Change vs FY 2023-24 (%)", lambda c: round(m.yoy(c), 2), lambda c: pct(m.yoy(c))))
        return
    if mid is None:
        if sid:
            a.title = f"{sname} companies"
            a.p(f"There are **{len(members)} companies** in {sname} "
                f"{a.c_note('Sector membership', f'Companies classified under {sname} among the companies covered.')}.")
            _list(ctx, sorted(members, key=lambda c: c["name"].lower()), sid, names_only=True)
            a.follow(f"Give me an overview of the {sname} sector", f"Top 10 {sname} companies by emissions")
            return
        return coverage(ctx)
    if mid in M.TEXT_Q:
        qid = M.TEXT_Q[mid]
        hits = [c for c in members if bool(c["values"].get(qid)) != negated]
        topic = lc(TEXT_TITLE.get(qid))
        a.title = f"Companies {'without' if negated else 'with'} disclosed {topic}"
        cite = a.c_calc(a.title, f"{len(hits)} of {len(members)} companies")
        a.p(f"**{len(hits)} of {len(members)}** companies{_where(sname)} {'have not disclosed' if negated else 'have disclosed'} "
            f"{topic} for FY 2024-25 {cite}.")
        _list(ctx, sorted(hits, key=lambda c: c["name"].lower()), sid, names_only=True)
        a.follow(f"Examples of {topic}" + (f" from {sname} companies" if sname else ""))
        return
    if mid == "scope3":
        mid = "scope3_reported"
    qid = M.BOOL_Q.get(mid)
    if qid is None:
        return ranking(ctx, mid, sid, None, None, None, None)
    _, _, plural = BOOL_PHRASE[qid]
    hits = [c for c in members if yes(c, qid) != negated]
    a.title = BOOL_TITLE.get(qid)
    cite = a.c_calc(f"{BOOL_TITLE.get(qid)}: companies answering {'No' if negated else 'Yes'}", f"{len(hits)} of {len(members)} companies")
    a.p(f"**{len(hits)} of {len(members)}** companies{_where(sname)} {('do not ' + plural) if negated else plural} {cite}.")
    _list(ctx, sorted(hits, key=lambda c: c["name"].lower()), sid, names_only=True)
    a.context.update({"metric": mid, "sector": sid})
    a.follow(f"{BOOL_TITLE.get(qid)} by sector" if not sid else f"Give me an overview of the {sname} sector",
             "Examples of GHG reduction projects" + (f" from {sname} companies" if sname else "") if qid == "1341" else None)


def _list(ctx, cos, sid, extra=None, names_only=False):
    a, kb = ctx.a, ctx.kb
    if not cos:
        return
    cols = [{"key": "company", "label": "Company"}]
    xcols = ["Company"]
    if not sid:
        cols.append({"key": "sector", "label": "Sector"})
        xcols.append("Sector")
    if extra:
        cols.append({"key": "extra", "label": extra[0].replace(" (%)", ""), "align": "right"})
        xcols.append(extra[0])
    rows, xrows = [], []
    for c in cos:
        r = {"company": short_name(c["name"]), "id": c["id"], "sector": kb.sector_of(c)["name"]}
        x = [c["name"]] + ([] if sid else [kb.sector_of(c)["name"]])
        if extra:
            r["extra"] = extra[2](c)
            x.append(extra[1](c))
        rows.append(r)
        xrows.append(x)
    title = f"{len(rows)} companies"
    a.block("table", title=title, columns=cols, rows=rows, export=export(a.title or title, xcols, xrows))
