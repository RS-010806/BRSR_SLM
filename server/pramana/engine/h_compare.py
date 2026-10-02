"""Company against company, and a company against its peers.

Peer answers describe where a company stands relative to the peer median in
plain words. They never give a rank position or a percentile.
"""
from __future__ import annotations

import re

from ..analytics import median
from . import metrics as M
from .common import bars, change_tone, eligible, export, fmt_short, fmt_value, ordered, strip, value_cite, yes, yes_count
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
    named = [m for m in dict.fromkeys(ctx.plan.metrics) if m in M.NUMERIC]
    if len(named) >= 2 and set(named) != {"scope12", "scope3"}:
        mid = None                                    # several measures named: the side-by-side shows them all
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


RE_ASKS_LOW = re.compile(r"\b(cleaner|greener|lower|less|smaller|least|lowest|fewer|better|efficient)\b")


def _edge(ctx, pairs):
    """(company, word): the highest of the figures, or the lowest when that is what the question asks about."""
    low = bool(RE_ASKS_LOW.search((ctx.plan.resolved_query or ctx.plan.query).lower()))
    pick = min(pairs, key=lambda t: t[1]) if low else max(pairs, key=lambda t: t[1])
    two = len(pairs) == 2
    return pick, ("lower" if two else "lowest") if low else ("higher" if two else "highest")


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
    have = [(c, m12.value(c)) for c in cos if m1.value(c) is not None and m2.value(c) is not None]
    if len(have) >= 2 and len({v for _, v in have}) > 1:
        top, word = _edge(ctx, have)
        a.p(f"On the combined figure, **{short_name(top[0]['name'])}** is the {word} "
            f"at {num(top[1])} {CO2} {value_cite(a, top[0], m12)}.")
    a.block("grouped", title="Scope 1 and Scope 2 emissions", subtitle=f"FY 2024-25, {CO2}", series=["Scope 1", "Scope 2"],
            groups=groups, log=True,
            export=export("Scope 1 and Scope 2 emissions", ["Company", "Scope 1 (tCO2e)", "Scope 2 (tCO2e)",
                                                           "Scope 1 + Scope 2 (tCO2e)", "Change in Scope 1 + 2 vs FY 2023-24 (%)"], rows))
    names = join([short_name(c["name"]) for c in cos])
    a.follow(f"Compare {names} on emission intensity", f"Compare {names} on Scope 3 emissions", f"Compare {names} on targets")


