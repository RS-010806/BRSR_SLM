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


_SCORES: dict = {}


def _sentence_score(g) -> float:
    key = g.get("id")
    if key is not None and key in _SCORES:
        return _SCORES[key]
    sc = _score(g)
    if key is not None:
        _SCORES[key] = sc
    return sc


def _score(g) -> float:
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


# Each practice in plain words: what it is, why it matters and a first step. The words are fixed general explanations;
# whether a company does it, how many do, and every example come from what companies disclosed.
PRACTICE = {
    "Renewable energy": dict(
        title="Switch to renewable electricity", short="Renewable electricity",
        what="Solar panels on rooftops or land the company owns, and green power bought through open access, a power "
             "purchase agreement or a green tariff from the electricity supplier.",
        why="Electricity bought from the grid is counted as Scope 2, and in India most of it is still made from coal. Each "
            "unit replaced by solar or wind power removes its emissions.",
        core=r"solar|wind|renewable|green (?:power|energy|tariff)|\bppa\b|open access|rooftop",
        step="Put solar panels on owned rooftops, then ask the electricity supplier for a green tariff or open-access green power."),
    "Energy efficiency": dict(
        title="Use less energy for the same work", short="Energy efficiency",
        what="Energy audits, LED lighting, efficient motors, pumps and air conditioning, variable-speed drives and building "
             "management systems.",
        why="Every unit of electricity or fuel saved removes its emissions and lowers the energy bill, which makes it the usual "
            "place to start. It cuts Scope 2 and, where fuel is saved, Scope 1.",
        core=r"\bled\b|energy[- ]efficien|energy audit|\bvfds?\b|variable (?:frequency|speed)|efficient (?:motors?|pumps?|"
             r"compressors?|chillers?|lighting|equipment)|retrofit|star rat|\bhvac\b|chillers?|building management|energy sav|"
             r"saved [\d,.]+ ?(?:kwh|mwh|units)|(?:kwh|mwh|units) (?:of (?:electricity|energy) )?saved",
        step="Commission an energy audit of the largest sites, then move lighting to LED and upgrade motors, pumps and cooling."),
    "Fuel switching and alternative fuels": dict(
        title="Replace coal, diesel and oil with cleaner fuels", short="Cleaner fuels",
        what="Natural gas, biomass, biofuels or refuse-derived fuel in boilers, kilns, furnaces and generators.",
        why="Fuel burnt on the company's own sites is Scope 1. Coal and diesel release more CO2 for the same heat than natural "
            "gas, and biomass from crop residues is treated as close to carbon-neutral.",
        core=r"biomass (?:boilers?|fuel|briquett|co-?fir)|natural gas|\bpng\b|\bcng\b|\brdf\b|refuse[- ]derived|biofuel|"
             r"alternative fuels?|briquett|replac\w* (?:\w+ )?(?:coal|diesel|furnace oil|hsd|ldo)|fuel switch|co-?firing",
        step="List where coal, diesel or furnace oil is burnt and replace the largest use with natural gas, biomass or electricity."),
    "Electrification and EVs": dict(
        title="Move vehicles and equipment to electric", short="Electric vehicles",
        what="Electric cars, two-wheelers, buses, forklifts and trucks in place of diesel and petrol ones, with charging points "
             "at offices and plants.",
        why="Fuel burnt by owned vehicles is Scope 1, and by hired transport and employee commuting it is Scope 3. An electric "
            "vehicle has no exhaust, and its emissions fall further as the electricity gets greener.",
        core=r"electric vehicles?|\bevs?\b|e-?vehicles?|charging|electric (?:bus|car|truck|forklift)",
        step="Replace owned cars and forklifts with electric ones at the next renewal, and offer electric cabs for commuting."),
    "Waste heat recovery": dict(
        title="Turn waste heat into power", short="Waste heat recovery",
        what="Boilers and turbines that capture hot exhaust gases from kilns, furnaces or engines and turn them into electricity "
             "or steam.",
        why="The heat has already been paid for in fuel. Using it again replaces electricity bought from the grid (Scope 2) "
            "without burning anything more.",
        core=r"waste heat|\bwhrs?\b|heat recovery",
        step="Check kilns, furnaces and engine exhausts for heat that could generate power or preheat another process."),
    "Green hydrogen": dict(
        title="Prepare for green hydrogen", short="Green hydrogen",
        what="Hydrogen made with renewable electricity, used in place of fossil fuels in refining, fertilisers, steel and heavy "
             "transport.",
        why="It is one of the few options for high-temperature heat and chemical processes that cannot easily run on "
            "electricity. Most projects are still pilots.",
        core=r"hydrogen|electroly",
        step="Pick one process that already uses hydrogen or high-temperature heat and study a pilot there."),
    "Carbon capture": dict(
        title="Capture the carbon that cannot be avoided", short="Carbon capture",
        what="Equipment that captures CO2 from a process or chimney so that it can be used or stored.",
        why="Some emissions, such as the CO2 released from limestone in cement making, remain even with clean energy. Most "
            "projects are still at pilot stage.",
        core=r"carbon capture|\bccus\b|\bccs\b|captur",
        step="Find where CO2 is released in a concentrated stream, which is the cheapest place to capture it."),
    "Science-based or net-zero targets": dict(
        title="Set a dated net-zero or science-based target", short="Net-zero or SBTi target",
        what="A public commitment to reach net zero by a stated year, ideally with near-term targets validated by the Science "
             "Based Targets initiative (SBTi).",
        why="A target turns separate projects into a plan: how much has to be cut, and by when. SBTi validation shows the "
            "target is in line with climate science.",
        core=r"net[- ]?zero|carbon neutral|\bsbti\b|science[- ]based",
        step="Set a dated net-zero target for operations with an interim milestone, and consider SBTi validation."),
    "Afforestation and carbon sinks": dict(
        title="Plant trees and restore land", short="Tree planting",
        what="Plantations, green belts around sites and restoration of degraded land or mangroves.",
        why="Trees absorb CO2 over many years, so planting can balance part of what remains. It does not reduce the company's "
            "own Scope 1 and Scope 2 emissions, so it is best reported separately from reductions.",
        core=r"plant(?:ed|ation of|ing of)\s+(?:over |about |more than )?[\d,.]+(?:\s?(?:lakh|million))?\s+(?:trees|saplings)|"
             r"saplings|afforest|mangrove|green belt|trees? (?:were |have been )?planted|miyawaki",
        step="Plant on owned land or with a local partner, and report the carbon absorbed separately from reductions."),
    "Green buildings": dict(
        title="Certify buildings as green", short="Green buildings",
        what="IGBC, GRIHA or LEED certification of offices, branches and plants, which sets standards for insulation, cooling, "
             "lighting and water.",
        why="A certified building uses less electricity for cooling and lighting for its whole life, which cuts Scope 2.",
        core=r"\bleed\b|\bigbc\b|griha|certifi|platinum|gold[- ]rated",
        step="Seek IGBC, GRIHA or LEED certification for the main office or plant, starting with new buildings."),
    "Internal carbon pricing": dict(
        title="Put an internal price on carbon", short="Internal carbon price",
        what="A notional cost per tonne of CO2 added to the cost of projects when comparing investments.",
        why="It puts the cost of emissions into investment decisions, so lower-carbon options win even before regulation "
            "prices carbon.",
        core=r"carbon pric|internal carbon|shadow pric",
        step="Apply a notional price per tonne of CO2 when comparing large investments."),
    "Logistics and transport optimisation": dict(
        title="Move goods more efficiently", short="Logistics",
        what="Shifting freight from road to rail or coastal shipping, planning routes, filling trucks fully and avoiding empty "
             "return trips.",
        why="Transport fuel is Scope 1 for an own fleet and Scope 3 for hired transport. Rail and full loads use much less fuel "
            "for each tonne moved.",
        core=r"\brail|routes?\b|logistic|loads?\b|multimodal|freight|shipping",
        step="Shift long-distance freight to rail where possible and plan routes to avoid empty return trips."),
    "Low-carbon products and materials": dict(
        title="Make lower-carbon products", short="Low-carbon products",
        what="Blended cement using fly ash or slag in place of clinker, recycled metals and plastics, and other low-carbon "
             "materials.",
        why="Clinker and virgin materials carry most of a product's emissions, so using less of them cuts process emissions "
            "and the Scope 3 emissions of customers.",
        core=r"fly ash|slag|blended|clinker|recycl|low[- ]carbon|green (?:steel|cement)",
        step="Raise the share of recycled or blended materials in the main products."),
}
# Scope 3 practices are about the value chain; each is recognised by its own wording in the disclosure.
SCOPE3_PRACTICE = {
    "Supplier engagement": dict(
        title="Work with suppliers to cut their emissions", short="Supplier engagement",
        what="Ask key suppliers to measure and report their emissions and set targets, and include emissions in how suppliers "
             "are chosen and assessed.",
        why="Purchased goods and services are usually the largest part of Scope 3, and those emissions fall only when "
            "suppliers act.",
        rx=r"(?:suppliers?|vendors?|supply chain|value chain partners?)\W+(?:\w+\W+){0,8}?(?:engag|assess|programm?e|training|"
           r"sensiti|collaborat|code of conduct|questionnaire|targets?|emission|carbon|decarboni)|(?:engag|assess|collaborat|"
           r"partner)\w*\W+(?:\w+\W+){0,6}?(?:suppliers?|vendors?)",
        step="Ask the largest suppliers to report their emissions, and add a carbon question to supplier assessments."),
    "Logistics and transport optimisation": dict(
        title="Move goods more efficiently", short="Logistics",
        what="Shifting freight from road to rail or coastal shipping, planning routes, filling trucks fully and avoiding empty "
             "return trips.",
        why="Fuel burnt by hired transporters is part of Scope 3. Rail and full loads use much less fuel for each tonne moved.",
        rx=r"\brail(?:way)?s?\b|route optimi|optimi[sz]\w* (?:routes?|loads?|logistics)|load factor|multi-?modal|freight|"
           r"fuel[- ]efficient (?:trucks|vehicles)|logistics partners?",
        step="Shift long-distance freight to rail where possible and ask transporters to plan routes that avoid empty return trips."),
    "Commuting and business travel": dict(
        title="Cut emissions from commuting and business travel", short="Commuting and travel",
        what="Electric or shared cabs and buses for employees, video calls in place of some trips, and a travel policy that "
             "prefers rail to air.",
        why="Employee commuting and business travel are part of Scope 3, and for offices and service firms they are often "
            "among its largest parts.",
        rx=r"commut|business travel|\bcabs?\b|shuttle|car ?pool|video ?conferenc|virtual meetings?|air travel|employee transport",
        step="Offer electric or shared transport for commuting, and replace some business trips with video calls."),
    "Low-carbon products and materials": dict(
        title="Make lower-carbon products", short="Low-carbon products",
        what="Products and materials with a lower footprint, such as blended cement, recycled metals and plastics, and "
             "measured product carbon footprints.",
        why="Emissions from making the materials a company buys, and from how customers use its products, sit in Scope 3.",
        rx=r"low[- ]carbon (?:products?|solutions?|cement|steel|materials?)|recycled (?:content|materials?|plastics?)|"
           r"green (?:products?|steel|cement)|product carbon footprint|\blca\b|life[- ]cycle assessment",
        ex=r"low[- ]carbon (?:products?|cement|steel|materials?)|recycled (?:content|materials?|plastics?)|"
           r"green (?:products?|steel|cement)|product carbon footprint",
        step="Measure the footprint of the main product and raise the share of recycled or low-carbon materials in it."),
    "Scope 3 measurement and targets": dict(
        title="Measure Scope 3 and set a target for it", short="Scope 3 measured or targeted",
        what="Calculate Scope 3 by category (purchased goods, transport, travel, use of products), then set a reduction "
             "target for the largest categories.",
        why="Scope 3 is often the largest part of a company's footprint, and what is not measured cannot be managed.",
        rx=r"scope[- ]?3\W+(?:\w+\W+){0,8}?(?:targets?|measur|inventor|calculat|assess|account|mapp|categor|reduc)|"
           r"(?:targets?|measur|calculat|assess|account|mapp|reduc)\w*\W+(?:\w+\W+){0,8}?scope[- ]?3",
        step="Calculate Scope 3 for the main categories, then set a target for the largest one."),
}
for _d in SCOPE3_PRACTICE.values():
    _d["rx"] = re.compile(_d["rx"], re.I)
    _d["core"] = re.compile(_d.pop("ex"), re.I) if "ex" in _d else _d["rx"]
