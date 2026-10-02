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
                     r"(?:switch|change|set) (?:my |our |the )?(?:company|lens|focus) to|^(?:switch|change|move) to|"
                     r"view as|answer as(?: if)?|"
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
                            r"linkedin post|post (?:on|for|about)|tweet|"
                            r"snapshot card|social(?: media)? post|post[- ]style|shareable (?:image|visual|card))\b")
RE_PEER_NOUN = re.compile(r"\b(peers?|competitors?|competition|peer group|peer set|peer companies|comparable companies|rivals?|"
                          r"counterparts?|other players|industry players|similar companies|companies like (?:us|me|ours|<co>))\b")
RE_PEER_VERB = re.compile(r"\b(compare|compares|compared|comparison|analysis|analyse|analyze|versus|vs|against|benchmark|stand|stands|stack|fare|fares|"
                          r"perform|performs|performing|position|rank|ranks|better|worse|ahead|behind|lag|lead|"
                          r"how do|how does|how am|how are|how is|relative to|than)\b")
# "how well does X do with respect to peers", "X against its competitors": an evaluation, not a request for names
RE_PEER_EVAL = re.compile(r"\b(how|well|compar\w*|analysis|analy[sz]e|versus|vs|against|benchmark\w*|stand\w*|stack\w*|fare\w*|"
                          r"perform\w*|position\w*|rank\w*|better|worse|ahead|behind|lag\w*|lead\w*|relative|respect|"
                          r"doing|do|does|did|evaluat\w*|assess\w*|than|where|measure\w*|match\w*)\b")
# "how does X stack up", "where does X stand in its sector": peers are implied
RE_PEER_IMPLIED = re.compile(r"\b(benchmark\w*|stacks? up|measures? up|fares?|faring|stands? (?:in|within|among)|standing (?:in|within|among)|"
                             r"(?:against|versus|vs|relative to|compared (?:to|with)) (?:the |its |our )?(?:sector|industry|others|rest)|"
                             r"(?:in|within) (?:its|our|the) (?:sector|industry))\b")
RE_PEER_ASK = re.compile(r"\b(who|which|list|names?|show|give|tell|identify|enumerate|what are|display|how many)\b")
RE_DEFINE = re.compile(r"\b(define|definition|meaning of|mean|means|meant|stand for|stands for|difference between|"
                       r"explain what|what is meant|what exactly (is|are)|in simple terms|in simple words|"
                       r"what (?:is|are) .{0,30}\b(?:exactly|precisely|actually)$|"
                       r"how (?:to|do you|do i|does one|is|are) .{0,25}(?:calculat\w*|comput\w*|measured?|defined|worked out|estimated?))\b")
RE_WHAT_IS_METRIC = re.compile(r"^(?:what|whats|what s) (?:is|are) (?:a |an |the )?(?:scope(?:12|1|2|3)(?: (?:and )?scope(?:12|1|2|3))*"
                               r"(?: emissions?| intensity| ghg emissions?)?|(?:emissions?|ghg|carbon) intensity|intensity|"
                               r"(?:independent |external |third party )?assurance)$")
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
                          r"which sectors?|which industr(?:y|ies)|what sectors?|sector split|sector breakdown|by industry|"
                          r"industry wise|sectors? with|industr(?:y|ies) with|top \S* ?sectors|sectors by|sectors ranked|"
                          r"rank(?:ing)? (?:of )?(?:the )?sectors|"
                          r"(?:cleanest|dirtiest|greenest|best|worst|largest|biggest|smallest) (?:sector|industry))\b")
# ---- wording that asks for a more specific answer than the broad kind of question
RE_YESNO = re.compile(r"^(?:and |so |but |ok |okay |please |hey |hi |hello |also )*"
                      r"(?:do|does|did|is|are|was|were|has|have|had|can|could|will|would)\b")
RE_WHO = re.compile(r"\b(who|whom|which (?:agency|firm|auditor|assurer|company|provider|organi[sz]ation)|name of|"
                    r"assurer|assurance provider|verifier|auditor)\b")
RE_TREND = re.compile(r"\b(trends?|trajectory|year on year|year over year|yoy|y o y|over time|over the (?:last |past )?years?|"
                      r"chang(?:e|ed|es|ing)|(?:go|goes|going|gone|went|gone) (?:up|down)|increas(?:e|ed|es|ing)|"
                      r"decreas(?:e|ed|es|ing)|reduc(?:e|ed|es|ing)|ris(?:e|en|ing)|rose|fall(?:en|ing)?|fell|"
                      r"cut|cuts|cutting|slash(?:ed|ing)?|lower(?:ed|ing)|up or down|both years|two years|each year|"
                      r"year wise|yearwise|year by year|"
                      r"(?:last|previous|prior) year (?:vs|versus|and|to|against|compared (?:to|with)) (?:this|the current|current)|"
                      r"this year (?:vs|versus|and|against|compared (?:to|with)) (?:last|the previous|previous)|"
                      r"grow(?:n|ing|th)?|grew|declin(?:e|ed|ing)|dropp?(?:ed|ing)?|improv(?:ed|ing)|worsen(?:ed|ing)?|"
                      r"(?:compared (?:to|with)|vs|versus|against|from|since|than) (?:the )?(?:last|previous|prior) year|"
                      r"movement|moved)\b")
RE_TREND_VERB = re.compile(r"\b(reduc\w*|cut|cuts|cutting|lower\w*|decreas\w*|increas\w*|rais\w*)\b")
RE_HOW_WHAT = re.compile(r"\b(what|how|which|why|projects?|initiatives?|measures|steps|plans?|examples?|anything|"
                         r"something|doing|done|taking|efforts?|working|trying|planning)\b")
RE_PROFILE = re.compile(r"\b(about|profile|overview|summary|summari[sz]e|details?|everything|snapshot|tell me|full|"
                        r"complete|whole|picture|all about|at a glance|disclos\w*|report card|how is|how are|doing)\b")
RE_SCOPE_SPLIT = re.compile(r"\b(scopes\b(?! ?[123])|which (?:of )?(?:\S+ ){0,5}scopes?\b|scope (?:split|mix|breakdown|wise|composition)|"
                            r"split (?:of|by|between|across) (?:the )?scopes?|breakdown (?:of|by|across) (?:the )?scopes?|by scope|"
                            r"(?:biggest|largest|main|major|primary|top) (?:source|contributor|part|component|chunk)s?|"
                            r"where do(?:es)? (?:\S+ ){0,4}emissions come from|composition of (?:\S+ ){0,4}emissions|"
                            r"emissions? (?:profile|mix|composition|breakdown|split))\b")
RE_SCOPE_VS = re.compile(r"\b(vs|versus|compared?|comparison|than|relative|against|ratio|bigger|larger|smaller|more|less|"
                         r"times|multiple|higher|lower)\b")