def _compare_numeric(ctx, cos, metric):
    a = ctx.a
    vals = [(c, metric.value(c), metric.prev(c), metric.yoy(c) if metric.yoy else None) for c in cos]
    odd = []
    if metric.kind == "intensity" and metric.comparable_levels:
        # a figure that appears to use a different unit is not set beside the others
        odd = [short_name(c["name"]) for c, v, _, _ in vals if v is not None and not metric.level_ok(c)]
        vals = [(c, v if (v is None or metric.level_ok(c)) else None, pv if (v is None or metric.level_ok(c)) else None, y)
                for c, v, pv, y in vals]
    shown = [f"**{short_name(c['name'])}** {fmt_value(metric, v)} {value_cite(a, c, metric)}" for c, v, _, _ in vals if v is not None]
    missing = [short_name(c["name"]) for c, v, _, _ in vals if v is None and short_name(c["name"]) not in odd]
    if odd:
        a.note("data", f"{join(odd)}: the disclosed {lc(metric.label)} appears to use a different unit from most filings, "
                       f"so it is not compared here.")
    ok = [(c, v) for c, v, _, _ in vals if v is not None and (metric.level_ok is None or metric.level_ok(c))]
    if len(ok) == 2 and metric.comparable_levels and ok[0][1] != ok[1][1]:
        # two companies: the answer in one sentence
        top, word = _edge(ctx, ok)
        o = next(x for x in ok if x[0]["id"] != top[0]["id"])
        a.p(f"**{short_name(top[0]['name'])}** has the {word} {lc(metric.label)} for FY 2024-25: {fmt_value(metric, top[1])} "
            f"{value_cite(a, top[0], metric)}, against {fmt_value(metric, o[1])} for {short_name(o[0]['name'])} "
            f"{value_cite(a, o[0], metric)}.")
    else:
        if shown:
            a.p(f"{metric.label} for FY 2024-25: {join(shown)}.")
        if len(ok) >= 2 and metric.comparable_levels and len({v for _, v in ok}) > 1:
            top, word = _edge(ctx, ok)
            a.p(f"**{short_name(top[0]['name'])}** reported the {word} figure.")
    if missing:
        a.p(f"{join(missing)} {'has' if len(missing) == 1 else 'have'} not disclosed this figure.")
    if not shown and not missing:
        a.status = "partial"
        a.p(f"None of these companies disclosed {lc(metric.label)} in a unit that can be compared.")
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
    # the answer first: which is higher on total emissions, and on intensity, which allows for size
    m12, mi = M.NUMERIC["scope12"], M.NUMERIC["intensity"]
    lines = []
    for m, what in ((m12, "combined Scope 1 and Scope 2 emissions"), (mi, "emission intensity, which allows for company size")):
        have = eligible(m, cos)
        if len(have) < 2 or len({v for _, v in have}) < 2:
            continue
        top, word = _edge(ctx, have)
        rest = [x for x in have if x[0]["id"] != top[0]["id"]]
        if len(have) == 2:
            o = rest[0]
            lines.append(f"**{short_name(top[0]['name'])}** has the {word} {what}: {fmt_value(m, top[1])} {value_cite(a, top[0], m)}, "
                         f"against {fmt_value(m, o[1])} for {short_name(o[0]['name'])} {value_cite(a, o[0], m)}.")
        else:
            lines.append(f"**{short_name(top[0]['name'])}** has the {word} {what}, {fmt_value(m, top[1])} {value_cite(a, top[0], m)}.")
    if lines:
        for x in lines:
            a.p(x)
    else:
        a.p(f"Here is how {join([f'**{short_name(c['name'])}**' for c in cos])} compare on their FY 2024-25 disclosures.")
    notes = []
    for mid, label in SIDE_ROWS:
        m = M.NUMERIC[mid]
        ok = eligible(m, cos)
        name = label.split(" (")[0]
        if len(ok) >= 2:
            hi, lo = max(ok, key=lambda t: t[1]), min(ok, key=lambda t: t[1])
            line = f"**{name}:** " + join([f"{short_name(x['name'])} {fmt_value(m, v)} {value_cite(a, x, m)}" for x, v in ok]) + "."
            if lo[1] > 0 and hi[1] != lo[1]:
                r = hi[1] / lo[1]
                line += (f" {short_name(hi[0]['name'])} is about {r:,.0f} times {short_name(lo[0]['name'])}." if r >= 20 else
                         f" {short_name(hi[0]['name'])} is about {r:.1f} times {short_name(lo[0]['name'])}." if r >= 1.5 else
                         f" {short_name(hi[0]['name'])} is {(r - 1) * 100:.0f}% higher than {short_name(lo[0]['name'])}.")
            notes.append(line)
        elif len(ok) == 1:
            notes.append(f"**{name}:** only {short_name(ok[0][0]['name'])} disclosed a comparable figure, "
                         f"{fmt_value(m, ok[0][1])} {value_cite(a, ok[0][0], m)}.")
    for q, label in SIDE_CHECKS:
        ys = [short_name(x["name"]) for x in cos if yes(x, q)]
        two = len(cos) == 2
        who = ("both" if two else "all of them") if len(ys) == len(cos) else \
            (("neither" if two else "none of them") if not ys else join(ys) + " only")
        notes.append(f"**{label}:** {who} {a.c_filing(cos[0], q)}.")
    if notes:
        a.block("points", title="Key points", items=notes)
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
    m1, m2, m3 = M.NUMERIC["scope1"], M.NUMERIC["scope2"], M.NUMERIC["scope3"]
    if any(m.value(c) for c in cos for m in (m1, m2, m3)):
        series = ["Scope 1", "Scope 2"] + (["Scope 3"] if any(m3.value(c) for c in cos) else [])
        ms = (m1, m2, m3)[:len(series)]
        a.block("grouped", title="Emissions by scope", subtitle=f"FY 2024-25, {CO2}", series=series, log=True,
                groups=[{"label": short_name(c["name"]), "values": [m.value(c) for m in ms],
                         "displays": [tile(m.value(c)) if m.value(c) is not None else "n/a" for m in ms]} for c in cos],
                export=export("Emissions by scope", ["Company"] + [f"{x} (tCO2e)" for x in series],
                              [[c["name"]] + [m.value(c) for m in ms] for c in cos]))
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
            items=[{"id": x["id"], "name": short_name(x["name"])} for x in others], sector=None if custom else sname,
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
        low = (ctx.plan.resolved_query or ctx.plan.query).lower()
        if re.search(r"\b(which|who|how many|number of|list|any|do|does|have|has)\b", low) and not re.search(
                r"\b(what|compar\w*|examples?|show|how (?:do|does|are|is))\b", low):
            return _peer_text_count(ctx, c, M.TEXT_Q[mid], others, where)
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
            f"be compared with {where} {a.c_filing(c, metric.cy_q or '1330')}.")
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
    if by == "value":
        # the same figures by name: the largest in the group, with the company picked out
        ranked = ordered(pairs + [mine])
        top = ranked[:10]
        if c["id"] not in [x["id"] for x, _ in top]:
            top = top[:9] + [mine]
        grp = "your chosen peers" if custom else f"{sname} companies"
        blk2 = bars(f"{metric.label}: {short} among {grp}", top, metric, focus_ids={c["id"]}, median_v=med,
                    median_label="Peer median", log=metric.kind in ("abs", "intensity"), show_rank=False,
                    subtitle="FY 2024-25" + ("" if len(ranked) <= 10 else f", the ten highest of {len(ranked)}"
                                             + ("" if c["id"] in [x["id"] for x, _ in ranked[:10]] else f" and {short}")))
        blk2["focus_label"] = short
        a.blocks.append(blk2)
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
    low = (ctx.plan.resolved_query or ctx.plan.query).lower()
    if not re.search(r"\b(compar\w*|versus|vs|against|how (?:do|does|am|are|is)|where (?:do|does))\b", low):
        group = "your chosen peers" if where == "your chosen peers" else where.replace("the other ", f"{short}'s ", 1).replace(" companies", " peers")
        a.p(f"**{y} of {group}** {plural} {cc}" + ("; they are listed below. " if y else ". ")
            + f"{short} itself {pos if is_yes else neg} {a.c_filing(c, qid)}.")
    else:
        a.p(f"{c['name']} {pos if is_yes else neg} {a.c_filing(c, qid)}. Among {where}, **{y} of {n}** {plural} {cc}.")
    hits = sorted([o for o in others if yes(o, qid)], key=lambda o: o["name"].lower())
    if hits:
        a.block("names", title=f"{BOOL_TITLE.get(qid)}: {y} of {n} peers",
                items=[{"id": o["id"], "name": short_name(o["name"])} for o in hits], sector=ctx.kb.sector_of(c)["name"],
                export=export(f"Peers of {c['name']}: {BOOL_TITLE.get(qid)}", ["Company", BOOL_TITLE.get(qid)],
                              [[o["name"], "Yes" if yes(o, qid) else "No"] for o in sorted(others, key=lambda o: o["name"].lower())]))
    a.context.update({"metric": ctx.plan.metric})
    a.follow(f"Which {ctx.kb.sector_of(c)['name']} companies {plural}?", f"How does {short} compare with its peers?")


