"""Greeting, definitions, how-it-works, things that are not available, not-found and clarification."""
from __future__ import annotations

import re

from rapidfuzz import fuzz

from ..nlu.lexicon import OFFTOPIC
from .common import ASK, ask, example_company
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

# What a term covers, why it matters and an everyday example: shown as short points under the definition.
EXPLAIN: dict[str, dict[str, str]] = {
    "scope1": {
        "covers": "Fuel burned on site and in the company's own vehicles, emissions from industrial processes such as "
                  "making cement or steel, and leaks of refrigerants and other gases.",
        "why": "It is the part of the footprint a company controls most directly, so changes of fuel or process show up here first.",
        "example": "A cement plant's kiln, a power station's boilers or a logistics company's own trucks."},
    "scope2": {
        "covers": "Electricity bought from the grid or another supplier, and any purchased heat, steam or cooling.",
        "why": "It falls when a company uses less electricity or buys more of it from renewable sources.",
        "example": "The power used by an IT campus, a bank's branches or the motors in a factory."},
    "scope3": {
        "covers": "Emissions outside the company's own operations: purchased goods and services, transport and "
                  "distribution, business travel, employee commuting and the use of the products it sells.",
        "why": "For many companies it is the largest part of the footprint and the hardest to measure. Under BRSR it is a "
               "leadership indicator, so reporting it is voluntary.",
        "example": "The fuel burned by the customers of an oil company, or the emissions of a retailer's suppliers."},
    "intensity": {
        "covers": "Scope 1 and Scope 2 emissions divided by turnover. BRSR also asks for intensity adjusted for purchasing "
                  "power parity and per unit of physical output.",
        "why": "It lets companies of different sizes be compared, and shows whether emissions are growing faster or slower "
               "than the business.",
        "example": "Two companies with the same emissions have very different intensities if one has twice the turnover."},
    "ghg_assurance": {
        "covers": "An independent agency checks the emissions data and how it was compiled, and gives a limited or "
                  "reasonable assurance statement.",
        "why": "It gives readers more confidence in the figures. BRSR asks whether such an assessment was carried out and "
               "by which agency."},
    "targets": {
        "covers": "A target year, the size of the reduction, the baseline it is measured from and the scopes it applies to.",
        "why": "A target with a year and a number can be tracked from one filing to the next; a general statement of intent cannot.",
        "example": "Net zero for Scope 1 and Scope 2 by a stated year, or a stated percentage cut in emission intensity from a baseline year."},
    "target_performance": {
        "covers": "What was achieved against each target in the year, and the reasons where a target was missed.",
        "why": "It shows whether targets are being delivered, not only set."},
    "projects": {
        "covers": "Measures such as renewable energy, energy efficiency, fuel switching, electrification and waste heat recovery.",
        "why": "They show what a company is doing about its emissions, beyond what it has promised."},
    "scope3_reported": {
        "covers": "Whether the company discloses a Scope 3 figure at all.",
        "why": "Reporting it is voluntary under BRSR, so the share of companies that do is a measure of how far disclosure has come."},
    "certifications": {
        "covers": "Standards such as ISO 14001 for environmental management and ISO 50001 for energy management, and frameworks "
                  "such as GRI or CDP.",
        "why": "They indicate that a recognised management system or reporting framework is in place."},
    "policy": {
        "covers": "A written policy on protecting the environment, whether the Board has approved it and whether it extends to "
                  "value chain partners.",
        "why": "It is the starting point for governance: targets and projects follow from it."},
}
SHORT = {"scope1": "what the company burns itself", "scope2": "the electricity and heat it buys",
         "scope3": "everything else in its value chain"}


