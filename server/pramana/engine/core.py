"""The answer engine: parse, route, compose, verify, fingerprint."""
from __future__ import annotations

import re
import time

from ..kb import KB
from ..nlu.parser import COMPANY_INTENTS, Parser
from . import h_company as HC
from . import h_compare as HM
from . import h_info as HI
from . import h_practice as HP
from . import h_sector as HS
from .answer import Answer
from .common import Ctx
from .evidence import DisclosureIndex
from .fmt import short_name

NUM_IN_TEXT = re.compile(r"(?<![\w\[])\d[\d,]*(?:\.\d+)?")
CITE = re.compile(r"\[(\d+)\]")


class Engine:
    def __init__(self, kb: KB):
        self.kb = kb
        self.parser = Parser(kb)
        self.index = DisclosureIndex(kb.corpus)

    # ------------------------------------------------------------------ public
    def ask(self, query: str, context: dict | None = None) -> dict:
        t0 = time.perf_counter()
        query = re.sub(r"\s+", " ", (query or "")).strip()[:600]
        context = context or {}
        plan = self.parser.parse(query, context)
        t1 = time.perf_counter()
        a = Answer(self.kb, plan)
        ctx = Ctx(self.kb, plan, self.index, a)
        if not query:
            HI.greeting(ctx)
        else:
            self._route(ctx)
        if plan.fy_out_of_range:
            a.note("scope", f"The dataset covers FY 2024-25 with FY 2023-24 comparatives only; {plan.fy_out_of_range} "
                            f"is not available, so the figures shown are for FY 2024-25.")
        if plan.intent != "out_of_scope":
            from ..nlu.lexicon import OFFTOPIC
            labels = {o["key"]: o for o in OFFTOPIC}
            for key in plan.offtopic:
                o = labels.get(key)
                if o:
                    where = f" (chapter {o['chapter']} of the IIMB report)" if o.get("chapter") else ""
                    a.note("scope", f"{o['label']} is outside the E1 dataset{where}, so that part of the question is "
                                    f"not answered here.")
        for name in plan.absent:
            if a.status not in ("not_found",):
                a.note("scope", f"{name} is not among the {len(self.kb.companies)} companies in the dataset.")
        # context for the next turn (explicit, client-held, so the server stays stateless)
        a.context.setdefault("intent", plan.intent)
        a.context.setdefault("companies", plan.companies[:6])
        a.context.setdefault("sector", plan.sector)
        a.context.setdefault("metric", plan.metric)
        a.context.setdefault("tech", plan.tech)
        if "lens" not in a.context and context.get("lens"):
            a.context["lens"] = context["lens"]
        body = a.payload()
        t2 = time.perf_counter()
        body["trace"] = self._trace(plan, a, body, (t1 - t0) * 1000, (t2 - t1) * 1000)
        return body

    # ------------------------------------------------------------------ routing
    def _route(self, ctx: Ctx):
        p, kb = ctx.plan, ctx.kb
        intent = p.intent
        if intent == "out_of_scope":
            return HI.out_of_scope(ctx)
        if intent == "greeting":
            return HI.greeting(ctx)
        if p.ambiguous and (intent in COMPANY_INTENTS or intent in ("compare", "best_practice")):
            return HI.clarify(ctx)
        if (p.absent or p.unknown_names) and not p.companies and intent in COMPANY_INTENTS | {"compare"}:
            return HI.not_found(ctx)
        cos = p.companies
        if intent == "compare" and len(cos) < 2:
            intent = "company_metric" if p.metric else "company_profile"
        if intent in COMPANY_INTENTS and not cos:
            ctx.a.status = "clarify"
            ctx.a.kicker = "Which company?"
            ctx.a.title = "Tell me which company"
            ctx.a.p("This question needs a company. Name one, or set your company lens so questions like "
                    "“how do we compare with our peers?” work without naming it every time.")
            ctx.a.follow("How does Tata Steel compare with its peers?", "I work at Infosys",
                         "What are UltraTech's Scope 1 emissions?")
            return
        c = kb.by_id[cos[0]] if cos else None
        if intent == "set_lens":
            return HC.set_lens(ctx, c)
        if intent == "company_profile":
            return HC.company_profile(ctx, c)
        if intent == "company_metric":
            return HC.company_metric(ctx, c, p.metric) if p.metric else HC.company_profile(ctx, c)
        if intent == "compare":
            return HM.compare(ctx, cos, p.metric)
        if intent == "peer_benchmark":
            return HM.peer_benchmark(ctx, c, p.metric)
        if intent == "simulate":
            return HC.simulate(ctx, c, p.metric or "scope12", p.pct)
        if intent == "sector_overview":
            if p.metric and not p.sector:
                return HS.all_sectors(ctx, p.metric)
            return HS.sector_overview(ctx, p.sector, p.metric)
        if intent == "ranking":
            return HS.ranking(ctx, p.metric, p.sector, p.n, p.extreme, p.quality, p.change)
        if intent == "aggregate":
            return HS.aggregate(ctx, p.metric, p.sector, p.change)
        if intent == "screen":
            return HS.screen(ctx, p.metric, p.sector, p.negated, p.change)
        if intent == "best_practice":
            lens = None
            if not cos and re.search(r"\b(we|our|us)\b", p.query.lower()):
                lens = p.used_context.get("lens")
            return HP.best_practice(ctx, p.metric, p.sector, cos[0] if cos else lens)
        if intent == "text_search":
            return HP.text_search(ctx, p.sector)
        if intent == "explain":
            return HI.explain(ctx)
        if intent == "report_insights":
            return HI.report_insights(ctx)
        return HI.greeting(ctx)

    # ------------------------------------------------------------------ trace
    def _trace(self, plan, a: Answer, body, parse_ms, compose_ms) -> dict:
        ungrounded = []
        numeric = 0
        for para in a.lead:
            stripped = CITE.sub("", para)
            if NUM_IN_TEXT.search(re.sub(r"\b(FY \d{4}-\d{2}|Q\d+|Scope [123]|1\+2|E1|NSE|Table \d+\.\d+|rank 1)\b", "", stripped)):
                numeric += 1
                if not CITE.search(para):
                    ungrounded.append(para[:120])
        max_ref = max((int(x) for para in a.lead for x in CITE.findall(para)), default=0)
        return {
            "query": plan.query,
            "normalized": plan.masked,
            "model": {"intent": plan.model.get("intent"), "p": plan.model.get("intent_p"),
                      "top3": plan.model.get("intent_top3"), "topic": plan.model.get("topic"),
                      "topic_p": plan.model.get("topic_p"), "tokens": plan.model.get("pieces")},
            "final_intent": plan.intent,
            "rules": plan.rules,
            "entities": {
                "companies": [{"id": c, "name": self.kb.by_id[c]["name"]} for c in plan.companies],
                "sector": self.kb.sector_by_id[plan.sector]["name"] if plan.sector else None,
                "metric": plan.metric, "metrics": plan.metrics, "offtopic": plan.offtopic, "tech": plan.tech,
                "absent": plan.absent, "unknown": plan.unknown_names, "ambiguous": plan.ambiguous,
                "n": plan.n, "pct": plan.pct, "extreme": plan.extreme, "quality": plan.quality, "change": plan.change,
                "negated": plan.negated,
            },
            "used_context": plan.used_context,
            "grounding": {"numeric_paragraphs": numeric, "uncited": ungrounded,
                          "citations": len(a.citations), "dangling_refs": max_ref > len(a.citations)},
            "timing_ms": {"understand": round(parse_ms, 1), "compose": round(compose_ms, 1)},
            "dataset": self.kb.meta["dataset_id"],
        }
