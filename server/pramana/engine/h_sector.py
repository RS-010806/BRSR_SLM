"""Sector overviews, rankings, aggregates and screens."""
from __future__ import annotations

from ..analytics import band_counts, median, rating_distribution, sector_sum, yes_count
from . import metrics as M
from .common import bars, eligible, fmt_short, fmt_value, kpi, strip, value_cite, yes_rate
from .fmt import lc, CO2, compact, join, num, pct, plural, share, short_name
from .h_company import BOOL_PHRASE, QTABLE

SECTOR_TABLES = {"1341": "2.1", "1340": "2.4", "1387": "2.3"}
AI_TABLE = {"277": "1.6", "286": "1.7", "295": "1.8", "1342": "2.2"}


def _in(scope: str) -> str:
    """'in Power' for a sector, 'in the dataset' for the whole market."""
    return "in the dataset" if scope == "all companies" else f"in {scope}"


def _obs_for_sector(kb, sname):
    """Verbatim report observations that mention a sector by name."""
    out = []
    for t in kb.report["tables"]:
        for o in t["observations"]:
            if sname.lower() in o.lower():
                out.append((t, o))
    return out


def _sector_row(t, sname):
    for r in t["rows"]:
        if r[0].endswith(sname) or r[0].split(" - ", 1)[-1] == sname:
            return r[0]
    return None


def sector_overview(ctx, sid, mid=None):
    a, kb = ctx.a, ctx.kb
    if sid is None:
        return all_sectors(ctx, mid)
    s = kb.sector_by_id[sid]
    sname = s["name"]
    members = kb.members(sid)
    a.kicker = f"Sector overview · NSE {s['nse_code']}"
    a.title = sname
    row = lambda tid: a.c_table(tid, _sector_row(kb.tables[tid], sname))
    s1, s2 = sector_sum(members, "1330"), sector_sum(members, "1332")
    p1, p2 = sector_sum(members, "1331"), sector_sum(members, "1333")
    tot_all = sector_sum(kb.companies, "1330") + sector_sum(kb.companies, "1332")
    yoy = (s1 + s2 - p1 - p2) / (p1 + p2) * 100 if (p1 + p2) else None
    dirs = [c["derived"]["scope12_direction"] for c in members]
    med_int = median(c["derived"]["intensity_cr_cy"] for c in members)
    med_int_yoy = median(c["derived"]["intensity_yoy_pct"] for c in members)
    proj, _ = yes_count(members, "1341")
    asr, _ = yes_count(members, "1340")
    s3, _ = yes_count(members, "1387")
    s3py = sum(1 for c in members if (c["values"].get("1389") or 0) > 0)
    a.p(f"**{sname}** has {len(members)} companies in the dataset "
        f"{a.c_report_text('Table 2.2: Sector Coverage, NSE Classification and Company Distribution', 23, 'Chapter 2')}. "
        f"Together they reported **{compact(s1 + s2)} {CO2}** of Scope 1+2 emissions in FY 2024-25 {row('3.1')}, "
        f"{share(round(s1 + s2), round(tot_all))} of the all-company total, and a change of **{pct(yoy, digits=2)}** "
        f"year on year {row('3.2')}.")
    a.p(f"At company level, {dirs.count('decreased')} companies decreased absolute Scope 1+2 emissions, "
        f"{dirs.count('increased')} increased and {dirs.count('not_available')} lack comparable data {row('3.3')}. "
        f"The median intensity is {num(med_int, 1)} {CO2} per ₹ crore of turnover, with a median year-on-year "
        f"change of {pct(med_int_yoy, digits=2)} {row('3.5')}.")
    a.p(f"On actions, {proj} of {len(members)} companies report GHG reduction projects {row('2.1')}, {asr} have "
        f"independent GHG assurance {row('2.4')}, and {s3} report Scope 3 emissions, up from {s3py} the previous "
        f"year {row('2.3')}.")
    a.block("kpis", items=[
        kpi("Companies", str(len(members)), sub="in dataset"),
        kpi("Scope 1+2", compact(s1 + s2).replace(" billion", "B").replace(" million", "M"), sub=CO2,
            delta=pct(yoy, digits=2) + " YoY", tone="good" if yoy is not None and yoy < 0 else "bad"),
        kpi("Median intensity", num(med_int, 1), sub=f"{CO2} per ₹ crore", delta=pct(med_int_yoy) + " YoY",
            tone="good" if med_int_yoy is not None and med_int_yoy < 0 else "bad"),
        kpi("Independent GHG assurance", share(asr, len(members)), sub=f"{asr} of {len(members)}"),
        kpi("Reports Scope 3", share(s3, len(members)), sub=f"{s3} of {len(members)}, was {s3py}"),
    ])
    m12 = M.NUMERIC["scope12"]
    pairs = sorted(eligible(m12, members), key=lambda cv: (-cv[1], cv[0]["name"].lower()))
    a.blocks.append(bars(f"Largest Scope 1+2 emitters in {sname}", pairs, m12, limit=10, log=True,
                         median_v=median(v for _, v in pairs), subtitle="FY 2024-25"))
    a.block("stack", title="Company-wise direction of Scope 1+2, FY 2023-24 to FY 2024-25", rows=[
        {"label": sname, "segments": [{"label": "Decreased", "value": dirs.count("decreased"), "tone": "pos"},
                                      {"label": "Increased", "value": dirs.count("increased"), "tone": "neg"},
                                      {"label": "Not available", "value": dirs.count("not_available"), "tone": "muted"}]},
        {"label": "All companies", "segments": [
            {"label": "Decreased", "value": sum(1 for c in kb.companies if c["derived"]["scope12_direction"] == "decreased"), "tone": "pos"},
            {"label": "Increased", "value": sum(1 for c in kb.companies if c["derived"]["scope12_direction"] == "increased"), "tone": "neg"},
            {"label": "Not available", "value": sum(1 for c in kb.companies if c["derived"]["scope12_direction"] == "not_available"), "tone": "muted"}]}])
    idx = sorted(eligible(M.NUMERIC["index"], members), key=lambda cv: (-cv[1], cv[0]["name"].lower()))
    a.blocks.append(bars(f"Highest derived E1 index in {sname}", idx, M.NUMERIC["index"], limit=8,
                         subtitle="Equal-weighted Rating-sheet pillars, 0 to 100", median_v=median(v for _, v in idx)))
    obs = _obs_for_sector(kb, sname)
    if obs:
        a.block("report_quotes", title=f"What the IIMB report says about {sname}",
                items=[{"text": o, "cite": a.c_report_text(o, t["pdf_page"], f"Key observations, Table {t['id']}"),
                        "where": f"Table {t['id']}", "pdf_page": t["pdf_page"]} for t, o in obs[:4]])
    a.context.update({"sector": sid})
    top = pairs[0][0] if pairs else None
    a.follow(f"Best practices on GHG reduction projects in {sname}",
             f"Which {sname} companies lack independent GHG assurance?",
             f"Rank {sname} companies by emission intensity",
             f"Show {short_name(top['name'])}'s E1 profile" if top else None)