def _peer_text_count(ctx, c, qid, others, where):
    """How many peers have a narrative disclosure (targets, projects, certifications), with their names."""
    a = ctx.a
    short = short_name(c["name"])
    title = TEXT_TITLE.get(qid, "This disclosure")
    fs = ctx.plan.focus_scope
    label = {"scope1": "Scope 1", "scope2": "Scope 2", "scope3": "Scope 3"}.get(fs)
    rx = re.compile(rf"\bscope[- ]?{fs[-1]}\b", re.I) if label else None
    has = (lambda o: bool(o["values"].get(qid)) and (rx is None or bool(rx.search(o["values"][qid]))))
    hits = sorted([o for o in others if has(o)], key=lambda o: o["name"].lower())
    mine = has(c)
    what = lc(title) + (f" that mention {label}" if label else "")
    cc = a.c_calc(f"{title} among peers", f"{len(hits)} of {len(others)} peers provided this disclosure"
                  + (f" and it mentions {label}" if label else ""))
    group = "your chosen peers" if where == "your chosen peers" else where.replace("the other ", f"{short}'s ", 1).replace(" companies", " peers")
    a.p(f"**{len(hits)} of {group}** have disclosed {what} for FY 2024-25 {cc}" + ("; they are listed below. " if hits else ". ")
        + f"{short} itself {'has' if mine else 'has not'} {'disclosed them' if not label else 'done so'} {a.c_filing(c, qid)}.")
    if hits:
        a.block("names", title=f"{title}{' mentioning ' + label if label else ''}: {len(hits)} of {len(others)} peers",
                items=[{"id": o["id"], "name": short_name(o["name"])} for o in hits], sector=ctx.kb.sector_of(c)["name"],
                export=export(f"Peers of {c['name']}: {title}", ["Company", "Disclosed"],
                              [[o["name"], "Yes" if has(o) else "No"] for o in sorted(others, key=lambda o: o["name"].lower())]))
    a.context.update({"metric": ctx.plan.metric})
    sname = ctx.kb.sector_of(c)["name"]
    a.follow(f"Examples of {lc(title)} from {sname} companies", f"What are {short}'s targets?" if qid == "286" else None,
             f"How does {short} compare with its peers?")


