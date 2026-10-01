"""Examples of good practice (shown exactly as disclosed) and search across disclosures."""
from __future__ import annotations

from . import metrics as M
from .common import export, yes
from .evidence import THEMES
from .fmt import join, lc, share, short_name
from .h_company import TEXT_TITLE, quote_item
from .public import TOPIC, item
from ..nlu.linker import TECH_TERMS

PRACTICE_QIDS = {"targets": "286", "target_performance": "295", "projects": "1342", "certifications": "277",
                 "ghg_assurance": "1342", "scope12": "1342", "intensity": "1342", "scope1": "1342", "scope2": "1342",
                 "scope3": "286"}
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
    qid = PRACTICE_QIDS.get(mid or "projects", "1342")
    me = kb.by_id[cid] if cid else None
    if me and not sid:
        sid = me["sector"]
    pool = kb.members(sid) if sid else kb.companies
    scope = kb.sector_by_id[sid]["name"] if sid else None
    what = EXAMPLE_NAME[qid]
    others = [c for c in pool if not me or c["id"] != me["id"]]
    leaders = [c for c in others if _strong(c, qid)]
    widened = False
    if len(leaders) < 3 and sid:
        extra = [c for c in kb.companies if _strong(c, qid) and c["sector"] != sid and (not me or c["id"] != me["id"])]
        extra.sort(key=lambda c: (-_detail(ctx, c, qid), c["name"].lower()))
        leaders = leaders + extra[: 3 - len(leaders)]
        widened = True
    leaders.sort(key=lambda c: (c["sector"] != sid if sid else False, -_detail(ctx, c, qid), c["name"].lower()))
    a.kicker = scope or "All companies"
    a.title = f"Examples: {what}"
    how = a.c_note("How examples are chosen",
                   "Examples are the disclosures with the most concrete detail: quantities, years, baselines and named "
                   "measures. The text is shown exactly as the company disclosed it.")
    picks = leaders[:3]
    if not picks:
        a.status = "partial"
        a.p(f"I could not find detailed disclosures on {what} {'in ' + scope if scope else ''} to show as examples.")
        return
    for c in picks:
        a.company_ref(c)
    src = f"{scope} companies" if scope and not widened else "companies" if not scope else f"{scope} and other companies"
    a.p(f"Here are {len(picks)} detailed examples of {what} disclosed by {src} for FY 2024-25 {how}. "
        f"The most specific points are highlighted.")
    if widened:
        a.note("context", f"{scope} has fewer than three detailed disclosures on this topic, so examples from other "
                          f"sectors are included and labelled.")
    items = [quote_item(ctx, c, qid) for c in picks]
    a.block("quotes", items=items)

    # measures named most often across the detailed disclosures
    detailed = [c for c in pool if _strong(c, qid)]
    common = []
    if len(detailed) >= 3:
        for t in THEMES:
            k = sum(1 for c in detailed if t in kb.themes(c["id"], qid))
            if k:
                common.append((t, k))
        common.sort(key=lambda t: (-t[1], t[0]))
        common = common[:5]
        if common:
            cc = a.c_calc("Measures named most often", f"Count across the {len(detailed)} most detailed disclosures "
                          f"{'in ' + scope if scope else 'among all companies'}",
                          note="A measure is counted when the disclosure names it. A mention is not a verified result.")
            a.p(f"Measures named most often in such disclosures: "
                f"{join([f'{lc(t)} ({k} of {len(detailed)})' for t, k in common])} {cc}.")
    if me:
        a.company_ref(me)
        short = short_name(me["name"])
        if me["values"].get(qid):
            mine = set(kb.themes(me["id"], qid))
            missing = [t for t, k in common if t not in mine and k / len(detailed) >= 0.3]
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


def text_search(ctx, sid):
    a, kb = ctx.a, ctx.kb
    labels = _labels(ctx)
    pool_ids = set(kb.sector_by_id[sid]["members"]) if sid else None
    pool_n = kb.sector_by_id[sid]["n"] if sid else len(kb.companies)
    scope = kb.sector_by_id[sid]["name"] if sid else None
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
    if not cids:
        a.status = "partial"
        a.p(f"No company{where} mentions {join(labels, 'or')} in these disclosures {cite}. The search is literal, so a "
            f"company may describe the same thing in other words.")
        a.follow("Which companies mention renewable energy?", "Examples of GHG reduction projects")
        return
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
