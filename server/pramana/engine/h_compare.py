"""Company vs company, and company vs sector peers."""
from __future__ import annotations

from ..analytics import median
from . import metrics as M
from .common import (bars, beat_share, change_tone, eligible, fmt_short, fmt_value, kpi, rank_of, rank_phrase,
                     strip)
from .evidence import highlight, themes_in
from .fmt import lc, CO2, join, num, pct, short_name
from .h_company import BOOL_PHRASE

PROFILE_ROWS = [
    ("scope1", "Scope 1 (tCO₂e)"), ("scope2", "Scope 2 (tCO₂e)"), ("scope3", "Scope 3 (tCO₂e)"),
    ("intensity", "Intensity (tCO₂e per ₹ crore)"),
]


def compare(ctx, cids, mid):
    a, kb = ctx.a, ctx.kb
    cos = [kb.by_id[i] for i in cids][:6]
    for c in cos:
        a.company_ref(c)
    names = [short_name(c["name"]) for c in cos]
    a.kicker = "Comparison"
    a.title = " vs ".join(names)
    if len(cids) > 6:
        a.note("method", "Comparisons are limited to six companies; the first six named are shown.")
    sectors = {c["sector"] for c in cos}
    if len(sectors) > 1:
        a.note("context", "These companies sit in different sectors, so absolute emissions reflect business models as "
                          "much as performance. Intensity and year-on-year change are the fairer comparison.")
    metric = M.get(mid, kb) if mid else None
    if metric is not None and metric.kind in ("abs", "intensity") and mid in M.NUMERIC:
        _compare_numeric(ctx, cos, metric)
    elif mid in M.TEXT_Q:
        _compare_text(ctx, cos, M.TEXT_Q[mid])
    elif mid in M.BOOL_Q:
        _compare_bool(ctx, cos, M.BOOL_Q[mid])
    else:
        _compare_profile(ctx, cos)
    a.context.update({"companies": [c["id"] for c in cos], "metric": mid})