RE_SHARE = re.compile(r"\b(share|percentage|percent|proportion|fraction|portion|contribut\w*|accounts? for|accounting for|"
                      r"how much of|what part of)\b")
RE_STAT = re.compile(r"\b(average|median|typical|avg|the mean|mean (?:value|of|emissions?|scope\w*|intensity))\b")
RE_STAT_NOT = re.compile(r"\b(compar\w*|above|below|higher|lower|than|versus|vs|against|better|worse|stand\w*)\b")
RE_FILTER_LOW = re.compile(r"\b(less|lower|fewer|smaller|below|under|cleaner|ahead of)\b")
RE_FILTER_HIGH = re.compile(r"\b(more|higher|greater|bigger|larger|above|over|exceed\w*)\b")
RE_FILTER_NEAR = re.compile(r"\b(similar|closest|nearest|comparable|same size|close to|like (?:us|ours))\b")
RE_FILTER_ASK = re.compile(r"\b(which|who|list|names?|how many|any|are there|show)\b")
RE_OWN_GROUP = re.compile(r"\b(sector|industry|peers?|competitors?|rivals?|peer group|class)\b")
RE_ADVISE = re.compile(r"\b(best practices?|good practices?|ideas?|suggest\w*|recommend\w*|advice|advise|tips|ways to|"
                       r"inspiration|learn (?:from|about)|lessons|"
                       r"how (?:can|could|should|do|does|to|might|would) .{0,50}\b(?:reduce|cut|lower|improve|decarboni[sz]e|"
                       r"bring down|curb|mitigate|shrink|do better)\b|"
                       r"what (?:can|should|could|must) (?!you\b).{0,50}\b(?:do|improve|learn|adopt|implement|change|focus)\b|"
                       r"what (?:does|do) (?:a |an )?good .{0,30}look like|good (?:example|target|disclosure)s?|"
                       r"how do (?:leading|top|the best|other) (?:companies|firms|peers))\b")
RE_HOW_USING = re.compile(r"\bhow (?:are|do|is|does|have|has) .{0,40}\b(?:using|use|adopting|adopt|deploying|implementing|approaching)\b")
RE_LEARN_FROM_CO = re.compile(r"(?:learn (?:from|about)|lessons from|take from|borrow from|copy from|adopt from|"
                              r"inspired by) (?:the |what )?<co>")
RE_GAPS = re.compile(r"\b(gaps?|missing|fall(?:ing)? short|shortfalls?|weak(?:ness|nesses| spots?| areas?| points?)|"
                     r"improve (?:\S+ ){0,3}(?:disclosures?|reporting|brsr|report)|"
                     r"(?:not|n't|yet to|have not|has not|haven't|hasn't) (?:\S+ ){0,2}(?:disclos\w+|report\w*)|"
                     r"what (?:else )?(?:should|can|could|do|does) (?:\S+ ){0,4}(?:disclose|report|add)|"
                     r"areas? (?:to|of|for) improve\w*|complete(?:ness)?|blind spots?|"
                     r"needs? to (?:improve|fix|work on|address)|where (?:can|should|could) (?:\S+ ){1,4}improve)\b")
RE_IT = re.compile(r"\b(it|its|the company|this company|that company|same company|this one|that one)\b")
RE_THEM = re.compile(r"\b(them|they|those|these|their|ones)\b")
PEER_VIEWS = ("peer_filter", "peer_search", "peer_change", "focus_rank")
CARRY_VIEWS = ("stat", "total_change", "sector_share", "listing")
RE_BOARD = re.compile(r"\b(tell|brief|briefing|present|presentation|update|report to|summary for|talking points|key points)\b"
                      r".{0,40}\b(board|management|leadership|investors?|directors|boss|team)\b")
RE_ALL_COMPANIES = re.compile(r"\b(?:list|show|names?|which|all|browse)\b.{0,25}\b(?:companies|firms)\b|\bcompanies (?:covered|list)\b")
RE_TOTALLED = re.compile(r"\b(total|overall|includ\w+|plus|together|all (?:the )?scopes|everything|altogether)\b")
RE_DOING = re.compile(r"\bwhat (?:are|is|have|has|do|does|did) .{0,70}\b(doing|done|taking|taken|working on|up to|"
                      r"do about|do to|do for|do on|did about|did to)\b")
RE_PEER_DEF = re.compile(r"\b(what (?:is|are) (?:a |the )?peers?(?: group)?$|definition of (?:a )?peers?|"
                         r"how (?:do you|are|is) .{0,25}(?:pick|choose|chosen|select|selected|decide|decided|defined?|determined?) "
                         r".{0,15}(?:peers?|competitors?|peer group)|how (?:are|is) (?:the )?(?:peers?|peer group) "
                         r"(?:picked|chosen|selected|decided|defined|determined))")
RE_EVAL_ADJ = re.compile(r"\b(high|low|good|bad|ok|okay|fine|normal|reasonable|large|small|too much|a lot|efficient|"
                         r"inefficient|acceptable|excessive)\b")
RE_SIDE = re.compile(r"(?:ahead of|behind|above|below|than|closest to|nearest to|similar to|close to|like|bigger than|"
                     r"smaller than|larger than) <co>|<co> (?:closest|nearest|most similar) to")
RE_OWN_SECTOR = re.compile(r"(?<!in )(?<!within )(?<!among )(?<!of )(?<!against )(?<!to )(?<!with )(?<!than )"
                           r"<co> (?:s )?(?:sector|industry)\b")
RE_OTHERS = re.compile(r"\b(others|other companies|other firms|everyone else|rest of the (?:sector|industry))\b")
RE_WHATIS = re.compile(r"^(?:what|whats|what s) (?:is|are|does|do)? ?(?:a |an |the )?"
                       r"(netzero|carbon neutral\w*|sbti?|science based targets?|brsr|ghg|tco2e?|co2e?|greenhouse gas(?:es)?)"
                       r"(?: target| targets| emissions?)?(?: mean| stand for| means)?$")
RE_SECTOR_LIST = re.compile(r"\b(how many (?:sectors|industries)|number of (?:sectors|industries)|"
                            r"list (?:of |all |the |all the )?(?:sectors|industries)|(?:sectors|industries) (?:list|names|covered)|"
                            r"(?:which|what) (?:sector|industry) has the (?:most|fewest|least|largest number of|highest number of|"
                            r"smallest number of) companies|companies (?:per|in each|by) (?:sector|industry)|"
                            r"(?:which|what) (?:sectors|industries) (?:are|do you) (?:covered|cover|included|available|there))\b|"
                            r"^(?:show |name |give me |what are |which are )?(?:all |the |all the )?(?:sectors|industries)$")
