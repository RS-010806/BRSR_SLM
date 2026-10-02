"""Sector overviews, rankings, totals, counts and lists.

Everything is computed from what companies disclosed. Sector totals leave out
the few values that are clearly in a different unit, and say so.
"""
from __future__ import annotations

import re

from ..analytics import band_counts, mean, median, sector_sum
from . import metrics as M
from .common import bars, eligible, export, fmt_value, kpi, ordered, strip, value_cite, yes, yes_count
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
    dirs = [c["derived"]["scope12_direction"] for c in members]
    down, up = dirs.count("decreased"), dirs.count("increased")
    if down + up:
        a.block("stack", title="How company emissions moved since FY 2023-24", subtitle="Combined Scope 1 and Scope 2, company by company",
                rows=[{"label": sname, "segments": [{"label": "Lower", "value": down, "tone": "pos"},
                                                     {"label": "Higher or unchanged", "value": up, "tone": "neg"},
                                                     {"label": "Not comparable", "value": n - down - up, "tone": "muted"}]}],
                export=export(f"{sname}: change in emissions", ["Direction", "Companies"],
                              [["Lower", down], ["Higher or unchanged", up], ["Not comparable", n - down - up]]))
    _excluded_note(a, members)
    a.context.update({"sector": sid})
    a.follow(f"List all {sname} companies", f"Examples of GHG reduction projects from {sname} companies",
             f"Which {sname} companies have independent assurance of GHG emissions?",
             f"Make an infographic for the {sname} sector")


def all_sectors(ctx, mid=None, n=None, low=False):
    a, kb = ctx.a, ctx.kb
    if mid in M.CATEGORY_Q:
        return _by_sector_review(ctx)
    if mid in M.BOOL_Q and mid not in M.TEXT_Q:
        return _by_sector_bool(ctx, M.BOOL_Q[mid])
    if mid in ("scope1", "scope2", "scope3"):
        return _by_sector_total(ctx, mid, n, low)
    if mid in ("intensity", "scope3_intensity"):
        return _by_sector_intensity(ctx, mid, n, low)
    if n or low:
        return _by_sector_total(ctx, "scope12", n, low)
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


def _by_sector_total(ctx, mid, n=None, low=False):
    a, kb = ctx.a, ctx.kb
    m = M.NUMERIC[mid]
    a.kicker = "All sectors"
    a.title = f"{m.label} by sector"
    rows = sorted(((s, _total(kb.members(s["id"]), mid)) for s in kb.sectors), key=lambda t: (-t[1], t[0]["name"]))
    grand = sum(v for _, v in rows)
    shown = [r for r in rows if r[1] > 0]
    if low:
        shown = shown[::-1]
    if n:
        shown = shown[:n]
    lead = shown[0]
    a.p(f"**{lead[0]['name']}** reported the {'lowest' if low else 'highest'} total {lc(m.label)} for FY 2024-25, "
        f"{compact(lead[1])} {CO2}, "
        + (f"followed by {join([s['name'] + ' (' + compact(v) + ')' for s, v in shown[1:3]])}, " if len(shown) > 2 else "")
        + f"out of {compact(grand)} {CO2} across all sectors {_total_cite(a, None, mid, kb.companies)}.")
    a.block("bars", title=f"{m.label} by sector", unit=CO2, log=True,
            subtitle="FY 2024-25" + (f", the {len(shown)} {'lowest' if low else 'highest'} of {len(rows)} sectors" if len(shown) < len(rows) else ""),
            rows=[{"id": s["id"], "label": s["name"], "value": v, "display": compact(v).replace(" billion", "B").replace(" million", "M"),
                   "full": f"{num(v)} {CO2}"} for s, v in shown],
            export=export(f"{m.label} by sector", ["Sector", f"{m.label} (tCO2e)"], [[s["name"], v] for s, v in rows]))
    _excluded_note(a, kb.companies)
    a.follow(f"Give me an overview of the {rows[0][0]['name']} sector", f"Top 10 companies by {lc(m.label)}")


