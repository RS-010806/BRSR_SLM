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
SCOPE_NAME = {"scope1": "Scope 1", "scope2": "Scope 2", "scope3": "Scope 3"}
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


# A sentence that reads as an example: a complete statement with an action and a number, not a list fragment or a code.
_ACTION = re.compile(r"\b(install\w*|commission\w*|achiev\w*|reduc\w*|target\w*|aim\w*|commit\w*|set up|replac\w*|switch\w*|"
                     r"implement\w*|adopt\w*|increas\w*|generat\w*|sav\w*|plan\w*|transition\w*|procur\w*|sourc\w*|deploy\w*|"
                     r"introduc\w*|launch\w*|expand\w*|convert\w*|shift\w*|use[ds]?|using|undert\w*|establish\w*|enhanc\w*|"
                     r"improv\w*|recover\w*|captur\w*|plant\w*|offset\w*|eliminat\w*|achieve)\b", re.I)


def _sentence_score(g) -> float:
    t = re.sub(r"\s+", " ", g["text"]).strip()
    n = len(t)
    s = float(g.get("spec") or 0)
    if n < 45:
        s -= 3
    if n > 260:
        s -= (n - 260) / 60
    if not _ACTION.search(t):
        s -= 2.5
    s -= 1.5 * sum(1 for w in t.split() if re.search(r"\d", w) and re.search(r"[A-Za-z]{2}", w) and not re.search(r"(?i)mw|kw|gw|tco|fy|%", w))
    if re.match(r"^[a-z]", t):
        s -= 6                                            # starts in the middle of a sentence
    elif re.match(r"^[(•\-–·*\d.)]", t):
        s -= 1
    if re.search(r"(?:\b(?:in|of|and|the|to|for|by|with|from|at|a|an|or)|[,(+&]|\b\d[\d,.]*)$", t):
        s -= 4                                            # stops in the middle of a sentence
    if t.count("(") != t.count(")"):
        s -= 2
    if t.count(":") >= 2:
        s -= 1
    return round(s, 3)


def _around(text: str, rx=None, n: int = 200, spans=None) -> str:
    """A long passage shortened to the part that matters: the stretch around the match, not its opening words."""
    t = re.sub(r"\s+", " ", text).strip()
    if len(t) <= n:
        return _clip(t, n)
    start = None
    if spans:
        start = spans[0][0]
    elif rx is not None:
        m = rx.search(t)
        start = m.start() if m else None
    if start is None or start < n - 60:
        return _clip(t, n)
    b = max(t.rfind(". ", 0, start), t.rfind("; ", 0, start))
    b = b + 2 if b >= 0 and start - b < n - 40 else max(0, start - 60)
    piece = t[b:]
    if b > 0 and not piece[:1].isupper():
        piece = piece.split(" ", 1)[-1]
        res = _clip(piece, n - 2)
        return res if res.startswith("… ") else "… " + res
    return _clip(piece, n)


def _best_sentence(ctx, c, qid, rx=None):
    segs = [g for g in ctx.index.by_cell.get((c["id"], qid), []) if rx is None or rx.search(g["text"])]
    if not segs:
        return None
    return max(segs, key=lambda g: (_sentence_score(g), -g["seg"]))


# A question about one practice ("best practices for solar", "how are cement companies using EVs") is answered about that practice.
TECH_THEME = {"solar": "Renewable energy", "wind": "Renewable energy", "renewable energy": "Renewable energy",
              "green hydrogen": "Green hydrogen", "biomass": "Fuel switching and alternative fuels",
              "alternative fuels": "Fuel switching and alternative fuels", "electric vehicles": "Electrification and EVs",
              "waste heat recovery": "Waste heat recovery", "carbon capture": "Carbon capture",
              "sbti": "Science-based or net-zero targets", "net zero": "Science-based or net-zero targets",
              "energy efficiency": "Energy efficiency", "heat pumps": "Energy efficiency",
              "afforestation": "Afforestation and carbon sinks", "internal carbon price": "Internal carbon pricing",
              "green buildings": "Green buildings"}
THEME_ASK = {t: q for q, t in (("solar", "Renewable energy"), ("green hydrogen", "Green hydrogen"), ("electric vehicles", "Electrification and EVs"),
                               ("waste heat recovery", "Waste heat recovery"), ("energy efficiency", "Energy efficiency"),
                               ("net zero", "Science-based or net-zero targets"), ("afforestation", "Afforestation and carbon sinks"),
                               ("alternative fuels", "Fuel switching and alternative fuels"), ("carbon capture", "Carbon capture"),
                               ("green buildings", "Green buildings"), ("internal carbon price", "Internal carbon pricing"))}
PRACTICE_SEARCH = {"1342", "286", "295"}


