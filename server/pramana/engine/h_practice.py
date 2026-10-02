"""Examples of good practice (shown exactly as disclosed) and search across disclosures."""
from __future__ import annotations

import re

from . import metrics as M
from .common import export
from .evidence import THEMES, _THEME_RE
from .fmt import clip as _clip, join, lc, share, short_name
from .h_company import quote_item
from .public import TOPIC, item

PRACTICE_QIDS = {"targets": "286", "target_performance": "295", "projects": "1342", "certifications": "277",
                 "ghg_assurance": "1342", "scope12": "1342", "intensity": "1342", "scope1": "1342", "scope2": "1342",
                 "scope3": "1342"}
# When advice is asked for one scope, prefer the disclosures that talk about what drives that scope.
FOCUS = {
    "scope1": (re.compile(r"\bscope[- ]?1\b|\bfuels?\b|biomass|boilers?|furnaces?|\bdiesel\b|natural gas|\bcng\b|\bpng\b|"
                          r"electric vehicles?|\bevs?\b|waste heat|fleet|combustion", re.I),
               "Scope 1 emissions, which come from fuel a company burns itself"),
    "scope2": (re.compile(r"\bscope[- ]?2\b|renewable|\bsolar\b|\bwind\b|green power|electricity|energy[- ]efficien|"
                          r"\bppa\b|open access|\bled\b", re.I),
               "Scope 2 emissions, which come from purchased electricity"),
    "scope3": (re.compile(r"\bscope[- ]?3\b|value chain|suppliers?|supply chain|upstream|downstream|vendors?|"
                          r"business travel|commut|logistics", re.I),
               "Scope 3 emissions, which arise in the value chain"),
}
EXAMPLE_NAME = {"286": "targets", "295": "progress against targets", "1342": "GHG reduction projects",
                "277": "certifications and standards"}
TECH_LABEL = {"sbti": "SBTi", "net zero": "net zero", "renewable energy": "renewable energy", "ev": "EVs",
              "electric vehicles": "electric vehicles", "carbon capture": "carbon capture (CCUS)"}
SEARCH_QIDS = {"286", "295", "1342", "277", "353", "1561"}


def _detail(ctx, c, qid):
    """How much concrete detail a disclosure carries (quantities, years, baselines, named measures)."""
    return ctx.kb.evidence_score(c["id"], qid)


def _strong(c, qid):
    return c["ratings"].get(qid) == 100 and bool(c["values"].get(qid))