def all_sectors(ctx, mid=None):
    a, kb = ctx.a, ctx.kb
    a.kicker = "Cross-sector view"
    a.title = "All 22 sectors"
    tot = {s["id"]: sector_sum(kb.members(s["id"]), "1330") + sector_sum(kb.members(s["id"]), "1332") for s in kb.sectors}
    grand = sum(tot.values())
    order = sorted(kb.sectors, key=lambda s: (-tot[s["id"]], s["name"]))
    top4 = order[:4]
    share4 = sum(tot[s["id"]] for s in top4) / grand * 100
    t31 = kb.tables["3.1"]
    a.p(f"Across all {len(kb.companies)} companies, disclosed Scope 1+2 emissions total **{compact(grand)} {CO2}** in "
        f"FY 2024-25 {a.c_table('3.1', 'Total (All Sectors)')}. **{top4[0]['name']}** alone accounts for "
        f"{share(round(tot[top4[0]['id']]), round(grand))}, and the four largest sectors ({join([s['name'] for s in top4])}) "
        f"account for {share4:.1f}%.")
    obs = t31["observations"][0] if t31["observations"] else None
    if obs:
        a.block("report_quotes", title="The report's reading", items=[
            {"text": obs, "cite": a.c_report_text(obs, t31["pdf_page"], "Key observations, Table 3.1"),
             "where": "Key observations, Table 3.1", "pdf_page": t31["pdf_page"]}])
    a.block("treemap", title="Share of disclosed Scope 1+2 emissions by sector", subtitle="FY 2024-25, report exclusions applied",
            items=[{"label": s["name"], "short": s["short"], "value": tot[s["id"]], "display": f"{compact(tot[s['id']])} {CO2}",
                    "share": round(tot[s["id"]] / grand * 100, 1), "id": s["id"]} for s in order])
    med = []
    for s in kb.sectors:
        mm = median(c["derived"]["intensity_cr_cy"] for c in kb.members(s["id"]))
        med.append((s, mm))
    med.sort(key=lambda t: (-(t[1] or 0), t[0]["name"]))
    a.block("bars", title="Median Scope 1+2 intensity by sector", subtitle=f"{CO2} per ₹ crore of turnover",
            unit=f"{CO2} per ₹ crore", log=True, rows=[{"id": s["id"], "label": s["name"], "value": v,
                                                            "display": num(v, 1), "full": f"{num(v, 1)} {CO2} per ₹ crore"}
                                                           for s, v in med if v],
            cite=a.c_table("3.5"))
    yo = []
    for s in kb.sectors:
        mem = kb.members(s["id"])
        cy = sector_sum(mem, "1330") + sector_sum(mem, "1332")
        py = sector_sum(mem, "1331") + sector_sum(mem, "1333")
        yo.append((s, (cy - py) / py * 100 if py else None))
    yo.sort(key=lambda t: (t[1] if t[1] is not None else 0, t[0]["name"]))
    a.block("bars", title="Year-on-year change in sector Scope 1+2", subtitle="FY 2023-24 to FY 2024-25", diverging=True,
            unit="% change", rows=[{"id": s["id"], "label": s["name"], "value": v, "display": pct(v),
                                    "full": pct(v, digits=2)} for s, v in yo if v is not None], cite=a.c_table("3.2"))
    a.p(f"The median company improved its emission intensity by {pct(median(c['derived']['intensity_yoy_pct'] for c in kb.companies), digits=2)} "
        f"{a.c_table('3.4', 'Total')}, while absolute emissions rose {pct((sum(sector_sum(kb.companies, q) for q in ('1330', '1332')) / sum(sector_sum(kb.companies, q) for q in ('1331', '1333')) - 1) * 100, digits=2)} "
        f"{a.c_table('3.2', 'Total (All Sectors)')}.")
    a.follow("Give me an overview of the Power sector", "Which sectors lead on Scope 3 reporting?",
             "What are the key findings of the E1 report?")