def _in_the_data(ctx, key) -> str | None:
    """One computed line that ties the definition to the companies covered."""
    from . import metrics as M
    from .common import eligible, yes_count
    from .fmt import CO2, compact, num, share
    from ..analytics import median
    a, kb = ctx.a, ctx.kb
    N = len(kb.companies)
    if key in ("scope1", "scope2", "scope3"):
        from .h_sector import _total
        m = M.NUMERIC[key]
        n = sum(1 for c in kb.companies if m.value(c) is not None)
        cite = a.c_calc(f"{m.label} across all companies", f"{n} of {N} companies disclosed a figure; the sum is {num(_total(kb.companies, key))} {CO2}")
        return f"{n} of the {N} companies covered disclosed it for FY 2024-25, a total of {compact(_total(kb.companies, key))} {CO2} {cite}."
    if key == "intensity":
        vals = [v for _, v in eligible(M.NUMERIC["intensity"], kb.companies)]
        cite = a.c_calc("Emission intensity across all companies", f"Median of the comparable figures disclosed by {len(vals)} companies")
        return f"{len(vals)} of the {N} companies covered disclosed a comparable figure; the median is {num(median(vals), 1)} {CO2} per ₹ crore {cite}."
    qid = {"ghg_assurance": "1340", "scope3_reported": "1387", "projects": "1341", "policy": "232"}.get(key)
    if qid:
        y, n = yes_count(kb.companies, qid)
        cite = a.c_calc("Companies answering Yes", f"{y} of {n} companies")
        return f"{y} of the {n} companies covered ({share(y, n)}) answered Yes for FY 2024-25 {cite}."
    tq = {"targets": "286", "target_performance": "295", "certifications": "277"}.get(key)
    if tq:
        y = sum(1 for c in kb.companies if c["values"].get(tq))
        cite = a.c_calc("Companies disclosing", f"{y} of {N} companies provided this disclosure")
        return f"{y} of the {N} companies covered ({share(y, N)}) provided this disclosure for FY 2024-25 {cite}."
    return None


def _for_company(ctx, key):
    """With a company set or being discussed, one closing line with its own figure, and the question that gives the rest."""
    from . import metrics as M
    from .common import fmt_value, value_cite
    from .fmt import CO2, num
    a, kb, plan = ctx.a, ctx.kb, ctx.plan
    cid = plan.lens or next(iter(plan.about), None)
    if not cid or cid not in kb.by_id:
        return None
    c = kb.by_id[cid]
    short = short_name(c["name"])
    mids = ["scope1", "scope2"] if key == "scope12" else [key]
    if any(m not in M.NUMERIC for m in mids):
        return None
    bits = []
    for m in mids:
        metric = M.NUMERIC[m]
        v = metric.value(c)
        ok = v is not None and (metric.kind != "intensity" or metric.level_ok(c))
        bits.append(f"{metric.label[0].lower() + metric.label[1:] if m not in ('scope1', 'scope2', 'scope3') else metric.label} of "
                    f"{fmt_value(metric, v)} {value_cite(a, c, metric)}" if ok else
                    f"no comparable figure for {metric.label} {a.c_filing(c, metric.cy_q)}")
    ask = f"What are {short}'s GHG emissions?" if key in ("scope12", "scope1", "scope2") else f"What is {short}'s {GLOSSARY[key][0].lower() if key not in ('scope3',) else 'Scope 3 emissions'}?"
    if key == "scope3":
        ask = f"What are {short}'s Scope 3 emissions?"
    return f"**For {short}:** it reported {join(bits)} for FY 2024-25.", ask


def _points(ctx, key, label: str | None = None):
    e = EXPLAIN.get(key)
    if not e:
        return
    items = [f"**What it covers:** {e['covers']}", f"**Why it matters:** {e['why']}"]
    if e.get("example"):
        items.append(f"**Example:** {e['example']}")
    data = _in_the_data(ctx, key)
    if data:
        items.append(f"**In the data:** {data}")
    ctx.a.block("points", items=items, **({"title": label} if label else {}))


TERMS = [
    (re.compile(r"\bbrsr\b|business responsibility"), "BRSR",
     "**BRSR** (Business Responsibility and Sustainability Report) is the sustainability disclosure that SEBI requires "
     "from the largest listed companies in India. It is filed every year and covers environmental, social and "
     "governance topics in a standard format."),
    (re.compile(r"\bsebi\b|securities and exchange board"), "SEBI",
     "**SEBI** (the Securities and Exchange Board of India) regulates India's securities market. It requires the largest "
     "listed companies to file a Business Responsibility and Sustainability Report (BRSR) every year."),
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

TERM_POINTS = {
    "Net zero": ("A net zero year is the most common headline climate commitment, and it only means something when the "
                 "scopes covered and the interim targets are stated.", "net zero"),
    "SBTi": ("A target validated by SBTi has been checked against what climate science says is needed, which makes it "
             "comparable across companies.", "sbti"),
    "BRSR": ("It puts the sustainability disclosures of listed companies in one standard format, so they can be compared "
             "company by company and year by year.", None),
    "Greenhouse gases": ("They are grouped into Scope 1, Scope 2 and Scope 3 according to where they arise, which is how "
                         "companies report them.", None),
    "tCO₂e": ("One common unit lets emissions of different gases, and of different companies, be added up and compared.", None),
}

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
    (re.compile(r"\b(years?|period|fy)\b.*\b(cover\w*|available|does|have|data)\b|(which|what) (years?|fy|period)|"
                r"\b20\d\d\b.{0,12}\bdata\b|\b(have|cover)\b.{0,14}\b20\d\d\b"),
     "Years covered",
     "I cover FY 2024-25, with FY 2023-24 figures for comparison. Other years are not available."),
    (re.compile(r"different unit|flag|outlier|unit|exclu|left out|missing from"), "Values in a different unit",
     "A few companies appear to have disclosed emissions in a different unit, for example thousand tonnes. Those "
     "figures are shown exactly as disclosed, with a note, and are left out of comparisons and totals."),
]


