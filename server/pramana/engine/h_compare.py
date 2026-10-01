"""Company against company, and a company against its peers.

Peer answers describe where a company stands relative to the peer median in
plain words. They never give a rank position or a percentile.
"""
from __future__ import annotations

from ..analytics import median
from . import metrics as M
from .common import change_tone, eligible, export, fmt_short, fmt_value, strip, value_cite, yes, yes_count
from .fmt import CO2, join, lc, num, pct, short_name, tile
from .h_company import BOOL_PHRASE, BOOL_TITLE, TEXT_TITLE, kicker, quote_item

SIDE_ROWS = [("scope1", "Scope 1 emissions (tCO₂e)"), ("scope2", "Scope 2 emissions (tCO₂e)"),
             ("scope3", "Scope 3 emissions (tCO₂e)"), ("intensity", "Emission intensity (tCO₂e per ₹ crore)")]
SIDE_CHECKS = [("1340", "GHG emissions independently assured"), ("1387", "Scope 3 emissions reported"),
               ("1341", "Projects to reduce GHG emissions")]


# --------------------------------------------------------------------------- company vs company

def compare(ctx, cids, mid):
    a, kb = ctx.a, ctx.kb
    cos = [kb.by_id[i] for i in cids][:6]
    for c in cos:
        a.company_ref(c)
    names = [short_name(c["name"]) for c in cos]
    a.kicker = "Comparison"
    a.title = " and ".join(names) if len(names) == 2 else join(names)
    if len(cids) > 6:
        a.note("method", "Comparisons show up to six companies; the first six named are included.")
    if len({c["sector"] for c in cos}) > 1:
        a.note("context", "These companies are in different sectors, so total emissions reflect the nature of each "
                          "business. Emission intensity is the fairer comparison.")
    if mid == "scope12":
        _compare_emissions(ctx, cos)
    elif mid in M.NUMERIC:
        _compare_numeric(ctx, cos, M.NUMERIC[mid])
    elif mid in M.TEXT_Q:
        _compare_text(ctx, cos, M.TEXT_Q[mid])
    elif mid in M.BOOL_Q:
        _compare_bool(ctx, cos, M.BOOL_Q[mid])
    else:
        _side_by_side(ctx, cos)
    for c in cos:
        a.flag_notes(c, M.NUMERIC[mid].qids if mid in M.NUMERIC else ["1330", "1331", "1332", "1333", "1334", "1335"], name=True)
    a.context.update({"companies": [c["id"] for c in cos], "metric": mid})


def _compare_emissions(ctx, cos):
    """Scope 1 and Scope 2 kept as separate figures for every company."""
    a = ctx.a
    m1, m2, m12 = M.NUMERIC["scope1"], M.NUMERIC["scope2"], M.NUMERIC["scope12"]
    parts, groups, rows = [], [], []
    for c in cos:
        v1, v2 = m1.value(c), m2.value(c)
        bits = []
        if v1 is not None:
            bits.append(f"Scope 1 emissions of {num(v1)} {CO2} {a.c_filing(c, '1330')}")
        if v2 is not None:
            bits.append(f"Scope 2 emissions of {num(v2)} {CO2} {a.c_filing(c, '1332')}")
        parts.append(f"**{short_name(c['name'])}** reported {join(bits)}" if bits else
                     f"**{short_name(c['name'])}** has not disclosed these figures {a.c_filing(c, '1330')}")
        groups.append({"label": short_name(c["name"]), "values": [v1, v2],
                       "displays": [tile(v1) if v1 is not None else "n/a", tile(v2) if v2 is not None else "n/a"]})
        rows.append([c["name"], v1, v2, m12.value(c), None if m12.yoy(c) is None else round(m12.yoy(c), 2)])
    a.p("For FY 2024-25: " + ". ".join(parts) + ".")
    a.block("grouped", title="Scope 1 and Scope 2 emissions", subtitle=f"FY 2024-25, {CO2}", series=["Scope 1", "Scope 2"],
            groups=groups, log=True,
            export=export("Scope 1 and Scope 2 emissions", ["Company", "Scope 1 (tCO2e)", "Scope 2 (tCO2e)",
                                                           "Scope 1 + Scope 2 (tCO2e)", "Change in Scope 1 + 2 vs FY 2023-24 (%)"], rows))
    names = join([short_name(c["name"]) for c in cos])
    a.follow(f"Compare {names} on emission intensity", f"Compare {names} on Scope 3 emissions", f"Compare {names} on targets")