DOING3 = {"Supplier engagement": "working with suppliers to cut their emissions",
          "Logistics and transport optimisation": "moving goods more efficiently",
          "Commuting and business travel": "cutting emissions from commuting and business travel",
          "Low-carbon products and materials": "making lower-carbon products",
          "Scope 3 measurement and targets": "measuring Scope 3 and setting a target for it"}
for _t, _d in SCOPE3_PRACTICE.items():
    _d["doing"] = DOING3[_t]
_RX_HIT: dict = {}


def _says(ctx, c, qid, rx) -> bool:
    key = (c["id"], qid, rx.pattern)
    if key not in _RX_HIT:
        _RX_HIT[key] = any(rx.search(g["text"]) for g in ctx.index.by_cell.get((c["id"], qid), []))
    return _RX_HIT[key]


DOING = {'Renewable energy': 'switching to renewable electricity',
         'Energy efficiency': 'using less energy for the same work',
         'Fuel switching and alternative fuels': 'replacing coal, diesel and oil with cleaner fuels',
         'Electrification and EVs': 'moving vehicles and equipment to electric',
         'Waste heat recovery': 'turning waste heat into power',
         'Green hydrogen': 'preparing for green hydrogen',
         'Carbon capture': 'capturing the carbon that cannot be avoided',
         'Science-based or net-zero targets': 'setting a dated net-zero or science-based target',
         'Afforestation and carbon sinks': 'planting trees and restoring land',
         'Green buildings': 'certifying buildings as green',
         'Internal carbon pricing': 'putting an internal price on carbon',
         'Logistics and transport optimisation': 'moving goods more efficiently',
         'Low-carbon products and materials': 'making lower-carbon products'}