def _compare_numeric(ctx, cos, metric):
    a = ctx.a
    rows, series = [], []
    vals = []
    for c in cos:
        v, pv, y = metric.value(c), metric.prev(c), metric.yoy(c)
        ok = v is not None and metric.level_ok(c)
        cite = a.c_cell(c, metric.cy_q) if metric.cy_q else a.c_derived(
            f"Scope 1+2 ({short_name(c['name'])})", f"{num(c['values'].get('1330'))} + {num(c['values'].get('1332'))} = {num(v)}",
            [a.c_cell(c, "1330"), a.c_cell(c, "1332")])
        vals.append((c, v, pv, y, ok, cite))
    reported = [(c, v, y, cite) for c, v, pv, y, ok, cite in vals if v is not None and ok]
    missing = [c for c, v, pv, y, ok, cite in vals if v is None]
    if reported and metric.comparable_levels:
        hi = max(reported, key=lambda t: (t[1], t[0]["name"]))
        lo = min(reported, key=lambda t: (t[1], t[0]["name"]))
        a.p(f"On {lc(metric.label)} in FY 2024-25, **{short_name(hi[0]['name'])}** reported the highest value "
            f"({fmt_value(metric, hi[1])}) {hi[3]} and **{short_name(lo[0]['name'])}** the lowest "
            f"({fmt_value(metric, lo[1])}) {lo[3]}.")
    ys = [(c, y) for c, v, pv, y, ok, cite in vals if y is not None and ok]
    if ys:
        best = min(ys, key=lambda t: (t[1], t[0]["name"])) if metric.better == "lower" else max(ys, key=lambda t: (t[1], t[0]["name"]))
        worst = max(ys, key=lambda t: (t[1], t[0]["name"])) if metric.better == "lower" else min(ys, key=lambda t: (t[1], t[0]["name"]))
        if best[0]["id"] != worst[0]["id"]:
            yc = a.c_derived("Year-on-year changes", "; ".join(f"{short_name(c['name'])} {pct(y, digits=2)}" for c, y in ys),
                             note="(FY 2024-25 minus FY 2023-24) divided by FY 2023-24, from the cited cells.")
            lo = min(ys, key=lambda t: (t[1], t[0]["name"]))
            hi = max(ys, key=lambda t: (t[1], t[0]["name"]))
            a.p(f"Year on year, changes ranged from {pct(lo[1])} ({short_name(lo[0]['name'])}) to {pct(hi[1])} "
                f"({short_name(hi[0]['name'])}); {'lower' if metric.better == 'lower' else 'higher'} is better for this "
                f"metric {yc}.")
    if missing:
        a.p(f"Not reported: {join([short_name(c['name']) + ' ' + a.c_cell(c, metric.cy_q or '1330') for c in missing])}.")
    for c, v, pv, y, ok, cite in vals:
        if v is not None and not ok:
            a.note("data_quality", f"{short_name(c['name'])}: value shown as reported but flagged; see citation.")
    for c in cos:
        for f in c["flags"]:
            if set(f["qids"]) & set(metric.qids):
                a.note("data_quality", f"{short_name(c['name'])}: {f['text']}")
    if not metric.comparable_levels and metric.note:
        a.note("method", metric.note)
    a.block("grouped", title=metric.label, subtitle=f"FY 2023-24 and FY 2024-25, {metric.unit}",
            series=["FY 2023-24", "FY 2024-25"],
            groups=[{"label": short_name(c["name"]), "values": [pv, v],
                     "displays": [fmt_short(metric, pv), fmt_short(metric, v)]} for c, v, pv, y, ok, cite in vals],
            log=metric.kind == "abs")
    table_rows = []
    for c, v, pv, y, ok, cite in vals:
        members = ctx.kb.members(c["sector"])
        pairs = eligible(metric, members)
        r, n, _ = rank_of(c, pairs, True) if ok and v is not None else (None, len(pairs), None)
        rq = metric.rating_q[0] if metric.rating_q else None
        table_rows.append({"company": short_name(c["name"]), "id": c["id"], "sector": ctx.kb.sector_of(c)["name"],
                           "cy": fmt_value(metric, v), "py": fmt_value(metric, pv), "yoy": pct(y) if y is not None else "n/a",
                           "rank": f"{r} of {n}" if r else "n/a",
                           "rating": str(c["ratings"].get(rq)) if rq and c["ratings"].get(rq) is not None else "n/a",
                           "cite": cite})
    a.block("table", title=f"{metric.label}: detail", rows=table_rows,
            columns=[{"key": "company", "label": "Company"}, {"key": "sector", "label": "Sector"},
                     {"key": "cy", "label": "FY 2024-25", "align": "right"}, {"key": "py", "label": "FY 2023-24", "align": "right"},
                     {"key": "yoy", "label": "YoY", "align": "right"}, {"key": "rank", "label": "Rank in sector (1 = highest)", "align": "right"},
                     {"key": "rating", "label": "Rating", "align": "right"}])
    a.follow(f"Compare {join([short_name(c['name']) for c in cos])} on Scope 3" if metric.id != "scope3" else
             f"Compare {join([short_name(c['name']) for c in cos])} on emission intensity",
             f"Compare {join([short_name(c['name']) for c in cos])} on targets",
             f"How does {short_name(cos[0]['name'])} compare with its peers?")


def _compare_text(ctx, cos, qid):
    a, kb = ctx.a, ctx.kb
    q = kb.q(qid)
    scored = sorted(cos, key=lambda c: (-(c["ratings"].get(qid) or -1), c["name"].lower()))
    parts = []
    for c in scored:
        s = c["ratings"].get(qid)
        parts.append(f"{short_name(c['name'])} {s if s is not None else 'n/a'}/100 {a.c_rating(c, qid)}")
    a.p(f"Rating-sheet scores for {lc(q['label'])}: {join(parts)}.")
    items = []
    for c in scored:
        text = c["values"].get(qid)
        if not text:
            continue
        segs = ctx.index.by_cell.get((c["id"], qid), [])
        items.append({"company": c["name"], "company_id": c["id"], "short": short_name(c["name"]),
                      "sector": kb.sector_of(c)["name"], "qid": qid, "question": q["label"], "score": c["ratings"].get(qid),
                      "text": text, "segments": highlight(segs, k=2), "themes": ctx.kb.themes(c["id"], qid),
                      "cite": a.c_cell(c, qid), "cell": c["cells"].get(qid)})
    if items:
        a.block("quotes", title=f"{q['label']}, side by side", items=items, columns=True)
    blank = [short_name(c["name"]) for c in cos if not c["values"].get(qid)]
    if blank:
        a.p(f"No disclosure text: {join(blank)}.")
    th = {c["id"]: set(ctx.kb.themes(c["id"], qid)) for c in cos}
    all_th = sorted(set().union(*th.values()))
    if all_th:
        a.block("matrix", title="Practices named in each disclosure", columns=[short_name(c["name"]) for c in cos],
                rows=[{"label": t, "values": [t in th[c["id"]] for c in cos]} for t in all_th])