def _compare_numeric(ctx, cos, metric):
    a = ctx.a
    vals = [(c, metric.value(c), metric.prev(c), metric.yoy(c) if metric.yoy else None) for c in cos]
    shown = [f"**{short_name(c['name'])}** {fmt_value(metric, v)} {value_cite(a, c, metric)}" for c, v, _, _ in vals if v is not None]
    missing = [short_name(c["name"]) for c, v, _, _ in vals if v is None]
    if shown:
        a.p(f"{metric.label} for FY 2024-25: {join(shown)}.")
    if missing:
        a.p(f"{join(missing)} {'has' if len(missing) == 1 else 'have'} not disclosed this figure.")
    if not metric.comparable_levels and metric.note:
        a.note("method", metric.note)
    unit = metric.unit if metric.comparable_levels else "unit as disclosed"
    a.block("grouped", title=metric.label, subtitle=f"FY 2023-24 and FY 2024-25, {unit}", series=["FY 2023-24", "FY 2024-25"],
            groups=[{"label": short_name(c["name"]), "values": [pv, v],
                     "displays": [fmt_short(metric, pv), fmt_short(metric, v)]} for c, v, pv, _ in vals],
            log=metric.kind == "abs",
            export=export(metric.label, ["Company", f"FY 2024-25 ({unit})", f"FY 2023-24 ({unit})", "Change (%)"],
                          [[c["name"], v, pv, None if y is None else round(y, 2)] for c, v, pv, y in vals]))
    names = join([short_name(c["name"]) for c in cos])
    a.follow(f"Compare {names} on Scope 3 emissions" if metric.id != "scope3" else f"Compare {names} on emission intensity",
             f"Compare {names} on targets", f"How does {short_name(cos[0]['name'])} compare with its peers?")


def _compare_text(ctx, cos, qid):
    a = ctx.a
    have = [c for c in cos if c["values"].get(qid)]
    blank = [short_name(c["name"]) for c in cos if not c["values"].get(qid)]
    topic = lc(TEXT_TITLE.get(qid, "this topic"))
    if have:
        a.p(f"These are the disclosures on {topic} from {join([f'**{short_name(c['name'])}**' for c in have])}, "
            f"shown side by side with the most specific points highlighted.")
        a.block("quotes", title=TEXT_TITLE.get(qid), items=[quote_item(ctx, c, qid, k=2) for c in have], columns=True)
    if blank:
        a.p(f"{join(blank)} {'has' if len(blank) == 1 else 'have'} not disclosed {topic}.")
    names = join([short_name(c["name"]) for c in cos])
    a.follow(f"Compare {names} on GHG emissions", f"Compare {names} on emission intensity")


def _compare_bool(ctx, cos, qid):
    a = ctx.a
    pos, neg, plural = BOOL_PHRASE[qid]
    ys = [c for c in cos if yes(c, qid)]
    ns = [c for c in cos if not yes(c, qid)]
    if ys:
        who = join([f"**{short_name(c['name'])}** {a.c_filing(c, qid)}" for c in ys])
        a.p(f"{who} {pos if len(ys) == 1 else plural}.")
    if ns:
        who = join([f"{short_name(c['name'])} {a.c_filing(c, qid)}" for c in ns])
        a.p(f"{who} {neg if len(ns) == 1 else 'do not ' + plural}.")
    a.block("checklist", title=BOOL_TITLE.get(qid), items=[{"label": short_name(c["name"]), "value": yes(c, qid),
                                                            "cite": a.c_filing(c, qid)} for c in cos])
    names = join([short_name(c["name"]) for c in cos])
    a.follow(f"Compare {names} on GHG emissions", f"Compare {names} on targets")