for _t, _d in PRACTICE.items():
    _d["core"] = re.compile(_d["core"], re.I)
    _d["doing"] = DOING[_t]
PRACTICE_TEXT = {t: (d["title"], d["what"]) for t, d in PRACTICE.items()}
SCOPE_THEMES = {"scope1": ["Fuel switching and alternative fuels", "Electrification and EVs", "Energy efficiency",
                           "Waste heat recovery", "Low-carbon products and materials", "Green hydrogen", "Carbon capture"],
                "scope2": ["Renewable energy", "Energy efficiency", "Waste heat recovery", "Green buildings"],
                "scope3": ["Logistics and transport optimisation", "Electrification and EVs", "Low-carbon products and materials",
                           "Science-based or net-zero targets", "Renewable energy"]}
_QTY = re.compile(r"\d[\d,.]*\s?(?:%|per ?cent\b|(?:mw|mwp|kw|kwp|gw|kwh|mwh|gwh|tonnes?|tco2e?|mt\b|kl|crore|lakh|units?|vehicles|"
                  r"trucks|buses|chargers|trees|saplings|hectares?|ha)\b)", re.I)


_SEG_INFO: dict = {}
# a sentence that leans on the one before it ("These initiatives ...") does not stand alone as an example
_VAGUE_START = re.compile(r"(?:these|this|they|it|such|those|the above|further|furthermore|also|hence|thus|additionally|"
                          r"moreover|accordingly|as a result)\b", re.I)


def _seg_info(ctx, c, qid):
    """Each sentence of a disclosure with its score (a quantity counts extra) and the practices it names, computed once."""
    key = (c["id"], qid)
    if key not in _SEG_INFO:
        _SEG_INFO[key] = [(g, _sentence_score(g) + (3 if _QTY.search(g["text"]) else 0),
                           {t for t, r in _THEME_RE.items() if r.search(g["text"])})
                          for g in ctx.index.by_cell.get(key, [])]
    return _SEG_INFO[key]


def _gist(t: str) -> str:
    """Two companies in a group sometimes file the same sentence; one is enough."""
    return re.sub(r"[^a-z]", "", t.lower())[:50]


def _shape(t: str) -> float:
    """How far a sentence is from a readable example: a heading, a run-on list or one too long to show whole."""
    n = len(t)
    return ((8 if n < 60 else 0) + max(0, n - 200) / 15 + (6 if n > 240 else 0)
            + (3 if len(re.findall(r"\s[-–•]\s|;\s", t)) >= 2 else 0) + (2 if re.match(r"^[A-Z]\d", t) else 0))


_EXAMPLES: dict = {}


def _example(ctx, cands_companies, qid, rx, used, sid, focus_rx=None, core=None, seen=None):
    """The most concrete sentence naming a practice: a quantity and an action, from a company not used yet."""
    key = (tuple(c["id"] for c in cands_companies), qid, rx.pattern, frozenset(used), sid,
           focus_rx.pattern if focus_rx is not None else None, core.pattern if core is not None else None,
           frozenset(seen or ()))
    if key not in _EXAMPLES:
        _EXAMPLES[key] = _example0(ctx, cands_companies, qid, rx, used, sid, focus_rx, core, seen)
    return _EXAMPLES[key]