def _compare_bool(ctx, cos, qid):
    a, kb = ctx.a, ctx.kb
    q = kb.q(qid)
    yes = [c for c in cos if c["ratings"].get(qid) == 100]
    no = [c for c in cos if c["ratings"].get(qid) != 100]
    pos, neg, plural = BOOL_PHRASE.get(qid, ("yes", "no", "report it"))
    if yes:
        a.p(f"**{join([short_name(c['name']) + ' ' + a.c_rating(c, qid) for c in yes])}** {plural.replace('report', 'report') if len(yes) > 1 else pos}.")
    if no:
        a.p(f"{join([short_name(c['name']) + ' ' + a.c_rating(c, qid) for c in no])} "
            f"{'do not' if len(no) > 1 else 'does not'} ({lc(q['label'])}).")
    a.block("checklist", title=q["label"], items=[{"label": short_name(c["name"]), "value": c["ratings"].get(qid) == 100,
                                                  "cite": a.c_rating(c, qid)} for c in cos])


def _compare_profile(ctx, cos):
    a, kb = ctx.a, ctx.kb
    a.p(f"Side-by-side E1 view of {join([f'**{short_name(c['name'])}**' for c in cos])}, using reported values "
        f"and Rating-sheet scores.")
    idx = [(c, c["derived"]["index"]["overall"]) for c in cos if c["derived"]["index"]["overall"] is not None]
    if idx:
        lead = max(idx, key=lambda t: (t[1], t[0]["name"]))
        a.p(f"On the derived E1 index, {short_name(lead[0]['name'])} leads at {lead[1]:.1f}/100 "
            f"{a.c_method('E1 index (derived)', M.NUMERIC['index'].note)}.")
    rows = []
    for mid, label in PROFILE_ROWS:
        m = M.NUMERIC[mid]
        vals = [m.value(c) for c in cos]
        comparable = [(i, v) for i, (c, v) in enumerate(zip(cos, vals)) if v is not None and m.level_ok(c)]
        best = min(comparable, key=lambda t: t[1])[0] if comparable else None
        rows.append({"label": label, "cells": [{"text": fmt_short(m, v) if v is not None else "n/r",
                                                "full": fmt_value(m, v), "best": i == best,
                                                "cite": a.c_cell(c, m.cy_q)} for i, (c, v) in enumerate(zip(cos, vals))]})
        ys = [m.yoy(c) for c in cos]
        rows.append({"label": f"{label.split(' (')[0]} YoY", "cells": [{"text": pct(y) if y is not None else "n/a",
                                                                         "tone": change_tone(y)} for y in ys]})
    for q, label in (("1340", "Independent GHG assurance"), ("1387", "Reports Scope 3"), ("1341", "GHG reduction projects"),
                     ("268", "Policy covers value chain")):
        rows.append({"label": label, "cells": [{"text": "Yes" if c["ratings"].get(q) == 100 else "No",
                                                "tone": "good" if c["ratings"].get(q) == 100 else "bad",
                                                "cite": a.c_rating(c, q)} for c in cos]})
    for q, label in (("286", "Targets score"), ("295", "Performance vs targets score"), ("1342", "Project quality score")):
        rows.append({"label": label, "cells": [{"text": str(c["ratings"].get(q)) if c["ratings"].get(q) is not None else "n/a",
                                                "score": c["ratings"].get(q), "cite": a.c_rating(c, q)} for c in cos]})
    rows.append({"label": "E1 index (derived)", "cells": [{"text": f"{c['derived']['index']['overall']:.1f}"
                                                           if c["derived"]["index"]["overall"] is not None else "n/a",
                                                           "score": c["derived"]["index"]["overall"]} for c in cos]})
    a.block("compare", title="Scorecard", columns=[{"label": short_name(c["name"]), "sub": kb.sector_of(c)["name"],
                                                    "id": c["id"]} for c in cos], rows=rows)
    groups = []
    for p_key, p_label in (("governance", "Governance"), ("action", "Action"), ("performance", "Performance")):
        vals = [c["derived"]["index"]["pillars"][p_key]["score"] for c in cos]
        groups.append({"label": p_label, "values": vals, "displays": [f"{v:.0f}" if v is not None else "n/a" for v in vals]})
    a.block("grouped", title="Pillar scores", subtitle="Average Rating-sheet score per pillar, 0 to 100",
            series=[short_name(c["name"]) for c in cos], groups=groups, max=100)
    a.follow(f"Compare {join([short_name(c['name']) for c in cos])} on Scope 1",
             f"Compare {join([short_name(c['name']) for c in cos])} on targets",
             f"Compare {join([short_name(c['name']) for c in cos])} on GHG reduction projects")