# --------------------------------------------------------------------------- ranking

def ranking(ctx, mid, sid, n, extreme, quality, change):
    a, kb = ctx.a, ctx.kb
    if mid is None:
        mid = "scope12" if extreme == "high" and quality is None else "index"
    if mid in M.TEXT_Q:
        from .h_practice import best_practice
        return best_practice(ctx, mid, sid, None)
    if mid in M.BOOL_Q and mid not in M.NUMERIC:
        return screen(ctx, mid, sid, False, None)
    metric = M.get(mid, kb)
    if metric is None:
        metric = M.NUMERIC["index"]
    members = kb.members(sid) if sid else kb.companies
    scope = kb.sector_by_id[sid]["name"] if sid else "all companies"
    by = "yoy" if change or not metric.comparable_levels else "value"
    if by == "yoy":
        if change == "increased":
            desc = True
        elif change == "decreased":
            desc = False
        elif quality == "worst":
            desc = metric.better == "lower"
        else:
            desc = False if metric.better == "lower" else True
    else:
        if quality == "best":
            desc = metric.better == "higher"
        elif quality == "worst":
            desc = metric.better == "lower"
        elif extreme == "low":
            desc = False
        else:
            desc = True
    pairs = eligible(metric, members, by=by)
    if by == "yoy" and change == "decreased":
        pairs = [(c, v) for c, v in pairs if v < 0]
    if by == "yoy" and change == "increased":
        pairs = [(c, v) for c, v in pairs if v > 0]
    ordered = sorted(pairs, key=lambda cv: (-cv[1] if desc else cv[1], cv[0]["name"].lower()))
    n = n or 10
    top = ordered[:n]
    excluded = len(members) - len(eligible(metric, members, by=by))
    what = f"{lc(metric.label)}{' change' if by == 'yoy' else ''}"
    direction = ("largest increases in" if desc else "largest reductions in") if by == "yoy" else ("highest" if desc else "lowest")
    a.kicker = f"Ranking · {scope}"
    a.title = f"{'Top' if desc or by == 'yoy' else 'Lowest'} {len(top)}: {what}"
    if not top:
        a.status = "partial"
        a.p(f"No company {_in(scope)} has comparable data for {what}.")
        return
    lead = top[0]
    cite = a.c_derived(f"Ranking of {scope} on {what}",
                       f"{len(pairs)} companies with comparable values; sorted {'descending' if desc else 'ascending'}",
                       note=f"{excluded} companies excluded (not reported, report exclusions or unit-check flags). "
                            f"Ties broken alphabetically.")
    val = (lambda v: pct(v, digits=2)) if by == "yoy" else (lambda v: fmt_value(metric, v))
    a.p(f"Ranked by the {direction} {what}, **{short_name(lead[0]['name'])}** comes first "
        f"({val(lead[1])})" + (f" {vc}" if (vc := value_cite(a, lead[0], metric, by)) else "")
        + (f", followed by {join([short_name(c['name']) + ' (' + val(v) + ')' for c, v in top[1:3]])}" if len(top) > 1 else "")
        + f". {len(pairs)} of {len(members)} companies {_in(scope)} have comparable data {cite}.")
    if by == "yoy" and metric.kind == "abs":
        a.note("method", "Percentage changes on very small baselines can be large; the absolute change is shown alongside.")
    if not metric.comparable_levels and metric.note:
        a.note("method", metric.note)
    if metric.id == "index":
        a.note("method", metric.note)
    med = median(v for _, v in pairs)
    a.blocks.append(bars(a.title, top, metric, median_v=med, value_kind=by,
                         subtitle=f"{scope}, FY 2024-25" + ("" if by == "value" else " vs FY 2023-24"),
                         log=by == "value" and metric.kind == "abs"))
    rows = []
    for i, (c, v) in enumerate(top, 1):
        cy, py = metric.value(c), metric.prev(c) if metric.prev else None
        rows.append({"rank": i, "company": short_name(c["name"]), "id": c["id"], "sector": kb.sector_of(c)["short"],
                     "cy": fmt_value(metric, cy), "py": fmt_value(metric, py) if metric.prev else "",
                     "yoy": pct(metric.yoy(c), digits=2) if metric.yoy and metric.yoy(c) is not None else "n/a",
                     "abs": (compact(cy - py) if cy is not None and py is not None and metric.kind == "abs" else ""),
                     "cite": a.c_cell(c, metric.cy_q) if metric.cy_q else None})
    cols = [{"key": "rank", "label": "#", "align": "right"}, {"key": "company", "label": "Company"}]
    if not sid:
        cols.append({"key": "sector", "label": "Sector"})
    cols += [{"key": "cy", "label": "FY 2024-25", "align": "right"}]
    if metric.prev:
        cols += [{"key": "py", "label": "FY 2023-24", "align": "right"}, {"key": "yoy", "label": "YoY", "align": "right"}]
    if by == "yoy" and metric.kind == "abs":
        cols.append({"key": "abs", "label": f"Change ({CO2})", "align": "right"})
    a.block("table", title="Ranked list", columns=cols, rows=rows)
    a.context.update({"metric": metric.id, "sector": sid})
    a.follow(f"Show {short_name(lead[0]['name'])}'s E1 profile",
             f"Compare {short_name(top[0][0]['name'])} and {short_name(top[1][0]['name'])}" if len(top) > 1 else None,
             f"Give me an overview of the {scope} sector" if sid else "Which sector emits the most?")