def _example0(ctx, cands_companies, qid, rx, used, sid, focus_rx, core, seen):
    if core is not None:
        hit = _example1(ctx, cands_companies, qid, rx, used, sid, focus_rx, core, seen, strict=True)
        if hit[0] is not None:
            return hit
    return _example1(ctx, cands_companies, qid, rx, used, sid, focus_rx, core, seen, strict=False)


def _example1(ctx, cands_companies, qid, rx, used, sid, focus_rx, core, seen, strict):
    theme = next((t for t, r in _THEME_RE.items() if r is rx), None)
    best = None
    for c in cands_companies:
        if theme and theme not in ctx.kb.themes(c["id"], qid):
            continue
        bonus = (-6 if c["id"] in used else 0) + (2 if sid and c["sector"] == sid else 0)
        for g, sc, themes in _seg_info(ctx, c, qid):
            if (theme and theme not in themes) or (not theme and not rx.search(g["text"])):
                continue
            if focus_rx is not None and not focus_rx.search(g["text"]):
                continue
            t = g["text"]
            if strict and (not core.search(t) or _VAGUE_START.match(t.strip()) or len(t) < 60):
                continue
            if len(t.strip()) < 40 or re.search(r"(?::|\b(?:and|or|the|of|to|for|with|in|by|a|an))$", t.strip()):
                continue
            if seen is not None and _gist(t) in seen:
                continue
            fit = ((3 if core is not None and core.search(t) else 0) - (6 if _VAGUE_START.match(t.strip()) else 0)
                   + (2 if _QTY.search(t) else 0) - _shape(t))
            key = (sc + bonus + fit, c["name"].lower())
            if best is None or key > best[0]:
                best = (key, c, g)
    return (best[1], best[2]) if best else (None, None)


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
        qid = "286"
    pool = kb.members(sid) if sid else kb.companies
    others = [c for c in pool if not me or c["id"] != me["id"]]
    scope = kb.sector_by_id[sid]["name"] if sid else None
    if qid == "286":
        return _target_practice(ctx, others, scope, sid, me, FOCUS.get(mid))
    if qid in ("295", "277"):
        return _plain_examples(ctx, qid, others, scope, sid, me)

    # ---- GHG reduction projects: each practice explained (what it is, why it matters, a real example), then how common
    # each is, then the user's own company, then the full disclosures on request
    focus = FOCUS.get(mid)
    have = [c for c in others if c["values"].get(qid)]
    widened = False
    if len(have) < 5 and sid:
        have = [c for c in kb.companies if c["values"].get(qid) and (not me or c["id"] != me["id"])]
        widened = True
    N = len(have)
    where = f"{scope} companies" if scope and not widened else "companies"
    a.kicker = scope or "All companies"
    a.title = f"Good practice: reducing {SCOPE_NAME[mid]} emissions" if focus else "Good practice: reducing GHG emissions"
    if not have:
        a.status = "partial"
        a.p(f"No company{' in ' + scope if scope else ''} has described projects to reduce GHG emissions for FY 2024-25.")
        return
    table = SCOPE3_PRACTICE if mid == "scope3" else PRACTICE
    allowed = list(SCOPE3_PRACTICE) if mid == "scope3" else SCOPE_THEMES.get(mid) if focus else list(PRACTICE)

    def tally(group):
        out = [(t, sum(1 for c in group if (_says(ctx, c, qid, table[t]["rx"]) if mid == "scope3" else t in kb.themes(c["id"], qid))))
               for t in allowed]
        return sorted([x for x in out if x[1]], key=lambda x: (-x[1], x[0]))[: (_count(ctx) or 6)]

    counts = tally(have)
    if not counts and sid and not widened:
        # no company in the sector describes such a practice: draw on all companies
        have = [c for c in kb.companies if c["values"].get(qid) and (not me or c["id"] != me["id"])]
        widened, N, where = True, len(have), "companies"
        counts = tally(have)
    if not counts:
        a.status = "partial"
        a.p(f"No company has described projects to reduce {focus[1] if focus else 'GHG emissions'} for FY 2024-25.")
        return
    mshort = short_name(me["name"]) if me else None
    top = [table[t]["doing"] for t, _ in counts[:3]]
    who = f"{scope} companies" if scope else "Companies"
    if focus:
        a.p(f"To reduce {focus[1]}, {where} most often start by {join(top)}. Each practice is explained "
            f"below with an example from a company's own disclosure.")
    else:
        a.p(f"{who} most often reduce their GHG emissions by {join(top)}. Each practice is explained below with an example "
            f"from a company's own disclosure.")
        pool_all = kb.members(sid) if sid and not widened else kb.companies
        from .h_sector import _total
        s1, s2 = _total(pool_all, "scope1"), _total(pool_all, "scope2")
        if s1 + s2 > 0:
            big = ("Purchased electricity (Scope 2)", s2) if s2 >= s1 else ("Fuel burnt on their own sites (Scope 1)", s1)
            cs = a.c_calc(f"Share of Scope 1 and 2 emissions, {scope or 'all companies'}",
                          f"{big[0].split(' (')[1].rstrip(')')} total ÷ (Scope 1 total + Scope 2 total), FY 2024-25",
                          note="Totals are the sum of what companies disclosed.")
            pct = 100 * big[1] / (s1 + s2)
            so = ("" if pct < 60 else ", so the practices that cut electricity use or make it renewable matter most" if s2 >= s1
                  else ", so the practices that cut the fuel burnt on site matter most")
            a.p(f"{big[0]} makes up {share(round(big[1]), round(s1 + s2), 0)} of the Scope 1 and 2 emissions "
                f"{'these companies' if scope else 'companies'} disclosed {cs}{so}.")
    if widened:
        a.note("context", f"Few or no {scope} companies describe such projects, so all companies are used.")
    items, details, examples, used, seen = [], [], [], set(), set()
    focus_rx = focus[0] if focus else None
    for t, k in counts:
        d = table[t]
        rx = d["rx"] if mid == "scope3" else _THEME_RE[t]
        c, g = _example(ctx, have, qid, rx, used, sid, focus_rx, d["core"], seen)
        if c is None and focus_rx is not None:
            c, g = _example(ctx, have, qid, rx, used, sid, None, d["core"], seen)
        if c is None and sid:
            c, g = _example(ctx, [x for x in kb.companies if x["values"].get(qid) and (not me or x["id"] != me["id"])],
                            qid, rx, used, sid, focus_rx, d["core"], seen)
        items.append(f"**{d['title']}**")
        details.append([{"label": "What it is", "text": d["what"]}, {"label": "Why it matters", "text": d["why"]}])
        if c is not None:
            used.add(c["id"])
            seen.add(_gist(g["text"]))
            a.company_ref(c)
            examples.append({"who": short_name(c["name"]) + (f" ({kb.sector_of(c)['name']})" if sid and c["sector"] != sid else ""),
                             "text": _around(g["text"], d["core"] if d["core"].search(g["text"]) else rx, 230),
                             "cite": a.c_filing(c, qid)})
        else:
            examples.append(None)
    a.block("points", title="The practices, explained", items=items, details=details, examples=examples, numbered=True)
    mine = set() if not (me and me["values"].get(qid)) else \
        {t for t, _ in counts if _says(ctx, me, qid, table[t]["rx"])} if mid == "scope3" else set(kb.themes(me["id"], qid))
    a.c_calc("How common each practice is", f"Companies whose disclosure names the practice ÷ the {N} {where} that "
             f"describe projects to reduce GHG emissions", note="A practice is counted when the disclosure names it. "
             "A mention is not a verified result.")
    a.block("bars", title="How common each practice is", unit="% of companies", max=100,
            subtitle=f"Share of the {N} {where} that describe GHG reduction projects, FY 2024-25",
            focus_label=f"In {mshort}'s disclosure" if mine else None,
            rows=[{"label": table[t]["short"], "value": round(100 * k / N, 1), "display": f"{100 * k / N:.0f}%",
                   "full": f"{k} of {N} companies", "highlight": t in mine} for t, k in counts],
            export=export("How common each practice is", ["Practice", "Companies describing it", "Companies with projects", "Share (%)"],
                          [[table[t]["title"], k, N, round(100 * k / N, 1)] for t, k in counts]))
    if me:
        a.company_ref(me)
        own = a.c_filing(me, qid)
        if me["values"].get(qid):
            checks = [{"label": table[t]["title"], "value": t in mine,
                       "sub": "Described in its disclosure" if t in mine else "Next step: " + table[t]["step"], "cite": own}
                      for t, k in counts]
        else:
            a.p(f"{mshort} has not described projects to reduce GHG emissions for FY 2024-25 {own}. The first steps are "
                f"listed below.")
            checks = [{"label": table[t]["title"], "value": False, "sub": "Next step: " + table[t]["step"], "cite": own}
                      for t, k in counts]
        a.block("checklist", title=f"What {mshort} already does, and next steps", items=checks)
    shown = list(dict.fromkeys(e["who"].split(" (")[0] for e in examples if e))
    full = [quote_item(ctx, c, qid) for c in have if short_name(c["name"]) in shown][:3]
    if full:
        a.block("quotes", items=full, collapsed=True, title="Full disclosures",
                summary=f"Read the full disclosures from {join([it['short'] for it in full])}")
    a.context.update({"metric": mid, "sector": sid, "companies": [cid] if cid else []})
    first = counts[0][0] if counts else None
    a.follow(f"How does {mshort} compare with its peers?" if me else (f"Tell me about {full[0]['short']}" if full else None),
             f"Which {scope + ' ' if scope else ''}companies mention {THEME_ASK[first]}?" if first in THEME_ASK and mid != "scope3" else None,
             "Best practices for setting GHG targets" + (f" in {scope}" if scope else ""))