RE_LISTING = re.compile(r"\b(table|tabulate|list|company wise|companywise|each company|company by company)\b")
RE_THANKS = re.compile(r"^(?:ok |okay |great |cool |nice |perfect |awesome |got it |many )*"
                       r"(?:thanks|thank you|thankyou|thx|ty|cheers|great|cool|nice|perfect|awesome|got it|ok|okay|"
                       r"that helps|helpful|good|fine|alright)(?: a lot| so much| very much| you)?$")
RE_ABOUT_ME = re.compile(r"\b(who (?:are|r) you|what (?:are|r) you|who (?:made|built|created|developed) (?:you|this)|"
                         r"what is pramana|what does pramana mean|about (?:you|pramana|this tool)|your name|"
                         r"what is this(?: tool| app| site)?)\b")
RE_ABOUT_DATA = re.compile(r"\b((?:which|what) (?:year|years|fy|period|data)|data (?:source|come|from)|where .{0,20}data|"
                           r"how (?:recent|old|current|reliable|accurate)|reliable|accurate|trust|hallucinat\w*|"
                           r"how do you (?:work|answer|know))\b")
RE_EXPORT = re.compile(r"\b(export|download|excel|xlsx|csv|spreadsheet|pdf|save (?:this|it|as))\b")
RE_SIM = re.compile(r"\b(what if|what-if|simulate|simulation|scenario|suppose|imagine|assume|"
                    r"if .{1,50}\b(cut|cuts|reduce|reduces|reduced|lower|lowers|lowered|decrease|decreases|increase|increases)\b|"
                    r"need to (cut|reduce|lower)|would need to)")
RE_PRONOUN = re.compile(r"\b(it|its|it's|they|their|them|this company|that company|the company|same company|"
                        r"these companies|those companies|he|she|this one|that one)\b")
RE_FOLLOW = re.compile(r"^(and|what about|how about|also|now|same for|then|ok and|and for|and in|what of)\b")
RE_NEG = re.compile(r"\b(without|don't|dont|do not|does not|doesn't|did not|didn't|lack|lacks|lacking|missing|"
                    r"not|no|haven't|hasn't|never|fail|fails|absent|skip|skips|skipping|omit|omits)\b")
RE_DECR = re.compile(r"\b(reduc\w*|decreas\w*|cut|cuts|lower\w*|fell|fall\w*|declin\w*|drop\w*|improvers?|improved|improving|"
                     r"go(?:es|ing)? down|went down)\b")
RE_INCR = re.compile(r"\b(increas\w*|rose|rise|rising|grew|grow\w*|higher|went up|go(?:es|ing)? up|jump\w*|worsen\w*)\b")
RE_HIGH = re.compile(r"\b(highest|largest|biggest|most|top|maximum|greatest|heaviest|major)\b")
RE_LOW = re.compile(r"\b(lowest|least|smallest|minimum|fewest|bottom|lightest)\b")
RE_BEST = re.compile(r"\b(best|cleanest|greenest|leading|leaders?|strongest|top performers?|top rated|highest scoring|"
                     r"most efficient|exemplary)\b")
RE_WORST = re.compile(r"\b(worst|dirtiest|laggards?|weakest|poorest|most polluting|lowest scoring|least efficient)\b")
RE_CLEAN = re.compile(r"\b(dirtiest|cleanest|greenest|cleaner|greener|dirtier|most polluting|least polluting|biggest polluters?)\b")
RE_DIRTY = re.compile(r"\b(dirtiest|dirtier|most polluting|biggest polluters?)\b")
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
    ({"scope1", "scope2"}, "scope12"),
    ({"intensity", "intensity_phys"}, "intensity_phys"),
    ({"intensity", "intensity_ppp"}, "intensity_ppp"),
    ({"scope12", "intensity_phys"}, "intensity_phys"),
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
    view: str | None = None                            # a more specific reading of the question, decided by its wording
    stat: str | None = None                            # average | median
    direction: str | None = None                       # lower | higher | similar (which peers ...)
    raw_metrics: list = field(default_factory=list)    # measures as named, before combining
    as_table: bool = False                             # a table was asked for
    about: list = field(default_factory=list)          # the company the conversation was about before this turn
    about_sector: str | None = None                    # and the sector
    missing: list = field(default_factory=list)        # words that stand where a company name would, and match no company
    focus_scope: str | None = None                     # "our Scope 3 projects": the scope the projects or targets are about
    yesno: bool = False                                # phrased as a yes/no question
    who: bool = False                                  # asks for a name ("who assured ...")

    def to_dict(self):
        return asdict(self)


