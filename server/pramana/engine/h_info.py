"""Greeting, definitions, how-it-works, things that are not available, not-found and clarification."""
from __future__ import annotations

import re

from rapidfuzz import fuzz

from ..nlu.lexicon import OFFTOPIC
from .fmt import join, short_name

OFF = {o["key"]: o for o in OFFTOPIC}
COVERS = ("Scope 1, Scope 2 and Scope 3 emissions, emission intensity, targets, projects to reduce GHG emissions and "
          "independent assurance")

# Plain-language definitions of the terms people ask about.
GLOSSARY: dict[str, tuple[str, str]] = {
    "scope1": ("Scope 1 emissions",
               "**Scope 1** emissions are the direct greenhouse gas emissions from sources a company owns or controls, "
               "such as fuel burned in its boilers, furnaces, generators and vehicles."),
    "scope2": ("Scope 2 emissions",
               "**Scope 2** emissions are the indirect emissions from the electricity, heat, steam or cooling a company "
               "buys and uses."),
    "scope3": ("Scope 3 emissions",
               "**Scope 3** emissions are all other indirect emissions in a company's value chain, such as purchased "
               "goods, transport, business travel and the use of its products."),
    "intensity": ("Emission intensity",
                  "**Emission intensity** is Scope 1 and Scope 2 emissions divided by turnover. Companies disclose it per "
                  "rupee of turnover; it is shown here per ₹ crore so the figures are easier to read."),
    "scope3_intensity": ("Scope 3 intensity",
                         "**Scope 3 intensity** is Scope 3 emissions divided by turnover, shown here per ₹ crore."),
    "intensity_phys": ("Intensity per unit of physical output",
                       "**Physical output intensity** is Scope 1 and Scope 2 emissions per unit of what a company "
                       "produces, for example per tonne of product. Each company chooses its own unit, so the levels "
                       "cannot be compared across companies."),
    "intensity_ppp": ("PPP-adjusted intensity",
                      "**PPP-adjusted intensity** is emission intensity per rupee of turnover, adjusted for purchasing "
                      "power parity so that it can be compared internationally."),
    "ghg_assurance": ("Independent assurance",
                      "**Independent assurance** means an external agency has assessed or verified the GHG emissions a "
                      "company reported."),
    "scope3_assurance": ("Independent assurance of Scope 3",
                         "**Independent assurance of Scope 3** means an external agency has assessed or verified the "
                         "Scope 3 emissions a company reported."),
    "scope3_reported": ("Scope 3 reporting", "Scope 3 reporting means a company discloses the indirect emissions in "
                                             "its value chain. Under BRSR this is a leadership indicator, so it is voluntary."),
    "targets": ("Commitments, goals and targets",
                "In BRSR, companies describe the specific **commitments, goals and targets** they have set, with timelines, "
                "for example a net zero year or a percentage cut in emissions."),
    "target_performance": ("Performance against targets",
                           "In BRSR, companies describe how they have **performed against** the commitments, goals and "
                           "targets they set."),
    "projects": ("Projects to reduce GHG emissions",
                 "In BRSR, companies state whether they have **projects to reduce GHG emissions** and describe them, "
                 "for example renewable energy, energy efficiency or fuel switching."),
    "certifications": ("Codes, certifications and standards",
                       "In BRSR, companies list the national and international **codes, certifications, labels and "
                       "standards** they have adopted, such as ISO 14001."),
    "policy": ("Environment policy", "In BRSR, companies state whether they have a **policy covering Principle 6**, "
                                     "which is about protecting and restoring the environment."),
}
GLOSSARY["scope12"] = ("Scope 1 and Scope 2 emissions", GLOSSARY["scope1"][1] + "\n" + GLOSSARY["scope2"][1])

TERMS = [
    (re.compile(r"\bbrsr\b|business responsibility"), "BRSR",
     "**BRSR** (Business Responsibility and Sustainability Report) is the sustainability disclosure that SEBI requires "
     "from the largest listed companies in India. It is filed every year and covers environmental, social and "
     "governance topics in a standard format."),
    (re.compile(r"\btco2e?\b|\bco2e\b|carbon dioxide equivalent|\bunit\b"), "tCO₂e",
     "**tCO₂e** means tonnes of carbon dioxide equivalent. It expresses all greenhouse gases as the amount of carbon "
     "dioxide that would have the same warming effect."),
    (re.compile(r"\bnet\s*-?\s*zero\b|netzero|carbon neutral"), "Net zero",
     "**Net zero** means cutting greenhouse gas emissions as far as possible and balancing whatever remains with removals."),
    (re.compile(r"\bsbti?\b|science based"), "SBTi",
     "**SBTi** (the Science Based Targets initiative) checks whether a company's emission reduction targets are in line "
     "with climate science."),
    (re.compile(r"\bghg\b|greenhouse gas"), "Greenhouse gases",
     "**Greenhouse gases (GHG)** are gases that trap heat in the atmosphere, such as carbon dioxide, methane and "
     "nitrous oxide. Company emissions are reported in tonnes of carbon dioxide equivalent (tCO₂e)."),
]