def _plain_examples(ctx, qid, others, scope, sid, me):
    """Progress against targets, certifications: the most concrete disclosures, each in a sentence."""
    a, kb = ctx.a, ctx.kb
    what = EXAMPLE_NAME[qid]
    have = [c for c in others if c["values"].get(qid)]
    a.kicker = scope or "All companies"
    a.title = f"Good practice: {what}"
    N = len(have)
    rx = _TARGET_QTY if qid == "295" else re.compile(r"\biso\s?\d{4,5}|leed|igbc|griha|gri\b|cdp|tcfd|sbti|bee|star rating", re.I)
    cands = []
    for c in have:
        segs = [g for g in ctx.index.by_cell.get((c["id"], qid), []) if rx.search(g["text"])]
        if segs:
            g = max(segs, key=lambda g: (_sentence_score(g), -g["seg"]))
            cands.append((_sentence_score(g) + (2 if sid and c["sector"] == sid else 0), c["name"].lower(), c, g))
    cands.sort(key=lambda x: (-x[0], x[1]))
    chosen = cands[: (_count(ctx) or 5)]
    cc = a.c_calc(f"Companies disclosing {what}", f"{N} {scope + ' ' if scope else ''}companies provided this disclosure")
    if qid == "295":
        a.p(f"Good reporting on progress gives, for each target, the figure reached against it in the year. {len(cands)} of the "
            f"{N} {scope + ' ' if scope else ''}companies that report progress give such figures {cc}; the most concrete are below.")
    else:
        a.p(f"Good disclosure names the standards and certifications, such as ISO 14001 for environmental management or ISO "
            f"50001 for energy management, and where they apply. {len(cands)} of the {N} {scope + ' ' if scope else ''}companies "
            f"that disclose certifications name specific ones {cc}.")
    if chosen:
        items, examples = [], []
        for _, _, c, g in chosen:
            a.company_ref(c)
            items.append(f"**{short_name(c['name'])}**" + (f" ({kb.sector_of(c)['name']})" if c["sector"] != sid else ""))
            examples.append({"who": "", "text": _around(g["text"], rx, 230), "cite": a.c_filing(c, qid)})
        a.block("points", title="Examples", items=items, examples=examples)
        full = [quote_item(ctx, c, qid) for _, _, c, _ in chosen[:3]]
        a.block("quotes", items=full, collapsed=True, title="Full disclosures",
                summary=f"View the full disclosures from {join([it['short'] for it in full])}")
    a.follow("Best practices for setting GHG targets" + (f" in {scope}" if scope else ""),
             "Best practices for reducing emissions" + (f" in {scope}" if scope else ""))


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
    n_ex = None
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
    k, N = len(rows), len(others) if not widened else len(kb.companies) - (1 if me else 0)
    where = f"{scope} companies" if scope and not widened else "companies"
    cc = a.c_calc(f"Companies mentioning {label}", f"{k} of {N} companies" + (f" in {scope}" if scope and not widened else ""),
                  note="A mention is not a verified project.")
    theme = next((TECH_THEME[t] for t in plan.tech if TECH_THEME.get(t) in PRACTICE), None)
    a.p(f"Good practice with {label} is to describe it concretely: how much, by when, and how it links to a target. "
        f"{k} of the {N} {where} mention {label} in their disclosures on projects or targets for FY 2024-25 {cc}.")
    if widened:
        a.note("context", f"Few {scope} companies mention it, so examples from other sectors are included and labelled.")
    if theme:
        d0 = PRACTICE[theme]
        a.block("points", title="What it is and why it matters", items=[f"**{d0['title']}**"],
                details=[[{"label": "What it is", "text": d0["what"]}, {"label": "Why it matters", "text": d0["why"]}]])

    def text_of(r):
        return " ".join(d["text"] for d, _ in r[5])
    GUIDES = [
        ("Give a size or a figure", "Capacity, a share of energy or the tonnes of CO2 avoided, so that progress can be checked "
         "from one year to the next.", lambda r: bool(_QTY.search(r[3]["text"])), lambda r: bool(_QTY.search(text_of(r))),
         "State the capacity, the share of energy or the tonnes of CO2 avoided."),
        ("Tie it to a year", "When it was installed or by when it will be reached, so that it reads as a commitment rather "
         "than an intention.", lambda r: bool(re.search(r"\b20[2-5]\d\b", r[3]["text"])),
         lambda r: bool(re.search(r"\b20[2-5]\d\b", text_of(r))), "Say when it was installed or by which year it will be reached."),
        ("Make it part of a target", "Link it to a GHG or renewable energy target, so that it is part of a plan rather than a "
         "one-off project.", lambda r: r[3]["qid"] in ("286", "295"), lambda r: any(d["qid"] in ("286", "295") for d, _ in r[5]),
         "Include it in the company's GHG or renewable energy target."),
    ]
    if ctx.plan.n:
        chosen = rows[: _count(ctx)]
        items, examples = [], []
        for score, _, c, d, spans, _ in chosen:
            a.company_ref(c)
            items.append(f"**{short_name(c['name'])}**" + (f" ({kb.sector_of(c)['name']})" if not scope or c["sector"] != sid else ""))
            examples.append({"who": "", "text": _around(d["text"], None, 240, spans), "cite": a.c_filing(c, d["qid"])})
        a.block("points", title="Examples", items=items, examples=examples)
    else:
        items, details, examples, used, chosen = [], [], [], set(), []
        for title, why, best_has, _, _ in GUIDES:
            pick = next((r for r in rows if r[2]["id"] not in used and best_has(r)), None)
            items.append(f"**{title}**")
            details.append([{"label": "Why it matters", "text": why}])
            if pick:
                _, _, c, d, spans, _ = pick
                used.add(c["id"])
                chosen.append(pick)
                a.company_ref(c)
                examples.append({"who": short_name(c["name"]) + (f" ({kb.sector_of(c)['name']})" if sid and c["sector"] != sid else ""),
                                 "text": _around(d["text"], None, 240, spans), "cite": a.c_filing(c, d["qid"])})
            else:
                examples.append(None)
        a.block("points", title="How to describe it well", items=items, details=details, examples=examples, numbered=True)
        chosen += [r for r in rows if r not in chosen][: max(0, 3 - len(chosen))]
    mine = ctx.index.search(plan.tech, [], PRACTICE_SEARCH, {me["id"]}).get(me["id"]) if me else None
    me_row = None
    if mine:
        d, spans = max(mine, key=lambda dsp: (_sentence_score(dsp[0]), -dsp[0]["seg"]))
        me_row = (0, "", me, d, spans, mine)
    ms = short_name(me["name"]) if me else None
    a.block("bars", title=f"How the {k} {'company' if k == 1 else 'companies'} mentioning {label} describe it", unit="% of companies",
            max=100, subtitle="Share that do each, FY 2024-25", focus_label=f"Done by {ms}" if me_row else None,
            rows=[{"label": g[0], "value": round(100 * sum(1 for r in rows if g[3](r)) / k, 1),
                   "display": f"{100 * sum(1 for r in rows if g[3](r)) / k:.0f}%",
                   "full": f"{sum(1 for r in rows if g[3](r))} of {k} companies", "highlight": bool(me_row and g[3](me_row))}
                  for g in GUIDES],
            export=export(f"How companies describe {label}", ["Practice", "Companies", "Companies mentioning it", "Share (%)"],
                          [[g[0], sum(1 for r in rows if g[3](r)), k, round(100 * sum(1 for r in rows if g[3](r)) / k, 1)] for g in GUIDES]))
    if me:
        a.company_ref(me)
        if me_row:
            cite = a.c_filing(me, me_row[3]["qid"])
            checks = [{"label": f"Mentions {label}", "value": True, "sub": "“" + _clip(me_row[3]["text"], 200) + "”", "cite": cite}]
            checks += [{"label": g[0], "value": g[3](me_row), "sub": "In its disclosure" if g[3](me_row) else "Next step: " + g[4],
                        "cite": cite} for g in GUIDES]
        else:
            cite = a.c_filing(me, "1342")
            checks = [{"label": f"Mentions {label}", "value": False,
                       "sub": f"Not in its disclosures on projects and targets; {k} of the {N} {where} mention it.", "cite": cite}]
        a.block("checklist", title=f"For {ms}", items=checks)
    full = []
    for score, _, c, d, spans, found in chosen[:3]:
        segs = [{"start": x["start"], "end": x["end"], "highlight": True, "marks": [[x["start"] + s0, x["start"] + s1] for s0, s1 in sp]}
                for x, sp in found if x["qid"] == d["qid"]][:4]
        full.append({"key": f"{c['id']}:{d['qid']}", "company": c["name"], "company_id": c["id"], "short": short_name(c["name"]),
                     "sector": kb.sector_of(c)["name"], "topic": item(d["qid"])[0], "text": c["values"][d["qid"]],
                     "segments": segs, "cite": a.c_filing(c, d["qid"])})
    a.block("quotes", items=full, excerpt=True, collapsed=True,
            summary=f"Read where {join([x['short'] for x in full])} mention it")
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