# --------------------------------------------------------------------------- aggregate

def aggregate(ctx, mid, sid, change=None):
    a, kb = ctx.a, ctx.kb
    members = kb.members(sid) if sid else kb.companies
    sname = kb.sector_by_id[sid]["name"] if sid else None
    scope = sname or "all companies"
    a.kicker = f"Aggregate · {scope}"

    if mid is None and change in ("decreased", "increased"):
        mid = "scope12"
    if mid is None:
        a.title = "The E1 dataset at a glance"
        a.p(f"The dataset covers **{len(kb.companies)} companies** across **{len(kb.sectors)} NSE sectors**, using BRSR "
            f"filings for FY 2024-25 with FY 2023-24 comparatives "
            f"{a.c_report_text('At the time of analysis, 982 companies had valid and sufficiently complete BRSR filings and therefore constituted the effective sample.', 22, 'Chapter 2, Scope of the Study')}. "
            f"The E1 theme (GHG emissions and climate risk) spans {len(kb.questions)} BRSR questions, of which 35 carry "
            f"company responses in the Base Data sheet.")
        a.block("bars", title="Companies per sector", subtitle="Report Table 2.2", unit="companies",
                rows=[{"id": s["id"], "label": s["name"], "value": s["n"], "display": str(s["n"]), "full": f"{s['n']} companies"}
                      for s in sorted(kb.sectors, key=lambda s: (-s["n"], s["name"]))])
        a.follow("What are the key findings of the E1 report?", "Which sector emits the most?",
                 "How many companies report Scope 3 emissions?")
        return

    metric = M.get(mid, kb)
    # yes / no questions
    if mid in M.BOOL_Q:
        qid = M.BOOL_Q.get(mid, "1341")
        q = kb.q(qid)
        a.title = q["label"]
        y, n = yes_rate(members, qid)
        Y, N = yes_rate(kb.companies, qid)
        tid = QTABLE.get(qid)
        pos, neg, plural_phrase = BOOL_PHRASE.get(qid, ("", "", lc(q["label"])))
        if sid:
            cite = a.c_table(tid, _sector_row(kb.tables[tid], sname)) if tid in ("2.1", "2.3", "2.4") else \
                a.c_derived(f"{q['label']} in {sname}", f"{y} of {n} companies with Rating-sheet score 100 on Q{qid}")
            a.p(f"In {sname}, **{y} of {n} companies ({share(y, n)})** {plural_phrase} {cite}. Across all companies the "
                f"figure is {Y} of {N} ({share(Y, N)}) {a.c_table(tid, 'Total') if tid else ''}.")
        else:
            cite = a.c_table(tid, "Yes") if tid else a.c_derived(q["label"], f"{Y} of {N} companies with score 100 on Q{qid}")
            a.p(f"**{Y} of {N} companies ({share(Y, N)})** {plural_phrase} {cite}; {N - Y} ({share(N - Y, N)}) do not "
                f"or left it blank.")
        if qid == "1387":
            py = sum(1 for c in members if (c["values"].get("1389") or 0) > 0)
            a.p(f"The number reporting Scope 3 rose from {py} in the previous year to {y}, a change of "
                f"{pct((y - py) / py * 100 if py else None, digits=0)} {a.c_table('2.3', _sector_row(kb.tables['2.3'], sname) if sid else 'Total')}.")
        t = kb.tables.get(tid) if tid else None
        if t and t["observations"]:
            o = t["observations"][0]
            a.block("report_quotes", title="Report observation", items=[
                {"text": o, "cite": a.c_report_text(o, t["pdf_page"], f"Key observations, Table {tid}"),
                 "where": f"Table {tid}", "pdf_page": t["pdf_page"]}])
        rows = []
        for s in kb.sectors:
            sy, sn = yes_rate(kb.members(s["id"]), qid)
            rows.append((s, 100 * sy / sn, sy, sn))
        rows.sort(key=lambda r: (-r[1], r[0]["name"]))
        a.block("bars", title=f"{q['label']}: share of companies by sector", unit="% of companies",
                subtitle=f"All-company rate {share(Y, N)}", median={"value": 100 * Y / N, "label": "All companies",
                                                                   "display": share(Y, N)},
                rows=[{"id": s["id"], "label": s["name"], "value": v, "display": f"{v:.0f}%", "full": f"{sy} of {sn}",
                       "highlight": s["id"] == sid} for s, v, sy, sn in rows], max=100,
                cite=a.c_table(tid) if tid in ("2.1", "2.3", "2.4") else None)
        a.context.update({"metric": mid, "sector": sid})
        in_scope = f" in {sname}" if sname else ""
        a.follow(f"Which companies{in_scope} do not {plural_phrase}?",
                 f"Best practices on {lc(q['label'])}" if qid in ("1340", "1341") else None,
                 "What are the key findings of the E1 report?")
        return

    # narrative questions scored on the report's quality scale
    if mid in M.TEXT_Q:
        qid = M.TEXT_Q[mid]
        q = kb.q(qid)
        tid = AI_TABLE[qid]
        t = kb.tables[tid]
        a.title = q["label"]
        levels = q["rubric"]
        if tid != "2.2":
            rep = [(r[0], int(r[1].replace(",", "")), r[2]) for r in t["rows"][1:6]]
        else:
            total = next(r for r in t["rows"] if r[0].startswith("Total"))
            labs = ["High impact", "Well defined", "Some measurable reduction", "Small in scale", "No projects"]
            rep = [(labs[i], int(total[i + 1]), None) for i in range(5)][::-1]
        dist = rating_distribution(members, qid)
        if not sid:
            top = rep[-1]
            a.p(f"The IIMB report classifies the quality of {lc(q['label'])} for all {len(kb.companies)} companies "
                f"{a.c_table(tid)}. At the top of the scale, **{top[1]} companies ({share(top[1], 982)})** reach the "
                f"highest level: “{levels[-1]['text'].rstrip('.')}”. At the bottom, {rep[0][1]} "
                f"({share(rep[0][1], 982)}) sit at the lowest level.")
            a.block("stack", title=f"Report {('Table ' + tid)}: quality distribution", rows=[
                {"label": "IIMB report", "segments": [{"label": f"{l['score']}: {l['text'][:60]}", "value": r[1], "score": l["score"]}
                                                     for l, r in zip(levels, rep)]},
                {"label": "Rating sheet (recount)", "segments": [{"label": f"{l['score']}", "value": dist[str(l['score'])], "score": l["score"]}
                                                               for l in levels]}], ordinal=True)
            a.note("method", f"The Rating sheet was re-scored after the report table was produced: it places "
                             f"{dist['100']} companies at 100 on Q{qid} versus {top[1]} in Report Table {tid}. Company-level "
                             f"answers use the Rating sheet; this aggregate quotes the report.")
        else:
            parts = [f"{dist[str(l['score'])]} at {l['score']}" for l in levels]
            cite = a.c_derived(f"Q{qid} scores in {sname}", f"count of Rating-sheet scores across {len(members)} companies")
            a.p(f"In {sname}, Rating-sheet scores for {lc(q['label'])} (Q{qid}) are distributed as follows: "
                f"{join(parts)} {cite}.")
            if tid == "2.2":
                row = next((r for r in t["rows"] if r[0].endswith(sname)), None)
                if row:
                    a.p(f"Report Table 2.2 gives the sector split as {row[1]} high impact, {row[2]} well defined, "
                        f"{row[3]} some measurable reduction, {row[4]} small in scale and {row[5]} with no projects "
                        f"{a.c_table('2.2', row[0])}.")
            a.block("stack", title=f"{q['label']}: score distribution in {sname}", ordinal=True, rows=[
                {"label": sname, "segments": [{"label": f"{l['score']}", "value": dist[str(l['score'])], "score": l["score"]} for l in levels]},
                {"label": "All companies", "segments": [{"label": f"{l['score']}", "value": rating_distribution(kb.companies, qid)[str(l['score'])], "score": l["score"]} for l in levels]}])
        a.block("rubric", qid=qid, question=q["label"], score=None,
                levels=[{"score": l["score"], "text": l["text"]} for l in levels], source=q.get("rating_rule_source"))
        a.follow(f"Best practices on {lc(q['label'])}" + (f" in {sname}" if sname else ""),
                 f"Which companies score 100 on {lc(q['label'])}?")
        return

    if mid in M.CATEGORY_Q:
        qid = M.CATEGORY_Q[mid][0]
        tid = {"308": "1.9", "326": "1.10"}[qid]
        t = kb.tables[tid]
        a.title = kb.q(qid)["label"]
        rows = [(r[0], int(r[1])) for r in t["rows"][1:-1]]
        a.p(f"Across all companies: {join([f'{v} {k}' for k, v in rows])} {a.c_table(tid)}.")
        a.block("bars", title=t["title"], unit="companies", rows=[{"label": k, "value": v, "display": str(v), "full": f"{v} companies"} for k, v in rows],
                cite=a.c_table(tid))
        return

    # numeric
    if metric is None or mid not in M.NUMERIC:
        metric = M.NUMERIC["scope12"]
    a.title = metric.label
    if metric.kind == "abs":
        qc = {"scope1": ["1330"], "scope2": ["1332"], "scope12": ["1330", "1332"], "scope3": ["1388"]}[metric.id]
        qp = {"scope1": ["1331"], "scope2": ["1333"], "scope12": ["1331", "1333"], "scope3": ["1389"]}[metric.id]
        cy = sum(sector_sum(members, q) for q in qc)
        py = sum(sector_sum(members, q) for q in qp)
        tid = "3.8" if metric.id == "scope3" else "3.1"
        rowlab = _sector_row(kb.tables[tid], sname) if sid else "Total (All Sectors)"
        yoy = (cy - py) / py * 100 if py else None
        a.p(f"Total {lc(metric.label)} for {scope} was **{compact(cy)} {CO2}** in FY 2024-25 {a.c_table(tid, rowlab)}, "
            f"against {compact(py)} {CO2} in FY 2023-24 ({pct(yoy, digits=2)}) "
            f"{a.c_table('3.2' if metric.id == 'scope12' else tid, rowlab)}.")
        if metric.id in ("scope12", "scope1", "scope2") or change:
            dirs = [c["derived"]["scope12_direction"] for c in members]
            a.p(f"Company by company (Scope 1+2), {dirs.count('decreased')} decreased, {dirs.count('increased')} increased "
                f"and {dirs.count('not_available')} lack comparable data {a.c_table('3.3', rowlab)}.")
        if metric.id == "scope3":
            n3 = sum(1 for c in members if c["values"].get("1388") is not None)
            a.p(f"Only companies that report Scope 3 contribute: {n3} of {len(members)}.")
        a.note("method", "Sector totals apply the report's two exclusions (SIS Limited, and Patel Engineering's "
                         "previous-year Scope 2), which reproduces Report Tables 3.1 and 3.2 exactly.")
        pairs = sorted(eligible(metric, members), key=lambda cv: (-cv[1], cv[0]["name"].lower()))
        a.blocks.append(bars(f"Largest contributors: {scope}", pairs, metric, limit=10, log=True, subtitle="FY 2024-25"))
        if not sid:
            by = []
            for s in kb.sectors:
                mem = kb.members(s["id"])
                by.append((s, sum(sector_sum(mem, q) for q in qc)))
            by.sort(key=lambda t: (-t[1], t[0]["name"]))
            a.block("bars", title=f"{metric.label} by sector", unit=CO2, log=True,
                    rows=[{"id": s["id"], "label": s["name"], "value": v, "display": compact(v).replace(" billion", "B").replace(" million", "M"),
                           "full": f"{num(v)} {CO2}"} for s, v in by if v > 0], cite=a.c_table(tid))
    else:
        vals = [v for _, v in eligible(metric, members, by="yoy")]
        bc = band_counts(vals)
        med = median(vals)
        tid = {"intensity": "3.4", "intensity_phys": "3.6", "scope3_intensity": "3.9"}.get(metric.id)
        a.p(f"{len(vals)} companies {_in(scope)} report a comparable year-on-year change in {lc(metric.label)}; the "
            f"median change is **{pct(med, digits=2)}** {a.c_table(tid, 'Total') if tid and not sid else a.c_derived('Median change', f'median of {len(vals)} company-level changes')}.")
        bcite = a.c_table(tid, "Total") if tid and not sid else a.c_derived("Change bands", f"{len(vals)} companies grouped by year-on-year change")
        a.p(f"{bc[0]} companies cut intensity by more than 10%, {bc[1]} by 5 to 10%, {bc[2]} stayed within 5%, "
            f"{bc[3]} rose 5 to 10% and {bc[4]} rose more than 10% {bcite}.")
        if metric.comparable_levels:
            lv = [v for _, v in eligible(metric, members)]
            a.p(f"The median level is {num(median(lv), 1)} {metric.unit} "
                f"{a.c_table('3.5', _sector_row(kb.tables['3.5'], sname) if sid else 'Total (All Sectors)') if metric.id == 'intensity' else ''}.")
        a.block("bars", title="Distribution of year-on-year change", unit="companies", ordinal=True,
                rows=[{"label": lab, "value": v, "display": str(v), "full": f"{v} companies"} for lab, v in
                      zip(["Cut > 10%", "Cut 5 to 10%", "Within ±5%", "Rose 5 to 10%", "Rose > 10%"], bc)])
        if not sid and metric.id == "intensity":
            rows = []
            for s in kb.sectors:
                rows.append((s, median(c["derived"]["intensity_yoy_pct"] for c in kb.members(s["id"]))))
            rows = sorted([r for r in rows if r[1] is not None], key=lambda t: (t[1], t[0]["name"]))
            a.block("bars", title="Median intensity change by sector", diverging=True, unit="% change",
                    rows=[{"id": s["id"], "label": s["name"], "value": v, "display": pct(v), "full": pct(v, digits=2)}
                          for s, v in rows], cite=a.c_table("3.5"))
        if metric.note:
            a.note("method", metric.note)
    a.context.update({"metric": metric.id, "sector": sid})
    a.follow(f"Top 10 {scope + ' ' if sid else ''}companies by {lc(metric.label)}",
             "Which sector emits the most?", "What are the key findings of the E1 report?")