def _peer_overview(ctx, c, others, where, custom):
    """Where the company sits among its peers, measure by measure: one dot per company, the peer median marked."""
    a, kb = ctx.a, ctx.kb
    short = short_name(c["name"])
    rows, xrows, below, above = [], [], [], []
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
            pos, mine_s = None, (("Not disclosed" if raw is None else "See note") if by == "value" else "Not comparable")
        else:
            mine_s = show(mine[1])
            if med is None:
                pos = None
            else:
                pos = "Same as median" if mine[1] == med else ("Below median" if mine[1] < med else "Above median")
                if mine[1] != med:
                    (below if mine[1] < med else above).append(lc(label) if by == "value" else "the change in emissions since FY 2023-24")
        vals = [x for _, x in pairs] + ([mine[1]] if mine else [])
        positive = [x for x in vals if x > 0]
        rows.append({"label": label if by == "yoy" else label, "unit": unit, "mine": mine_s,
                     "median": show(med) if med is not None else None, "relation": pos,
                     "n": len(pairs), "of": len(others), "yoy": by == "yoy",
                     "log": by == "value" and len(positive) > 2 and max(positive) / min(positive) > 200,
                     "median_value": med,
                     "points": [{"value": x, "label": short_name(o["name"]), "display": show(x)} for o, x in pairs]
                               + ([{"value": mine[1], "label": short, "display": mine_s, "focus": True}] if mine else [])})
        xrows.append([f"{label} ({unit})" if by == "value" else f"{label} (%)", mine[1] if mine else None, med, pos or "n/a",
                      len(pairs), len(others)])
    cite = a.c_calc("Peer medians", "For each measure, the median of the peers that disclosed a comparable figure",
                    note="Figures that appear to use a different unit are left out of the medians.")
    notes = []
    for r in rows:
        unit = "" if r["yoy"] else f" {r['unit']}"
        if r["relation"]:
            rel = {"Below median": "below", "Above median": "above", "Same as median": "the same as"}[r["relation"]]
            notes.append(f"**{r['label']}:** {r['mine']}{unit}, {rel} the peer median of {r['median']}{unit} "
                         f"({r['n']} of {r['of']} peers disclosed a figure) {cite}.")
        elif r["mine"] in ("Not disclosed", "Not comparable", "See note"):
            how = {"Not disclosed": "not disclosed", "Not comparable": "not comparable between the two years",
                   "See note": "disclosed in a unit that cannot be compared"}[r["mine"]]
            notes.append(f"**{r['label']}:** {how} by {short}; {r['n']} of {r['of']} peers disclosed a comparable figure {cite}.")
    flags = []
    for q, label in (("1340", "independent assurance of GHG emissions"), ("1387", "Scope 3 reporting"), ("1341", "projects to reduce GHG emissions")):
        y, n = yes_count(others, q)
        flags.append(f"{'has' if yes(c, q) else 'does not have'} {label} ({y} of {n} peers do)")
    notes.append(f"**Disclosures:** {short} {join(flags)} {a.c_calc('Peer disclosure counts', 'Peers answering Yes to each item')}.")
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
    a.block("points", title="Key points", items=notes)
    a.block("position", title=f"{short} and its peers", company=short, rows=rows,
            subtitle="Each dot is a company and the vertical line marks the peer median. Further left means a lower figure.",
            export=export(f"{c['name']} and the peer median", ["Measure", c["name"], "Peer median", "Position",
                                                               "Peers disclosing", "Peers in group"], xrows))
    # the peer group on combined emissions, with the company picked out
    m12 = M.NUMERIC["scope12"]
    mine12 = next(iter(eligible(m12, [c])), None)
    pairs12 = eligible(m12, others)
    if mine12 and pairs12:
        ranked = ordered(pairs12 + [mine12])
        top = ranked[:10]
        if c["id"] not in [x["id"] for x, _ in top]:
            top = top[:9] + [mine12]
        grp = "your chosen peers" if custom else f"{kb.sector_of(c)['name']} companies"
        blk = bars(f"Scope 1 + Scope 2 emissions: {short} among {grp}", top, m12, focus_ids={c["id"]},
                   median_v=median(x for _, x in pairs12), median_label="Peer median", log=True, show_rank=False,
                   subtitle="FY 2024-25" + ("" if len(ranked) <= 10 else f", the ten largest of {len(ranked)}"
                                            + ("" if c["id"] in [x["id"] for x, _ in ranked[:10]] else f" and {short}")))
        blk["focus_label"] = short
        a.blocks.append(blk)
    a.flag_notes(c, ["1330", "1331", "1332", "1333", "1334", "1335"])
    sname = kb.sector_of(c)["name"]
    a.follow(f"Who are {short}'s peers?", f"How does {short} compare with its peers on Scope 1 emissions?",
             f"Examples of GHG reduction projects from {sname} companies")


