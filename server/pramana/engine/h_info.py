"""Greeting, explanations, report insights, refusals, not-found and clarification."""
from __future__ import annotations

import re

from rapidfuzz import fuzz, process

from ..nlu.lexicon import KNOWN_ABSENT, METRICS, OFFTOPIC
from . import metrics as M
from .fmt import lc, join, short_name

OFF = {o["key"]: o for o in OFFTOPIC}

TOOL_DOCS = {
    "hallucination": ("How Pramana stays grounded",
                      "Pramana does not generate free text with a language model. A small transformer, trained from scratch "
                      "on this domain, only classifies what you are asking; the entities are then resolved against the 982 "
                      "companies, 22 sectors and 38 questions in the dataset, the numbers are computed from the workbook, "
                      "and the answer is assembled from fixed sentence templates. Every figure carries a citation to the "
                      "exact cell, rating, report table or report page it came from. If something is not in the sources, "
                      "the answer says so instead of guessing, and the assistant has no internet access."),
    "deterministic": ("Why answers never change",
                      "There is no sampling anywhere in the pipeline. The same question with the same conversation context "
                      "produces byte-identical output, and each answer carries a fingerprint (a hash of its content and the "
                      "dataset version) so anyone can confirm two answers are identical."),
    "index": ("E1 index (derived)", M.NUMERIC["index"].note + " Pillars: Governance (Q232 to Q353, 14 questions), "
              "Action (Q1329, Q1340, Q1341, Q1342, Q1387, Q1560, Q1561, Q1828) and Performance (Q1330, Q1332, Q1334 to "
              "Q1339, Q1388, Q1390, Q1391). Questions without a score for a company are left out of that company's "
              "pillar average. Note that the Rating sheet awards 100 when both years of a metric are reported as 0."),
    "sources": ("Where the data comes from",
                "Three files provided by the IIMB team: the E1 workbook (Questions, Base Data and Rating sheets), the E1 "
                "chapter of the report, and the published report 'Business Responsibility and Sustainability in India' "
                "(FY 2024-25). The workbook covers 982 companies with BRSR filings on NSE for FY 2024-25 with FY 2023-24 "
                "comparatives. All 597 figures in the E1 chapter's tables are reproduced exactly from the workbook."),
    "exclusions": ("Excluded and flagged values",
                   "Following the report, SIS Limited's Scope 1 and 2 values (up to 39.2 billion tCO2e) and Patel "
                   "Engineering's previous-year Scope 2 (31.3 billion tCO2e) are excluded from sector totals. Separately, "
                   "per-rupee intensities above 0.001 tCO2e per rupee (10,000 tCO2e per crore) are shown as reported but "
                   "flagged as a probable unit inconsistency and kept out of level rankings. Nothing is corrected or "
                   "imputed: the report's 'as-reported' principle is preserved."),
    "period": ("Reporting period",
               "Current year is FY 2024-25 and the comparative previous year is FY 2023-24, as filed in BRSR. No other "
               "years are in the dataset."),
}
RE_TOOL = [
    ("hallucination", re.compile(r"hallucinat|make things up|trust|reliable|accurate|accuracy|guardrail|how do you (work|answer)|grounded|made up")),
    ("deterministic", re.compile(r"determinis|same answer|consistent|change (your|the) answer|different answers|fingerprint")),
    ("index", re.compile(r"\b(e1 )?index\b|composite|overall score|pillar")),
    ("exclusions", re.compile(r"exclu|flag|outlier|unit (check|inconsisten)|sis limited|patel")),
    ("sources", re.compile(r"data (come|source)|where .*data|source(s)? of|dataset|methodolog|xbrl|nse filing")),
    ("period", re.compile(r"\b(year|period|fy)\b.*\b(cover|covered|available|does)\b|which (year|fy)")),
]