# Good practice for GHG targets: each practice explained, how many companies' targets show it, and an example target.
_TARGET_GHG = re.compile(r"emission|ghg|carbon|scope[- ]?[123]|renewable|energy|net[- ]?zero|climate|co2|decarboni|"
                         r"electri|fuel|green power|solar|re ?100|neutral", re.I)
_TARGET_QTY = re.compile(r"\d[\d.,]*\s?(?:%|per ?cent|mw|gw|tonnes?|tco2|crore|lakh|mwh)", re.I)
_YEAR = re.compile(r"\b20(?:2[5-9]|[3-7]\d)\b")
TARGET_PRACTICES = [
    dict(title="Put a number and a date on it", short="Number and date",
         what="State how much will be cut and by which year, as a percentage or in tonnes of CO2.",
         why="A target with a number and a year can be tracked from one annual report to the next; “we aim to reduce "
             "emissions” cannot.",
         test=lambda t: bool(_TARGET_QTY.search(t) and _YEAR.search(t)),
         step="Restate the goal as a percentage cut by a named year."),
    dict(title="Measure it from a stated base year", short="Base year",
         what="Name the year the cut is measured from, and the emissions in that year.",
         why="A percentage cut means little without its starting point, and a fixed base year keeps the target from moving "
             "when the business changes.",
         test=lambda t: bool(re.search(r"base ?line|base year|\bfrom (?:fy ?)?20[0-2]\d\b|\b(?:vs\.?|compared to|against) "
                                       r"(?:fy ?)?20[0-2]\d", t, re.I)),
         step="Name a base year and give its emissions alongside the target."),
    dict(title="Say which scopes it covers", short="Scopes covered",
         what="State whether the target covers Scope 1, Scope 2 and Scope 3, or only some of them.",
         why="Scope 1 and Scope 2 are in the company's direct control. Including Scope 3 extends the target to suppliers and "
             "customers, where most emissions often lie.",
         test=lambda t: bool(re.search(r"scope[- ]?[123]", t, re.I)),
         prefer=re.compile(r"scope[- ]?1\b.{0,25}\b(?:scope[- ]?)?[23]\b", re.I),
         step="State the scopes the target covers, and add Scope 3 once it is measured."),
    dict(title="Anchor it to net zero or a science-based pathway", short="Net zero or SBTi",
         what="Commit to a year for net zero, and have near-term targets validated by the Science Based Targets initiative "
              "(SBTi).",
         why="Validation shows the cut is deep and fast enough to be in line with climate science, which investors and "
             "customers increasingly ask for.",
         test=lambda t: bool(re.search(r"net[- ]?zero|carbon neutral|science[- ]based|sbti", t, re.I)),
         step="Set a net-zero year and submit near-term targets to SBTi."),
    dict(title="Add interim milestones", short="Interim milestones",
         what="Set near-term steps, for example one for this decade, on the way to the long-term goal.",
         why="A long-term goal alone can be put off. A near-term milestone shows the cuts that have to happen now.",
         test=lambda t: len(set(re.findall(r"\bby (?:fy ?)?(20(?:2[5-9]|[3-7]\d))\b", t, re.I))) >= 2
         and bool(re.search(r"net[- ]?zero|carbon neutral|emission|ghg|scope", t, re.I)),
         step="Add a milestone for the next five years on the way to the long-term goal."),
    dict(title="Back it with a renewable electricity target", short="Renewable electricity",
         what="Set the share of electricity that will come from renewable sources by a given year.",
         why="Purchased electricity is Scope 2, often the largest part of a company's own emissions, so a renewable share is "
             "usually the first lever.",
         test=lambda t: bool(re.search(r"renewable|re ?100|green (?:power|energy|electricity)|solar", t, re.I) and _TARGET_QTY.search(t)),
         step="Set the share of renewable electricity to reach by a named year."),
    dict(title="Use an intensity target if output is growing", short="Intensity target",
         what="Set the cut per tonne of product, per unit or per rupee of revenue, alongside the absolute cut.",
         why="If output grows, total emissions can rise even as the business gets more efficient; an intensity target shows "
             "that progress. An absolute target is still needed for net zero.",
         test=lambda t: bool(re.search(r"intensity|per (?:tonne|ton|unit|employee|mwh|crore|rupee|revenue)", t, re.I)),
         prefer=re.compile(r"(?:emission|ghg|carbon|co2)\w* intensity|intensity.{0,40}(?:emission|ghg|carbon|co2)", re.I),
         step="Add a target per unit of output alongside the absolute one."),
]