def thanks(ctx):
    a = ctx.a
    a.kicker = "Pramana"
    a.title = "Glad to help"
    a.p("Glad to help. Ask me anything else about emissions and climate disclosures.")
    a.follow(ask(ctx, "peers"), ask(ctx, "targets"), ask(ctx, "infographic") if ctx.plan.lens else "Which sector emits the most?")


def about(ctx):
    a = ctx.a
    a.kicker = "About"
    a.title = "What Pramana is"
    a.p(f"I am **Pramana**, an assistant for the GHG emissions and climate disclosures of the {len(ctx.kb.companies)} listed "
        f"companies I cover. The name is Sanskrit for proof: every figure I give comes from what a company disclosed in "
        f"its BRSR filing, and each answer lists its sources.")
    a.p("You can ask about one company, compare companies, see how a company stands against its peers, look at a whole "
        "sector, or ask for examples of what other companies are doing.")
    a.follow("What can you do?", ask(ctx, "emissions"), ask(ctx, "peers"))


def export_help(ctx):
    a = ctx.a
    a.kicker = "How to"
    a.title = "Downloading an answer"
    a.p("Every answer can be downloaded. Use **Excel** or **PDF** under an answer to save the whole answer, or the "
        "**Excel** button on a chart or table to save just that part. Infographics have a **Download image** button.")
    a.p("Ask a question first, for example the ones below, and the buttons appear with the answer.")
    a.follow(ask(ctx, "emissions"), "Top 10 emitters", ask(ctx, "infographic"))


def peer_def(ctx):
    a = ctx.a
    a.kicker = "About"
    a.title = "How peers are chosen"
    a.p("A company's **peers** are the other companies in the same sector among the companies covered. Sectors follow the "
        "sector classification used here.")
    a.p("You can also name your own peer group, for example “my peers are Blue Dart and Delhivery”, and comparisons in "
        "that conversation will use those companies.")
    a.follow(ask(ctx, "peer_list"), ask(ctx, "peers"), "How many sectors are there?")


def greeting(ctx):
    a = ctx.a
    a.kicker = "Pramana"
    a.title = "How can I help?"
    a.p(f"I answer questions about the GHG emissions and climate disclosures of **{len(ctx.kb.companies)} listed "
        f"companies**, based on their BRSR filings for FY 2024-25.")
    c, own = example_company(ctx)
    sname = ctx.kb.sector_of(c)["name"] if own else None
    a.block("capabilities", items=[
        {"title": "A company's figures", "text": "Scope 1, 2 and 3 emissions, intensity, targets and projects.",
         "example": ask(ctx, "emissions")},
        {"title": "Peers", "text": "See who the peers are and how a company compares.",
         "example": ask(ctx, "peers") if own else "How does ACC compare with its peers?"},
        {"title": "Good practice", "text": "What other companies do, in short points with their own words as examples.",
         "example": f"How can we reduce emissions?" if own else "Best practices for reducing emissions in cement"},
        {"title": "Sectors", "text": "Totals, trends and the largest emitters in any sector.",
         "example": f"Give me an overview of the {sname} sector" if own else "Give me an overview of the power sector"},
        {"title": "Infographics", "text": "A shareable one-page visual for a company or sector.",
         "example": ask(ctx, "infographic") if own else "Make an infographic for UltraTech"},
        {"title": "What-if", "text": "See the effect of a cut in emissions.",
         "example": ask(ctx, "whatif")},
    ])
    a.follow(ask(ctx, "emissions"), "Top 10 emitters", "Which sector emits the most?")