def best_practice(ctx, mid, sid, cid):
    a, kb = ctx.a, ctx.kb
    me = kb.by_id[cid] if cid else None
    if mid in M.BOOL_Q and mid not in M.TEXT_Q and mid != "ghg_applicable":
        # a yes/no disclosure has no narrative to quote: show who does it instead
        if me:
            from .h_compare import peer_compare
            return peer_compare(ctx, me, mid, ctx.plan.prefs.get("peers"))
        from .h_sector import screen
        return screen(ctx, mid, sid, False, None)
    qid = PRACTICE_QIDS.get(mid or "projects", "1342")
    if mid in FOCUS and "targets" in ctx.plan.raw_metrics:
        qid = "286"                                   # "scope 3 targets": targets that talk about that scope
    if me and not sid:
        sid = me["sector"]
    pool = kb.members(sid) if sid else kb.companies
    scope = kb.sector_by_id[sid]["name"] if sid else None
    what = EXAMPLE_NAME[qid]
    focus = FOCUS.get(mid)
    rel = (lambda c: bool(focus[0].search(c["values"].get(qid) or ""))) if focus else (lambda c: True)
    others = [c for c in pool if not me or c["id"] != me["id"]]
    leaders = [c for c in others if _strong(c, qid) and rel(c)]
    widened = False
    if len(leaders) < 3 and sid:
        extra = [c for c in kb.companies if _strong(c, qid) and rel(c) and c["sector"] != sid and (not me or c["id"] != me["id"])]
        extra.sort(key=lambda c: (-_detail(ctx, c, qid), c["name"].lower()))
        leaders = leaders + extra[: 3 - len(leaders)]
        widened = True
    leaders.sort(key=lambda c: (c["sector"] != sid if sid else False, -_detail(ctx, c, qid), c["name"].lower()))
    a.kicker = scope or "All companies"
    a.title = f"Good practice: {what}"
    how = a.c_note("How this is put together",
                   "Drawn from the disclosures with the most concrete detail: quantities, years, baselines and named "
                   "measures. Quoted text is exactly as the company disclosed it.")
    picks = leaders[:3]
    if not picks:
        a.status = "partial"
        a.p(f"I could not find detailed disclosures on {what} {'in ' + scope if scope else ''} to draw on.")
        return
    for c in picks:
        a.company_ref(c)
    src = f"{scope} companies" if scope and not widened else "companies" if not scope else f"{scope} and other companies"
    detailed = [c for c in pool if _strong(c, qid)]
    base = detailed if len(detailed) >= 3 else leaders
    a.p(f"This is what {src} with the most detailed disclosures on {what} have in common for FY 2024-25 {how}. "
        + (f"The examples were chosen because they address {focus[1]}. " if focus else "")
        + "Each point names one company as an example; the full disclosures are at the end.")
    if widened:
        a.note("context", f"{scope} has fewer than three detailed disclosures on this topic, so examples from other "
                          f"sectors are included and labelled.")

    # ---- what a strong disclosure states (targets only): counted across the detailed disclosures
    if qid == "286" and len(base) >= 3:
        feats = [("A target year", re.compile(r"\b20[3-7]\d\b")),
                 ("A quantified reduction", re.compile(r"\d[\d.]*\s?(?:%|per ?cent)", re.I)),
                 ("A baseline year to measure against", re.compile(r"base ?line|base year", re.I)),
                 ("The scopes it covers", re.compile(r"scope[- ]?[123]", re.I)),
                 ("A net-zero or science-based commitment", re.compile(r"net[- ]?zero|carbon neutral|science[- ]based|sbti", re.I))]
        fc = a.c_calc("What detailed targets state", f"Count across the {len(base)} most detailed target disclosures "
                      f"{'in ' + scope if scope else 'among all companies'}",
                      note="An item is counted when the disclosure states it. A statement is not a verified result.")
        rows = [(label, sum(1 for c in base if rx.search(c["values"].get(qid) or ""))) for label, rx in feats]
        a.block("points", title="What a strong target states",
                items=[f"**{label}**: stated in {k} of the {len(base)} detailed disclosures {fc}." for label, k in rows if k])

    # ---- what companies commonly do, each with one named example in the company's own words
    common = []
    for t in THEMES:
        k = sum(1 for c in base if t in kb.themes(c["id"], qid))
        if k:
            common.append((t, k))
    common.sort(key=lambda t: (-t[1], t[0]))
    common = [t for i, t in enumerate(common[:5]) if i < 3 or t[1] * 5 >= len(base)]
    if common:
        cc = a.c_calc("Measures named most often", f"Count across the {len(base)} most detailed disclosures "
                      f"{'in ' + scope if scope else 'among all companies'}",
                      note="A measure is counted when the disclosure names it. A mention is not a verified result.")
        used, items, examples = set(), [], []
        ranked = sorted(base, key=lambda c: (c in picks, _detail(ctx, c, qid)), reverse=True)
        for t, k in common:
            ex = None
            for c in [x for x in ranked if x["id"] not in used] + ranked:
                segs = [g for g in ctx.index.by_cell.get((c["id"], qid), []) if _THEME_RE[t].search(g["text"])]
                if segs:
                    g = max(segs, key=lambda g: ((g.get("spec") or 0) - 0.01 * max(0, len(g["text"]) - 220), -g["seg"]))
                    ex = (c, _clip(g["text"]))
                    break
            items.append(f"**{t}**: {k} of the {len(base)} detailed disclosures name it {cc}.")
            if ex:
                used.add(ex[0]["id"])
                a.company_ref(ex[0])
                examples.append({"who": short_name(ex[0]["name"]), "text": ex[1], "cite": a.c_filing(ex[0], qid)})
            else:
                examples.append(None)
        a.block("points", title="What companies commonly do", items=items, examples=examples)
    items = [quote_item(ctx, c, qid) for c in picks]
    if focus:
        for it in items:
            on = [s for s in it["segments"] if focus[0].search(it["text"][s["start"]:s["end"]])]
            if on:
                keep = {id(s) for s in on[:4]}
                for s in it["segments"]:
                    s["highlight"] = id(s) in keep
    a.block("quotes", items=items, collapsed=True, title="Full disclosures",
            summary=f"View the full disclosures from {join([it['short'] for it in items])}")
    if me:
        a.company_ref(me)
        short = short_name(me["name"])
        if me["values"].get(qid):
            mine = set(kb.themes(me["id"], qid))
            missing = [t for t, k in common if t not in mine and k / len(base) >= 0.3]
            if missing:
                a.p(f"**For {short}:** its own disclosure {a.c_filing(me, qid)} does not mention {join([lc(t) for t in missing], 'or')}, "
                    f"which these companies describe.")
            else:
                a.p(f"**For {short}:** its own disclosure {a.c_filing(me, qid)} already covers the measures named most "
                    f"often by these companies.")
        else:
            a.p(f"**For {short}:** it has not disclosed {TOPIC.get(qid, what)} for FY 2024-25 {a.c_filing(me, qid)}.")
    a.context.update({"metric": mid, "sector": sid, "companies": [cid] if cid else []})
    other = "targets" if qid != "286" else "GHG reduction projects"
    a.follow(f"Tell me about {items[0]['short']}",
             f"Examples of {other}" + (f" from {scope} companies" if scope else ""),
             "Which companies mention green hydrogen?" if qid == "1342" else "Which companies mention SBTi?")