_GHG_TEXT: dict = {}
_TARGET_SEGS: dict = {}


def _ghg_text(c, qid="286"):
    """The GHG-related sentences of a target disclosure (target disclosures also cover water, waste and people)."""
    key = (c["id"], qid)
    if key not in _GHG_TEXT:
        t = c["values"].get(qid) or ""
        _GHG_TEXT[key] = " ".join(x for x in re.split(r"(?<=[.;\n])\s+", t) if _TARGET_GHG.search(x))
    return _GHG_TEXT[key]


_FOLLOWS: dict = {}


def _follows(c, n, test) -> bool:
    key = (c["id"], n)
    if key not in _FOLLOWS:
        _FOLLOWS[key] = bool(test(_ghg_text(c)))
    return _FOLLOWS[key]


def _target_segs(ctx, c, qid="286"):
    """Sentences of a target disclosure that are GHG targets with a year, scored once."""
    key = (c["id"], qid)
    if key not in _TARGET_SEGS:
        _TARGET_SEGS[key] = [(g, _sentence_score(g) + (3 if _TARGET_QTY.search(g["text"]) else 0))
                             for g in ctx.index.by_cell.get((c["id"], qid), [])
                             if _TARGET_GHG.search(g["text"]) and _YEAR.search(g["text"])]
    return _TARGET_SEGS[key]