def define(ctx):
    """A short definition. Nothing else is added."""
    a, plan = ctx.a, ctx.plan
    low = plan.query.lower()
    a.kicker = "Definition"
    mids = [m for m in ([plan.metric] + list(plan.metrics)) if m in GLOSSARY]
    mids = list(dict.fromkeys(mids))
    # a named term (net zero, SBTi, GHG, BRSR) wins over the broad topic it belongs to
    if not re.search(r"\bscope\s*[123]\b|intensity", low) and (not mids or mids[0] in ("targets", "scope12", "certifications")):
        for rx, title, text in TERMS:
            if rx.search(low):
                a.title = title
                a.p(text)
                extra = TERM_POINTS.get(title)
                if extra:
                    items = [f"**Why it matters:** {extra[0]}"]
                    if extra[1]:
                        from .h_practice import SEARCH_QIDS
                        n = len(ctx.index.search([extra[1]], [], SEARCH_QIDS))
                        N = len(ctx.kb.companies)
                        cite = a.c_note("How mentions are counted", "An exact, case-insensitive match in what companies disclosed on "
                                        "targets, progress, projects and certifications. A mention is not a verified commitment.")
                        items.append(f"**In the data:** {n} of the {N} companies covered mention it in their disclosures {cite}.")
                    a.block("points", items=items)
                a.follow({"Net zero": "Which companies mention net zero?", "SBTi": "Which companies mention SBTi?"}.get(title),
                         ask(ctx, "emissions"), "Top 10 emitters")
                return True
    # "scope 1 and scope 2" arrives as one combined metric; show the two definitions separately
    if mids:
        title, text = GLOSSARY[mids[0]]
        a.title = title
        for para in text.split("\n"):
            a.p(para)
        second = None
        for extra in mids[1:2]:
            if extra != mids[0] and not (mids[0] == "scope12" and extra in ("scope1", "scope2")):
                a.p(GLOSSARY[extra][1])
                second = extra
        key = mids[0]
        if key == "scope12":
            _points(ctx, "scope1", "Scope 1")
            _points(ctx, "scope2", "Scope 2")
        else:
            _points(ctx, key)
            if second:
                _points(ctx, second, GLOSSARY[second][0])
        mine = _for_company(ctx, key)
        if mine:
            a.block("points", items=[mine[0]])
            a.follow(mine[1])
        q = ask(ctx, key) if key in ASK else ("How many companies have independent assurance of GHG emissions?"
                                                  if key == "ghg_assurance" else None)
        a.follow(q, "What is the difference between Scope 1, Scope 2 and Scope 3?" if key in ("scope1", "scope2", "scope3", "scope12") and "difference" not in low else None,
                 f"Which sector has the highest {GLOSSARY[key][0]}?" if key in ("scope1", "scope2", "scope3") else "Top 10 emitters")
        return True
    for rx, title, text in TERMS:
        if rx.search(low):
            a.title = title
            a.p(text)
            a.follow(ask(ctx, "emissions"), "Top 10 emitters")
            return True
    return False


def explain(ctx):
    a, plan = ctx.a, ctx.plan
    low = plan.query.lower()
    if re.search(r"difference between.{0,40}scope|scope.{0,40}difference|scope 1,? (scope )?2 and (scope )?3|all three scopes", low):
        a.kicker = "Definition"
        a.title = "Scope 1, Scope 2 and Scope 3"
        for k in ("scope1", "scope2", "scope3"):
            a.p(GLOSSARY[k][1])
        a.block("points", title="In short", items=[f"**Scope {k[-1]}:** {SHORT[k]}." for k in ("scope1", "scope2", "scope3")]
                + ["**Why the split matters:** each scope is reduced in a different way: Scope 1 by changing fuels and "
                   "processes, Scope 2 by using less electricity or buying renewable power, and Scope 3 by working with "
                   "suppliers and customers."])
        a.follow(ask(ctx, "emissions"), "How many companies report Scope 3 emissions?")
        return
    for rx, title, text in ABOUT:
        if rx.search(low) and not plan.metric:
            a.kicker = "About"
            a.title = title
            a.p(text)
            a.follow("What can you do?", ask(ctx, "emissions"))
            return
    if define(ctx):
        return
    for rx, title, text in ABOUT:
        if rx.search(low):
            a.kicker = "About"
            a.title = title
            a.p(text)
            a.follow("What can you do?", ask(ctx, "emissions"))
            return
    a.status = "not_found"
    a.kicker = "Not available"
    a.title = "I do not have that"
    a.p(f"I could not find that in the disclosures I cover. I can help with {COVERS}.")
    a.follow("What can you do?", ask(ctx, "emissions"), "Top 10 emitters")


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
        a.follow(ask(ctx, "emissions"), "Top 10 emitters", "Companies with the lowest emission intensity")


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
        a.follow("What can you do?", ask(ctx, "emissions"), "Top 10 emitters")


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


def not_available_measure(ctx, what: str):
    a = ctx.a
    a.status = "out_of_scope"
    a.kicker = "Not available"
    a.title = f"{what} are not available yet"
    a.p(f"**{what} are not available yet.** For now I cover {COVERS}.")
    a.follow("Which companies mention carbon credits?", ask(ctx, "projects"), "Examples of GHG reduction projects")