def _labels(ctx):
    plan = ctx.plan
    return [TECH_LABEL.get(t, t) for t in plan.tech] + [f"“{k}”" for k in plan.keywords]


def text_search(ctx, sid, me=None):
    a, kb = ctx.a, ctx.kb
    labels = _labels(ctx)
    pool_ids = set(kb.sector_by_id[sid]["members"]) if sid else None
    pool_n = kb.sector_by_id[sid]["n"] if sid else len(kb.companies)
    scope = kb.sector_by_id[sid]["name"] if sid else None
    mine = None
    if me and pool_ids:
        # the question is about the company's peers, so the company itself is counted separately
        mine = bool(ctx.index.search(ctx.plan.tech, ctx.plan.keywords, SEARCH_QIDS, {me["id"]}))
        pool_ids = pool_ids - {me["id"]}
        pool_n -= 1
    a.kicker = scope or "All companies"
    a.title = f"Mentions of {join(labels, 'or')}" if labels else "Search disclosures"
    if not labels:
        a.status = "partial"
        a.p("Tell me what to look for, for example a technology such as green hydrogen or waste heat recovery, or a "
            "phrase in quotation marks.")
        return
    hits = ctx.index.search(ctx.plan.tech, ctx.plan.keywords, SEARCH_QIDS, pool_ids)
    cids = sorted(hits, key=lambda cid: (-sum(len(sp) for _, sp in hits[cid]), kb.by_id[cid]["name"].lower()))
    cite = a.c_note("How the search works",
                    "An exact, case-insensitive match in what companies disclosed on targets, progress against targets, "
                    "projects to reduce GHG emissions and certifications. A mention is not a verified project.")
    where = f" in {scope}" if scope else ""
    own = ""
    if me:
        a.company_ref(me)
        where = f" among {short_name(me['name'])}'s {scope} peers"
        own = f" {short_name(me['name'])} itself {'mentions' if mine else 'does not mention'} it."
    if not cids:
        a.status = "partial"
        a.p(f"No company{where} mentions {join(labels, 'or')} in these disclosures {cite}. The search is literal, so a "
            f"company may describe the same thing in other words.{own}")
        a.follow("Which companies mention renewable energy?", "Examples of GHG reduction projects")
        return
    if me:
        a.p(f"**{len(cids)} of {short_name(me['name'])}'s {pool_n} {scope} peers ({share(len(cids), pool_n)})** mention "
            f"{join(labels, 'or')} in their disclosures {cite}.{own}")
    else:
        a.p(f"**{len(cids)} of {pool_n} companies ({share(len(cids), pool_n)})**{where} mention {join(labels, 'or')} in their "
            f"disclosures {cite}.")
    items = []
    for cid in cids[:5]:
        c = kb.by_id[cid]
        a.company_ref(c)
        d, spans = hits[cid][0]
        items.append({"key": f"{cid}:{d['qid']}", "company": c["name"], "company_id": cid, "short": short_name(c["name"]),
                      "sector": kb.sector_of(c)["name"], "topic": item(d["qid"])[0], "text": c["values"][d["qid"]],
                      "segments": [{"start": d["start"], "end": d["end"], "highlight": True,
                                    "marks": [[d["start"] + s0, d["start"] + s1] for s0, s1 in spans]}],
                      "mentions": sum(len(sp) for _, sp in hits[cid]), "cite": a.c_filing(c, d["qid"])})
    a.block("quotes", title="Where it is mentioned", items=items, excerpt=True)
    rows = [{"company": short_name(kb.by_id[cid]["name"]), "id": cid, "sector": kb.sector_of(kb.by_id[cid])["name"],
             "mentions": sum(len(sp) for _, sp in hits[cid])} for cid in cids]
    a.block("table", title=f"All {len(cids)} companies",
            columns=[{"key": "company", "label": "Company"}, {"key": "sector", "label": "Sector"},
                     {"key": "mentions", "label": "Mentions", "align": "right"}], rows=rows,
            export=export(a.title, ["Company", "Sector", "Mentions"],
                          [[kb.by_id[cid]["name"], kb.sector_of(kb.by_id[cid])["name"], r["mentions"]] for cid, r in zip(cids, rows)]))
    a.context.update({"tech": ctx.plan.tech, "sector": sid})
    a.follow(f"Show {items[0]['short']}'s projects to reduce GHG emissions",
             "Examples of GHG reduction projects" + (f" from {scope} companies" if scope else ""),
             "Which companies mention waste heat recovery?" if "waste heat recovery" not in labels else "Which companies mention green hydrogen?")