def greeting(ctx):
    a = ctx.a
    a.kicker = "Pramana"
    a.title = "Evidence-grounded answers on BRSR climate disclosures"
    t22 = a.c_report_text("Table 2.2: Sector Coverage, NSE Classification and Company Distribution", 23, "Chapter 2")
    a.p(f"I answer questions about the **E1 theme (GHG emissions and climate risk)** for **{len(ctx.kb.companies)} "
        f"listed companies** across {len(ctx.kb.sectors)} sectors {t22}, using their FY 2024-25 BRSR filings and the "
        f"IIMB analysis. Every number links to the exact source cell, rating or report page.")
    a.p("I do not browse the web or guess. If something is not in the data, I say so and show what is.")
    a.block("capabilities", items=[
        {"title": "Plain data", "text": "Scope 1, 2 and 3, intensity, assurance, targets for any company.",
         "example": "What are Tata Steel's Scope 1 emissions?"},
        {"title": "Peer comparison", "text": "Rank a company within its sector on every E1 dimension.",
         "example": "How does ACC compare with its peers?"},
        {"title": "Best practices", "text": "Verbatim examples from the top-rated disclosures.",
         "example": "Best practices for GHG reduction projects in cement"},
        {"title": "Sector insight", "text": "Totals, medians and report findings by sector.",
         "example": "Give me an overview of the power sector"},
        {"title": "What-if", "text": "See how a cut would change a company's rating and rank.",
         "example": "What if NTPC cuts Scope 1 by 10%?"},
        {"title": "Search disclosures", "text": "Find every company that mentions a practice.",
         "example": "Which companies mention green hydrogen?"},
    ])
    a.follow("What are the key findings of the E1 report?", "Show me Infosys's E1 profile",
             "Top 10 emitters", "How do you avoid hallucinations?")


def explain(ctx):
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    low = plan.query.lower()
    a.kicker = "Explainer"
    for key, rx in RE_TOOL:
        if rx.search(low) and not (key == "index" and plan.metric and plan.metric != "index"):
            title, text = TOOL_DOCS[key]
            a.title = title
            a.p(text + " " + a.c_method(title, "Pramana method note. Describes how this assistant works; it is not "
                                               "BRSR or report content."))
            if key == "sources":
                a.block("kpis", items=[{"label": "Companies", "value": str(len(kb.companies))},
                                       {"label": "Sectors", "value": str(len(kb.sectors))},
                                       {"label": "Questions", "value": str(len(kb.questions))},
                                       {"label": "Report figures reproduced", "value": "597 / 597"}])
            a.follow("How is the E1 index computed?", "Why are some values excluded?", "Where does your data come from?")
            return
    mid = plan.metric
    if mid and mid in METRICS and mid != "index":
        return _explain_metric(ctx, mid)
    hits = ctx.index.bm25(plan.query, {"report", "report_obs", "report_insight", "pdf"}, limit=3)
    if not hits or hits[0][0] < 4.0:
        a.status = "not_found"
        a.title = "Not covered in the sources"
        a.p("I could not find this in the E1 workbook, the E1 chapter or the report's front matter, so I will not "
            "answer it from general knowledge.")
        a.follow("What does the report say about Scope 3?", "Where does your data come from?")
        return
    a.title = "What the sources say"
    a.p("These are the most relevant passages, quoted exactly. Nothing is added beyond them.")
    items = []
    for s, d in hits:
        page = d.get("pdf_page")
        where = d.get("section") or d.get("ref") or f"Report, PDF page {page}"
        items.append({"text": d["text"], "cite": a.c_report_text(d["text"], page, str(where)), "where": str(where),
                      "pdf_page": page, "score": s})
    a.block("report_quotes", title="Passages", items=items)


