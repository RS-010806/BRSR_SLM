"""Best practices (verbatim, from top-rated disclosures) and disclosure search."""
from __future__ import annotations

import re

from ..analytics import median
from . import metrics as M
from .evidence import THEMES, highlight, specificity, themes_in
from .fmt import lc, join, pct, share, short_name
from ..nlu.linker import TECH_TERMS

PRACTICE_QIDS = {"targets": "286", "target_performance": "295", "projects": "1342", "certifications": "277",
                 "ghg_assurance": "1342", "scope12": "1342", "intensity": "1342", "scope1": "1342", "scope2": "1342",
                 "scope3": "286", "index": "1342"}
TECH_LABEL = {"sbti": "SBTi", "net zero": "net zero", "renewable energy": "renewable energy", "ev": "EVs",
              "electric vehicles": "electric vehicles", "carbon capture": "carbon capture (CCUS)"}
SEARCH_QIDS = {"286", "295", "1342", "277", "353", "1561"}


def _evidence_score(ctx, c, qid):
    segs = ctx.index.by_cell.get((c["id"], qid), [])
    scores = sorted((specificity(s["text"]) for s in segs), reverse=True)
    return round(sum(scores[:3]), 3)


def best_practice(ctx, mid, sid, cid):
    a, kb = ctx.a, ctx.kb
    qid = PRACTICE_QIDS.get(mid or "projects", "1342")
    q = kb.q(qid)
    me = kb.by_id[cid] if cid else None
    if me and not sid:
        sid = me["sector"]
    pool = kb.members(sid) if sid else kb.companies
    scope = kb.sector_by_id[sid]["name"] if sid else "all companies"
    leaders = [c for c in pool if c["ratings"].get(qid) == 100 and c["values"].get(qid) and (not me or c["id"] != me["id"])]
    widened = False
    if len(leaders) < 3 and sid:
        extra = [c for c in kb.companies if c["ratings"].get(qid) == 100 and c["values"].get(qid)
                 and c["sector"] != sid and (not me or c["id"] != me["id"])]
        extra.sort(key=lambda c: (-_evidence_score(ctx, c, qid), c["name"].lower()))
        leaders = leaders + extra[: 3 - len(leaders)]
        widened = True
    leaders.sort(key=lambda c: (c["sector"] != sid if sid else False, -_evidence_score(ctx, c, qid),
                                -(c["derived"]["index"]["overall"] or 0), c["name"].lower()))
    a.kicker = f"Best practices · {scope}"
    a.title = q["label"]
    top_level = (q.get("rubric") or [{}])[-1].get("text", "")
    n100 = sum(1 for c in pool if c["ratings"].get(qid) == 100)
    sel = a.c_derived(f"Leaders on Q{qid} in {scope}",
                      f"{n100} of {len(pool)} companies score 100; ordered by specificity of their three most concrete "
                      f"sentences, then derived E1 index, then name",
                      note="Specificity counts quantities with units, years, baselines and named practices. "
                           "Selection is deterministic.")
    if n100:
        a.p(f"In {scope}, **{n100} of {len(pool)} companies** score 100 on {lc(q['label'])}, the level described as "
            f"“{top_level.rstrip('.')}” {sel}. The most specific of these disclosures are reproduced verbatim below, "
            f"with their most concrete sentences highlighted.")
    else:
        a.p(f"No company in {scope} scores 100 on {lc(q['label'])} {sel}.")
    if widened:
        a.note("method", f"Fewer than three {scope} companies score 100 here, so the closest examples are drawn from other "
                         f"sectors and labelled with their sector.")
    items = []
    for c in leaders[:3]:
        a.company_ref(c)
        segs = ctx.index.by_cell.get((c["id"], qid), [])
        text = c["values"][qid]
        items.append({"company": c["name"], "company_id": c["id"], "short": short_name(c["name"]),
                      "sector": kb.sector_of(c)["name"], "qid": qid, "question": q["label"], "score": 100,
                      "text": text, "segments": highlight(segs, k=3), "themes": themes_in(text),
                      "cite": a.c_cell(c, qid), "rating_cite": a.c_rating(c, qid), "cell": c["cells"].get(qid)})
    if items:
        a.p(f"Examples: {join([f'**{i['short']}** ({i['sector']}) {i['cite']}' for i in items])}.")
        a.block("quotes", title="Top-rated disclosures, verbatim", items=items)

    # practices that distinguish leaders from the rest of the pool
    all100 = [c for c in pool if c["ratings"].get(qid) == 100 and c["values"].get(qid)]
    rest = [c for c in pool if c["ratings"].get(qid) != 100 and c["values"].get(qid)]
    rows = []
    if len(all100) >= 2:
        for t in THEMES:
            l = sum(1 for c in all100 if t in themes_in(c["values"][qid]))
            r = sum(1 for c in rest if t in themes_in(c["values"][qid]))
            if l:
                rows.append({"label": t, "values": [100 * l / len(all100), 100 * r / len(rest) if rest else 0],
                             "displays": [f"{100 * l / len(all100):.0f}%", f"{100 * r / len(rest):.0f}%" if rest else "0%"],
                             "counts": [l, r]})
        rows.sort(key=lambda r: (-r["values"][0], r["label"]))
        rows = rows[:8]
        if rows:
            a.block("grouped", title="Practices named in top-rated vs other disclosures",
                    subtitle=f"Share of companies whose Q{qid} text names each practice ({scope})",
                    series=[f"Score 100 ({len(all100)})", f"Other disclosures ({len(rest)})"], groups=rows, max=100,
                    unit="%", horizontal=True)
            gap = [r for r in rows if r["values"][0] - r["values"][1] >= 15]
            if gap:
                a.p(f"Practices named far more often by top-rated companies than by the rest: "
                    f"{join([f'{lc(r['label'])} ({r['displays'][0]} vs {r['displays'][1]})' for r in gap[:4]])} "
                    f"{a.c_derived('Practice frequency', 'keyword families matched in disclosure text of each group', note='Keyword families are listed in the method note; matches are exact, case-insensitive.')}.")

    # personalised gap analysis
    if me:
        a.company_ref(me)
        s = me["ratings"].get(qid)
        mine = set(themes_in(me["values"].get(qid) or ""))
        common = [r["label"] for r in rows if r["values"][0] >= 40] if rows else []
        missing = [t for t in common if t not in mine]
        my_spec = _evidence_score(ctx, me, qid)
        lead_spec = median(_evidence_score(ctx, c, qid) for c in all100) if all100 else None
        txt = (f"**For {short_name(me['name'])}:** its disclosure scores **{s if s is not None else 'n/a'}/100** "
               f"{a.c_rating(me, qid)}")
        if me["values"].get(qid):
            txt += f" {a.c_cell(me, qid)}"
            if lead_spec is not None:
                txt += (f". Its three most concrete sentences have a specificity score of {my_spec:.1f} against a median of "
                        f"{lead_spec:.1f} for top-rated peers")
            if missing:
                txt += f". Practices common among top-rated peers but not named in its text: {join([m.lower() for m in missing])}"
        else:
            txt += ". The disclosure is blank"
        a.p(txt + ".")
        a.block("gap", company=short_name(me["name"]), score=s, peers_score=100, my_themes=sorted(mine),
                missing=missing, my_specificity=my_spec, leader_specificity=lead_spec, qid=qid, question=q["label"])
        a.note("method", "The gap view compares what is disclosed, not what is done. It never recommends actions the "
                         "sources do not describe; every practice listed appears verbatim in a top-rated disclosure.")
    a.context.update({"metric": mid, "sector": sid, "companies": [cid] if cid else []})
    a.follow(f"Show {items[0]['short']}'s E1 profile" if items else None,
             f"Best practices on {'targets' if qid != '286' else 'GHG reduction projects'}" + (f" in {scope}" if sid else ""),
             f"Which companies mention green hydrogen?" if qid == "1342" else "Which companies mention SBTi?")