def _target_practice(ctx, others, scope, sid, me, focus=None):
    a, kb = ctx.a, ctx.kb
    qid = "286"
    have = [c for c in others if _ghg_text(c)]
    widened = False
    if len(have) < 5 and sid:
        have = [c for c in kb.companies if _ghg_text(c) and (not me or c["id"] != me["id"])]
        widened = True
    N = len(have)
    where = f"{scope} companies" if scope and not widened else "companies"
    a.kicker = scope or "All companies"
    a.title = "Good practice: setting GHG targets" + (f" for {SCOPE_NAME[[k for k, v in FOCUS.items() if v is focus][0]]}" if focus else "")
    mshort = short_name(me["name"]) if me else None
    if not have:
        a.status = "partial"
        a.p(f"No company{' in ' + scope if scope else ''} disclosed a GHG target for FY 2024-25.")
        return
    rows = [(d, sum(1 for c in have if _follows(c, n, d["test"]))) for n, d in enumerate(TARGET_PRACTICES)]
    a.p("A strong GHG target is specific: it says how much will be cut, by which year, from which base year and for which "
        "scopes, and it is tied to net zero. The seven practices below are each explained with a real target as an example.")
    if widened:
        a.note("context", f"Few {scope} companies disclosed GHG targets, so examples come from all companies.")
    items, details, examples, used, seen = [], [], [], set(), set()
    for d, k in rows:
        items.append(f"**{d['title']}**")
        details.append([{"label": "What it means", "text": d["what"]}, {"label": "Why it matters", "text": d["why"]}])
        best = None
        for c in have:
            for g, base_sc in _target_segs(ctx, c, qid):
                t = g["text"]
                if not d["test"](t) or (focus and not focus[0].search(t)) or _gist(t) in seen:
                    continue
                sc = (base_sc - (12 if c["id"] in used else 0) + (2 if sid and c["sector"] == sid else 0)
                      - (6 if _VAGUE_START.match(t.strip()) else 0) + (4 if d.get("prefer") and d["prefer"].search(t) else 0)
                      - _shape(t), c["name"].lower())
                if best is None or sc > best[0]:
                    best = (sc, c, g)
        if best:
            _, c, g = best
            used.add(c["id"])
            seen.add(_gist(g["text"]))
            a.company_ref(c)
            examples.append({"who": short_name(c["name"]) + (f" ({kb.sector_of(c)['name']})" if sid and c["sector"] != sid else ""),
                             "text": _clip(g["text"], 230), "cite": a.c_filing(c, qid)})
        else:
            examples.append(None)
    a.block("points", title="The practices, explained", items=items, details=details, examples=examples, numbered=True)
    own = _ghg_text(me) if me else ""
    a.c_calc("How common each practice is", f"Companies whose target disclosure shows the practice ÷ the {N} {where} whose "
             f"targets include GHG or energy goals", note="A practice is counted when the target disclosure states it. "
             "A statement is not a verified result.")
    a.block("bars", title="How common each practice is", unit="% of companies", max=100,
            subtitle=f"Share of the {N} {where} with GHG or energy targets, FY 2024-25",
            focus_label=f"In {mshort}'s target" if own else None,
            rows=[{"label": d["short"], "value": round(100 * k / N, 1), "display": f"{100 * k / N:.0f}%",
                   "full": f"{k} of {N} companies", "highlight": bool(own and d["test"](own))} for d, k in rows],
            export=export("How common each practice is", ["Practice", "Companies following it", "Companies with GHG targets", "Share (%)"],
                          [[d["title"], k, N, round(100 * k / N, 1)] for d, k in rows]))
    if me:
        a.company_ref(me)
        cite = a.c_filing(me, qid)
        if not own:
            a.p(f"{mshort} has not disclosed a GHG or energy target for FY 2024-25 {cite}. The first steps are listed below.")
        a.block("checklist", title=f"How {mshort}'s target measures up", items=[
            {"label": d["title"], "value": bool(own and d["test"](own)),
             "sub": "In its target disclosure" if own and d["test"](own) else "Next step: " + d["step"], "cite": cite}
            for d, _ in rows])
    shown = list(dict.fromkeys(e["who"].split(" (")[0] for e in examples if e))
    full = [quote_item(ctx, c, qid) for c in have if short_name(c["name"]) in shown][:3]
    if full:
        a.block("quotes", items=full, collapsed=True, title="Full disclosures",
                summary=f"Read the full target disclosures from {join([it['short'] for it in full])}")
    a.context.update({"metric": "targets", "sector": sid, "companies": [me["id"]] if me else []})
    a.follow(f"What are {mshort}'s targets?" if me else None, f"Which {scope + ' ' if scope else ''}companies mention SBTi?",
             "Best practices for reducing emissions" + (f" in {scope}" if scope else ""))
