"""Query understanding: linker + neural intent model + deterministic rules.

The model proposes an intent; explicit rules override it where the text is
unambiguous (a second company means comparison, "what if" means simulation,
an off-topic term means refusal). Every rule that fires is recorded in the
plan trace so the user can see exactly how the question was understood.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .lexicon import WEAK_PHRASES
from .linker import Linker
from .model import IntentModel
from .normalize import mask, prep, tokenize

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
HARD_OFFTOPIC = {"FIN", "PEOPLE", "FUTURE", "WEB", "GENERAL"}
COMPANY_INTENTS = {"company_profile", "company_metric", "peer_benchmark", "peer_list", "simulate", "set_lens"}

# "my company is X", "I work at X", "answer as X": sets the user's company
RE_LENS = re.compile(r"\b(i am|i'm|im|i work|i'm working|we are|we're|i represent|representing|"
                     r"(?:my|our) (?:company|firm|employer|organi[sz]ation|business) is|set .{1,40} as (?:my|our)|"
                     r"(?:switch|change|set) (?:my |our |the )?(?:company|lens|focus) to|view as|answer as(?: if)?|"
                     r"use .{1,40} as (?:my|our) company)\b")
RE_CLEAR_LENS = re.compile(r"\b(clear|remove|reset|forget|unset|stop using)\b.{0,20}\b(my company|our company|company|lens)\b")
# First-person references that stand for the user's company. The first match is
# replaced by the company name, later ones by "its".
RE_MINE = [
    (re.compile(r"\b(?:my|our)\s+(?:own\s+)?(?:company|firm|organi[sz]ation|business|employer)(?:'s|’s)?(?=\W|$)", re.I), "{N}"),
    (re.compile(r"\b(how|where|what)\s+am\s+i\b", re.I), r"\1 is {N}"),
    (re.compile(r"\bam\s+i\b", re.I), "is {N}"),
    (re.compile(r"\b(do|did|have|should|can|could|would|will)\s+i\b", re.I), r"\1 {N}"),
    (re.compile(r"\bi\s+(stand|rank|compare|emit|perform|reduce|report|disclose)\b", re.I), r"{N} \1"),
    (re.compile(r"\b(?:we|ours|ourselves)\b", re.I), "{N}"),
    (re.compile(r"(?<!tell )(?<!show )(?<!give )(?<!let )(?<!help )(?<!send )\bus\b"), "{N}"),
    (re.compile(r"\b(?:my|our)\b(?!\s+(?:question|query|opinion|understanding|view|request|name|friend|team))", re.I), "{N}"),
]
RE_INFOGRAPHIC = re.compile(r"\b(infographics?|info graphic|poster|one[- ]pager|fact ?sheet|visual summary|summary card|"
                            r"snapshot card|social(?: media)? post|post[- ]style|shareable (?:image|visual|card))\b")
RE_PEER_NOUN = re.compile(r"\b(peers?|competitors?|peer group|peer set|peer companies|comparable companies|rivals?)\b")
RE_PEER_VERB = re.compile(r"\b(compare|compares|compared|comparison|analysis|analyse|analyze|versus|vs|against|benchmark|stand|stands|stack|fare|fares|"
                          r"perform|performs|performing|position|rank|ranks|better|worse|ahead|behind|lag|lead|"
                          r"how do|how does|how am|how are|how is|relative to|than)\b")
# "how well does X do with respect to peers", "X against its competitors": an evaluation, not a request for names
RE_PEER_EVAL = re.compile(r"\b(how|well|compar\w*|analysis|analy[sz]e|versus|vs|against|benchmark\w*|stand\w*|stack\w*|fare\w*|"
                          r"perform\w*|position\w*|rank\w*|better|worse|ahead|behind|lag\w*|lead\w*|relative|respect|"
                          r"doing|do|does|did|evaluat\w*|assess\w*|than|where|measure\w*|match\w*)\b")
# "how does X stack up", "where does X stand in its sector": peers are implied
RE_PEER_IMPLIED = re.compile(r"\b(stacks? up|measures? up|fares?|faring|stands? (?:in|within|among)|standing (?:in|within|among)|"
                             r"(?:against|versus|vs|relative to|compared (?:to|with)) (?:the |its |our )?(?:sector|industry|others|rest)|"
                             r"(?:in|within) (?:its|our|the) (?:sector|industry))\b")
RE_PEER_ASK = re.compile(r"\b(who|which|list|names?|show|give|tell|identify|enumerate|what are|display|how many)\b")
RE_DEFINE = re.compile(r"\b(define|definition|meaning of|mean|means|meant|stand for|stands for|difference between|"
                       r"explain what|what is meant|what exactly (is|are)|in simple terms)\b")
RE_MARKET = re.compile(r"\b(how many|number of|count of|total|overall|all companies|companies|sector|sectors|sector wise|"
                       r"industry|industries|market|india|across|average|median|top|highest|lowest|largest|biggest|"
                       r"smallest|most|least|best|worst|rank|ranking|list|which|who|everyone|each)\b")
RE_ADVICE = re.compile(r"\b(best practices?|practices|examples?|learn|adopt|improve|ideas|inspiration|ways to|how (can|do|should|could)|"
                       r"what (can|should|could))\b")
FRACTIONS = [(re.compile(r"\b(halve[sd]?|halving|by half|in half|by a half)\b"), 50.0), (re.compile(r"\b(a|one) third\b"), 33.3),
             (re.compile(r"\b(a|one) quarter\b"), 25.0), (re.compile(r"\b(a|one) fifth\b"), 20.0),
             (re.compile(r"\b(a|one) tenth\b"), 10.0)]
RE_COUNT = re.compile(r"\b(how many|number of|count of|count|which|who|list|share of|proportion|percentage)\b")
RE_PLEDGE = re.compile(r"\b(netzero|carbon neutral\w*|science based|sbti?)\b")
RE_SCORE_WORD = re.compile(r"\b(score|scores|scorecard|rating|ratings|rated|index|maturity|grade|grading)\b")
RE_BY_SECTOR = re.compile(r"\b(by sector|sector wise|sectorwise|per sector|each sector|across sectors|sector by sector|"
                          r"which sectors?|sector split|sector breakdown|by industry)\b")
RE_SIM = re.compile(r"\b(what if|what-if|simulate|simulation|scenario|suppose|imagine|assume|"
                    r"if .{1,50}\b(cut|cuts|reduce|reduces|reduced|lower|lowers|lowered|decrease|decreases|increase|increases)\b|"
                    r"need to (cut|reduce|lower)|would need to)")
RE_PRONOUN = re.compile(r"\b(it|its|it's|they|their|them|this company|that company|the company|same company|"
                        r"these companies|those companies|he|she|this one|that one)\b")
RE_FOLLOW = re.compile(r"^(and|what about|how about|also|now|same for|then|ok and|and for|and in|what of)\b")
RE_NEG = re.compile(r"\b(without|don't|dont|do not|does not|doesn't|did not|didn't|lack|lacks|lacking|missing|"
                    r"not|no|haven't|hasn't|never|fail|fails|absent|skip|skips|skipping|omit|omits)\b")
RE_DECR = re.compile(r"\b(reduc\w*|decreas\w*|cut|cuts|lower\w*|fell|fall\w*|declin\w*|drop\w*|improvers?|go(?:es|ing)? down|went down)\b")
RE_INCR = re.compile(r"\b(increas\w*|rose|rise|rising|grew|grow\w*|higher|went up|go(?:es|ing)? up|jump\w*)\b")
RE_HIGH = re.compile(r"\b(highest|largest|biggest|most|top|maximum|greatest|heaviest|major)\b")
RE_LOW = re.compile(r"\b(lowest|least|smallest|minimum|fewest|bottom|lightest)\b")
RE_BEST = re.compile(r"\b(best|cleanest|greenest|leading|leaders?|strongest|top performers?|top rated|highest scoring|"
                     r"most efficient|exemplary)\b")
RE_WORST = re.compile(r"\b(worst|dirtiest|laggards?|weakest|poorest|most polluting|lowest scoring|least efficient)\b")
RE_CLEAN = re.compile(r"\b(dirtiest|cleanest|greenest|most polluting|least polluting|biggest polluters?)\b")
RE_DIRTY = re.compile(r"\b(dirtiest|most polluting|biggest polluters?)\b")
RE_EMITTER = re.compile(r"\b(emitters?|polluters?|emitting)\b")
RE_PY = re.compile(r"\b(last year|previous year|prior year|fy ?24|2023-24|2023 24|fy 2023-24)\b")
RE_FY_RANGE = re.compile(r"\b(20\d{2})\s*[-/]\s*(\d{2}|20\d{2})\b")
RE_FY_SHORT = re.compile(r"\bfy\s*'?\s*(\d{2}|20\d{2})\b", re.I)


def fiscal_starts(text: str) -> list[int]:
    """Start years of fiscal years mentioned (FY 2024-25 -> 2024, FY25 -> 2024)."""
    out = []
    t = text.lower()
    for m in RE_FY_RANGE.finditer(t):
        out.append(int(m.group(1)))
    t = RE_FY_RANGE.sub(" ", t)
    for m in RE_FY_SHORT.finditer(t):
        y = int(m.group(1))
        y = y if y > 1000 else 2000 + y
        out.append(y - 1)
    return out


# Two metric mentions that together mean one more specific metric.
COMBOS = [
    ({"ghg_assurance", "scope3"}, "scope3_assurance"),
    ({"scope3", "intensity"}, "scope3_intensity"),
    ({"scope1", "intensity"}, "intensity"),
    ({"scope2", "intensity"}, "intensity"),
    ({"scope12", "intensity"}, "intensity"),
    ({"targets", "target_performance"}, "target_performance"),
    ({"policy", "board_approval"}, "board_approval"),
    ({"policy", "policy_link"}, "policy_link"),
    ({"policy", "procedures"}, "procedures"),
    ({"policy", "value_chain"}, "value_chain"),
    ({"policy", "policy_assessment"}, "policy_assessment"),
    ({"scope12", "ghg_assurance"}, "ghg_assurance"),
    ({"scope12", "projects"}, "projects"),
    ({"scope12", "targets"}, "targets"),
    ({"scope3", "scope3_reported"}, "scope3_reported"),
]


# ---- in-context learning: statements that teach the conversation something
RE_FORGET = re.compile(r"\b(forget|reset|clear|remove|drop)\b.{0,20}\b(preferences|preference|peer group|peers|settings|"
                       r"definitions|what i (said|told you))\b")
RE_PEER_PREF = re.compile(r"\b(my|our|its)\s+(peers|peer group|peer set|competitors|comparables|comparison set|benchmark set)\s+"
                          r"(are|is|include|includes|should be|will be)\b|\b(use|treat|consider|set)\b.{1,120}\bas\s+(my|our|the)\s+"
                          r"(peers|peer group|competitors|comparison set)\b|\bset\s+(my|our)\s+(peer group|peers)\s+to\b")
RE_EMIS_PREF = re.compile(r"\b(by|when i say|whenever i say|if i say|when i ask about|when i mention)\s+(emissions|emission|carbon|ghg|"
                          r"footprint|carbon emissions|ghg emissions|carbon footprint)\b,?\s*(i mean|i am referring to|i refer to|"
                          r"means|use|refers to|=|assume)\b(.*)$")
RE_N_PREF = re.compile(r"\b(always|by default|from now on|default to)\b.{0,40}\btop\s+(\d{1,2})\b|\btop\s+(\d{1,2})\b.{0,40}"
                       r"\b(by default|from now on|always)\b")
RE_COMPARE_WORD = re.compile(r"\b(compare|compared|vs|versus|against|than|with)\b")
GENERIC_EMISSIONS = {"emissions", "emission", "ghg", "ghg emissions", "carbon", "carbon emissions", "co2", "co2 emissions",
                     "greenhouse gas emissions", "greenhouse gases", "total emissions", "total ghg emissions",
                     "carbon footprint", "emitters", "emitter", "emitting", "emit", "emits", "absolute emissions",
                     "operational emissions", "pollutes most"}
PREF_METRICS = {"scope12": "Scope 1+2 emissions", "scope1": "Scope 1 emissions", "scope2": "Scope 2 emissions",
                "scope3": "Scope 3 emissions", "intensity": "Scope 1+2 intensity"}


@dataclass
class Plan:
    query: str
    intent: str = "unknown"
    confidence: float = 0.0
    companies: list = field(default_factory=list)
    ambiguous: list = field(default_factory=list)
    absent: list = field(default_factory=list)
    unknown_names: list = field(default_factory=list)
    sector: str | None = None
    sectors: list = field(default_factory=list)
    metric: str | None = None
    metrics: list = field(default_factory=list)
    offtopic: list = field(default_factory=list)
    tech: list = field(default_factory=list)
    keywords: list = field(default_factory=list)
    n: int | None = None
    pct: float | None = None
    extreme: str | None = None        # high | low (of the value)
    quality: str | None = None        # best | worst
    change: str | None = None         # decreased | increased
    negated: bool = False
    period: str = "CY"
    fy_out_of_range: str | None = None
    followup: bool = False
    used_context: dict = field(default_factory=dict)
    rules: list = field(default_factory=list)
    model: dict = field(default_factory=dict)
    masked: str = ""
    prefs: dict = field(default_factory=dict)          # preferences learned in this conversation
    learned: dict = field(default_factory=dict)        # what this turn taught
    neighbors: list = field(default_factory=list)      # few-shot exemplars nearest to the query
    lens: str | None = None                            # the user's own company, if set
    resolved_query: str | None = None                  # the question with "we/our/my" replaced by that company
    generic_emissions: bool = False                    # "emissions" without naming a scope
    by_sector: bool = False                            # asks for a breakdown by sector
    infographic: bool = False

    def to_dict(self):
        return asdict(self)


class Parser:
    def __init__(self, kb):
        self.kb = kb
        self.model = IntentModel(ARTIFACTS)
        self.linker = Linker(kb, known_words=self.model.known_words)
        self.name_tokens = {c["id"]: set(tokenize(prep(c["name"]))) for c in kb.companies}
        self.common_words = set(kb.meta.get("english_name_tokens", []))
        self._load_exemplars()

    # ------------------------------------------------------------------ few-shot retrieval
    def _load_exemplars(self):
        """Embed a bank of labelled example questions with the model's own encoder.

        At inference the nearest examples act as few-shot context: when the
        model is unsure, a similarity-weighted vote of its nearest labelled
        neighbours decides. The bank is versioned with the model, so this
        stays deterministic.
        """
        path = ARTIFACTS / "exemplars.jsonl"
        self.exemplars, self.ex_matrix = [], None
        if not path.exists():
            return
        import json
        import numpy as np
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        vecs = []
        for r in rows:
            toks, _, _ = mask(self.linker.link(r["q"]).masked)
            vecs.append(self.model.embed(" ".join(toks)))
            self.exemplars.append(r)
        self.ex_matrix = np.stack(vecs)

    def _neighbors(self, masked: str, k: int = 5):
        if self.ex_matrix is None:
            return []
        import numpy as np
        sims = self.ex_matrix @ self.model.embed(masked)
        order = np.argsort(-sims, kind="stable")[:k]
        return [(self.exemplars[int(i)]["q"], self.exemplars[int(i)]["intent"], round(float(sims[i]), 3)) for i in order]

    def _clean_prefs(self, prefs: dict | None) -> dict:
        prefs = dict(prefs or {})
        out = {}
        peers = [c for c in prefs.get("peers", []) if c in self.kb.by_id]
        if peers:
            out["peers"] = peers
        if prefs.get("emissions") in PREF_METRICS:
            out["emissions"] = prefs["emissions"]
        n = prefs.get("n")
        if isinstance(n, int) and 1 <= n <= 50:
            out["n"] = n
        aliases = {t: c for t, c in (prefs.get("aliases") or {}).items() if isinstance(t, str) and c in self.kb.by_id}
        if aliases:
            out["aliases"] = aliases
        return out

    # ------------------------------------------------------------------ helpers
    def _pick_metric(self, ents, text):
        if not ents:
            return None, []
        ids = list(dict.fromkeys(e.value for e in ents))
        strong = [e.value for e in ents if e.text not in WEAK_PHRASES]
        order = list(dict.fromkeys(strong + ids))
        present = set(order)
        for parts, result in COMBOS:
            if parts <= present:
                order = [result] + [m for m in order if m not in parts and m != result]
                present = set(order)
        return order[0], order

    def _group_candidates(self, token: str):
        hits = sorted(cid for cid, toks in self.name_tokens.items() if token in toks)
        return hits

    # ------------------------------------------------------------------ the user's own company
    def _first_person(self, query: str) -> bool:
        return any(rx.search(query) for rx, _ in RE_MINE)

    def _personalise(self, query: str, lens: str | None) -> tuple[str, bool]:
        """Replace "we / our / my company" with the user's company so the rest of the pipeline sees a named company."""
        if not lens:
            return query, False
        low = prep(query)
        if RE_FORGET.search(low) or RE_PEER_PREF.search(low) or RE_EMIS_PREF.search(low) or RE_N_PREF.search(low) \
                or RE_CLEAR_LENS.search(low):
            return query, False
        link = self.linker.link(query)
        named = link.of("company") + link.of("absent")
        if named and RE_LENS.search(low):
            return query, False                      # "my company is X" sets the company instead
        if named and not RE_COMPARE_WORD.search(low):
            return query, False                      # the question is about another company
        name = self.kb.by_id[lens]["name"]
        state = {"n": 0}

        def sub(tmpl):
            def f(m):
                state["n"] += 1
                return m.expand(tmpl).replace("{N}", name if state["n"] == 1 else "its")
            return f

        out = query
        for rx, tmpl in RE_MINE:
            out = rx.sub(sub(tmpl), out)
        return (out, True) if state["n"] else (query, False)

    # ------------------------------------------------------------------ main
    def parse(self, query: str, context: dict | None = None) -> Plan:
        context = context or {}
        lens = context.get("lens") if context.get("lens") in self.kb.by_id else None
        resolved, personal = self._personalise(query, lens)
        p = self._parse(resolved, context, lens, first_person=self._first_person(query))
        p.query = query
        p.lens = lens
        if personal:
            p.resolved_query = resolved
            if lens in p.companies:
                p.used_context["lens"] = lens
                p.rules.append("'we / our / my' read as your company")
        return p

    def _parse(self, query: str, context: dict, lens: str | None, first_person: bool = False) -> Plan:
        p = Plan(query=query)
        low = prep(query)
        link = self.linker.link(query)
        toks, nums, pcts = mask(link.masked)
        p.masked = " ".join(toks)
        pred = self.model.predict(p.masked)
        p.model = pred
        p.intent, p.confidence = pred["intent"], pred["intent_p"]
        p.prefs = self._clean_prefs(context.get("prefs"))
        p.neighbors = self._neighbors(p.masked)
        pred["neighbors"] = p.neighbors[:3]
        top_q, top_lab, top_sim = p.neighbors[0] if p.neighbors else (None, None, 0.0)
        if top_sim >= 0.97 and top_lab != p.intent:
            self._set(p, top_lab, f"few-shot: near-identical labelled example ({top_sim:.2f})")
        elif p.confidence < 0.55 and p.neighbors:
            votes: dict[str, float] = {}
            for _, lab, sim in p.neighbors:
                if sim >= 0.5:
                    votes[lab] = votes.get(lab, 0.0) + sim
            if votes:
                best = max(sorted(votes), key=lambda l: votes[l])
                if best != p.intent and votes[best] / sum(votes.values()) >= 0.6:
                    self._set(p, best, f"few-shot: nearest labelled examples favour {best} (model was {p.confidence:.2f})")

        # ---- entities
        for e in link.of("company"):
            if len(e.value) == 1:
                if e.value[0] not in p.companies:
                    p.companies.append(e.value[0])
            else:
                p.ambiguous.append({"text": e.text, "ids": list(e.value)})
        p.absent = [e.value for e in link.of("absent")]
        p.sectors = list(dict.fromkeys(e.value for e in link.of("sector")))
        p.sector = p.sectors[0] if p.sectors else None
        p.metric, p.metrics = self._pick_metric(link.of("metric"), low)
        p.offtopic = list(dict.fromkeys(e.value for e in link.of("offtopic")))
        p.tech = list(dict.fromkeys(e.value for e in link.of("tech")))
        p.keywords = re.findall(r'"([^"]{2,60})"', query)
        p.n = next((int(x) for x in nums if 1 <= x <= 50 and float(x).is_integer()), None)
        p.pct = pcts[0] if pcts else None
        if p.pct is None:
            for rx, val in FRACTIONS:
                if rx.search(low):
                    p.pct = val
                    break
        p.negated = bool(RE_NEG.search(low))
        p.change = "decreased" if RE_DECR.search(low) else "increased" if RE_INCR.search(low) else None
        p.period = "PY" if RE_PY.search(low) else "CY"
        p.by_sector = bool(RE_BY_SECTOR.search(low))
        p.infographic = bool(RE_INFOGRAPHIC.search(low))
        p.generic_emissions = p.metric == "scope12" and not re.search(r"\bscope(12|1|2)\b", low)
        for start in fiscal_starts(query):
            if start not in (2023, 2024):
                p.fy_out_of_range = f"FY {start}-{str(start + 1)[2:]}"
        if p.metric == "scope3" and re.search(r"\b(report|reports|reporting|reported|disclose|discloses|disclosing)\b", low) \
                and p.intent in ("aggregate", "screen"):
            p.metric, p.rules = "scope3_reported", p.rules + ["scope3 + reporting verb -> scope3_reported"]

        # unknown words that might be a company the user named
        for u in link.unknown:
            if u in self.model.known_words or len(u) < 3 or u in self.common_words:
                continue
            group = self._group_candidates(u)
            if len(group) == 1 and group[0] not in p.companies:
                p.companies.append(group[0])
                p.rules.append(f"'{u}' uniquely names one company")
            elif len(group) > 1:
                p.ambiguous.append({"text": u, "ids": group})
            elif not (p.infographic and RE_INFOGRAPHIC.fullmatch(u)):
                p.unknown_names.append(u)

        # ---- in-context learning: earlier clarification choices
        aliases = p.prefs.get("aliases", {})
        still = []
        for amb in p.ambiguous:
            cid = aliases.get(amb["text"])
            if cid in amb["ids"]:
                if cid not in p.companies:
                    p.companies.append(cid)
                p.rules.append(f"'{amb['text']}' resolved from your earlier choice in this conversation")
            else:
                still.append(amb)
        p.ambiguous = still
        pending = context.get("pending") or {}
        if pending.get("text") and pending.get("ids"):
            chosen = [c for c in p.companies if c in pending["ids"]]
            if len(chosen) == 1:
                p.prefs.setdefault("aliases", {})[pending["text"]] = chosen[0]
                p.learned["alias"] = {"text": pending["text"], "id": chosen[0]}
                p.rules.append(f"learned: '{pending['text']}' means {self.kb.by_id[chosen[0]]['name']}")

        # ---- in-context learning: statements that set a preference
        learned = self._learn(low, p)
        if learned:
            p.learned.update(learned)
            p.rules.append("in-context learning: " + ", ".join(sorted(learned)))
            self._set(p, "set_pref", "the question teaches a preference")
            return p

        # ---- direction words
        if RE_BEST.search(low):
            p.quality = "best"
        elif RE_WORST.search(low):
            p.quality = "worst"
        if RE_LOW.search(low):
            p.extreme = "low"
        elif RE_HIGH.search(low) or RE_EMITTER.search(low):
            p.extreme = "high"

        # "cleanest" / "dirtiest" compare emission efficiency, so default to intensity (size-neutral)
        if p.metric is None and RE_CLEAN.search(low):
            p.metric, p.metrics = "intensity", ["intensity"]
            p.quality = "worst" if RE_DIRTY.search(low) else "best"
            p.rules.append("cleanest/dirtiest -> emission intensity")

        # ---- scores and ratings are not offered; generic words like "performance" carry no metric
        wants_score = False
        if "index" in p.metrics:
            wants_score = bool(RE_SCORE_WORD.search(low))
            rest = [m for m in p.metrics if m != "index"]
            p.metric, p.metrics = (rest[0] if rest else None), rest
            p.rules.append("score/rating wording: no such measure is offered")

        # ---- "how many companies have net zero targets" is a search for that pledge, not a count of any target
        if p.metric == "targets" and not p.tech and not p.companies and p.intent in ("aggregate", "screen") and RE_COUNT.search(low):
            m = RE_PLEDGE.search(low)
            if m:
                p.tech = ["sbti" if m.group(1).startswith(("science", "sbt")) else "net zero"]
                p.rules.append("pledge named in a count question: searched in the disclosures")

        # ---- apply learned definitions
        pref_m = p.prefs.get("emissions")
        if pref_m and p.metric == "scope12" and p.generic_emissions:
            p.metric = pref_m
            p.metrics = [pref_m] + [m for m in p.metrics if m not in ("scope12", pref_m)]
            p.generic_emissions = False
            p.rules.append(f"learned definition: 'emissions' means {PREF_METRICS[pref_m]}")

        # ---- rules
        hard = [o for o in p.offtopic if o in HARD_OFFTOPIC]
        soft = [o for o in p.offtopic if o not in HARD_OFFTOPIC]
        has_metric = p.metric is not None
        if hard:
            self._set(p, "out_of_scope", f"hard guardrail: {', '.join(hard)}")
        elif soft and not has_metric and not p.tech:
            self._set(p, "out_of_scope", f"topic not covered: {', '.join(soft)}")
        elif p.infographic:
            self._set(p, "infographic", "asks for an infographic")
        elif p.intent == "out_of_scope" and (has_metric or p.tech) and p.confidence < 0.9:
            self._set(p, "company_metric" if (p.companies or p.ambiguous) else "aggregate",
                      "covered measure present, model refusal overridden")

        has_peers = bool(RE_PEER_NOUN.search(low))
        counting = bool(re.search(r"\bhow many\b", low))
        peer_eval = has_peers and not counting and bool(RE_PEER_EVAL.search(low) or RE_PEER_VERB.search(low))
        peer_list = has_peers and not has_metric and not peer_eval and (bool(RE_PEER_ASK.search(low)) or len(toks) <= 5)
        strict_define = bool(RE_DEFINE.search(low)) and (has_metric or not p.companies)
        if p.intent != "out_of_scope":
            if RE_CLEAR_LENS.search(low) and not p.companies:
                self._set(p, "clear_lens", "asks to stop answering as a company")
                return p
            if RE_LENS.search(low) and (p.companies or p.ambiguous):
                self._set(p, "set_lens", "self-identification phrase")
            elif wants_score and (not has_metric or p.intent in ("explain", "ranking", "aggregate", "screen", "report_insights")):
                self._set(p, "no_scores", "asks for a score or rating")
                return p
            elif RE_SIM.search(low) and (p.companies or RE_PRONOUN.search(low) or first_person):
                self._set(p, "simulate", "what-if phrase")
            elif p.infographic:
                pass
            elif len(p.companies) >= 2 and p.intent not in ("best_practice", "text_search"):
                self._set(p, "compare", "two or more companies named")
            elif peer_list and p.intent not in ("best_practice", "text_search"):
                self._set(p, "peer_list", "asks who the peers are")
            elif peer_eval and p.intent not in ("best_practice", "text_search", "peer_benchmark", "simulate"):
                self._set(p, "peer_benchmark", "asks how a company does against its peers")
            elif RE_PEER_IMPLIED.search(low) and len(p.companies) == 1 and not p.sector \
                    and p.intent in ("company_profile", "company_metric", "ranking", "aggregate", "explain", "greeting", "unknown"):
                self._set(p, "peer_benchmark", "asks how a company does within its sector")
            elif strict_define and not p.companies:
                self._set(p, "explain", "asks what a term means")
            elif p.tech and p.intent in ("screen", "aggregate", "ranking", "company_metric", "best_practice") and not p.companies:
                self._set(p, "text_search", "technology keyword")
            elif p.keywords and not p.companies:
                self._set(p, "text_search", "quoted keyword")

        strong_metric = any(e.text not in WEAK_PHRASES for e in link.of("metric"))
        if p.intent == "company_profile" and strong_metric and p.metric is not None and len(p.companies) == 1:
            self._set(p, "company_metric", "explicit metric named for one company")
        if p.intent == "greeting" and has_metric:
            self._set(p, "explain", "a measure with no other request")

        # ---- context carry-over (follow-ups)
        ctx_companies = [c for c in context.get("companies", []) if c in self.kb.by_id]
        short = len(toks) <= 6
        is_follow = bool(RE_FOLLOW.search(low)) or (short and bool(context.get("intent")))
        pronoun = bool(RE_PRONOUN.search(low))
        market = bool(RE_MARKET.search(low))

        if p.intent not in ("out_of_scope", "infographic"):
            only_metric = p.metric and not p.companies and not p.sector and not p.ambiguous
            only_company = p.companies and not p.metric and not p.sector
            only_sector = p.sector and not p.companies and not p.metric
            prev = context.get("intent")
            if is_follow and prev and not p.absent and not p.unknown_names and not first_person and p.intent != "peer_list":
                if only_metric and prev in ("company_metric", "compare", "peer_benchmark", "company_profile", "simulate",
                                            "peer_list", "infographic") and not strict_define and not market:
                    if ctx_companies:
                        p.companies = list(ctx_companies)
                        new = "compare" if len(ctx_companies) > 1 else ("company_metric" if prev in ("company_profile", "peer_list", "infographic") else prev)
                        self._set(p, new, "follow-up: new measure, same company")
                        p.used_context["companies"] = ctx_companies
                elif only_metric and prev in ("ranking", "aggregate", "screen", "best_practice", "sector_overview") and not strict_define:
                    if context.get("sector"):
                        p.sector = context["sector"]
                        p.used_context["sector"] = p.sector
                    self._set(p, "ranking" if prev == "sector_overview" else prev, "follow-up: new measure, same view")
                elif only_company and prev in ("company_metric", "peer_benchmark", "simulate", "company_profile", "peer_list"):
                    if context.get("metric") and prev not in ("company_profile", "peer_list"):
                        p.metric = context["metric"]
                        p.used_context["metric"] = p.metric
                    self._set(p, prev, "follow-up: same question, new company")
                elif only_company and prev == "compare" and ctx_companies:
                    p.companies = list(dict.fromkeys(ctx_companies + p.companies))
                    if context.get("metric"):
                        p.metric = context["metric"]
                    self._set(p, "compare", "follow-up: add company to comparison")
                elif only_sector and prev in ("ranking", "aggregate", "screen", "best_practice", "text_search", "sector_overview"):
                    if context.get("metric") and not p.metric:
                        p.metric = context["metric"]
                        p.used_context["metric"] = p.metric
                    if prev == "text_search" and context.get("tech"):
                        p.tech = context["tech"]
                    self._set(p, prev, "follow-up: same question, new sector")
                p.followup = bool(p.used_context) or any(r.startswith("follow-up") for r in p.rules)

            if p.intent in COMPANY_INTENTS and not p.companies and not p.ambiguous:
                if (pronoun or is_follow) and ctx_companies and not first_person:
                    p.companies = ctx_companies[:1]
                    p.used_context["companies"] = p.companies
                    p.rules.append("company taken from the conversation")
                elif p.absent or p.unknown_names:
                    pass  # handled as not-found by the engine
                elif p.sector:
                    self._set(p, {"company_profile": "sector_overview", "company_metric": "aggregate",
                                  "peer_benchmark": "ranking", "peer_list": "screen", "simulate": "sector_overview",
                                  "set_lens": "sector_overview"}[p.intent], "no company named, sector given")
                elif lens and not (market and p.intent == "company_metric"):
                    p.companies = [lens]
                    p.used_context["lens"] = lens
                    p.rules.append("no company named: answered for your company")
                elif ctx_companies and p.intent in ("company_metric", "peer_benchmark", "peer_list", "simulate"):
                    p.companies = ctx_companies[:1]
                    p.used_context["companies"] = p.companies
                    p.rules.append("company carried over from conversation")
                elif p.metric and p.intent == "company_metric" and not first_person:
                    self._set(p, "aggregate", "measure without company")

            # with your company set, a bare measure ("scope 3", "ghg emissions") means your company's figure
            if lens and not p.companies and not p.ambiguous and not p.absent and not p.unknown_names and not p.sector \
                    and p.metric and not market and not strict_define and not p.by_sector \
                    and p.intent in ("aggregate", "explain", "company_metric", "company_profile", "unknown"):
                p.companies = [lens]
                p.used_context["lens"] = lens
                self._set(p, "company_metric", "no company named: answered for your company")

            if p.intent == "best_practice" and not p.companies and first_person and lens:
                p.companies = [lens]
                p.used_context["lens"] = lens

            # "our emissions" with no company set: ask which company instead of guessing
            if first_person and not lens and not p.companies and not p.ambiguous and not p.sector and not p.absent \
                    and (p.intent in COMPANY_INTENTS or bool(RE_PEER_NOUN.search(low))
                         or (has_metric and p.intent in ("aggregate", "explain", "greeting", "unknown"))
                         or (p.intent == "best_practice" and not RE_ADVICE.search(low))):
                self._set(p, "need_company", "first-person question with no company set")

            if p.intent == "aggregate" and p.change and p.metric in (None, "scope12", "scope1", "scope2") and RE_COUNT.search(low):
                self._set(p, "screen", "counts companies by direction of change")
            if p.intent == "ranking" and p.n is None and p.prefs.get("n"):
                p.n = p.prefs["n"]
                p.rules.append(f"learned default: top {p.n}")

        if p.intent == "infographic":
            # named company > named sector > the company or sector being discussed > your company > the market
            whole = re.search(r"\b(all companies|all sectors|overall|whole market|the market|india|everything|all of them)\b", low)
            if not p.companies and not p.ambiguous and not p.sector and not p.absent and not p.unknown_names and not whole:
                if first_person and lens:
                    p.companies = [lens]
                    p.used_context["lens"] = lens
                elif ctx_companies:
                    p.companies = ctx_companies[:1]
                    p.used_context["companies"] = p.companies
                elif context.get("sector") in self.kb.sector_by_id:
                    p.sector = context["sector"]
                    p.used_context["sector"] = p.sector
                elif lens:
                    p.companies = [lens]
                    p.used_context["lens"] = lens
                elif first_person:
                    self._set(p, "need_company", "asks for their own infographic with no company set")

        # model topic as a fallback when the lexicon found no metric
        if p.metric is None and pred["topic"] not in ("none", "index") and pred["topic_p"] >= 0.75 and \
                p.intent in ("company_metric", "ranking", "aggregate", "screen", "best_practice", "compare",
                             "peer_benchmark", "simulate"):
            p.metric = pred["topic"]
            p.metrics = [p.metric]
            p.generic_emissions = p.metric == "scope12"
            p.rules.append(f"metric inferred by model topic head ({pred['topic_p']:.2f})")
        return p

    def _learn(self, low: str, p: Plan) -> dict:
        """Detect a statement that teaches the conversation something."""
        if RE_FORGET.search(low):
            p.prefs = {}
            return {"reset": True}
        out = {}
        if RE_PEER_PREF.search(low) and p.companies:
            p.prefs["peers"] = list(p.companies)
            out["peers"] = list(p.companies)
        m = RE_EMIS_PREF.search(low)
        if m:
            tail = m.group(4)
            for tok, mid in (("scope12", "scope12"), ("scope1", "scope1"), ("scope2", "scope2"), ("scope3", "scope3"),
                             ("intensity", "intensity")):
                if re.search(rf"\b{tok}\b", tail):
                    p.prefs["emissions"] = mid
                    out["emissions"] = mid
                    break
        m = RE_N_PREF.search(low)
        if m:
            n = int(m.group(2) or m.group(3))
            if 1 <= n <= 50:
                p.prefs["n"] = n
                out["n"] = n
        return out

    @staticmethod
    def _set(p: Plan, intent: str, why: str):
        if p.intent != intent:
            p.rules.append(f"{p.intent} -> {intent}: {why}")
        else:
            p.rules.append(f"confirmed {intent}: {why}")
        p.intent = intent