ABOUT = [
    (re.compile(r"hallucinat|make things up|made up|trust|reliable|accurate|accuracy|guardrail|how do you (work|answer)|grounded|sure"),
     "How answers are produced",
     "Every answer is computed directly from what companies disclosed in their BRSR filings. I do not use the internet "
     "and I do not write figures from memory, so each number links to the disclosure it came from. If something is "
     "not available, I say so."),
    (re.compile(r"determinis|same answer|consistent|change (your|the) answer|different answers"),
     "Consistent answers",
     "The same question always gets the same answer, because every figure is looked up and calculated rather than "
     "generated afresh each time."),
    (re.compile(r"data (come|source)|where .*data|source(s)? of|which data|what data|methodolog"),
     "Where the figures come from",
     "The figures are what each company disclosed in its BRSR filing for FY 2024-25, with FY 2023-24 shown for "
     "comparison. Totals and medians are calculated from those disclosures."),
    (re.compile(r"\b(year|period|fy)\b.*\b(cover|covered|available|does)\b|which (year|fy)"),
     "Years covered",
     "I cover FY 2024-25, with FY 2023-24 figures for comparison. Other years are not available."),
    (re.compile(r"different unit|flag|outlier|unit|exclu|left out|missing from"), "Values in a different unit",
     "A few companies appear to have disclosed emissions in a different unit, for example thousand tonnes. Those "
     "figures are shown exactly as disclosed, with a note, and are left out of comparisons and totals."),
]


def greeting(ctx):
    a = ctx.a
    a.kicker = "Pramana"
    a.title = "How can I help?"
    a.p(f"I answer questions about the GHG emissions and climate disclosures of **{len(ctx.kb.companies)} listed "
        f"companies**, based on their BRSR filings for FY 2024-25.")
    a.block("capabilities", items=[
        {"title": "A company's figures", "text": "Scope 1, 2 and 3 emissions, intensity, targets and projects.",
         "example": "What are NTPC's GHG emissions?"},
        {"title": "Peers", "text": "See who the peers are and how a company compares.",
         "example": "How does ACC compare with its peers?"},
        {"title": "Good examples", "text": "Detailed disclosures from other companies, in their own words.",
         "example": "Examples of GHG reduction projects from cement companies"},
        {"title": "Sectors", "text": "Totals and the largest emitters in any sector.",
         "example": "Give me an overview of the power sector"},
        {"title": "Infographics", "text": "A shareable one-page visual for a company or sector.",
         "example": "Make an infographic for UltraTech"},
        {"title": "What-if", "text": "See the effect of a cut in emissions.",
         "example": "What if NTPC cuts Scope 1 by 10%?"},
    ])
    a.follow("What are NTPC's GHG emissions?", "Top 10 emitters", "Which sector emits the most?")


def define(ctx):
    """A short definition. Nothing else is added."""
    a, plan = ctx.a, ctx.plan
    low = plan.query.lower()
    a.kicker = "Definition"
    mids = [m for m in ([plan.metric] + list(plan.metrics)) if m in GLOSSARY]
    mids = list(dict.fromkeys(mids))
    # "scope 1 and scope 2" arrives as one combined metric; show the two definitions separately
    if mids:
        title, text = GLOSSARY[mids[0]]
        a.title = title
        for para in text.split("\n"):
            a.p(para)
        for extra in mids[1:2]:
            if extra != mids[0] and not (mids[0] == "scope12" and extra in ("scope1", "scope2")):
                a.p(GLOSSARY[extra][1])
        key = mids[0]
        ask = {"scope12": "What are NTPC's Scope 1 and Scope 2 emissions?", "scope1": "What are NTPC's Scope 1 emissions?",
               "scope2": "What are NTPC's Scope 2 emissions?", "scope3": "What are Infosys's Scope 3 emissions?",
               "intensity": "What is UltraTech's emission intensity?", "targets": "What are Infosys's targets?",
               "projects": "Show UltraTech's projects to reduce GHG emissions",
               "ghg_assurance": "How many companies have independent assurance of GHG emissions?"}.get(key)
        a.follow(ask, "What is the difference between Scope 1, Scope 2 and Scope 3?" if key in ("scope1", "scope2", "scope3", "scope12") and "difference" not in low else None,
                 "Top 10 emitters")
        return True
    for rx, title, text in TERMS:
        if rx.search(low):
            a.title = title
            a.p(text)
            a.follow("What are NTPC's GHG emissions?", "Top 10 emitters")
            return True
    return False