# --------------------------------------------------------------------------- screen

def screen(ctx, mid, sid, negated, change):
    a, kb = ctx.a, ctx.kb
    members = kb.members(sid) if sid else kb.companies
    sname = kb.sector_by_id[sid]["name"] if sid else None
    scope = sname or "all companies"
    a.kicker = f"Screen · {scope}"
    if change in ("decreased", "increased") and (mid is None or mid in ("scope12", "scope1", "scope2")):
        hits = [c for c in members if c["derived"]["scope12_direction"] == change]
        a.title = f"Companies whose Scope 1+2 {change}"
        a.p(f"**{len(hits)} of {len(members)}** companies {_in(scope)} {change} absolute Scope 1+2 emissions between "
            f"FY 2023-24 and FY 2024-25 {a.c_table('3.3', _sector_row(kb.tables['3.3'], sname) if sid else 'Total (All Sectors)')}.")
        m = M.NUMERIC["scope12"]
        hits.sort(key=lambda c: ((m.yoy(c) or 0) * (1 if change == "decreased" else -1), c["name"].lower()))
        _list_table(ctx, hits, sid, extra=("yoy", "Scope 1+2 YoY", lambda c: pct(m.yoy(c), digits=2) if m.yoy(c) is not None else "n/a"))
        return
    if mid is None:
        if sid:
            a.title = f"{sname}: all {len(members)} companies"
            a.p(f"The {len(members)} {sname} companies in the dataset, with their headline E1 figures "
                f"{a.c_report_text('Table 2.2: Sector Coverage, NSE Classification and Company Distribution', 23, 'Chapter 2')}.")
            _list_table(ctx, sorted(members, key=lambda c: c["name"].lower()), sid)
            a.follow(f"Give me an overview of the {sname} sector", f"Rank {sname} companies by emission intensity")
            return
        return aggregate(ctx, None, None)
    if mid in M.TEXT_Q:
        qid = M.TEXT_Q[mid]
        q = kb.q(qid)
        if negated:
            hits = [c for c in members if (c["ratings"].get(qid) or 0) == 0]
            a.title = f"No meaningful disclosure: {lc(q['label'])}"
        else:
            hits = [c for c in members if (c["ratings"].get(qid) or 0) >= 75]
            a.title = f"Strong disclosure: {lc(q['label'])}"
        rule = "Rating-sheet score is 0 or blank" if negated else "Rating-sheet score is 75 or more"
        cite = a.c_derived(f"Q{qid} screen", rule)
        a.p(f"**{len(hits)} of {len(members)}** companies {_in(scope)} score "
            f"{'0 or blank' if negated else '75 or 100'} on {lc(q['label'])} (Q{qid}) {cite}.")
        hits.sort(key=lambda c: (-(c["ratings"].get(qid) or 0), c["name"].lower()))
        _list_table(ctx, hits, sid, extra=("score", "Score", lambda c: str(c["ratings"].get(qid)) if c["ratings"].get(qid) is not None else "blank"))
        return
    qid = M.BOOL_Q.get(mid)
    if qid is None:
        return ranking(ctx, mid, sid, None, None, None, None)
    q = kb.q(qid)
    pos, neg, plural_phrase = BOOL_PHRASE.get(qid, ("", "", lc(q["label"])))
    hits = [c for c in members if (c["ratings"].get(qid) == 100) != negated]
    a.title = f"{'Without' if negated else 'With'}: {lc(q['label'])}"
    tid = SECTOR_TABLES.get(qid) or QTABLE.get(qid)
    cite = a.c_table(tid, _sector_row(kb.tables[tid], sname) if sid and tid in ("2.1", "2.3", "2.4") else None) if tid else \
        a.c_derived(q["label"], f"Rating-sheet score {'not ' if negated else ''}= 100 on Q{qid}")
    a.p(f"**{len(hits)} of {len(members)}** companies {_in(scope)} "
        f"{('do not ' + plural_phrase) if negated else plural_phrase} {cite}.")
    hits.sort(key=lambda c: c["name"].lower())
    _list_table(ctx, hits, sid)
    if not sid:
        counts = {}
        for c in hits:
            counts[c["sector"]] = counts.get(c["sector"], 0) + 1
        a.block("bars", title="By sector", unit="companies", rows=[
            {"id": s, "label": kb.sector_by_id[s]["name"], "value": v, "display": str(v),
             "full": f"{v} of {kb.sector_by_id[s]['n']}"} for s, v in sorted(counts.items(), key=lambda t: (-t[1], kb.sector_by_id[t[0]]["name"]))])
    a.context.update({"metric": mid, "sector": sid})
    a.follow(f"Best practices on {lc(q['label'])}" if qid in ("1340", "1341") else None,
             f"Give me an overview of the {sname} sector" if sname else None)