def _by_sector_intensity(ctx, mid, n=None, low=False):
    a, kb = ctx.a, ctx.kb
    m = M.NUMERIC[mid]
    a.kicker = "All sectors"
    a.title = f"{m.label} by sector"
    rows = [(s, median(v for _, v in eligible(m, kb.members(s["id"])))) for s in kb.sectors]
    rows = sorted([r for r in rows if r[1]], key=lambda t: (-t[1], t[0]["name"]))
    cite = a.c_calc(f"Median {lc(m.label)} by sector", "Median of the comparable figures disclosed by companies in each sector")
    if low:
        rows = rows[::-1]
        a.p(f"**{rows[0][0]['name']}** has the lowest median {lc(m.label)}, {num(rows[0][1], 2)} {m.unit}, followed by "
            f"{join([s['name'] + ' (' + num(v, 2) + ')' for s, v in rows[1:3]])}. **{rows[-1][0]['name']}** has the "
            f"highest, {num(rows[-1][1], 1)} {m.unit} {cite}.")
    else:
        a.p(f"**{rows[0][0]['name']}** has the highest median {lc(m.label)}, {num(rows[0][1], 1)} {m.unit}, and "
            f"**{rows[-1][0]['name']}** the lowest, {num(rows[-1][1], 2)} {m.unit} {cite}.")
    if n:
        rows = rows[:n]
    a.block("bars", title=f"Median {lc(m.label)} by sector", subtitle=f"FY 2024-25, {m.unit}", unit=m.unit, log=True,
            rows=[{"id": s["id"], "label": s["name"], "value": v, "display": num(v, 1 if v >= 10 else 2), "full": f"{num(v, 2)} {m.unit}"}
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

def ranking(ctx, mid, sid, n, extreme, quality, change, focus=None):
    a, kb = ctx.a, ctx.kb
    if mid in M.CATEGORY_Q:
        return sector_review(ctx, sid)
    if mid in M.TEXT_Q:
        from .h_practice import best_practice
        return best_practice(ctx, mid, sid, None)
    if mid in M.BOOL_Q:
        return screen(ctx, mid, sid, False, None)
    assumed = None
    if mid not in M.NUMERIC:
        if change:
            mid = "scope12"
        elif quality == "best" or (quality == "worst" and extreme != "high"):
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
    if by == "yoy":
        a.note("method", "Changes of more than tenfold between the two years are left out, because they usually reflect "
                         "a change of unit or reporting boundary. Percentage changes can still be large when the "
                         "previous year's figure is small.")
    if metric.note and metric.kind == "intensity":
        a.note("method", metric.note)
    shown = top
    if focus:
        # the company the question is about is always in the chart, and positions are not numbered
        a.company_ref(focus)
        fshort = short_name(focus["name"])
        mine = next(((c, v) for c, v in ranked if c["id"] == focus["id"]), None)
        if mine is None:
            a.p(f"{focus['name']} has no comparable figure for {what}, so it is not in this list.")
        elif mine[0]["id"] != lead[0]["id"]:
            a.p(f"**{fshort}** reported {val(mine[1])} {value_cite(a, focus, metric, by)}.")
        if mine and mine not in top:
            shown = top[:-1] + [mine] if len(top) >= (n or 10) else top + [mine]
    blk = bars(head, shown, metric, value_kind=by, log=by == "value" and metric.kind == "abs",
               focus_ids={focus["id"]} if focus else (), show_rank=not focus,
               subtitle=f"{scope or 'All companies'}, FY 2024-25" + ("" if by == "value" else " vs FY 2023-24")
                        + (f", {len(top)} of {len(ranked)} companies" if len(ranked) > len(top) else ""))
    if focus:
        blk["focus_label"] = short_name(focus["name"])
    if ctx.plan.view == "listing" or ctx.plan.as_table:
        blk["view"] = "table"                   # a table was asked for: open on the table, the chart is one click away
    top = shown
    xcols = ([] if focus else ["Position"]) + ["Company"] + ([] if sid else ["Sector"])
    if mid == "scope12":
        xcols += ["Scope 1 (tCO2e)", "Scope 2 (tCO2e)", "Scope 1 + Scope 2 (tCO2e)", "Change vs FY 2023-24 (%)"]
    else:
        unit = metric.unit if metric.comparable_levels else "unit as disclosed"
        xcols += [f"FY 2024-25 ({unit})", f"FY 2023-24 ({unit})", "Change vs FY 2023-24 (%)"]
    xrows = []
    for i, (c, v) in enumerate(top, 1):
        r = ([] if focus else [i]) + [c["name"]] + ([] if sid else [kb.sector_of(c)["name"]])
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
        srows = [{"label": sname or "All companies", "segments": [{"label": "Yes", "value": y, "tone": "pos"},
                                                               {"label": "No or not disclosed", "value": n - y, "tone": "neg"}]}]
        if sid:
            srows.append({"label": "All sectors", "segments": [{"label": "Yes", "value": Y, "tone": "pos"},
                                                             {"label": "No or not disclosed", "value": N - Y, "tone": "neg"}]})
        a.block("stack", title=f"Companies that {plural}", rows=srows,
                export=export(BOOL_TITLE.get(qid), ["Group", "Yes", "No or not disclosed"],
                              [[r["label"], r["segments"][0]["value"], r["segments"][1]["value"]] for r in srows]))
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
        return sector_review(ctx, sid)

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
    if ctx.plan.view == "coverage":
        a.p("To browse every company by name, open **Companies** in the sidebar. To see one sector, ask for example "
            "“list all cement companies”.")
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
    short_total = lambda v: compact(v).replace(" billion", "B").replace(" million", "M")
    a.block("kpis", items=[
        kpi("Scope 1 + Scope 2", short_total(t1 + t2), sub=CO2, delta=(pct(yoy) + " vs FY 2023-24") if yoy is not None else None,
            tone="good" if yoy is not None and yoy < 0 else "bad"),
        kpi("Report Scope 3", share(s3, N), sub=f"{s3} of {N} companies"),
        kpi("Independently assured", share(asr, N), sub=f"{asr} of {N} companies"),
        kpi("Have reduction projects", share(proj, N), sub=f"{proj} of {N} companies"),
    ])
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
    order = sorted(kb.sectors, key=lambda x: (-tot[x["id"]], x["name"]))
    grand = t1 + t2
    a.block("treemap", title="Share of Scope 1 + Scope 2 emissions by sector", subtitle="FY 2024-25",
            items=[{"label": x["name"], "short": x["short"], "value": tot[x["id"]], "display": f"{compact(tot[x['id']])} {CO2}",
                    "share": round(tot[x["id"]] / grand * 100, 1), "id": x["id"]} for x in order],
            export=export("Emissions by sector", ["Sector", "Companies", "Scope 1 + Scope 2 (tCO2e)", "Share of total (%)"],
                          [[x["name"], x["n"], tot[x["id"]], round(tot[x["id"]] / grand * 100, 2)] for x in order]))
    _excluded_note(a, cos)
    a.follow("Which sector emits the most?", "Top 10 emitters", "Examples of net zero targets")


# --------------------------------------------------------------------------- lists

def screen(ctx, mid, sid, negated, change):
    a, kb = ctx.a, ctx.kb
    if mid in M.CATEGORY_Q:
        return sector_review(ctx, sid)
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
    title = f"{len(rows)} companies" if len(rows) != 1 else "1 company"
    a.block("table", title=title, columns=cols, rows=rows, export=export(a.title or title, xcols, xrows))


# --------------------------------------------------------------------------- average and median

def statistic(ctx, mid, sid, focus=None, stat="average"):
    """The average and the median of a figure across a sector or all companies, with every company as a dot."""
    a, kb = ctx.a, ctx.kb
    metric = M.NUMERIC.get(mid) or M.NUMERIC["scope12"]
    members = kb.members(sid) if sid else kb.companies
    sname = kb.sector_by_id[sid]["name"] if sid else None
    asks_change = bool(re.search(r"\b(chang\w*|year on year|yoy|reduc\w*|increas\w*|decreas\w*)\b", ctx.plan.query.lower()))
    by = "value" if metric.comparable_levels and not asks_change else "yoy"
    what = lc(metric.label) + (" (change vs FY 2023-24)" if by == "yoy" else "")
    a.kicker = sname or "All companies"
    a.title = f"Average and median {'change in ' if by == 'yoy' else ''}{lc(metric.label)}"
    pairs = eligible(metric, members, by=by)
    if len(pairs) < 2:
        a.status = "partial"
        a.p(f"Fewer than two companies {_in(sname)} disclosed a comparable figure for {what}, so an average is not shown.")
        return
    vals = [v for _, v in pairs]
    med, avg = median(vals), mean(vals)
    show = (lambda x: pct(x)) if by == "yoy" else (lambda x: fmt_value(metric, x))
    cite = a.c_calc(f"Average and median {what}, {sname or 'all companies'}",
                    f"Across the {len(vals)} companies with a comparable figure: average = total ÷ {len(vals)} = {show(avg)}; "
                    f"median (the middle value) = {show(med)}",
                    note="Figures that appear to use a different unit are left out.")
    pair = [("median", med), ("average", avg)] if stat == "median" else [("average", avg), ("median", med)]
    a.p(f"Among the {len(vals)} {sname + ' ' if sname else ''}companies that disclosed {'a comparable figure for ' if by == 'yoy' else ''}"
        f"{what}, the **{pair[0][0]} is {show(pair[0][1])}** and the {pair[1][0]} is {show(pair[1][1])} for FY 2024-25 {cite}.")
    if by == "value" and med > 0 and avg > 3 * med:
        a.p("The average is far above the median because a few companies report much larger figures than the rest, so "
            "the median is the better guide to a typical company.")
    tiles = [kpi("Median", pct(med) if by == "yoy" else fmt_short_stat(metric, med), sub=metric.unit if by == "value" else "change vs FY 2023-24"),
             kpi("Average", pct(avg) if by == "yoy" else fmt_short_stat(metric, avg), sub=metric.unit if by == "value" else "change vs FY 2023-24"),
             kpi("Companies with a figure", f"{len(vals)} of {len(members)}")]
    mine = None
    if focus:
        a.company_ref(focus)
        fshort = short_name(focus["name"])
        mine = next(((c, v) for c, v in pairs if c["id"] == focus["id"]), None)
        if mine:
            rel = "the same as" if mine[1] == med else ("below" if mine[1] < med else "above")
            a.p(f"**{fshort}** reported {show(mine[1])} {value_cite(a, focus, metric, by)}, which is {rel} the median.")
            tiles.append(kpi(fshort, pct(mine[1]) if by == "yoy" else fmt_short_stat(metric, mine[1]),
                             sub=metric.unit if by == "value" else "change vs FY 2023-24"))
        else:
            a.p(f"{focus['name']} has no comparable figure for {what}.")
    a.block("kpis", items=tiles)
    blk = strip(f"{metric.label}: {sname or 'all'} companies", pairs, metric, focus_ids={focus["id"]} if mine else (),
                subtitle="Each dot is a company, FY 2024-25" + (" vs FY 2023-24" if by == "yoy" else ""), value_kind=by)
    blk["median_label"] = "Median"
    a.blocks.append(blk)
    if metric.note:
        a.note("method", metric.note)
    a.context.update({"metric": metric.id, "sector": sid})
    a.follow(f"Top 10 {sname + ' ' if sname else ''}companies by {lc(metric.label)}",
             f"How does {short_name(focus['name'])} compare with its peers?" if focus else
             (f"Give me an overview of the {sname} sector" if sname else f"{metric.label} by sector"),
             f"Which {sname + ' ' if sname else ''}companies have the lowest {lc(metric.label)}?")


def fmt_short_stat(metric, v):
    from .fmt import tile
    return tile(v) if metric.kind == "abs" else num(v)


# --------------------------------------------------------------------------- sector against sector

def sector_compare(ctx, sids):
    a, kb = ctx.a, ctx.kb
    secs = [kb.sector_by_id[s] for s in sids][:4]
    mem = {s["id"]: kb.members(s["id"]) for s in secs}
    a.kicker = "Sector comparison"
    a.title = " and ".join(s["name"] for s in secs) if len(secs) == 2 else join([s["name"] for s in secs])
    mi = M.NUMERIC["intensity"]
    parts, tot = [], {}
    for s in secs:
        m = mem[s["id"]]
        t1, t2 = _total(m, "scope1"), _total(m, "scope2")
        tot[s["id"]] = (t1, t2)
        parts.append(f"**{s['name']}** ({len(m)} companies) reported combined Scope 1 and Scope 2 emissions of "
                     f"{compact(t1 + t2)} {CO2} {_total_cite(a, s['name'], 'scope12', m)}")
    a.p("For FY 2024-25: " + "; ".join(parts) + ".")
    big = max(secs, key=lambda s: sum(tot[s["id"]]))
    small = min(secs, key=lambda s: sum(tot[s["id"]]))
    if sum(tot[small["id"]]) > 0 and big is not small:
        r = sum(tot[big["id"]]) / sum(tot[small["id"]])
        rc = a.c_calc(f"{big['name']} relative to {small['name']}",
                      f"{num(sum(tot[big['id']]))} ÷ {num(sum(tot[small['id']]))} = {r:,.2f}")
        a.p(f"The {big['name']} total is " + (f"about {r:,.1f} times" if r >= 1.5 else f"{(r - 1) * 100:.0f}% higher than")
            + f" that of {small['name']} {rc}. Sectors differ in size and in the nature of their business, so emission "
            f"intensity is the fairer comparison.")

    def cell(text, tone=None):
        return {"text": text, **({"tone": tone} if tone else {})}

    def cnt(m, q, text=False):
        k = sum(1 for c in m if (bool(c["values"].get(q)) if text else yes(c, q)))
        return f"{k} of {len(m)} ({share(k, len(m))})", k

    rows, xrows = [], []

    def add(label, cells, raw):
        rows.append({"label": label, "cells": cells})
        xrows.append([label] + raw)

    add("Companies", [cell(str(len(mem[s["id"]]))) for s in secs], [len(mem[s["id"]]) for s in secs])
    add("Scope 1 emissions (tCO₂e)", [cell(compact(tot[s["id"]][0])) for s in secs], [tot[s["id"]][0] for s in secs])
    add("Scope 2 emissions (tCO₂e)", [cell(compact(tot[s["id"]][1])) for s in secs], [tot[s["id"]][1] for s in secs])
    ys = [_yoy(mem[s["id"]], "scope12") for s in secs]
    add("Change in Scope 1 + Scope 2 vs FY 2023-24", [cell(pct(y) if y is not None else "n/a",
                                                          None if y is None else ("good" if y < 0 else "bad")) for y in ys],
        [None if y is None else round(y, 2) for y in ys])
    meds = [median(v for _, v in eligible(mi, mem[s["id"]])) for s in secs]
    add("Median emission intensity (tCO₂e per ₹ crore)", [cell(num(v, 2) if v is not None else "n/a") for v in meds],
        [None if v is None else round(v, 4) for v in meds])
    for q, label, text in (("1387", "Companies reporting Scope 3 emissions", False),
                           ("1340", "Companies with independent assurance of GHG emissions", False),
                           ("1341", "Companies with projects to reduce GHG emissions", False),
                           ("286", "Companies disclosing targets", True)):
        got = [cnt(mem[s["id"]], q, text) for s in secs]
        add(label, [cell(t) for t, _ in got], [k for _, k in got])
    a.block("grouped", title="Scope 1 and Scope 2 emissions by sector", subtitle=f"FY 2024-25, {CO2}", series=["Scope 1", "Scope 2"],
            log=True, groups=[{"label": s["name"], "values": list(tot[s["id"]]),
                               "displays": [compact(v).replace(" billion", "B").replace(" million", "M") for v in tot[s["id"]]]}
                              for s in secs],
            export=export("Scope 1 and Scope 2 emissions by sector", ["Sector", "Scope 1 (tCO2e)", "Scope 2 (tCO2e)"],
                          [[s["name"], tot[s["id"]][0], tot[s["id"]][1]] for s in secs]))
    a.block("compare", title="Side by side", columns=[{"label": s["name"], "sub": f"{len(mem[s['id']])} companies", "id": s["id"]}
                                                      for s in secs], rows=rows,
            export=export("Sector comparison", ["Measure"] + [s["name"] for s in secs], xrows))
    for s in secs:
        _excluded_note(a, mem[s["id"]])
    a.context.update({"sector": secs[0]["id"]})
    a.follow(f"Give me an overview of the {secs[0]['name']} sector", f"Give me an overview of the {secs[1]['name']} sector",
             "Emission intensity by sector")


# --------------------------------------------------------------------------- which sectors there are

def sector_list(ctx):
    a, kb = ctx.a, ctx.kb
    order = sorted(kb.sectors, key=lambda s: (-s["n"], s["name"]))
    a.kicker = "All sectors"
    a.title = "Sectors covered"
    note = a.c_note("Sector classification", "Each company is placed in one sector, as in the sector classification used here.")
    a.p(f"The {len(kb.companies)} companies covered fall into **{len(order)} sectors**. **{order[0]['name']}** has the most "
        f"companies ({order[0]['n']}), followed by {join([s['name'] + ' (' + str(s['n']) + ')' for s in order[1:3]])}; "
        f"{order[-1]['name']} has the fewest ({order[-1]['n']}) {note}.")
    a.block("bars", title="Companies per sector", unit="companies",
            rows=[{"id": s["id"], "label": s["name"], "value": s["n"], "display": str(s["n"]), "full": f"{s['n']} companies"}
                  for s in order],
            export=export("Companies per sector", ["Sector", "Companies"], [[s["name"], s["n"]] for s in order]))
    a.follow("Which sector emits the most?", f"Give me an overview of the {order[0]['name']} sector", "Emission intensity by sector")


# --------------------------------------------------------------------------- a sector's share of the total

def sector_share(ctx, sid, mid):
    a, kb = ctx.a, ctx.kb
    mid = mid if mid in ("scope1", "scope2", "scope3") else "scope12"
    m = M.NUMERIC[mid]
    s = kb.sector_by_id[sid]
    sname = s["name"]
    a.kicker = sname
    a.title = f"Share of {lc(m.label)}"
    tot = sorted(((x, _total(kb.members(x["id"]), mid)) for x in kb.sectors), key=lambda t: (-t[1], t[0]["name"]))
    grand = sum(v for _, v in tot)
    st = next(v for x, v in tot if x["id"] == sid)
    sp = 100 * st / grand if grand else 0
    calc = a.c_calc(f"{sname}: share of {lc(m.label)}", f"{num(st)} ÷ {num(grand)} = {sp:.2f}%",
                    note="Totals are the sum of what companies disclosed for FY 2024-25.")
    a.p(f"**{sname}** accounts for **{share(round(st), round(grand))}** of the {lc(m.label)} disclosed by all "
        f"{len(kb.companies)} companies for FY 2024-25: {compact(st)} of {compact(grand)} {CO2} {calc}."
        + (" It is the largest of the sectors on this measure." if tot[0][0]["id"] == sid else ""))
    a.block("stack", title=f"{sname} and all other sectors", subtitle=f"{m.label}, FY 2024-25", categorical=True,
            rows=[{"label": "All companies", "segments": [
                {"label": sname, "value": st, "display": f"{num(st)} {CO2}"},
                {"label": "Other sectors", "value": max(grand - st, 0), "display": f"{num(grand - st)} {CO2}"}]}],
            export=export(f"{sname}: share of {lc(m.label)}", ["Group", f"{m.label} (tCO2e)", "Share (%)"],
                          [[sname, st, round(sp, 2)], ["Other sectors", grand - st, round(100 - sp, 2)]]))
    top = [t for t in tot if t[1] > 0][:8]
    if sid not in [x["id"] for x, _ in top]:
        top = top[:7] + [(s, st)]
    a.block("bars", title=f"{m.label} by sector", subtitle="FY 2024-25, the largest sectors", unit=CO2, log=True,
            focus_label=sname,
            rows=[{"id": x["id"], "label": x["name"], "value": v, "highlight": x["id"] == sid,
                   "display": compact(v).replace(" billion", "B").replace(" million", "M"), "full": f"{num(v)} {CO2}"}
                  for x, v in top],
            export=export(f"{m.label} by sector", ["Sector", f"{m.label} (tCO2e)", "Share of total (%)"],
                          [[x["name"], v, round(100 * v / grand, 2)] for x, v in tot]))
    _excluded_note(a, kb.companies)
    a.context.update({"sector": sid, "metric": mid})
    a.follow(f"Give me an overview of the {sname} sector", f"Top 10 {sname} companies by emissions", "Emissions by sector")


# --------------------------------------------------------------------------- how emissions moved, sector by sector

def sector_change(ctx, change):
    a, kb = ctx.a, ctx.kb
    rows = [(s, _yoy(kb.members(s["id"]), "scope12")) for s in kb.sectors]
    rows = [r for r in rows if r[1] is not None]
    up = change == "increased"
    rows.sort(key=lambda r: (-r[1] if up else r[1], r[0]["name"]))
    a.kicker = "All sectors"
    a.title = "Change in emissions by sector"
    allc = _yoy(kb.companies, "scope12")
    cite = a.c_calc("Change in Scope 1 + Scope 2 by sector",
                    "(Sector total for FY 2024-25 − sector total for FY 2023-24) ÷ sector total for FY 2023-24",
                    note="Totals are the sum of what companies disclosed for each year.")
    lead = rows[0]
    moved = "rose" if lead[1] > 0 else "fell"
    a.p(f"Combined Scope 1 and Scope 2 emissions {moved} the most in **{lead[0]['name']}** ({pct(lead[1])}) between "
        f"FY 2023-24 and FY 2024-25, followed by {join([s['name'] + ' (' + pct(y) + ')' for s, y in rows[1:3]])} {cite}."
        + (f" Across all companies the change was {pct(allc)}." if allc is not None else ""))
    down = sum(1 for _, y in rows if y < 0)
    a.p(f"Emissions were lower in {down} of the {len(rows)} sectors and higher in {len(rows) - down} {cite}.")
    a.block("bars", title="Change in Scope 1 + Scope 2 emissions by sector", subtitle="FY 2024-25 vs FY 2023-24",
            unit="% change", diverging=True,
            rows=[{"id": s["id"], "label": s["name"], "value": y, "display": pct(y), "full": pct(y, digits=2)} for s, y in rows],
            export=export("Change in Scope 1 + Scope 2 emissions by sector", ["Sector", "FY 2024-25 (tCO2e)", "FY 2023-24 (tCO2e)", "Change (%)"],
                          [[s["name"], _total(kb.members(s["id"]), "scope12"), _total(kb.members(s["id"]), "scope12", "py"), round(y, 2)]
                           for s, y in rows]))
    _excluded_note(a, kb.companies)
    a.follow(f"Give me an overview of the {lead[0]['name']} sector", "Which companies reduced emissions the most?",
             "Emissions by sector")


# --------------------------------------------------------------------------- how the total moved between the two years

def total_change(ctx, sid, mid):
    a, kb = ctx.a, ctx.kb
    members = kb.members(sid) if sid else kb.companies
    sname = kb.sector_by_id[sid]["name"] if sid else None
    a.kicker = sname or "All companies"
    mids = [mid] if mid in ("scope1", "scope2", "scope3") else ["scope1", "scope2"]
    main = mid if mid in ("scope1", "scope2", "scope3") else "scope12"
    label = lc(M.NUMERIC[main].label) if main != "scope12" else "combined Scope 1 and Scope 2 emissions"
    a.title = f"Change in {'total ' + lc(M.NUMERIC[main].label) if main != 'scope12' else 'total emissions'}"
    cy, py, y = _total(members, main), _total(members, main, "py"), _yoy(members, main)
    who = f"the {len(members)} {sname} companies" if sname else f"the {len(members)} companies covered"
    if y is None:
        a.status = "partial"
        a.p(f"The change cannot be worked out, because no FY 2023-24 figure for {label} was disclosed by {who}.")
        return
    c1, c0 = _total_cite(a, sname, main, members), _total_cite(a, sname, main, members, "py")
    yn = ""
    low = ctx.plan.query.lower()
    asks_down = re.search(r"\b(reduc\w*|cut|lower\w*|decreas\w*|declin\w*|fall\w*|fell|drop\w*|down)\b", low)
    asks_up = re.search(r"\b(increas\w*|rise|rose|rising|grow\w*|grew|up|higher)\b", low)
    if ctx.plan.yesno and round(y, 1) != 0 and not (asks_down and asks_up):
        if asks_down:
            yn = "**Yes.** " if y < 0 else "**No.** "
        elif asks_up:
            yn = "**Yes.** " if y > 0 else "**No.** "
    cap = label[0].upper() + label[1:]
    if round(y, 1) == 0:
        a.p(f"{cap} disclosed by {who} were unchanged at {compact(cy)} {CO2} {c1} between FY 2023-24 and FY 2024-25 {c0}.")
    else:
        a.p(f"{yn}{cap} disclosed by {who} {'rose' if y > 0 else 'fell'} **{abs(y):.1f}%**, from {compact(py)} {CO2} in "
            f"FY 2023-24 {c0} to {compact(cy)} {CO2} in FY 2024-25 {c1}.")
    rows = []
    for m in mids:
        v, pv, yy = _total(members, m), _total(members, m, "py"), _yoy(members, m)
        rows.append((M.NUMERIC[m].label.replace(" emissions", ""), v, pv, yy))
    if len(rows) > 1:
        bits = [f"{lab} {'rose' if yy > 0 else 'fell'} {abs(yy):.1f}%" for lab, _, _, yy in rows if yy is not None]
        if bits:
            a.p("By scope: " + join(bits) + f" {a.c_calc('Change by scope' + (', ' + sname if sname else ''), 'Total for FY 2024-25 compared with the total for FY 2023-24, scope by scope')}.")
    short_total = lambda v: compact(v).replace(" billion", "B").replace(" million", "M")
    tiles = [kpi(lab, short_total(v), sub=CO2, delta=(pct(yy) + " vs FY 2023-24") if yy is not None else None,
                 tone="neutral" if yy is None else ("good" if yy < 0 else "bad")) for lab, v, _, yy in rows]
    if len(rows) > 1:
        tiles.append(kpi("Scope 1 + Scope 2", short_total(cy), sub=CO2, delta=pct(y) + " vs FY 2023-24", tone="good" if y < 0 else "bad"))
    a.block("kpis", items=tiles)
    a.block("grouped", title="FY 2023-24 and FY 2024-25", subtitle=f"{sname or 'All companies'}, {CO2}", series=["FY 2023-24", "FY 2024-25"],
            groups=[{"label": lab, "values": [pv, v], "displays": [short_total(pv), short_total(v)]} for lab, v, pv, _ in rows],
            log=len(rows) > 1,
            export=export(f"{sname or 'All companies'}: total emissions in both years",
                          ["Scope", "FY 2023-24 (tCO2e)", "FY 2024-25 (tCO2e)", "Change (%)"],
                          [[lab, pv, v, None if yy is None else round(yy, 2)] for lab, v, pv, yy in rows]))
    if main in ("scope12", "scope1", "scope2"):
        dirs = [c["derived"]["scope12_direction"] for c in members]
        down, up = dirs.count("decreased"), dirs.count("increased")
        if down + up:
            a.block("stack", title="How company emissions moved since FY 2023-24", subtitle="Combined Scope 1 and Scope 2, company by company",
                    rows=[{"label": sname or "All companies", "segments": [
                        {"label": "Lower", "value": down, "tone": "pos"}, {"label": "Higher or unchanged", "value": up, "tone": "neg"},
                        {"label": "Not comparable", "value": len(members) - down - up, "tone": "muted"}]}],
                    export=export("Change in emissions, company by company", ["Direction", "Companies"],
                                  [["Lower", down], ["Higher or unchanged", up], ["Not comparable", len(members) - down - up]]))
    _excluded_note(a, members)
    a.context.update({"sector": sid, "metric": main})
    a.follow(f"Which {sname + ' ' if sname else ''}companies reduced emissions the most?",
             f"Give me an overview of the {sname} sector" if sname else "Which sector improved the most?",
             f"Which {sname + ' ' if sname else ''}companies increased emissions the most?")


# --------------------------------------------------------------------------- how the scopes split across companies

def scope_split(ctx, sid=None):
    a, kb = ctx.a, ctx.kb
    members = kb.members(sid) if sid else kb.companies
    sname = kb.sector_by_id[sid]["name"] if sid else None
    a.kicker = sname or "All companies"
    a.title = "Emissions by scope"
    rows = [(lab, mid, _total(members, mid)) for lab, mid in (("Scope 1", "scope1"), ("Scope 2", "scope2"), ("Scope 3", "scope3"))]
    with3 = "scope3" in ctx.plan.raw_metrics
    rows = [r for r in rows if r[2] > 0 and (with3 or r[1] != "scope3")]
    total = sum(v for _, _, v in rows)
    who = f"the {len(members)} {sname} companies" if sname else f"the {len(members)} companies covered"
    cite = a.c_calc("Share of each scope" + (f", {sname}" if sname else ""),
                    "Total of each scope ÷ total of " + join([lab for lab, _, _ in rows]) + f" ({num(total)} {CO2})",
                    note="Totals are the sum of what companies disclosed for FY 2024-25.")
    parts = [f"**{lab}** accounts for **{share(round(v), round(total))}** ({compact(v)} {CO2})" for lab, _, v in rows]
    a.p(f"Of the {join([lab for lab, _, _ in rows])} emissions disclosed by {who} for FY 2024-25, {join(parts)} {cite}.")
    if not with3:
        a.p("Scope 3 is left out of this split because fewer than half of the companies disclose it; ask for it by name to include it.")
    a.block("stack", title="Emissions by scope", subtitle="Share of disclosed emissions, FY 2024-25", categorical=True,
            rows=[{"label": sname or "All companies", "segments": [
                {"label": f"{lab} {share(round(v), round(total))}", "value": v, "display": f"{num(v)} {CO2}"} for lab, _, v in rows]}],
            export=export("Emissions by scope", ["Scope", "Emissions (tCO2e)", "Share (%)"],
                          [[lab, v, round(100 * v / total, 2)] for lab, _, v in rows]))
    _excluded_note(a, members)
    a.follow("Emissions by sector", "Top 10 emitters", "How many companies report Scope 3 emissions?")


# --------------------------------------------------------------------------- who reviews the environment policy

def sector_review(ctx, sid):
    from .h_company import GOV_ITEMS, GOV_NOTE, HOW_OFTEN, WHO_MID
    a, kb = ctx.a, ctx.kb
    members = kb.members(sid) if sid else kb.companies
    sname = kb.sector_by_id[sid]["name"] if sid else None
    a.kicker = sname or "All companies"
    a.title = "Governance of the environment policy"
    order = ["Committee of the Board", "Director", "Any other Committee"]
    who = {k: [c for c in members if c["values"].get("308") == k] for k in order}
    nd = [c for c in members if c["values"].get("308") not in order]
    ranked = sorted(order, key=lambda k: (-len(who[k]), order.index(k)))
    n = len(members)
    cc = a.c_calc("Who reviews the environment policy", f"Count of each answer across {n} companies")
    where = f"{n} {sname} companies" if sname else f"{n} companies covered"
    a.p(f"Across the {where}, performance against the environment policy is most often reviewed by {WHO_MID[ranked[0]]} "
        f"({len(who[ranked[0]])} of {n}), then {WHO_MID[ranked[1]]} ({len(who[ranked[1]])}) and {WHO_MID[ranked[2]]} "
        f"({len(who[ranked[2]])}) {cc}.")
    often = {}
    for c in members:
        k = c["values"].get("326")
        if k:
            often[k] = often.get(k, 0) + 1
    oc = a.c_calc("How often the environment policy is reviewed", f"Count of each answer across {n} companies")
    gc = a.c_calc("Governance disclosures", f"Companies answering Yes to each item, out of {n}")
    pts = []
    if often:
        top = sorted(often.items(), key=lambda kv: (-kv[1], kv[0]))
        pts.append("**How often it is reviewed:** " + join([f"{HOW_OFTEN.get(k, k.lower())} ({v})" for k, v in top]) + f" {oc}.")
    for q, label in GOV_ITEMS:
        k = sum(1 for c in members if yes(c, q))
        pts.append(f"**{label}:** {k} of {n} companies ({share(k, n)}) {gc}.")
    if nd:
        pts.append(f"**Reviewer not disclosed:** {len(nd)} of {n} companies {cc}.")
    a.block("points", title="Key points", items=pts)
    a.block("bars", title="Who reviews the environment policy", subtitle=f"{sname or 'All companies'}, number of companies, FY 2024-25",
            unit="companies", rows=[{"label": k, "value": len(who[k]), "display": str(len(who[k])),
                                     "full": f"{len(who[k])} of {n} companies"} for k in ranked],
            export=export("Governance of the environment policy", ["Company"] + ([] if sid else ["Sector"])
                          + ["Reviewed by", "How often"] + [label for _, label in GOV_ITEMS],
                          [[c["name"]] + ([] if sid else [kb.sector_of(c)["name"]]) + [c["values"].get("308") or "Not disclosed",
                                                                                        c["values"].get("326") or "Not disclosed"]
                           + ["Yes" if yes(c, q) else "No" for q, _ in GOV_ITEMS]
                           for c in sorted(members, key=lambda c: c["name"].lower())]))
    a.note("context", GOV_NOTE)
    a.context.update({"metric": "review_level", "sector": sid})
    a.follow("Who reviews the environment policy, sector by sector?" if not sid else f"Give me an overview of the {sname} sector",
             f"Which {sname + ' ' if sname else ''}companies have independent assurance of GHG emissions?")


def _by_sector_review(ctx):
    a, kb = ctx.a, ctx.kb
    a.kicker = "All sectors"
    a.title = "Who reviews the environment policy, by sector"
    rows = []
    for s in kb.sectors:
        m = kb.members(s["id"])
        k = sum(1 for c in m if c["values"].get("308") == "Committee of the Board")
        rows.append((s, 100 * k / len(m), k, len(m)))
    rows.sort(key=lambda r: (-r[1], r[0]["name"]))
    K = sum(1 for c in kb.companies if c["values"].get("308") == "Committee of the Board")
    N = len(kb.companies)
    cc = a.c_calc("Review by a Committee of the Board, by sector", "Companies answering 'Committee of the Board' ÷ companies in the sector")
    a.p(f"**{rows[0][0]['name']}** has the highest share of companies whose environment policy is reviewed by a Committee of "
        f"the Board, {rows[0][2]} of {rows[0][3]} ({rows[0][1]:.0f}%), and **{rows[-1][0]['name']}** the lowest, {rows[-1][2]} of "
        f"{rows[-1][3]} ({rows[-1][1]:.0f}%). Across all companies it is {K} of {N} ({share(K, N)}) {cc}.")
    a.block("bars", title="Share of companies where a Committee of the Board reviews the environment policy", unit="% of companies",
            max=100, median={"value": 100 * K / N, "label": "All companies", "display": share(K, N)},
            rows=[{"id": s["id"], "label": s["name"], "value": v, "display": f"{v:.0f}%", "full": f"{k} of {n} companies"}
                  for s, v, k, n in rows],
            export=export("Review by a Committee of the Board, by sector", ["Sector", "Companies", "Committee of the Board", "Share (%)"],
                          [[s["name"], n, k, round(v, 1)] for s, v, k, n in rows]))
    a.follow(f"Who reviews the environment policy in {rows[0][0]['name']}?", "How often do companies review their environment policy?")