def _side_by_side(ctx, cos):
    a, kb = ctx.a, ctx.kb
    a.p(f"Here is how {join([f'**{short_name(c['name'])}**' for c in cos])} compare on their FY 2024-25 disclosures.")
    rows, xrows = [], []
    for mid, label in SIDE_ROWS:
        m = M.NUMERIC[mid]
        cells = []
        for c in cos:
            v = m.value(c)
            ok = v is not None and (m.kind != "intensity" or m.level_ok(c))
            cells.append({"text": fmt_short(m, v) if ok else ("Not disclosed" if v is None else "See note"),
                          "full": fmt_value(m, v) if v is not None else None,
                          "cite": value_cite(a, c, m) if v is not None else None})
        rows.append({"label": label, "cells": cells})
        xrows.append([label] + [m.value(c) if (m.kind != "intensity" or m.level_ok(c)) else None for c in cos])
    m12 = M.NUMERIC["scope12"]
    rows.append({"label": "Change in Scope 1 + Scope 2 vs FY 2023-24",
                 "cells": [{"text": pct(m12.yoy(c)) if m12.yoy(c) is not None else "n/a", "tone": change_tone(m12.yoy(c))}
                           for c in cos]})
    xrows.append(["Change in Scope 1 + Scope 2 vs FY 2023-24 (%)"] + [None if m12.yoy(c) is None else round(m12.yoy(c), 2) for c in cos])
    for q, label in SIDE_CHECKS:
        rows.append({"label": label, "cells": [{"text": "Yes" if yes(c, q) else "No", "tone": "good" if yes(c, q) else "muted",
                                                "cite": a.c_filing(c, q)} for c in cos]})
        xrows.append([label] + ["Yes" if yes(c, q) else "No" for c in cos])
    a.block("compare", title="Side by side", columns=[{"label": short_name(c["name"]), "sub": kb.sector_of(c)["name"],
                                                       "id": c["id"]} for c in cos], rows=rows,
            export=export("Side by side", ["Measure"] + [c["name"] for c in cos], xrows))
    names = join([short_name(c["name"]) for c in cos])
    a.follow(f"Compare {names} on targets", f"Compare {names} on GHG reduction projects",
             f"Compare {names} on emission intensity")


# --------------------------------------------------------------------------- peers

def _peer_group(ctx, c, peers):
    """(peer companies excluding c, name of the group, whether it is the user's own list)."""
    kb = ctx.kb
    custom = [kb.by_id[x] for x in (peers or []) if x in kb.by_id and x != c["id"]]
    if custom:
        return custom, "your chosen peers", True
    return [m for m in kb.members(c["sector"]) if m["id"] != c["id"]], kb.sector_of(c)["name"], False


def _nearest(c, others):
    """The peer whose combined Scope 1 and Scope 2 emissions are closest to the company's."""
    m = M.NUMERIC["scope12"]
    v = m.value(c)
    pool = [(abs(x - v), o["name"].lower(), o) for o, x in eligible(m, others)] if v is not None else []
    return min(pool, key=lambda t: (t[0], t[1]))[2] if pool else (others[0] if others else None)


def peer_list(ctx, c, peers=None):
    """Who the peers are: names only."""
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    others, grp, custom = _peer_group(ctx, c, peers)
    sname = kb.sector_of(c)["name"]
    short = short_name(c["name"])
    a.kicker = kicker(ctx, c)
    a.title = f"Peers of {short}"
    others = sorted(others, key=lambda x: x["name"].lower())
    if custom:
        a.p(f"You set these **{len(others)} companies** as the peer group for {short} earlier in this conversation.")
    else:
        n = len(others) + 1
        a.p(f"**{c['name']}** is classified under **{sname}**, which has {n} companies including it "
            f"{a.c_note('Peer group', f'The {n} companies classified under {sname} among the companies covered. Peers are the other {n - 1}.')}. "
            f"Its {n - 1} peers are listed below.")
    a.block("names", title=f"{len(others)} peers" if not custom else "Your peer group",
            items=[{"id": x["id"], "name": short_name(x["name"])} for x in others],
            export=export(f"Peers of {c['name']}", ["Company", "Sector"], [[x["name"], kb.sector_of(x)["name"]] for x in others]))
    a.context.update({"companies": [c["id"]], "intent": "peer_benchmark"})
    near = _nearest(c, others)
    a.follow(f"How does {short} compare with its peers?",
             f"Compare {short} with {short_name(near['name'])}" if near else None,
             f"Examples of GHG reduction projects from {sname} companies")