def _explain_metric(ctx, mid):
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    m = METRICS[mid]
    a.title = m["label"]
    qids = [q for q in m["qids"] if q in kb.questions]
    if qids:
        q = kb.q(qids[0])
        a.p(f"In the BRSR form this is question **Q{q['qid']}**: “{q['ask']}” "
            f"{a.c_method(f'Q{q['qid']} in the Questions sheet', q.get('brsr_element') or q['ask'])}.")
    rm = M.NUMERIC.get(mid)
    if rm and rm.note:
        a.p(rm.note)
    query = {"scope1": "Scope 1 direct emissions", "scope2": "Scope 2 indirect energy emissions",
             "scope12": "Scope 1 and Scope 2 emissions", "scope3": "Scope 3 value chain emissions",
             "intensity": "emission intensity per rupee of turnover", "scope3_intensity": "Scope 3 intensity",
             "intensity_phys": "physical output intensity", "ghg_assurance": "independent assurance GHG",
             "targets": "targets commitments goals", "projects": "GHG reduction projects",
             "target_performance": "performance against targets"}.get(mid, m["label"])
    hits = ctx.index.bm25(query, {"report", "report_obs", "report_insight"}, limit=2)
    if hits:
        items = [{"text": d["text"], "cite": a.c_report_text(d["text"], d.get("pdf_page"), str(d.get("ref") or d.get("section"))),
                  "where": str(d.get("section") or d.get("ref")), "pdf_page": d.get("pdf_page")} for _, d in hits]
        a.block("report_quotes", title="How the IIMB report frames it", items=items)
    rq = next((q for q in qids if kb.q(q).get("rubric")), None)
    if rq:
        q = kb.q(rq)
        nums = [int(x) for x in re.findall(r"\b(0|25|50|75|100)\b", plan.query)]
        a.p(f"Companies are scored on Q{rq} using the {q.get('rating_rule_source', 'Rating sheet rubric').lower()} shown "
            f"below {a.c_method(f'Q{rq} rubric', 'Rating sheet row ' + str(q.get('rating_row')) + ', columns D to H')}.")
        from .h_company import friendly_rule
        a.block("rubric", qid=rq, question=q["label"], score=nums[0] if nums else None,
                levels=[{"score": l["score"], "text": friendly_rule(l["text"]), "raw": l["text"]} for l in q["rubric"]],
                source=q.get("rating_rule_source"))
    a.note("method", "Definitions here are limited to what the BRSR form, the Rating sheet and the IIMB report state. "
                     "No outside definitions are added.")
    a.follow(f"How many companies report {lc(m['label'])}?" if mid in ("scope3", "ghg_assurance") else
             f"Top 10 companies by {lc(m['label'])}", "What are the key findings of the E1 report?")


KEYS = {"scope3": ["scope 3"], "scope3_reported": ["scope 3"], "scope1": ["scope 1"], "scope2": ["scope 2"],
        "scope12": ["scope 1+2", "emissions"], "intensity": ["intensity"], "targets": ["target"],
        "target_performance": ["performance", "target"], "projects": ["project"], "ghg_assurance": ["assurance"],
        "policy": ["policy", "policies"], "value_chain": ["value chain"], "board_approval": ["board"]}


def report_insights(ctx):
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    rep = kb.report
    a.kicker = "IIMB report · E1 chapter"
    sid = plan.sector
    keys = KEYS.get(plan.metric or "", [])
    if sid:
        sname = kb.sector_by_id[sid]["name"]
        keys = [sname.lower()]
    if keys:
        a.title = f"What the report says about {sname if sid else lc(METRICS[plan.metric]['label'])}"
        pool = []
        for k in rep["key_insights"]:
            if any(x in k["observation"].lower() or x in k["area"].lower() for x in keys):
                pool.append((k["observation"], k["pdf_page"], f"Key insight: {k['area']}"))
        for b in rep.get("insight_blocks", []):
            for it in b["items"]:
                if any(x in it.lower() for x in keys):
                    pool.append((it, b["pdf_page"], f"Insights, {b['section'].split(':')[0]}"))
        for t in rep["tables"]:
            for o in t["observations"]:
                if any(x in o.lower() for x in keys):
                    pool.append((o, t["pdf_page"], f"Key observations, Table {t['id']}"))
        seen, items = set(), []
        for text, page, where in pool:
            if text in seen:
                continue
            seen.add(text)
            items.append({"text": text, "cite": a.c_report_text(text, page, where), "where": where, "pdf_page": page})
        if not items:
            a.status = "partial"
            a.p("The E1 chapter does not discuss this directly.")
        else:
            a.p("The E1 chapter's statements on this are quoted exactly below, each with its page in the published report.")
            a.block("report_quotes", title="From the report", items=items[:8])
        a.follow("What are the key findings of the E1 report?")
        return
    a.title = "Key findings of the E1 chapter"
    a.p(f"The IIMB report closes the E1 chapter with ten signals across policy, targets, emissions and assurance "
        f"{a.c_report_text(rep['key_insights'][0]['observation'], rep['key_insights'][0]['pdf_page'], 'Key Insights table')}.")
    a.block("insights", items=[{"area": k["area"].replace(" — ", ": ").replace("—", ":"), "signal": k["signal"],
                                "observation": k["observation"],
                                "cite": a.c_report_text(k["observation"], k["pdf_page"], f"Key insight: {k['area']}"),
                                "pdf_page": k["pdf_page"]} for k in rep["key_insights"]])
    concl = rep["conclusion"]
    a.block("report_quotes", title="The chapter's conclusion", items=[
        {"text": concl["text"], "cite": a.c_report_text(concl["text"], concl["pdf_page"], "Conclusion"),
         "where": "Conclusion", "pdf_page": concl["pdf_page"]}])
    a.follow("Which sector emits the most?", "How many companies report Scope 3 emissions?",
             "Show me good examples of net zero targets")