def _patterns_for(ctx):
    plan = ctx.plan
    pats, labels = [], []
    for term in plan.tech:
        phs = TECH_TERMS.get(term, [term])
        pats += [r"\b" + re.escape(p).replace(r"\ ", r"[\s-]+") + r"\b" for p in phs]
        labels.append(TECH_LABEL.get(term, term))
    for k in plan.keywords:
        pats.append(re.escape(k))
        labels.append(f"“{k}”")
    return pats, labels


def text_search(ctx, sid):
    a, kb = ctx.a, ctx.kb
    pats, labels = _patterns_for(ctx)
    pool_ids = set(kb.sector_by_id[sid]["members"]) if sid else None
    pool_n = kb.sector_by_id[sid]["n"] if sid else len(kb.companies)
    scope = kb.sector_by_id[sid]["name"] if sid else "all companies"
    a.kicker = f"Disclosure search · {scope}"
    a.title = f"Mentions of {join(labels, 'or')}" if labels else "Disclosure search"
    if not pats:
        a.status = "partial"
        a.p("Tell me what to look for, for example a technology (green hydrogen, waste heat recovery) or a quoted phrase.")
        return
    hits = ctx.index.phrase(pats, SEARCH_QIDS, pool_ids)
    cids = sorted(hits, key=lambda cid: (-sum(len(sp) for _, sp in hits[cid]), kb.by_id[cid]["name"].lower()))
    cite = a.c_derived("Disclosure search", f"exact, case-insensitive match of {len(pats)} phrase variants across "
                                            f"Q286, Q295, Q1342, Q277, Q353 and Q1561 for {pool_n} companies",
                       note="Matches are literal text in the filing. A mention is not a verified project.")
    if not cids:
        a.status = "partial"
        a.p(f"No disclosure in {scope} mentions {join(labels, 'or')} {cite}. The search is literal, so companies may "
            f"describe the same practice in other words.")
        a.follow("Which companies mention renewable energy?", "Best practices on GHG reduction projects")
        return
    by_q = {}
    for cid in cids:
        for d, _ in hits[cid]:
            by_q.setdefault(d["qid"], set()).add(cid)
    where = f" in {scope}" if sid else ""
    a.p(f"**{len(cids)} of {pool_n} companies ({share(len(cids), pool_n)})**{where} mention {join(labels, 'or')} in "
        f"their E1 disclosures {cite}: "
        + join([f"{len(v)} in {lc(kb.q(q)['label'])}" for q, v in sorted(by_q.items(), key=lambda t: (-len(t[1]), t[0]))])
        + ".")
    items = []
    for cid in cids[:6]:
        c = kb.by_id[cid]
        a.company_ref(c)
        d, spans = hits[cid][0]
        text = c["values"][d["qid"]]
        segs = [{"start": d["start"], "end": d["end"], "highlight": True,
                 "marks": [[d["start"] + s0, d["start"] + s1] for s0, s1 in spans]}]
        items.append({"company": c["name"], "company_id": cid, "short": short_name(c["name"]),
                      "sector": kb.sector_of(c)["name"], "qid": d["qid"], "question": kb.q(d["qid"])["label"],
                      "score": c["ratings"].get(d["qid"]), "text": text, "segments": segs, "excerpt": True,
                      "mentions": sum(len(sp) for _, sp in hits[cid]), "cite": a.c_cell(c, d["qid"]),
                      "cell": c["cells"].get(d["qid"])})
    a.block("quotes", title="Matching sentences, verbatim", items=items, excerpt=True)
    if not sid:
        counts = {}
        for cid in cids:
            s = kb.by_id[cid]["sector"]
            counts[s] = counts.get(s, 0) + 1
        a.block("bars", title="Companies mentioning it, by sector", unit="companies",
                rows=[{"id": s, "label": kb.sector_by_id[s]["name"], "value": v, "display": str(v),
                       "full": f"{v} of {kb.sector_by_id[s]['n']} ({share(v, kb.sector_by_id[s]['n'])})"}
                      for s, v in sorted(counts.items(), key=lambda t: (-t[1], kb.sector_by_id[t[0]]["name"]))])
    a.block("table", title=f"All {len(cids)} companies", csv=True,
            columns=[{"key": "company", "label": "Company"}, {"key": "sector", "label": "Sector"},
                     {"key": "mentions", "label": "Mentions", "align": "right"}, {"key": "where", "label": "Where"}],
            rows=[{"company": short_name(kb.by_id[cid]["name"]), "id": cid, "sector": kb.sector_of(kb.by_id[cid])["short"],
                   "mentions": sum(len(sp) for _, sp in hits[cid]),
                   "where": ", ".join(sorted({f"Q{d['qid']}" for d, _ in hits[cid]}))} for cid in cids])
    a.context.update({"tech": ctx.plan.tech, "sector": sid})
    a.follow(f"Show {items[0]['short']}'s GHG reduction projects",
             f"Best practices on GHG reduction projects" + (f" in {scope}" if sid else ""),
             "Which companies mention waste heat recovery?" if "waste heat recovery" not in labels else "Which companies mention green hydrogen?")