class Parser:
    def __init__(self, kb):
        self.kb = kb
        self.model = IntentModel(ARTIFACTS)
        self.linker = Linker(kb, known_words=self.model.known_words)
        self.name_tokens = {c["id"]: set(tokenize(prep(c["name"]))) for c in kb.companies}
        self.common_words = set(kb.meta.get("english_name_tokens", []))
        path = ARTIFACTS / "english.txt.gz"
        if path.exists():
            import gzip
            self.english = frozenset(gzip.decompress(path.read_bytes()).decode().split("\n"))
        else:
            self.english = frozenset()
        self._vocab = sorted(w for w in (self.linker.vocab | self.model.known_words) if len(w) >= 4 and w.isalpha())
        # companies known by one ordinary word ("Trent", "Raymond", "Symphony"): matched only where a name is meant
        from .aliases import strip_suffix
        from .normalize import norm_name
        owners: dict[str, list] = {}
        for c in kb.companies:
            core = strip_suffix(norm_name(c["name"]), True)
            if len(core) == 1 and core[0] not in self.linker.vocab and core[0] not in kb.aliases and len(core[0]) >= 3 \
                    and "corporation" not in norm_name(c["name"]):
                owners.setdefault(core[0], []).append(c)
        self.single_names = {w: cs[0] for w, cs in owners.items() if len(cs) == 1}
        self._load_exemplars()

    def _names_a_company(self, word: str, low: str, raw: str = "") -> bool:
        """An unrecognised word that sits where a company name would ("emissions of zyxcorp", "zyxcorp vs NTPC") and is
        not just a misspelling of a word the assistant knows."""
        from rapidfuzz import process
        from rapidfuzz.distance import Levenshtein
        m = re.search(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", raw, re.I)
        capital = bool(m and m.start() > 0 and m.group(0)[0].isupper() and not raw.isupper())
        if len(word) < 4 or not word.isalpha() or (not capital and process.extractOne(
                word, self._vocab, scorer=Levenshtein.normalized_similarity, score_cutoff=0.78)):
            return False
        w = re.escape(word)
        return bool(re.search(rf"\b(?:of|for|about|on|from|at|by|is|does|did|has|do|compare|vs|versus|and|with|than|against|"
                              rf"are|show|give|tell)\s+{w}\b", low)
                    or re.search(rf"\b{w}\s+(?:emissions?|scope\w*|ghg|carbon|intensity|targets?|projects?|peers?|vs|versus|and|"
                                 rf"limited|ltd|data|numbers|profile|details)\b", low))

    def _ordinary(self, word: str, raw: str) -> bool:
        """An ordinary English word, not a name: "smaller", "setting", "audits". A capitalised word inside the
        sentence is still treated as a name ("emissions of Shell")."""
        m = re.search(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", raw, re.I)
        if m and m.start() > 0 and m.group(0)[0].isupper() and not raw.isupper():
            return False
        w = word
        if w in self.english:
            return True
        for suf, rep in (("ies", "y"), ("es", ""), ("s", ""), ("ing", ""), ("ing", "e"), ("ed", ""), ("ed", "e"), ("er", ""),
                         ("er", "e"), ("est", ""), ("est", "e"), ("ly", "")):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                stem = w[: -len(suf)] + rep
                if stem in self.english or (len(stem) > 3 and stem[-1] == stem[-2] and stem[:-1] in self.english):
                    return True
        return False

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
            if parts == {"scope3", "intensity"} and not any(
                    a.end == b.start for a in ents for b in ents if {a.value, b.value} == parts):
                continue
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
    def _name_single(self, query: str) -> str:
        """Write out the official name of a company known by one ordinary word, where the word is used as a name:
        capitalised, possessive, in a very short question, or where a company name would stand."""
        if not self.single_names:
            return query
        low = query.lower()
        if not any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low) for w in self.single_names):
            return query
        taken = {t for e in self.linker.link(query).of("company") if e.method == "exact" for t in e.text.split()}
        n_words = len(re.findall(r"[A-Za-z0-9]+", query))
        for w, c in self.single_names.items():
            if w in taken:
                continue                                  # part of a longer company name ("Alembic Pharmaceuticals")
            m = re.search(rf"(?<![A-Za-z]){re.escape(w)}(?![A-Za-z])(?:\s+(?:corp|india|limited|ltd)\b\.?)*", query, re.I)
            if not m or c["name"].lower() in low:
                continue
            word = query[m.start(): m.start() + len(w)]
            named = word[0].isupper() or n_words <= 4 or low[m.end(): m.end() + 2] in ("'s", "’s") \
                or re.search(rf"\b(?:of|for|about|from|at|by|compare|vs|versus|and|with|than|against)\s+{re.escape(w)}\b", low) \
                or re.search(rf"\b{re.escape(w)}\s+(?:emissions?|scope|ghg|carbon|intensity|targets?|projects?|peers?|vs|versus|and)\b", low)
            if named:
                query = query[: m.start()] + c["name"] + query[m.end():]
                low = query.lower()
        return query

    def parse(self, query: str, context: dict | None = None) -> Plan:
        context = context or {}
        lens = context.get("lens") if context.get("lens") in self.kb.by_id else None
        original = query
        query = self._name_single(query)
        resolved, personal = self._personalise(query, lens)
        p = self._parse(resolved, context, lens, first_person=self._first_person(query))
        p.query = original
        p.lens = lens
        if query != original:
            p.resolved_query = resolved
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
        for e in sorted(link.of("company") + link.of("absent"), key=lambda e: -len(e.text)):
            low = re.sub(rf"(?<![a-z0-9]){re.escape(e.text)}(?![a-z0-9])", "<co>", re.sub(r"\s+", " ", low))
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
        p.raw_metrics = list(dict.fromkeys(e.value for e in link.of("metric")))
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
        starts = fiscal_starts(query)
        p.period = "PY" if RE_PY.search(low) or (2023 in starts and 2024 not in starts) else "CY"
        p.by_sector = bool(RE_BY_SECTOR.search(low))
        p.infographic = bool(RE_INFOGRAPHIC.search(low))
        p.generic_emissions = p.metric == "scope12" and not re.search(r"\bscope(12|1|2)\b", low)
        for start in fiscal_starts(query):
            if start not in (2023, 2024):
                p.fy_out_of_range = f"FY {start}-{str(start + 1)[2:]}"
        peer_q = bool(RE_PEER_NOUN.search(low) and RE_FILTER_ASK.search(low))
        if p.metric == "scope3" and ((p.intent in ("aggregate", "screen") and re.search(
                r"\b(report|reports|reporting|reported|disclose|discloses|disclosing)\b", low)) or (peer_q and re.search(
                r"\b(report|reports|reporting|reported|disclose|discloses|disclosing|disclosed)\b", low))):
            p.metric, p.rules = "scope3_reported", p.rules + ["scope3 + reporting verb -> scope3_reported"]

        # unknown words that might be a company the user named
        for u in link.unknown:
            if u in self.model.known_words or len(u) < 3 or u in self.common_words or self._ordinary(u, query):
                continue
            group = self._group_candidates(u)
            if len(group) == 1 and group[0] not in p.companies:
                p.companies.append(group[0])
                p.rules.append(f"'{u}' uniquely names one company")
            elif len(group) > 1:
                p.ambiguous.append({"text": u, "ids": group})
            elif not (p.infographic and RE_INFOGRAPHIC.fullmatch(u)):
                p.unknown_names.append(u)
                if self._names_a_company(u, low, query):
                    p.missing.append(u)

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
        elif p.infographic and len(p.companies) >= 2:
            p.infographic = False
            p.view = "from_infographic"
            self._set(p, "compare", "an infographic covers one company; two were named")
        elif p.infographic:
            self._set(p, "infographic", "asks for an infographic")
        elif p.intent == "out_of_scope" and (has_metric or p.tech) and p.confidence < 0.9:
            self._set(p, "company_metric" if (p.companies or p.ambiguous) else "aggregate",
                      "covered measure present, model refusal overridden")

        has_peers = bool(RE_PEER_NOUN.search(low))
        counting = bool(re.search(r"\bhow many\b", low))
        peer_eval = has_peers and not counting and bool(RE_PEER_EVAL.search(low) or RE_PEER_VERB.search(low))
        peer_list = has_peers and not has_metric and not peer_eval and (bool(RE_PEER_ASK.search(low)) or len(toks) <= 5)
        # "what is scope 3", "what are scope 1 and scope 2 emissions": asks what the term means, whoever is asking
        plain = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", low)).strip()
        asks_meaning = bool(RE_WHAT_IS_METRIC.match(plain)) and not first_person and not p.companies and not p.ambiguous
        strict_define = (bool(RE_DEFINE.search(low)) or asks_meaning) and (has_metric or not p.companies)
        p.about = [c for c in context.get("companies", []) if c in self.kb.by_id][:1]
        p.about_sector = context.get("sector") if context.get("sector") in self.kb.sector_by_id else None
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
        if p.metric is None and pred["topic"] not in ("none", "index") and \
                pred["topic_p"] >= (0.75 if pred["topic"] in ("scope12", "scope1", "scope2", "scope3", "intensity") else 0.93) and \
                p.intent in ("company_metric", "ranking", "aggregate", "screen", "best_practice", "compare",
                             "peer_benchmark", "simulate"):
            p.metric = pred["topic"]
            p.metrics = [p.metric]
            p.generic_emissions = p.metric == "scope12"
            p.rules.append(f"metric inferred by model topic head ({pred['topic_p']:.2f})")
        self._refine(p, low, lens, first_person, ctx_companies, context)
        return p

    # ------------------------------------------------------------------ specific readings
    def _view(self, p: Plan, view: str, intent: str, why: str):
        p.view = view
        self._set(p, intent, why)

    def _carry(self, p: Plan, low: str, lens: str | None, first_person: bool, ctx_companies, context: dict) -> bool:
        """Follow-ups that name nothing themselves: "and last year?", "trend?", "how did it change", "by 40%",
        "which of them have assurance". Returns True when "them" means the peers just discussed."""
        if first_person or p.companies or p.ambiguous or p.absent or p.sector or (p.offtopic and p.intent == "out_of_scope"):
            return False
        if p.unknown_names and p.intent in COMPANY_INTENTS:
            return False
        prev, prev_view = context.get("intent"), context.get("view")
        words = low.split()
        if RE_THEM.search(low) and ctx_companies and (prev in ("peer_list", "peer_benchmark") or prev_view in PEER_VIEWS):
            p.companies = [ctx_companies[0]]
            p.used_context["companies"] = p.companies
            p.rules.append("'them' read as the peers just discussed")
            return True
        period = p.period == "PY" or bool(fiscal_starts(p.query))
        bare = len(words) <= 4 and (period or bool(RE_TREND.search(low)) or p.pct is not None) and not RE_MARKET.search(low)
        if not (RE_IT.search(low) or bare) or RE_ABOUT_DATA.search(low) or RE_ABOUT_ME.search(low):
            return False
        ctx_metric = context.get("metric")

        def metric_from_context():
            if p.metric is None and isinstance(ctx_metric, str) and ctx_metric:
                p.metric, p.metrics = ctx_metric, [ctx_metric]
                p.generic_emissions = ctx_metric == "scope12"
                p.used_context["metric"] = ctx_metric
            elif p.metric is None and bare:
                p.metric, p.metrics, p.generic_emissions = "scope12", ["scope12"], True     # "and last year?": emissions

        if ctx_companies:
            p.companies = list(ctx_companies) if prev == "compare" else list(ctx_companies[:1])
            p.used_context["companies"] = p.companies
            metric_from_context()
            new = "compare" if len(p.companies) > 1 else "simulate" if (prev == "simulate" and p.pct is not None) \
                else p.intent if p.intent in COMPANY_INTENTS and p.intent != "set_lens" else "company_metric"
            self._set(p, new, "follow-up: the company being discussed")
            p.followup = True
        elif context.get("sector") in self.kb.sector_by_id:
            p.sector = context["sector"]
            p.sectors = [p.sector]
            p.used_context["sector"] = p.sector
            metric_from_context()
            if context.get("view") in CARRY_VIEWS and not p.view and not RE_TREND.search(low):
                p.view, p.stat = context["view"], context.get("stat")
            p.rules.append("follow-up: the sector being discussed")
            p.followup = True
        elif lens and bare:
            p.companies = [lens]
            p.used_context["lens"] = lens
            self._set(p, "company_metric", "no company named: answered for your company")
        return False

    def _refine(self, p: Plan, low: str, lens: str | None, first_person: bool, ctx_companies=(), context: dict | None = None):
        """Wording that asks for something more specific than the broad kind of question: a trend, a previous
        year, a share, a filter on peers, a sector-level view, advice. Each rule records itself in the trace."""
        kb = self.kb
        low = re.sub(r"\s+", " ", re.sub(r"[^\w\s<>%'+-]", " ", low)).strip()
        NUM = ("scope1", "scope2", "scope12", "scope3", "intensity", "scope3_intensity", "intensity_phys", "intensity_ppp")
        ABS = ("scope1", "scope2", "scope12", "scope3")
        TEXTY = (None, "targets", "target_performance", "projects", "certifications")
        context = context or {}
        p.yesno = bool(RE_YESNO.match(low))
        p.who = bool(RE_WHO.search(low))
        them = False
        if p.intent not in ("set_pref", "clear_lens", "no_scores", "infographic", "need_company") and not p.view:
            them = self._carry(p, low, lens, first_person, ctx_companies, context)
            # "which of them ...", "who are they": the peers just discussed, even if "they" was first read as the company
            after_peers = context.get("intent") in ("peer_list", "peer_benchmark") or context.get("view") in PEER_VIEWS
            if not them and after_peers and ctx_companies and RE_THEM.search(low) and not first_person and not p.sector \
                    and not p.ambiguous and p.companies in ([], list(ctx_companies[:1])):
                p.companies = list(ctx_companies[:1])
                p.used_context["companies"] = p.companies
                p.rules.append("'them' read as the peers just discussed")
                them = True
        if p.intent == "simulate" and p.metric is None and context.get("intent") == "simulate" and context.get("metric"):
            p.metric, p.metrics = context["metric"], [context["metric"]]
            p.used_context["metric"] = p.metric
        has_peers = bool(RE_PEER_NOUN.search(low)) or them
        bare = not (p.companies or p.ambiguous or p.absent or p.sector or p.metric or p.tech or p.offtopic)

        # the model can propose "set your company" for any short question that names one
        if p.intent == "set_lens" and not RE_LENS.search(low) and not re.search(r"\b(i|i'm|im|my|our|we|me|us)\b", low):
            self._set(p, "company_metric" if p.metric else "company_profile", "no self-identification phrase")

        if bare and p.intent in ("greeting", "unknown", "explain", "out_of_scope", "company_profile", "text_search"):
            if RE_THANKS.match(low):
                return self._view(p, "thanks", "greeting", "an acknowledgement")
            if RE_ABOUT_ME.search(low):
                return self._view(p, "about", "greeting", "asks what this is")
            if RE_EXPORT.search(low) and not p.unknown_names:
                return self._view(p, "export", "greeting", "asks how to download")
            if RE_ALL_COMPANIES.search(low) and not has_peers and not p.change and not p.unknown_names:
                return self._view(p, "coverage", "aggregate", "asks which companies are covered")
            if RE_ABOUT_DATA.search(low) or re.search(r"\b(?:have|cover|data for|figures for) .{0,12}20\d\d\b|\b20\d\d data\b", low):
                return self._set(p, "explain", "asks about the data or how answers are produced")
            if p.intent == "explain" and len(low.split()) <= 2 and not RE_WHATIS.match(low):
                return self._set(p, "greeting", "nothing named to explain")

        if RE_PEER_DEF.search(low) and not p.companies and not p.sector:
            p.unknown_names = []
            return self._view(p, "peer_def", "explain", "asks how peers are chosen")
        # a refusal proposed by the model with nothing off-topic in the question, about a named company: answer it
        covered = bool(p.raw_metrics or p.tech or RE_SCOPE_SPLIT.search(low) or RE_SIDE.search(p.masked) or RE_TREND.search(low)
                       or re.search(r"\b(numbers|figures|kpis|disclos\w*)\b", low))
        future = re.search(r"^will\b|\bwill (?:\S+ ){0,3}(?:hit|reach|achieve|meet|become|be|emit|reduce|cut)\b|\bgoing to\b|"
                           r"\bpredict\w*|\bforecast\w*|\bexpected?\b", low)
        if p.intent == "out_of_scope" and not p.offtopic and len(p.companies) == 1 and not p.ambiguous and covered and not future:
            self._set(p, "company_metric" if p.metric else "company_profile", "a covered topic for a named company")
        if p.intent == "out_of_scope" and not p.offtopic and not p.ambiguous and RE_PEER_NOUN.search(low) and not future \
                and (len(p.companies) == 1 or lens):
            p.companies = p.companies or [lens]
            self._set(p, "peer_list" if RE_PEER_ASK.search(low) and not p.metric else "peer_benchmark", "a question about peers")
        hard = any(o in HARD_OFFTOPIC for o in p.offtopic)
        advice = bool(RE_ADVISE.search(low)) and not hard and not RE_SIM.search(low) and not p.infographic
        gaps = bool(RE_GAPS.search(low)) and not [o for o in p.offtopic if o != "FUTURE"]
        if p.intent == "out_of_scope" and not (advice and not p.offtopic) and not (gaps and (p.companies or lens)):
            return
        if p.intent in ("set_pref", "clear_lens", "no_scores", "set_lens", "infographic") or p.view:
            return
        if p.intent == "simulate" and (RE_SIM.search(low) or p.pct is not None):
            return
        if len(p.companies) == 1 and not p.ambiguous and not first_person and not has_peers and not p.sector and \
                re.search(r"\b(compare|compared|comparison|vs|versus|against)\b", low):
            other = next((x for x in ctx_companies if x != p.companies[0]), None) or (lens if lens and lens != p.companies[0] else None)
            if other:
                p.companies = [other, p.companies[0]]
                if "metric" in p.used_context:              # a measure carried over from the last turn was not asked for here
                    p.metric, p.metrics = None, []
                    p.used_context.pop("metric")
                p.used_context["companies"] = [other]
                return self._set(p, "compare", "one company named to compare with: the other is the one being discussed")
        if len(p.companies) == 2 and not p.ambiguous and re.search(r"<co> .{0,12}learn (?:from|about) (?:the |what )?<co>", p.masked):
            p.companies = [p.companies[1], p.companies[0]]          # the company to learn from, then the learner
            return self._view(p, "learn_from", "best_practice", "asks what one company can learn from another")
        if p.ambiguous or len(p.companies) > 1:
            return
        if p.view in CARRY_VIEWS:
            return
        # an unrecognised word only matters when it may be a company the user named
        free = not p.absent and not p.missing and not (p.unknown_names and not p.companies and p.intent in COMPANY_INTENTS)
        if has_peers and not p.companies and not p.sector and free and p.intent != "explain":
            # "which peers ...", "do peers ..." with nobody named: the peers of your company, or of the one being discussed
            who = lens or next(iter(ctx_companies), None)
            if who:
                p.companies = [who]
                p.used_context["lens" if who == lens else "companies"] = who if who == lens else [who]
                p.rules.append("peers named without a company: taken as " + ("your company" if who == lens else "the company being discussed"))
            else:
                return self._set(p, "need_company", "peers named with no company to take them from")
        one = p.companies[0] if p.companies else None
        named_other = bool(one) and one != lens          # a company the user named, not their own
        if one and RE_BOARD.search(low) and not hard:
            p.metric, p.metrics = None, []
            return self._set(p, "company_profile", "asks for a summary to present")

        # ---- what is missing from a company's disclosures
        if gaps and not p.sector and free and p.metric not in NUM:
            c = one or (lens if not re.search(r"\b(companies|firms|which|who|how many|peers?|sectors?|industry)\b", low) else None)
            if c:
                p.companies = [c]
                return self._view(p, "gaps", "company_profile", "asks what is not yet disclosed")
            if first_person:
                return self._set(p, "need_company", "first-person question with no company set")

        # ---- advice: examples of what other companies disclose
        if advice:
            if named_other and (RE_LEARN_FROM_CO.search(p.masked) or re.fullmatch(
                    r"(?:what are |show |the )?(?:<co> (?:s )?(?:best |good )?practices|(?:best |good )?practices (?:of|at|by|from) <co>)",
                    p.masked.strip())):
                return self._view(p, "learn_from", "best_practice", "asks what can be learned from a named company")
            if not named_other and free:
                if lens and not one:
                    p.companies = [lens]
                    p.used_context["lens"] = lens
                return self._set(p, "best_practice", "asks for ideas or good practice")
        if p.intent == "need_company":
            return
        if p.intent == "best_practice" and p.companies and not advice and not has_peers and not p.sector and free \
                and p.metric in (None, "projects", "targets", "target_performance", "certifications") \
                and not re.search(r"\b(examples?|practices?|others|companies|firms|leaders|leading|best|like)\b", low):
            p.metric = p.metric or "projects"
            p.metrics = [p.metric]
            return self._set(p, "company_metric", "asks what one company itself is doing")
        if RE_DOING.search(low) and p.metric in (None, "projects", "scope12", "scope1", "scope2", "scope3") and free:
            if (has_peers or RE_OTHERS.search(low)) and (one or lens) and not p.sector:
                p.companies = [one or lens]
                return self._set(p, "best_practice", "asks what peers are doing")
            if (p.sector or RE_OTHERS.search(low)) and not one:
                return self._set(p, "best_practice", "asks what other companies are doing")

        # ---- definitions of terms that are also search words
        if not one and not p.sector and RE_WHATIS.match(low.rstrip("? ")):
            return self._set(p, "explain", "asks what a term means")
        pledge = RE_PLEDGE.search(low)
        terms = list(p.tech) or (["sbti" if pledge.group(1).startswith(("science", "sbt")) else "net zero"] if pledge else [])
        if p.intent == "text_search" and (p.tech or terms) and (re.search(r"\b(examples?|best practices?|good practices?)\b", low)
                                                                 or RE_HOW_USING.search(low)) and not RE_FILTER_ASK.search(low):
            p.tech = p.tech or terms
            if lens and not one:
                p.companies = [lens]
            return self._set(p, "best_practice", "asks for examples of one measure")
        if p.intent == "text_search" and not p.tech and not p.keywords:
            if terms:
                p.tech = terms
            elif not one:
                return self._set(p, "best_practice" if p.metric in ("targets", "projects", "certifications", "target_performance")
                                 else "explain", "nothing to search for")

        # ---- one company
        peer_ask = has_peers and bool(RE_FILTER_ASK.search(low)) and (them or bool(p.tech) or bool(RE_PLEDGE.search(low)))
        if one and free and (p.intent != "best_practice" or peer_ask):
            c = kb.by_id[one]
            if p.intent == "peer_benchmark" and not has_peers and not RE_PEER_IMPLIED.search(low) and not re.search(
                    r"\b(compar\w*|versus|vs|against|stand\w*|stack\w*|fare\w*|perform\w*|position\w*|rank\w*|better|worse|"
                    r"ahead|behind|lag\w*|lead\w*|relative|doing|than|average|median)\b", low):
                self._set(p, "company_metric" if p.metric else "company_profile", "no comparison is asked for")
            scopes = [m for m in p.raw_metrics if m in ("scope1", "scope2", "scope3")]
            # "Scope 3 projects implemented by my competition", "our Scope 3 targets": projects or targets about one scope
            practice_m = [m for m in p.raw_metrics if m in ("projects", "targets", "target_performance")]
            if practice_m and scopes and not p.tech and p.intent not in ("simulate",):
                if has_peers or RE_OTHERS.search(low):
                    if not re.search(r"\b(how many|which of|which peers|which competitors|who)\b", low):
                        p.metric, p.metrics = scopes[0], [scopes[0]] + practice_m
                        return self._set(p, "best_practice", "asks what peers do about one scope")
                    p.metric, p.metrics, p.focus_scope = practice_m[0], practice_m + scopes, scopes[0]
                    return self._set(p, "peer_benchmark", "asks which peers have projects or targets about one scope")
                elif not RE_TREND.search(low):
                    p.metric, p.metrics, p.focus_scope = practice_m[0], practice_m + scopes, scopes[0]
                    return self._set(p, "company_metric", "asks for the company's projects or targets about one scope")
            own_group = has_peers or (bool(RE_OWN_GROUP.search(low)) and not p.sector)
            versus = bool(re.search(r"\b(compar\w*|versus|vs|against|than)\b", low))
            direction = "similar" if RE_FILTER_NEAR.search(low) else \
                "lower" if (RE_FILTER_LOW.search(low) or re.search(r"\bahead\b", low)) else \
                "higher" if (RE_FILTER_HIGH.search(low) or re.search(r"\bbehind\b", low)) else None
            # "which power companies are below NTPC", "who is ahead of us": a filter on the peer group, however it is worded
            if direction and RE_SIDE.search(p.masked) and RE_FILTER_ASK.search(low) and p.metric in (None,) + NUM \
                    and (p.sector is None or p.sector == c["sector"]):
                p.direction, p.sector = direction, None
                return self._view(p, "peer_filter", "peer_benchmark", "asks which companies are lower, higher or closest")
            # "is our scope 3 high", "are we efficient": only a comparison can say
            if p.yesno and RE_EVAL_ADJ.search(low) and not own_group and not versus and not p.tech \
                    and (p.metric in NUM or (p.metric is None and re.search(r"\b(in)?efficient\b", low))):
                if p.metric is None:
                    p.metric, p.metrics = "intensity", ["intensity"]
                return self._set(p, "peer_benchmark", "asks whether a figure is high or low: compared with peers")
            if p.metric == "scope3" and RE_TOTALLED.search(low) and "scope12" not in p.raw_metrics and not own_group:
                p.metric, p.metrics, p.generic_emissions = "scope12", ["scope12", "scope3"], True
                return self._set(p, "company_metric", "a total that includes Scope 3: all scopes are shown")
            if p.metric is None and RE_DOING.search(low) and not own_group and not terms:
                p.metric, p.metrics = "projects", ["projects"]
                return self._set(p, "company_metric", "asks what a company is doing: its projects")
            if not has_peers and RE_OWN_SECTOR.search(p.masked) and not RE_PEER_IMPLIED.search(low.replace("sector", "").replace("industry", "")) \
                    and not (p.quality or p.extreme) and not RE_STAT.search(low):
                # the question is about the company's sector as a whole
                own = c["sector"]
                p.sector, p.sectors, p.companies = own, [own] + [x for x in p.sectors if x != own], []
                p.rules.append("the question is about the company's own sector")
                if len(p.sectors) >= 2:
                    return self._view(p, "sector_compare", "sector_overview", "the company's sector against another")
                if RE_TREND.search(low) and p.metric in (None,) + ABS:
                    p.metric = p.metric if p.metric in ABS else "scope12"
                    return self._view(p, "total_change", "aggregate", "asks how the sector's total moved")
                if p.metric in NUM and re.search(r"\b(total|overall|sum|combined|aggregate|altogether)\b", low):
                    return self._set(p, "aggregate", "asks for the sector's total")
                return self._set(p, "sector_overview", "asks about the company's sector")
            if not own_group:
                if RE_SCOPE_SPLIT.search(low) or (len(scopes) >= 2 and RE_SCOPE_VS.search(low)) or \
                        (scopes and "scope12" in p.raw_metrics and RE_SHARE.search(low)):
                    return self._view(p, "scopes", "company_metric", "asks how the scopes compare within one company")
                yes_no_cut = p.metric == "projects" and p.yesno and bool(RE_TREND_VERB.search(low)) \
                    and not RE_HOW_WHAT.search(low)
                both_years = {2023, 2024} <= set(fiscal_starts(p.query))
                if ((RE_TREND.search(low) or both_years) and p.metric in (None,) + NUM and not p.tech) or yes_no_cut:
                    if p.metric not in NUM:
                        p.metric, p.generic_emissions = "scope12", True
                    return self._view(p, "change", "company_metric", "asks how a figure moved between the two years")
                if terms and p.metric in TEXTY and p.intent != "peer_benchmark":
                    p.tech = terms
                    return self._view(p, "mentions", "company_metric", "asks about a pledge or technology for one company")
            if RE_SHARE.search(low) and p.metric in (None,) + ABS and not p.change and not has_peers \
                    and not re.search(r"\b(companies|firms)\b", low):
                return self._view(p, "share", "company_metric", "asks what share of emissions a company accounts for")
            if own_group and p.sector is None:
                if RE_STAT.search(low) and p.metric in (None,) + NUM and not RE_STAT_NOT.search(low):
                    p.stat = "median" if "median" in low else "average"
                    p.sector = c["sector"]
                    return self._view(p, "stat", "aggregate", "asks for the average or median of the peer group")
                if has_peers and (RE_FILTER_ASK.search(low) or re.search(r"\bpeers? (?:\S+ ){0,3}with\b|^(?:smaller|bigger|larger|lower|higher) peers$", low)) \
                        and p.metric in (None,) + NUM and direction:
                    p.direction = direction
                    return self._view(p, "peer_filter", "peer_benchmark", "asks which peers are lower, higher or closest")
                if has_peers and RE_LISTING.search(low) and p.metric in NUM:
                    p.sector, p.n, p.as_table = c["sector"], p.n or 25, True
                    return self._view(p, "focus_rank", "ranking", "asks for the peers with their figures")
                if (p.quality or p.extreme) and not versus and p.metric in (None,) + NUM:
                    p.sector = c["sector"]
                    return self._view(p, "focus_rank", "ranking", "asks who leads within the company's own sector")
                if has_peers and p.change and RE_FILTER_ASK.search(low) and (p.metric in (None, "scope12", "scope1", "scope2") or (
                        p.metric == "projects" and not re.search(r"\b(projects?|initiatives?|measures|steps)\b", low))):
                    p.sector, p.metric = c["sector"], None
                    return self._view(p, "peer_change", "screen", "asks which peers raised or lowered emissions")
                if has_peers and terms and p.metric in TEXTY:
                    p.tech = terms
                    p.sector = c["sector"]
                    return self._view(p, "peer_search", "text_search", "asks whether peers mention a pledge or technology")
                if has_peers and p.metric and p.intent not in ("peer_benchmark", "text_search"):
                    return self._set(p, "peer_benchmark", "a measure and the peer group are both named")
                if them and not p.metric and not terms:
                    return self._set(p, "peer_list", "asks who the peers just discussed are")
            if p.intent == "compare":
                return self._set(p, "peer_benchmark", "a comparison with one company named: against its peers")
            if p.intent in ("company_profile", "greeting", "unknown") and one == lens and re.fullmatch(
                    r"(?:what is |show |tell me |and )?<co> (?:position|standing|rank|ranking)", p.masked.strip()):
                return self._set(p, "peer_benchmark", "asks where your company stands")
            if p.intent in ("greeting", "unknown") and not p.metric:
                return self._set(p, "company_profile", "a company is named and nothing more specific is asked")
            if p.intent == "company_profile" and p.metric and not RE_PROFILE.search(low):
                return self._set(p, "company_metric", "a measure is named and no overview is asked for")
            return

        # ---- sectors and the whole market
        if one or not free:
            return
        if p.followup and p.sector and not p.view and context.get("view") in CARRY_VIEWS and not RE_TREND.search(low) \
                and not RE_STAT.search(low) and (p.metric is None or "metric" in p.used_context) and len(low.split()) <= 5:
            p.view, p.stat = context["view"], context.get("stat")
            p.rules.append("follow-up: same view, new sector")
            return
        if len(p.sectors) >= 2 and (RE_COMPARE_WORD.search(low) or "difference" in low):
            return self._view(p, "sector_compare", "sector_overview", "two or more sectors named")
        if RE_SECTOR_LIST.search(low.rstrip("? ")) and p.metric is None and not p.change and not p.sector:
            return self._view(p, "sector_list", "aggregate", "asks which sectors are covered")
        if p.sector and RE_SHARE.search(low) and p.metric in (None,) + ABS and not p.change \
                and not re.search(r"\b(companies|firms)\b", low):
            return self._view(p, "sector_share", "aggregate", "asks what share of emissions a sector accounts for")
        if p.metric == "projects" and p.change and p.intent in ("ranking", "screen", "aggregate") and not re.search(
                r"\b(projects?|initiatives?|measures|steps|actions?|plans?|examples?|doing)\b", low):
            p.metric, p.metrics = None, []                 # "which companies cut emissions most": the figures, not the projects
        if p.tech and p.by_sector and not p.sector:
            return self._set(p, "text_search", "a technology or pledge, across sectors")
        if not p.sector and (RE_SHARE.search(low) or RE_SCOPE_SPLIT.search(low)) and not re.search(r"\b(companies|firms)\b", low) \
                and [m for m in p.raw_metrics if m in ("scope1", "scope2", "scope3")] and \
                ("scope12" in p.raw_metrics or RE_SCOPE_SPLIT.search(low)) and not p.change:
            return self._view(p, "market_scopes", "aggregate", "asks how the scopes split across all companies")
        if p.sector and p.metric is None and not p.change and not terms and re.search(r"\b(how many|number of|count of)\b", low) \
                and re.search(r"\b(companies|firms)\b", low):
            return self._set(p, "screen", "asks how many companies a sector has")
        counting = bool(re.search(r"\b(which|who|how many|companies|firms|top|most|least|largest|biggest|list|number of)\b", low))
        yes_no_cut = p.metric == "projects" and p.yesno and bool(RE_TREND_VERB.search(low)) and not RE_HOW_WHAT.search(low)
        if not p.by_sector and not counting and len(p.sectors) <= 1 and (p.raw_metrics or p.sector or len(low.split()) <= 3) and \
                ((RE_TREND.search(low) and p.metric in (None,) + ABS and not p.tech) or yes_no_cut) and \
                p.intent in ("aggregate", "sector_overview", "explain", "report_insights", "ranking", "screen", "unknown",
                             "company_metric", "greeting", "best_practice"):
            if p.metric not in ABS:
                p.metric = "scope12"
            return self._view(p, "total_change", "aggregate", "asks how total emissions moved between the two years")
        improved = "decreased" if re.search(r"\bimprov\w*\b", low) else "increased" if re.search(r"\bworsen\w*\b", low) else None
        if p.by_sector and not p.sector and (p.change or improved or RE_TREND.search(low)) and p.metric in (None,) + ABS:
            p.change = p.change or improved or "decreased"
            return self._view(p, "sector_change", "aggregate", "asks how emissions moved sector by sector")
        if RE_STAT.search(low) and p.metric in NUM and not p.by_sector and not RE_STAT_NOT.search(low) \
                and p.intent in ("aggregate", "ranking", "screen", "explain", "company_metric", "sector_overview", "unknown",
                                 "report_insights", "peer_benchmark"):
            p.stat = "median" if "median" in low else "average"
            if not p.sector and lens and RE_OWN_GROUP.search(low):
                p.sector = kb.by_id[lens]["sector"]
                p.companies = [lens]
                p.used_context["lens"] = lens
            return self._view(p, "stat", "aggregate", "asks for an average or median")
        if p.sector and p.metric in NUM and RE_LISTING.search(low) and p.intent in ("aggregate", "screen", "ranking") \
                and not re.search(r"\b(how many|total|sum|combined|altogether)\b", low):
            p.n = p.n or 25
            return self._view(p, "listing", "ranking", "asks for the companies of a sector with their figures")

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