def _count(ctx) -> int | None:
    n = ctx.plan.n
    return max(1, min(int(n), 8)) if n else None


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
    if me and not sid:
        sid = me["sector"]
    low = (ctx.plan.resolved_query or ctx.plan.query).lower()
    if not ctx.plan.tech:
        # a pledge named in the question ("examples of net zero targets") is the topic, like a technology
        if re.search(r"\bsbti\b|science[- ]based", low):
            ctx.plan.tech = ["sbti"]
        elif re.search(r"net[- ]?zero|carbon neutral", low):
            ctx.plan.tech = ["net zero"]
    if ctx.plan.tech:
        return _topic_practice(ctx, sid, me)
    qid = PRACTICE_QIDS.get(mid or "projects", "1342")
    if mid in FOCUS and "targets" in ctx.plan.raw_metrics:
        qid = "286"                                   # "scope 3 targets": targets that talk about that scope
    pool = kb.members(sid) if sid else kb.companies
    scope = kb.sector_by_id[sid]["name"] if sid else None
    what = EXAMPLE_NAME[qid]
    focus = FOCUS.get(mid)
    n_full = _count(ctx) or 3
    rel = (lambda c: bool(focus[0].search(c["values"].get(qid) or ""))) if focus else (lambda c: True)
    others = [c for c in pool if not me or c["id"] != me["id"]]
    leaders = [c for c in others if _strong(c, qid) and rel(c)]
    if len(leaders) < max(n_full, 6):
        # top up with the sector's own most detailed disclosures before looking at other sectors
        rest = sorted([c for c in others if c not in leaders and c["values"].get(qid) and rel(c) and _detail(ctx, c, qid) > 0],
                      key=lambda c: (-_detail(ctx, c, qid), c["name"].lower()))
        leaders = leaders + rest[: max(n_full, 6) - len(leaders)]
    widened = False
    if len(leaders) < n_full and sid:
        extra = [c for c in kb.companies if _strong(c, qid) and rel(c) and c["sector"] != sid and (not me or c["id"] != me["id"])]
        extra.sort(key=lambda c: (-_detail(ctx, c, qid), c["name"].lower()))
        leaders = leaders + extra[: n_full - len(leaders)]
        widened = bool(extra)
    leaders.sort(key=lambda c: (c["sector"] != sid if sid else False, -_detail(ctx, c, qid), c["name"].lower()))
    a.kicker = scope or "All companies"
    a.title = f"Good practice: {what}" + (f" for {SCOPE_NAME[mid]}" if focus else "")
    how = a.c_note("How this is put together",
                   "Drawn from the disclosures with the most concrete detail: quantities, years, baselines and named "
                   "measures. Quoted text is exactly as the company disclosed it.")
    picks = leaders[:n_full]
    if not picks:
        a.status = "partial"
        a.p(f"I could not find detailed disclosures on {what}{' in ' + scope if scope else ''} to draw on.")
        a.follow(f"Which companies have disclosed {what}?")
        return
    for c in picks:
        a.company_ref(c)
    src = f"{scope} companies" if scope and not widened else "companies" if not scope else f"{scope} and other companies"
    detailed = [c for c in others if _strong(c, qid)]
    base = detailed if len(detailed) >= 6 else leaders
    mshort = short_name(me["name"]) if me else None
    a.p(f"This is what {src} with the most detailed disclosures on {what} have in common for FY 2024-25 {how}"
        + (f", and how {mshort}'s own disclosure compares. " if me else ". ")
        + (f"The examples address {focus[1]}." if focus else "Each point names one company as an example."))
    if widened:
        a.note("context", f"{scope} has few detailed disclosures on this topic, so examples from other sectors are included "
                          f"and labelled.")

    # ---- what a strong target states: counted across the detailed disclosures
    if qid == "286" and len(base) >= 3 and not focus:
        feats = [("A target year", re.compile(r"\b20[3-7]\d\b")),
                 ("A quantified reduction", re.compile(r"\d[\d.]*\s?(?:%|per ?cent)", re.I)),
                 ("A baseline year to measure against", re.compile(r"base ?line|base year", re.I)),
                 ("The scopes it covers", re.compile(r"scope[- ]?[123]", re.I)),
                 ("A net-zero or science-based commitment", re.compile(r"net[- ]?zero|carbon neutral|science[- ]based|sbti", re.I))]
        fc = a.c_calc("What detailed targets state", f"Count across the {len(base)} most detailed target disclosures "
                      f"{'in ' + scope if scope else 'among all companies'}",
                      note="An item is counted when the disclosure states it. A statement is not a verified result.")
        rows = sorted([(label, sum(1 for c in base if rx.search(c["values"].get(qid) or ""))) for label, rx in feats],
                      key=lambda r: -r[1])
        a.block("points", title="What a strong target states",
                items=[f"**{label}**: in {k} of the {len(base)} detailed disclosures {fc}." for label, k in rows if k])

    # ---- what companies commonly do, each with one named example in the company's own words
    common = []
    for t in THEMES:
        k = sum(1 for c in base if t in kb.themes(c["id"], qid))
        if k:
            common.append((t, k))
    common.sort(key=lambda t: (-t[1], t[0]))
    common = [t for i, t in enumerate(common[:6]) if i < 3 or t[1] * 5 >= len(base)]
    if common:
        cc = a.c_calc("Measures named most often", f"Count across the {len(base)} most detailed disclosures "
                      f"{'in ' + scope if scope else 'among all companies'}",
                      note="A measure is counted when the disclosure names it. A mention is not a verified result.")
        used, items, examples = set(), [], []
        for t, k in common:
            cands = []
            for c in base:
                g = _best_sentence(ctx, c, qid, _THEME_RE[t])
                if g:
                    cands.append((_sentence_score(g) - (6 if c["id"] in used else 0) + (2 if sid and c["sector"] == sid else 0),
                                  c["name"].lower(), c, g))
            items.append(f"**{t}**: named in {k} of the {len(base)} detailed disclosures {cc}.")
            if cands:
                _, _, c, g = max(cands, key=lambda x: (x[0], x[1]))
                used.add(c["id"])
                a.company_ref(c)
                examples.append({"who": short_name(c["name"]), "text": _around(g["text"], _THEME_RE[t]), "cite": a.c_filing(c, qid)})
            else:
                examples.append(None)
        a.block("points", title="What companies commonly do", items=items, examples=examples)

    # ---- the company the question is about: what it already covers and what it could add
    if me:
        a.company_ref(me)
        if me["values"].get(qid):
            mine = set(kb.themes(me["id"], qid))
            have = [t for t, _ in common if t in mine]
            gaps = [(t, k) for t, k in common if t not in mine]
            own = a.c_filing(me, qid)
            pts = []
            if have:
                pts.append(f"**Already in its disclosure:** {join([lc(t) for t in have])} {own}.")
            for t, k in gaps[:4]:
                pts.append(f"**{t}:** not mentioned in its disclosure; named in {k} of the {len(base)} detailed disclosures {own}.")
            if not gaps:
                pts.append(f"**Coverage:** its disclosure already names every measure listed above {own}.")
            a.block("points", title=f"For {mshort}", items=pts)
        else:
            a.block("points", title=f"For {mshort}",
                    items=[f"**No disclosure yet:** {mshort} has not disclosed {TOPIC.get(qid, what)} for FY 2024-25 "
                           f"{a.c_filing(me, qid)}; {len(detailed)} of its {len(others)} peers have a detailed one."])
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
    a.context.update({"metric": mid, "sector": sid, "companies": [cid] if cid else []})
    other = "targets" if qid != "286" else "GHG reduction projects"
    top_theme = common[0][0] if common else None
    a.follow(f"How does {mshort} compare with its peers?" if me else f"Tell me about {items[0]['short']}",
             f"Which {scope + ' ' if scope else ''}companies mention {THEME_ASK[top_theme]}?" if top_theme in THEME_ASK else None,
             f"Examples of {other}" + (f" from {scope} companies" if scope else ""))