def _list_table(ctx, cos, sid, extra=None):
    a, kb = ctx.a, ctx.kb
    m = M.NUMERIC["scope12"]
    rows = []
    for c in cos:
        r = {"company": short_name(c["name"]), "id": c["id"], "sector": kb.sector_of(c)["short"],
             "s12": fmt_short(m, m.value(c)) if m.value(c) is not None else "n/r",
             "index": f"{c['derived']['index']['overall']:.1f}" if c["derived"]["index"]["overall"] is not None else "n/a",
             "assured": "Yes" if c["ratings"].get("1340") == 100 else "No",
             "scope3": "Yes" if c["ratings"].get("1387") == 100 else "No"}
        if extra:
            r[extra[0]] = extra[2](c)
        rows.append(r)
    cols = [{"key": "company", "label": "Company"}]
    if not sid:
        cols.append({"key": "sector", "label": "Sector"})
    if extra:
        cols.append({"key": extra[0], "label": extra[1], "align": "right"})
    cols += [{"key": "s12", "label": "Scope 1+2 (tCO₂e)", "align": "right"}, {"key": "assured", "label": "GHG assured"},
             {"key": "scope3", "label": "Scope 3"}, {"key": "index", "label": "E1 index", "align": "right"}]
    a.block("table", title=f"{len(rows)} companies", columns=cols, rows=rows, csv=True)