def explain(ctx):
    a, plan = ctx.a, ctx.plan
    low = plan.query.lower()
    if re.search(r"difference between|scope 1,? (scope )?2 and (scope )?3|all three scopes", low):
        a.kicker = "Definition"
        a.title = "Scope 1, Scope 2 and Scope 3"
        for k in ("scope1", "scope2", "scope3"):
            a.p(GLOSSARY[k][1])
        a.follow("What are NTPC's GHG emissions?", "How many companies report Scope 3 emissions?")
        return
    for rx, title, text in ABOUT:
        if rx.search(low) and not plan.metric:
            a.kicker = "About"
            a.title = title
            a.p(text)
            a.follow("What can you do?", "What are NTPC's GHG emissions?")
            return
    if define(ctx):
        return
    for rx, title, text in ABOUT:
        if rx.search(low):
            a.kicker = "About"
            a.title = title
            a.p(text)
            a.follow("What can you do?", "What are NTPC's GHG emissions?")
            return
    a.status = "not_found"
    a.kicker = "Not available"
    a.title = "I do not have that"
    a.p(f"I could not find that in the disclosures I cover. I can help with {COVERS}.")
    a.follow("What can you do?", "What are NTPC's GHG emissions?", "Top 10 emitters")


def no_scores(ctx):
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    a.status = "out_of_scope"
    a.kicker = "Not available"
    a.title = "Scores and ratings are not available"
    cos = [kb.by_id[c] for c in plan.companies]
    who = f" for {short_name(cos[0]['name'])}" if cos else ""
    a.p(f"I do not provide scores, ratings or rankings of overall performance{who}. I can show what "
        f"{'the company' if cos else 'a company'} disclosed: {COVERS}.")
    if cos:
        s = short_name(cos[0]["name"])
        a.company_ref(cos[0])
        a.follow(f"Tell me about {s}", f"What are {s}'s GHG emissions?", f"How does {s} compare with its peers?")
    else:
        a.follow("What are NTPC's GHG emissions?", "Top 10 emitters", "Companies with the lowest emission intensity")


def out_of_scope(ctx):
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    a.status = "out_of_scope"
    keys = plan.offtopic or ["GENERAL"]
    o = OFF.get(keys[0], OFF["GENERAL"])
    a.kicker = "Not available"
    cos = [kb.by_id[c] for c in plan.companies]
    who = f" for {short_name(cos[0]['name'])}" if cos else ""
    low = plan.query.lower()
    if o["chapter"]:
        topic = o["label"]
        a.title = f"{topic} is not available yet"
        a.p(f"**That is not available yet.** I do not have {topic[0].lower() + topic[1:]} information{who}. "
            f"For now I cover {COVERS}.")
    elif o["key"] == "FIN":
        a.title = "Financial information is not available"
        a.p(f"**That is not available.** I do not have revenue, profit, share price or valuation figures{who}. "
            + ("I also do not give investment advice. " if re.search(r"\b(buy|sell|invest)\b", low) else "")
            + "The closest measure I have is emission intensity, which relates emissions to turnover.")
    elif o["key"] == "FUTURE":
        a.title = "Forecasts are not available"
        a.p("**I only share what companies have disclosed** for FY 2024-25 and FY 2023-24, so I cannot forecast future "
            "emissions. A what-if on the disclosed figures is the closest I can offer.")
    elif o["key"] == "WEB":
        a.title = "I do not use the internet"
        a.p("**I do not search the internet.** Every answer is based on what companies disclosed in their BRSR filings.")
    elif o["key"] == "PEOPLE":
        a.title = "That is not available"
        a.p(f"**That is not available.** I do not have details such as executives, addresses or contacts{who}.")
    else:
        a.title = "That is outside what I can help with"
        a.p(f"That is outside what I can help with. I answer questions about the GHG emissions and climate disclosures "
            f"of listed companies: {COVERS}.")
    if cos:
        c = cos[0]
        s = short_name(c["name"])
        a.company_ref(c)
        a.follow(f"What are {s}'s GHG emissions?", f"What is {s}'s emission intensity?" if o["key"] == "FIN" else
                 f"What if {s} cuts Scope 1 by 10%?" if o["key"] == "FUTURE" else f"What are {s}'s targets?",
                 f"Tell me about {s}")
    else:
        a.follow("What can you do?", "What are NTPC's GHG emissions?", "Top 10 emitters")