def learn_from(ctx, c, me=None):
    """What one named company disclosed on projects and targets, set against the user's own disclosure."""
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    short = short_name(c["name"])
    sname = kb.sector_of(c)["name"]
    a.kicker = f"{short} · {sname}"
    a.title = f"What {short} has disclosed"
    qids = [q for q in ("1342", "286", "295") if c["values"].get(q)]
    if not qids:
        a.status = "partial"
        a.p(f"**{c['name']}** has not disclosed projects to reduce GHG emissions or targets for FY 2024-25 "
            f"{a.c_filing(c, '1342')}, so there is nothing to draw on.")
        a.follow(f"Examples of GHG reduction projects from {sname} companies", f"Tell me about {short}")
        return
    items = [quote_item(ctx, c, q) for q in qids[:2]]
    topics = join([TOPIC.get(q, lc(item(q)[0])) for q in qids[:2]])
    a.p(f"This is what **{c['name']}** disclosed on {topics} for FY 2024-25 {items[0]['cite']}. The most specific points "
        f"are highlighted.")
    a.block("quotes", items=items)
    theirs = [t for q in qids for t in kb.themes(c["id"], q)]
    theirs = list(dict.fromkeys(theirs))
    if me and me["id"] != c["id"]:
        a.company_ref(me)
        mshort = short_name(me["name"])
        mine = {t for q in ("1342", "286", "295") for t in kb.themes(me["id"], q)}
        new = [t for t in theirs if t not in mine]
        own = a.c_filing(me, "1342")
        if new:
            a.p(f"**For {mshort}:** {short} names {join([lc(t) for t in new[:4]])}, which {mshort}'s own disclosures {own} "
                f"do not mention.")
        elif theirs:
            a.p(f"**For {mshort}:** its own disclosures {own} already mention the measures {short} names.")
    elif theirs:
        a.p(f"Measures it names: {join([lc(t) for t in theirs[:5]])}.")
    a.context.update({"companies": [c["id"]]})
    a.follow(f"Compare {short_name(me['name'])} with {short}" if me and me["id"] != c["id"] else f"Tell me about {short}",
             f"Examples of GHG reduction projects from {sname} companies", f"What are {short}'s GHG emissions?")