def peer_filter(ctx, c, mid, direction, peers=None):
    """Which peers reported a lower or higher figure than the company, or the ones closest to it."""
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    others, grp, custom = _peer_group(ctx, c, peers)
    sname = kb.sector_of(c)["name"]
    short = short_name(c["name"])
    metric = M.NUMERIC.get(mid) or M.NUMERIC["scope12"]
    by = "value" if metric.comparable_levels else "yoy"
    what = lc(metric.label) + (" (change vs FY 2023-24)" if by == "yoy" else "")
    a.kicker = kicker(ctx, c)
    pairs = eligible(metric, others, by=by)
    mine = next(iter(eligible(metric, [c], by=by)), None)
    show = (lambda x: pct(x)) if by == "yoy" else (lambda x: fmt_value(metric, x))
    if mine is None:
        a.status = "partial"
        a.title = f"{short} and its peers"
        raw = metric.value(c)
        a.p(f"{c['name']} {'has not disclosed' if raw is None else 'has no comparable figure for'} {what}, so its peers "
            f"cannot be set against it.")
        a.flag_notes(c, metric.qids)
        a.follow(f"Who are {short}'s peers?", f"Tell me about {short}")
        return
    v = mine[1]
    mc = value_cite(a, c, metric, by)
    group = "your chosen peers" if custom else f"{sname} peers"
    if direction == "similar":
        near = sorted(pairs, key=lambda t: (abs(t[1] - v), t[0]["name"].lower()))[:6]
        a.title = f"Peers closest to {short}"
        cc = a.c_calc(f"Peers closest to {short} on {what}", f"The {len(near)} peers with the smallest difference from {show(v)}",
                      note=f"{len(pairs)} of {len(others)} peers disclosed a comparable figure.")
        a.p(f"On {what}, the peers closest to **{c['name']}** ({show(v)} {mc}) are "
            f"{join([f'**{short_name(o['name'])}**' for o, _ in near[:3]])} {cc}.")
        chosen = near
        title = f"{metric.label}: {short} and its closest peers"
    else:
        lower = direction == "lower"
        hits = [(o, x) for o, x in pairs if (x < v if lower else x > v)]
        word = "lower" if lower else "higher"
        a.title = f"Peers with {word} {lc(metric.label)}"
        cc = a.c_calc(f"Peers with {word} {what} than {short}", f"{len(hits)} of the {len(pairs)} peers that disclosed a comparable figure",
                      note=f"{len(pairs)} of {len(others)} peers disclosed a comparable figure.")
        if not hits:
            a.p(f"None of the {len(pairs)} {group} that disclosed {what} reported a {word} figure than **{c['name']}** "
                f"({show(v)} {mc}) {cc}.")
            a.follow(f"How does {short} compare with its peers?", f"Who are {short}'s peers?")
            return
        a.p(f"**{len(hits)} of the {len(pairs)}** {group} that disclosed {what} reported a {word} figure than "
            f"**{c['name']}** ({show(v)} {mc}) {cc}.")
        # the ones nearest to the company first: they are the most useful to look at
        chosen = sorted(hits, key=lambda t: (abs(t[1] - v), t[0]["name"].lower()))[:12]
        title = f"{metric.label}: peers {'below' if lower else 'above'} {short}"
        if len(hits) > len(chosen):
            a.note("context", f"The chart shows the {len(chosen)} peers closest to {short}. The Excel download lists all {len(hits)}.")
    rows = ordered(chosen + [mine])
    blk = bars(title, rows, metric, focus_ids={c["id"]}, log=by == "value" and metric.kind in ("abs", "intensity"),
               show_rank=False, value_kind=by, subtitle="FY 2024-25" + (" vs FY 2023-24" if by == "yoy" else ""))
    blk["focus_label"] = short
    full = ordered((chosen if direction == "similar" else hits) + [mine])
    unit = "% change" if by == "yoy" else metric.unit
    blk["export"] = export(title, ["Company", f"{metric.label} ({unit})"], [[o["name"], x] for o, x in full])
    a.blocks.append(blk)
    if metric.note:
        a.note("method", metric.note)
    a.flag_notes(c, metric.qids)
    a.context.update({"metric": metric.id})
    a.follow(f"How does {short} compare with its peers?",
             f"Compare {short} with {short_name(chosen[0][0]['name'])}",
             f"Examples of GHG reduction projects from {sname} companies")