def out_of_scope(ctx):
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    a.status = "out_of_scope"
    keys = plan.offtopic or ["GENERAL"]
    o = OFF.get(keys[0], OFF["GENERAL"])
    a.kicker = "Outside this dataset"
    cos = [kb.by_id[c] for c in plan.companies]
    who = f" for {short_name(cos[0]['name'])}" if cos else ""
    if o["chapter"]:
        a.title = f"{o['label']} is not part of E1"
        es = kb.exec_summary.get(o["chapter"])
        toc = a.c_report_text(f"{o['chapter']} {o['label']}: chapter starting on printed page {o['pdf_page'] - 6}", 5,
                              "Table of Contents")
        a.p(f"**Not available here.** {o['label']}{who} is covered by chapter {o['chapter']} of the IIMB report {toc}, "
            f"but this assistant is loaded only with the E1 data on GHG emissions and climate risk, so I cannot give "
            f"company-level figures for it.")
        if es:
            first = es["text"].split("\n")[0].strip("• ").strip()
            a.block("report_quotes", title=f"For context, the IIMB report's executive summary on {o['chapter']} "
                                           f"({es['title']}) states", items=[
                {"text": first, "cite": a.c_report_text(first, es["pdf_page"], f"Executive summary, {o['chapter']}"),
                 "where": f"Executive summary, {o['chapter']}", "pdf_page": es["pdf_page"]}])
    elif o["key"] == "FIN":
        a.title = "Financial data is not in the dataset"
        a.p(f"**Not available.** Revenue, profit, share prices and valuations{who} are not part of the BRSR E1 data. "
            + ("I also do not give investment advice. " if re.search(r"\b(buy|sell|invest)\b", plan.query.lower()) else "")
            + "The closest E1 measure is emission intensity per rupee of turnover, which relates emissions to revenue "
              "without disclosing the revenue itself.")
    elif o["key"] == "FUTURE":
        a.title = "No forecasts"
        a.p("**I only report what companies disclosed** for FY 2024-25 and FY 2023-24. I do not forecast future "
            "emissions. A what-if scenario on the reported figures is the closest thing I can offer.")
    elif o["key"] == "WEB":
        a.title = "No web access, by design"
        a.p("**I have no internet access.** Every answer comes from the E1 workbook and the IIMB report, which keeps "
            "answers verifiable and repeatable.")
    elif o["key"] == "PEOPLE":
        a.title = "Not in the dataset"
        a.p(f"**Not available.** Details such as executives, addresses or contacts{who} are not part of the E1 data.")
    else:
        a.title = "Outside what I can answer"
        a.p("That is outside what I can help with. I answer questions about GHG emissions and climate disclosures of "
            "the companies in the BRSR E1 dataset, and I only use those sources.")
    if cos:
        c = cos[0]
        a.company_ref(c)
        a.p(f"For {short_name(c['name'])}, I can show Scope 1, Scope 2 and Scope 3 emissions, intensity, assurance, "
            f"targets and GHG reduction projects.")
        a.follow(f"Show {short_name(c['name'])}'s E1 profile", f"What are {short_name(c['name'])}'s Scope 1 emissions?",
                 f"What if {short_name(c['name'])} cuts Scope 1 by 10%?" if o["key"] == "FUTURE" else
                 f"How does {short_name(c['name'])} compare with its peers?")
    else:
        a.follow("What can you do?", "What are the key findings of the E1 report?", "Top 10 emitters")