def not_found(ctx):
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    a.status = "not_found"
    names = [n for n in plan.absent] + [u for u in plan.unknown_names]
    label = names[0] if names else "that company"
    shown = label if plan.absent else (label.upper() if len(label) <= 5 else label.title())
    a.kicker = "Company not found"
    a.title = f"{shown} is not covered"
    a.p(f"**{shown} is not among the {len(kb.companies)} companies I cover**, so I cannot share its figures. I will not "
        f"substitute another company or estimate.")
    # suggest companies that share a distinctive word with the name asked for
    from ..nlu.lexicon import STOP
    words = [w for w in re.findall(r"[a-z0-9]+", (names[0] if names else "").lower()) if w not in STOP and len(w) >= 3]
    sugg = []
    if words:
        pool = [c for c in kb.companies if any(w in re.findall(r"[a-z0-9]+", c["name"].lower()) for w in words)]
        pool.sort(key=lambda c: (-fuzz.WRatio(" ".join(words), c["name"].lower()), c["name"].lower()))
        sugg = [c["id"] for c in pool[:3]]
    if sugg:
        a.p(f"Companies with a similar name that are covered: {join([kb.by_id[c]['name'] for c in sugg])}.")
        a.follow(*[f"Tell me about {short_name(kb.by_id[c]['name'])}" for c in sugg[:3]])
    if plan.sector:
        a.follow(f"List all {kb.sector_by_id[plan.sector]['name']} companies")
    a.follow("What can you do?")


def clarify(ctx):
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    a.status = "clarify"
    a.kicker = "One detail needed"
    group = plan.ambiguous[0]
    ids, text = group["ids"], group["text"]
    a.title = f"Which “{text}” do you mean?"
    a.p(f"{len(ids)} companies match “{text}”. Choose one and I will answer for it.")
    opts = []
    base = plan.resolved_query or plan.query
    for cid in ids[:8]:
        c = kb.by_id[cid]
        rx = re.compile(re.escape(text), re.I)
        q2 = rx.sub(c["name"], base, count=1) if rx.search(base) else f"{base} ({c['name']})"
        opts.append({"id": cid, "name": c["name"], "sector": kb.sector_of(c)["name"], "query": q2})
    a.block("choices", items=opts)


PREF_LABEL = {"scope12": "Scope 1 and Scope 2 emissions", "scope1": "Scope 1 emissions", "scope2": "Scope 2 emissions",
              "scope3": "Scope 3 emissions", "intensity": "emission intensity"}


def learned(ctx):
    """Confirm what the conversation was just told to remember."""
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    up = plan.learned
    a.kicker = "Noted"
    if up.get("reset"):
        a.title = "Preferences cleared"
        a.p("Done. I have cleared the peer group, definitions and defaults set in this conversation.")
        a.follow("How does Tata Power compare with its peers?", "Top 10 emitters")
        return
    a.title = "Noted for this conversation"
    lines = []
    if up.get("peers"):
        names = [short_name(kb.by_id[x]["name"]) for x in up["peers"]]
        a.p(f"Your peer group is now **{join(names)}**. Peer comparisons in this conversation will use these companies.")
        lines.append({"key": "peers", "label": "Peer group", "value": join(names)})
        for x in up["peers"]:
            a.company_ref(kb.by_id[x])
    if up.get("emissions"):
        a.p(f"When you ask about “emissions” without naming a scope, I will show **{PREF_LABEL[up['emissions']]}**.")
        lines.append({"key": "emissions", "label": "“Emissions” means", "value": PREF_LABEL[up["emissions"]]})
    if up.get("n"):
        a.p(f"Lists of top companies will show **{up['n']}** unless you ask for a different number.")
        lines.append({"key": "n", "label": "List size", "value": f"Top {up['n']}"})
    a.block("learned", items=lines)
    first = kb.by_id[up["peers"][0]]["name"] if up.get("peers") else None
    a.follow("How do we compare with our peers?" if plan.prefs.get("peers") and plan.lens else None,
             f"How does {short_name(first)} compare with its peers?" if first else None,
             "What are NTPC's emissions?" if up.get("emissions") else None,
             "Top emitters in cement" if up.get("n") else None,
             "Forget my preferences")