def peer_compare(ctx, c, mid, peers=None):
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    others, grp, custom = _peer_group(ctx, c, peers)
    sname = kb.sector_of(c)["name"]
    short = short_name(c["name"])
    a.kicker = kicker(ctx, c)
    a.title = f"{short} and its peers"
    where = "your chosen peers" if custom else f"the other {len(others)} {sname} companies"
    if custom:
        a.note("context", f"Using the peer group you set earlier: {join([short_name(x['name']) for x in others])}. "
                          f"Say “forget my peer group” to compare with the whole sector again.")
    if mid in M.BOOL_Q and mid not in M.TEXT_Q:
        return _peer_bool(ctx, c, M.BOOL_Q[mid], others, where)
    if mid in M.TEXT_Q:
        from .h_practice import best_practice
        return best_practice(ctx, mid, c["sector"], c["id"])
    if mid == "scope12" or mid not in M.NUMERIC:
        return _peer_overview(ctx, c, others, where, custom)
    metric = M.NUMERIC[mid]
    by = "value" if metric.comparable_levels else "yoy"
    pairs = eligible(metric, others, by=by)
    mine = next(iter(eligible(metric, [c], by=by)), None)
    label = lc(metric.label) + (" (change vs FY 2023-24)" if by == "yoy" else "")
    if mine is None:
        a.status = "partial"
        raw = metric.value(c)
        a.p(f"{c['name']} {'has not disclosed' if raw is None else 'has no comparable figure for'} {label}, so it cannot "
            f"be compared with {where}.")
        a.flag_notes(c, metric.qids)
        a.follow(f"What are {short}'s GHG emissions?", f"Who are {short}'s peers?")
        return
    v = mine[1]
    shown = pct(v) if by == "yoy" else fmt_value(metric, v)
    if not pairs:
        a.status = "partial"
        a.p(f"{c['name']} reported {label} of {shown} {value_cite(a, c, metric, by)}, but none of {where} disclosed a "
            f"comparable figure.")
        return
    med = median(x for _, x in pairs)
    med_s = pct(med) if by == "yoy" else fmt_value(metric, med)
    rel = "the same as" if v == med else ("below" if v < med else "above")
    mc = a.c_calc(f"Peer median: {label}", f"Median of the {len(pairs)} peers that disclosed this figure = {med_s}",
                  note=f"{len(pairs)} of {len(others)} peers disclosed a comparable figure.")
    a.p(f"**{c['name']}** reported {label} of **{shown}** {value_cite(a, c, metric, by)}, which is **{rel}** the "
        f"peer median of {med_s} {mc}.")
    a.p(f"{len(pairs)} of its {len(others)} peers disclosed this figure {mc}.")
    blk = strip(f"{metric.label}: {short} and its peers", pairs + [mine], metric, focus_ids={c["id"]},
                subtitle="Each dot is a company, FY 2024-25" + (" vs FY 2023-24" if by == "yoy" else ""), value_kind=by)
    blk["median"], blk["median_display"], blk["median_label"] = med, (pct(med) if by == "yoy" else fmt_short(metric, med)), "Peer median"
    a.blocks.append(blk)
    if metric.note:
        a.note("method", metric.note)
    a.flag_notes(c, metric.qids)
    a.context.update({"metric": mid})
    a.follow(f"How does {short} compare with its peers?", f"Who are {short}'s peers?",
             f"What if {short} cuts {lc(metric.label)} by 10%?" if metric.comparable_levels else None)