# --------------------------------------------------------------------------- peers

PEER_DIMENSIONS = [
    ("index", "value", "E1 index (derived)"),
    ("scope12", "yoy", "Scope 1+2 change, YoY"),
    ("intensity", "value", "Scope 1+2 intensity"),
    ("intensity", "yoy", "Intensity change, YoY"),
    ("scope12", "value", "Scope 1+2 emissions"),
    ("targets", "value", "Targets score"),
    ("projects", "value", "GHG project quality score"),
]


def peer_benchmark(ctx, c, mid, peers=None):
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    sec = kb.sector_of(c)
    sname = sec["name"]
    members = kb.members(c["sector"])
    grp, grp_n = sname, sec["n"]
    custom = [kb.by_id[x] for x in (peers or []) if x in kb.by_id and x != c["id"]]
    if custom:
        members = [c] + custom
        grp, grp_n = "your peer group", len(members)
        for x in custom:
            a.company_ref(x)
        a.note("context", f"Using the peer group you set earlier in this conversation: "
                          f"{join([short_name(x['name']) for x in custom])}. Say \u201cforget my peer group\u201d to "
                          f"go back to the full {sname} sector.")
    from .h_company import flag_notes
    flag_notes(ctx, c, ["1330", "1331", "1332", "1333", "1334", "1335"])
    a.kicker = f"{c['name']} · Peer benchmark"
    a.title = f"Against {grp_n - 1} {sname} peers" if not custom else f"Against your {grp_n - 1} chosen peers"
    if mid and mid not in ("index",) and M.get(mid, kb) is not None:
        metric = M.get(mid, kb)
        by = "yoy" if not metric.comparable_levels else "value"
        pairs = eligible(metric, members, by=by)
        mine = next((v for x, v in pairs if x["id"] == c["id"]), None)
        if mine is None:
            a.status = "partial"
            a.p(f"{c['name']} has no comparable value for {lc(metric.label)}"
                f"{' (units vary by company, so only the change is compared)' if by == 'yoy' else ''}.")
        else:
            desc = True
            r, n, ordered = rank_of(c, pairs, desc)
            beat, others = beat_share(mine, pairs, c, metric.better)
            med = median(v for _, v in pairs)
            unit_word = "change" if by == "yoy" else ""
            shown = pct(mine) if by == "yoy" else fmt_value(metric, mine)
            a.p(f"On {lc(metric.label)}{' (year-on-year change)' if by == 'yoy' else ''}, {c['name']} "
                f"({shown}) ranks **{rank_phrase(r, n)}** among {n} {'companies in ' + grp if custom else sname + ' companies'} with comparable data "
                f"{a.c_derived('Peer ranking', f'{n} companies sorted high to low on ' + lc(metric.label) + (' change' if by == 'yoy' else ''))}. "
                f"It is {'better' if (mine < med if metric.better == 'lower' else mine > med) else 'worse'} than the sector "
                f"median ({pct(med) if by == 'yoy' else fmt_value(metric, med)}) and outperforms {beat} of {others} peers.")
            a.blocks.append(bars(f"{metric.label}{' change' if by == 'yoy' else ''}: {grp}", ordered, metric,
                                 focus_ids={c["id"]}, median_v=med, subtitle=f"{n} companies, FY 2024-25",
                                 log=metric.kind == "abs" and by == "value", value_kind=by, limit=25 if n > 25 else None))
            if n > 25 and r > 25:
                a.blocks[-1]["rows"].append({"id": c["id"], "label": short_name(c["name"]), "value": mine, "rank": r,
                                             "display": pct(mine) if by == "yoy" else fmt_short(metric, mine),
                                             "full": shown, "highlight": True})
            a.blocks.append(strip(f"Distribution in {grp}", pairs, metric, focus_ids={c["id"]}, value_kind=by))
        a.context.update({"metric": mid})
        a.follow(f"How does {short_name(c['name'])} compare with its peers?",
                 f"Best practices in {sname}", f"What if {short_name(c['name'])} cuts Scope 1 by 10%?")
        return

    # multi-dimension positioning
    rows, strong, weak = [], [], []
    for dim_mid, by, label in PEER_DIMENSIONS:
        metric = M.get(dim_mid, kb)
        pairs = eligible(metric, members, by=by)
        mine = next((v for x, v in pairs if x["id"] == c["id"]), None)
        if mine is None or len(pairs) < 3:
            rows.append({"label": label, "percentile": None, "n": len(pairs), "display": "n/a", "points": []})
            continue
        beat, others = beat_share(mine, pairs, c, metric.better)
        pctl = round(100 * beat / others) if others else None
        med = median(v for _, v in pairs)
        rows.append({"label": label, "percentile": pctl, "n": len(pairs),
                     "display": pct(mine) if by == "yoy" else fmt_value(metric, mine),
                     "median_display": pct(med) if by == "yoy" else fmt_value(metric, med),
                     "points": [{"value": v, "focus": x["id"] == c["id"], "label": short_name(x["name"])} for x, v in pairs],
                     "better": metric.better, "log": by == "value" and metric.kind == "abs", "yoy": by == "yoy"})
        if pctl is not None:
            (strong if pctl >= 67 else weak if pctl <= 33 else []).append((label, pctl))
    pc = a.c_derived("Peer percentiles", "share of sector peers with a worse value on each dimension",
                     note="Ties count as not outperformed. Companies without comparable data are excluded per dimension.")
    a.p(f"{c['name']} benchmarked against the {grp_n} companies in {grp} on seven E1 dimensions. Each row shows "
        f"the share of peers it outperforms (for emissions, lower is better; for scores, higher is better) {pc}.")
    if strong:
        a.p(f"**Relative strengths:** {join([f'{lc(l)} (beats {p}% of peers)' for l, p in strong])} {pc}.")
    if weak:
        a.p(f"**Relative weaknesses:** {join([f'{lc(l)} (beats {p}% of peers)' for l, p in weak])} {pc}.")
    a.block("position", title=f"Position within {grp}", subtitle="Each dot is a company; the highlighted dot is "
            f"{short_name(c['name'])}", rows=rows, company=short_name(c["name"]))
    idx_pairs = eligible(M.NUMERIC["index"], members)
    ordered = sorted(idx_pairs, key=lambda cv: (-cv[1], cv[0]["name"].lower()))
    table = []
    for i, (x, v) in enumerate(ordered, 1):
        table.append({"rank": i, "company": short_name(x["name"]), "id": x["id"], "index": f"{v:.1f}",
                      "s12": fmt_short(M.NUMERIC["scope12"], M.NUMERIC["scope12"].value(x)) if M.NUMERIC["scope12"].value(x) is not None else "n/r",
                      "yoy": pct(x["derived"]["scope12_yoy_pct"]) if x["derived"]["scope12_yoy_pct"] is not None else "n/a",
                      "assured": "Yes" if x["ratings"].get("1340") == 100 else "No",
                      "scope3": "Yes" if x["ratings"].get("1387") == 100 else "No",
                      "highlight": x["id"] == c["id"]})
    a.block("table", title=f"{grp[0].upper() + grp[1:]}: all peers by derived E1 index", rows=table,
            columns=[{"key": "rank", "label": "#", "align": "right"}, {"key": "company", "label": "Company"},
                     {"key": "index", "label": "E1 index", "align": "right"},
                     {"key": "s12", "label": "Scope 1+2 (tCO₂e)", "align": "right"},
                     {"key": "yoy", "label": "YoY", "align": "right"}, {"key": "assured", "label": "GHG assured"},
                     {"key": "scope3", "label": "Scope 3 reported"}])
    near = [x for x, _ in ordered if x["id"] != c["id"]][:2]
    a.follow(f"Compare {short_name(c['name'])} with {join([short_name(x['name']) for x in near])}" if near else None,
             f"Where does {short_name(c['name'])} rank on emission intensity?",
             f"What can {short_name(c['name'])} learn from the best in {sname}?")