def not_found(ctx):
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    a.status = "not_found"
    names = [n for n in plan.absent] + [u for u in plan.unknown_names]
    label = names[0] if names else "that company"
    a.kicker = "Company not found"
    a.title = f"{label if plan.absent else label.upper() if len(label) <= 5 else label.title()} is not in the dataset"
    a.p(f"**{label if plan.absent else chr(8216) + label + chr(8217)} is not among the {len(kb.companies)} companies** "
        f"with FY 2024-25 BRSR filings in the E1 dataset "
        f"{a.c_report_text('XBRL-formatted BRSR filings submitted by 982 companies to the NSE for FY 2024-25, available as of 9 December 2025, were downloaded from the NSE public repository', 26, 'Chapter 2, Data Collection and Extraction')}. "
        f"I will not substitute a different company or estimate its figures.")
    q = names[0].lower() if names else ""
    sugg = []
    if q:
        for alias, score, _ in process.extract(q, sorted(kb.aliases), scorer=fuzz.WRatio, limit=12, score_cutoff=70):
            for cid in kb.aliases[alias]:
                if cid not in sugg:
                    sugg.append(cid)
        sugg = sugg[:4]
    if sugg:
        a.p(f"Closest names in the dataset: {join([kb.by_id[c]['name'] for c in sugg], 'or')}.")
        a.follow(*[f"Show {short_name(kb.by_id[c]['name'])}'s E1 profile" for c in sugg[:3]])
    if plan.sector:
        a.follow(f"Give me an overview of the {kb.sector_by_id[plan.sector]['name']} sector")
    a.follow("List all companies in the Oil Gas & Consumable Fuels sector" if "oil" in q or "ongc" in q else "What can you do?")


def clarify(ctx):
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    a.status = "clarify"
    a.kicker = "Which one?"
    group = plan.ambiguous[0]
    ids, text = group["ids"], group["text"]
    a.title = f"“{text}” matches {len(ids)} companies"
    a.p(f"Several companies in the dataset match “{text}”. Pick one and I will answer for it.")
    opts = []
    for cid in ids[:8]:
        c = kb.by_id[cid]
        rx = re.compile(re.escape(text), re.I)
        q2 = rx.sub(c["name"], plan.query, count=1) if rx.search(plan.query) else f"{plan.query} ({c['name']})"
        opts.append({"id": cid, "name": c["name"], "sector": kb.sector_of(c)["name"], "query": q2})
    a.block("choices", items=opts)
    for o in opts[:4]:
        a.follow(o["query"])


PREF_LABEL = {"scope12": "Scope 1+2 emissions", "scope1": "Scope 1 emissions", "scope2": "Scope 2 emissions",
              "scope3": "Scope 3 emissions", "intensity": "Scope 1+2 intensity per crore of turnover"}


def learned(ctx):
    """Confirm what the conversation just learned (in-context learning)."""
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    up = plan.learned
    a.kicker = "Learned in this conversation"
    src = a.c_method("Conversation preference", "Set by you in this conversation. It lives only in this conversation's "
                                                "context, applies to later questions, and can be cleared at any time.")
    if up.get("reset"):
        a.title = "Preferences cleared"
        a.p(f"Done. I have forgotten the peer group, definitions and defaults learned in this conversation {src}.")
        a.follow("How does Tata Steel compare with its peers?", "Top 10 emitters")
        return
    a.title = "Noted for this conversation"
    lines = []
    if up.get("peers"):
        names = [short_name(kb.by_id[x]["name"]) for x in up["peers"]]
        lens = plan.prefs.get("lens")
        a.p(f"Your peer group is now **{join(names)}** {src}. Peer comparisons will use this group instead of the whole "
            f"sector, and I will say so each time.")
        lines.append({"key": "peers", "label": "Peer group", "value": join(names)})
        for x in up["peers"]:
            a.company_ref(kb.by_id[x])
    if up.get("emissions"):
        a.p(f"When you ask about \u201cemissions\u201d without saying which scope, I will use **{PREF_LABEL[up['emissions']]}** "
            f"{src}. Naming a scope explicitly always overrides this.")
        lines.append({"key": "emissions", "label": "\u201cEmissions\u201d means", "value": PREF_LABEL[up["emissions"]]})
    if up.get("n"):
        a.p(f"Rankings will show the top **{up['n']}** unless you ask for a different number {src}.")
        lines.append({"key": "n", "label": "Ranking size", "value": f"Top {up['n']}"})
    a.block("learned", items=lines)
    a.note("method", "Preferences are part of the conversation context sent with each question, so answers stay "
                     "deterministic: the same question in the same conversation always gets the same answer.")
    first = kb.by_id[up["peers"][0]]["name"] if up.get("peers") else None
    a.follow("How do we compare with our peers?" if ctx.plan.prefs.get("peers") else None,
             f"How does {short_name(first)} compare with its peers?" if first else None,
             "What are the emissions of NTPC?" if up.get("emissions") else None,
             "Top emitters in cement" if up.get("n") else None,
             "Forget my preferences")