def _peer_bool(ctx, c, qid, others, where):
    a = ctx.a
    short = short_name(c["name"])
    pos, neg, plural = BOOL_PHRASE[qid]
    is_yes = yes(c, qid)
    y, n = yes_count(others, qid)
    cc = a.c_calc(f"{BOOL_TITLE.get(qid)} among peers", f"{y} of {n} peers answered Yes")
    a.p(f"{c['name']} {pos if is_yes else neg} {a.c_filing(c, qid)}. Among {where}, **{y} of {n}** {plural} {cc}.")
    a.follow(f"Which {ctx.kb.sector_of(c)['name']} companies {plural}?", f"How does {short} compare with its peers?")


def _peer_overview(ctx, c, others, where, custom):
    """One compact table: the company's figure beside the peer median, measure by measure."""
    a, kb = ctx.a, ctx.kb
    short = short_name(c["name"])
    rows, xrows, below, above, level = [], [], [], [], []
    dims = [("scope1", "value", "Scope 1 emissions"), ("scope2", "value", "Scope 2 emissions"),
            ("scope3", "value", "Scope 3 emissions"), ("intensity", "value", "Emission intensity"),
            ("scope12", "yoy", "Change in Scope 1 + Scope 2 vs FY 2023-24")]
    for mid, by, label in dims:
        metric = M.NUMERIC[mid]
        pairs = eligible(metric, others, by=by)
        mine = next(iter(eligible(metric, [c], by=by)), None)
        med = median(x for _, x in pairs) if pairs else None
        unit = "%" if by == "yoy" else metric.unit
        show = (lambda x: pct(x)) if by == "yoy" else (lambda x: (tile(x) if metric.kind == "abs" else num(x)))
        if mine is None:
            raw = metric.value(c) if by == "value" else None
            pos, mine_s = "n/a", ("Not disclosed" if raw is None else "See note")
        else:
            mine_s = show(mine[1])
            if med is None:
                pos = "n/a"
            else:
                pos = "Same as median" if mine[1] == med else ("Below median" if mine[1] < med else "Above median")
                (level if mine[1] == med else below if mine[1] < med else above).append(lc(label) if by == "value" else "the change in emissions since FY 2023-24")
        rows.append({"measure": f"{label} ({unit})" if by == "value" else label, "mine": mine_s,
                     "median": show(med) if med is not None else "n/a", "position": pos,
                     "reporting": f"{len(pairs)} of {len(others)}"})
        xrows.append([f"{label} ({unit})", mine[1] if mine else None, med, pos, len(pairs), len(others)])
    cite = a.c_calc("Peer medians", "For each measure, the median of the peers that disclosed a comparable figure",
                    note="The number of peers disclosing each figure is shown in the table. Figures that appear to use a "
                         "different unit are left out of the medians.")
    bits = []
    if below:
        bits.append(f"below the peer median on {join(below)}")
    if above:
        bits.append(f"above it on {join(above)}" if below else f"above the peer median on {join(above)}")
    if bits:
        a.p(f"Compared with {where}, **{c['name']}** is {join(bits)} {cite}.")
    else:
        a.status = "partial"
        a.p(f"{c['name']} has not disclosed figures that can be compared with {where} {cite}.")
    a.block("table", title=f"{short} and the peer median", rows=rows,
            columns=[{"key": "measure", "label": "Measure"}, {"key": "mine", "label": short, "align": "right"},
                     {"key": "median", "label": "Peer median", "align": "right"},
                     {"key": "position", "label": "Position"}, {"key": "reporting", "label": "Peers disclosing", "align": "right"}],
            export=export(f"{c['name']} and the peer median", ["Measure", c["name"], "Peer median", "Position",
                                                               "Peers disclosing", "Peers in group"], xrows))
    a.flag_notes(c, ["1330", "1331", "1332", "1333", "1334", "1335"])
    sname = kb.sector_of(c)["name"]
    a.follow(f"Who are {short}'s peers?", f"How does {short} compare with its peers on Scope 1 emissions?",
             f"Examples of GHG reduction projects from {sname} companies")