def _topic_practice(ctx, sid, me):
    """Good practice on one measure the question names: who describes it, how concretely, and their own words."""
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    labels = [TECH_LABEL.get(t, t) for t in plan.tech]
    label = join(labels, "or")
    scope = kb.sector_by_id[sid]["name"] if sid else None
    pool = kb.members(sid) if sid else kb.companies
    others = [c for c in pool if not me or c["id"] != me["id"]]
    hits = ctx.index.search(plan.tech, [], PRACTICE_SEARCH, {c["id"] for c in others})
    widened = False
    if len(hits) < 3 and sid:
        more = ctx.index.search(plan.tech, [], PRACTICE_SEARCH, {c["id"] for c in kb.companies if not me or c["id"] != me["id"]})
        widened = len(more) > len(hits)
        hits = more if widened else hits
    a.kicker = scope or "All companies"
    a.title = f"Good practice: {label}"
    how = a.c_note("How this is put together",
                   "An exact match for the term in what companies disclosed on projects, targets and progress against "
                   "targets. Examples are the most concrete sentences: quantities, years and named measures.")
    if not hits:
        a.status = "partial"
        a.p(f"No company{' in ' + scope if scope else ''} mentions {label} in its disclosures on projects or targets for "
            f"FY 2024-25 {how}. The search is literal, so a company may describe the same thing in other words.")
        a.follow("Examples of GHG reduction projects" + (f" from {scope} companies" if scope else ""))
        return
    rows = []
    for cid, found in hits.items():
        c = kb.by_id[cid]
        d, spans = max(found, key=lambda dsp: (_sentence_score(dsp[0]), -dsp[0]["seg"]))
        rows.append((_sentence_score(d), c["name"].lower(), c, d, spans, found))
    rows.sort(key=lambda r: (-r[0], r[1]))
    n_ex = _count(ctx) or min(5, len(rows))
    k, N = len(rows), len(others) if not widened else len(kb.companies) - (1 if me else 0)
    texts = {r[2]["id"]: " ".join(d["text"] for d, _ in r[5]) for r in rows}
    quant = sum(1 for t in texts.values() if re.search(r"\d[\d,.]*\s?(?:%|per ?cent\b|(?:mw|kw|gw|mwp|kwp|kwh|mwh|gwh|tonnes?|tco2e?|kl|crore|lakh|units?)\b)", t, re.I))
    year = sum(1 for t in texts.values() if re.search(r"\b20[2-5]\d\b", t))
    in_targets = sum(1 for r in rows if any(d["qid"] in ("286", "295") for d, _ in r[5]))
    cc = a.c_calc(f"Companies mentioning {label}", f"{k} of {N} companies" + (f" in {scope}" if scope and not widened else ""),
                  note="A mention is not a verified project.")
    where = f"{scope} companies" if scope and not widened else "companies"
    a.p(f"**{k} of the {N} {where}** mention {label} in their disclosures on projects or targets for FY 2024-25 {cc}. "
        f"These are the most concrete examples {how}.")
    if widened:
        a.note("context", f"Few {scope} companies mention it, so examples from other sectors are included and labelled.")
    a.block("points", title="At a glance", items=[
        f"**Give a size or a figure** (capacity, percentage or tonnes): {quant} of the {k} {cc}.",
        f"**Tie it to a year:** {year} of the {k} {cc}.",
        f"**Make it part of a target:** {in_targets} of the {k} mention it in their targets or progress against targets {cc}."])
    chosen = rows[:n_ex]
    items, examples = [], []
    for score, _, c, d, spans, _ in chosen:
        a.company_ref(c)
        items.append(f"**{short_name(c['name'])}**" + (f" ({kb.sector_of(c)['name']})" if not scope or c["sector"] != sid else ""))
        examples.append({"who": "", "text": _around(d["text"], None, 240, spans), "cite": a.c_filing(c, d["qid"])})
    a.block("points", title="Examples", items=items, examples=examples)
    if me:
        a.company_ref(me)
        mine = ctx.index.search(plan.tech, [], PRACTICE_SEARCH, {me["id"]}).get(me["id"])
        ms = short_name(me["name"])
        if mine:
            d, _ = max(mine, key=lambda dsp: (_sentence_score(dsp[0]), -dsp[0]["seg"]))
            a.block("points", title=f"For {ms}", items=[f"**Already mentioned:** {ms} describes it in its own disclosure {a.c_filing(me, d['qid'])}."],
                    examples=[{"who": "", "text": _clip(d["text"], 240), "cite": a.c_filing(me, d["qid"])}])
        else:
            a.block("points", title=f"For {ms}", items=[
                f"**Not mentioned yet:** {ms}'s disclosures on projects and targets do not mention {label} "
                f"{a.c_filing(me, '1342')}; {k} of the {N} {where} do {cc}."])
    full = []
    for score, _, c, d, spans, found in chosen[:3]:
        segs = [{"start": x["start"], "end": x["end"], "highlight": True, "marks": [[x["start"] + s0, x["start"] + s1] for s0, s1 in sp]}
                for x, sp in found if x["qid"] == d["qid"]][:4]
        full.append({"key": f"{c['id']}:{d['qid']}", "company": c["name"], "company_id": c["id"], "short": short_name(c["name"]),
                     "sector": kb.sector_of(c)["name"], "topic": item(d["qid"])[0], "text": c["values"][d["qid"]],
                     "segments": segs, "cite": a.c_filing(c, d["qid"])})
    a.block("quotes", items=full, excerpt=True, collapsed=True,
            summary=f"View where {join([x['short'] for x in full])} mention it")
    a.context.update({"tech": plan.tech, "sector": sid, "companies": [me["id"]] if me else []})
    a.follow(f"Which {scope + ' ' if scope else ''}companies mention {labels[0]}?",
             f"Tell me about {short_name(chosen[0][2]['name'])}",
             "Examples of GHG reduction projects" + (f" from {scope} companies" if scope else ""))


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
    a.block("table", title=f"All {len(cids)} companies" if len(cids) > 1 else "The company",
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
