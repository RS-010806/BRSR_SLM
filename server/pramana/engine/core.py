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
from . import h_visual as HV
from . import metrics as M
from .answer import Answer
from .common import Ctx
from .evidence import DisclosureIndex

NUM_IN_TEXT = re.compile(r"(?<![\w\[])\d[\d,]*(?:\.\d+)?")
CITE = re.compile(r"\[(\d+)\]")
# Numbers that are labels, not figures: years, scope names, "Principle 6", "top 10".
LABEL_NUM = re.compile(r"\b(FY \d{4}-\d{2}|Scope [123]|1 \+ Scope 2|Principle 6|top \d+|"
                       r"\d[\d,]* (?:listed )?companies(?:\*\*)? (?:covered|I cover|match)|\d[\d,]* listed companies)\b")


class Engine:
    def __init__(self, kb: KB):
        self.kb = kb
        self.parser = Parser(kb)
        self.index = DisclosureIndex(kb)

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
        if any(r.startswith("no company named: answered for your company") or "-> company_metric: no company named" in r
               for r in plan.rules) and plan.metric in HI.GLOSSARY:
            term = {"scope1": "Scope 1", "scope2": "Scope 2", "scope3": "Scope 3", "scope12": "Scope 1 and Scope 2"}.get(
                plan.metric) or (HI.GLOSSARY[plan.metric][0][0].lower() + HI.GLOSSARY[plan.metric][0][1:])
            a.followups = a.followups[:3] + [f"What {'do' if plan.metric == 'scope12' else 'does'} {term} mean?"]
        for e in a.entities:
            # a company whose sector looks unexpected: say where the classification comes from
            if any(f["type"] == "classification" for f in self.kb.by_id[e["id"]]["flags"]):
                a.note("data", f"{e['short']} is shown under {e['sector']}, as in the sector classification used here.")
        if plan.fy_out_of_range:
            a.note("scope", f"Only FY 2024-25 and FY 2023-24 are available; {plan.fy_out_of_range} is not, so the figures "
                            f"shown are for FY 2024-25.")
        if plan.intent != "out_of_scope":
            from ..nlu.lexicon import OFFTOPIC
            labels = {o["key"]: o for o in OFFTOPIC}
            for key in plan.offtopic:
                o = labels.get(key)
                if o:
                    a.note("scope", f"{o['label']} is not available yet, so that part of the question is not answered.")
        for name in plan.absent:
            if a.status not in ("not_found",):
                a.note("scope", f"{name} is not among the {len(self.kb.companies)} companies covered.")
        # context for the next turn (explicit, client-held, so the server stays stateless)
        a.context.setdefault("intent", plan.intent)
        a.context.setdefault("companies", plan.companies[:6])
        a.context.setdefault("sector", plan.sector)
        a.context.setdefault("metric", plan.metric)
        a.context.setdefault("tech", plan.tech)
        # what the conversation has been told to remember travels with it (client-held)
        a.context["prefs"] = plan.prefs
        a.context["pending"] = {"text": plan.ambiguous[0]["text"], "ids": plan.ambiguous[0]["ids"]} \
            if a.status == "clarify" and plan.ambiguous else None
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
        if intent == "no_scores":
            return HI.no_scores(ctx)
        if intent == "greeting":
            return HI.greeting(ctx)
        if intent == "set_pref":
            return HI.learned(ctx)
        if intent == "clear_lens":
            return HC.clear_lens(ctx)
        if intent == "need_company":
            return HC.need_company(ctx)
        if p.ambiguous and (intent in COMPANY_INTENTS or intent in ("compare", "best_practice", "infographic")):
            return HI.clarify(ctx)
        if (p.absent or p.unknown_names) and not p.companies and intent in COMPANY_INTENTS | {"compare", "infographic"}:
            return HI.not_found(ctx)
        cos = p.companies
        if intent == "compare" and len(cos) < 2:
            intent = "company_metric" if p.metric else "company_profile"
        if intent in COMPANY_INTENTS and not cos:
            return HC.need_company(ctx)
        c = kb.by_id[cos[0]] if cos else None
        generic = p.generic_emissions or "scope3" in p.metrics
        if intent == "infographic":
            return HV.infographic(ctx, c, p.sector)
        if intent == "set_lens":
            return HC.set_lens(ctx, c)
        if intent == "company_profile":
            return HC.company_profile(ctx, c)
        if intent == "company_metric":
            return HC.company_metric(ctx, c, p.metric, generic) if p.metric else HC.company_profile(ctx, c)
        if intent == "compare":
            return HM.compare(ctx, cos, p.metric)
        if intent == "peer_list":
            return HM.peer_list(ctx, c, p.prefs.get("peers"))
        if intent == "peer_benchmark":
            return HM.peer_compare(ctx, c, p.metric, p.prefs.get("peers"))
        if intent == "simulate":
            return HC.simulate(ctx, c, p.metric or "scope12", p.pct)
        if intent == "sector_overview":
            if p.metric and not p.sector:
                return HS.all_sectors(ctx, p.metric)
            return HS.sector_overview(ctx, p.sector, p.metric)
        if p.by_sector and not p.sector and intent in ("ranking", "aggregate", "screen"):
            return HS.all_sectors(ctx, p.metric)
        if intent == "ranking":
            return HS.ranking(ctx, p.metric, p.sector, p.n, p.extreme, p.quality, p.change)
        if intent == "aggregate":
            return HS.aggregate(ctx, p.metric, p.sector, p.change)
        if intent == "screen":
            return HS.screen(ctx, p.metric, p.sector, p.negated, p.change)
        if intent == "best_practice":
            return HP.best_practice(ctx, p.metric, p.sector, cos[0] if cos else None)
        if intent == "text_search":
            return HP.text_search(ctx, p.sector)
        if intent == "explain":
            return HI.explain(ctx)
        if intent == "report_insights":
            if p.sector:
                return HS.sector_overview(ctx, p.sector, p.metric)
            if p.metric in M.NUMERIC or p.metric in M.BOOL_Q or p.metric in M.TEXT_Q:
                return HS.aggregate(ctx, p.metric, None)
            return HS.highlights(ctx)
        return HI.greeting(ctx)

    # ------------------------------------------------------------------ trace (internal: never sent to the browser)
    def _trace(self, plan, a: Answer, body, parse_ms, compose_ms) -> dict:
        ungrounded = []
        numeric = 0
        texts = list(a.lead)
        for b in a.blocks:
            if b["type"] == "points":
                texts += b["items"]
        for para in texts:
            stripped = LABEL_NUM.sub("", CITE.sub("", para))
            if NUM_IN_TEXT.search(stripped):
                numeric += 1
                if not CITE.search(para):
                    ungrounded.append(para[:120])
        max_ref = max((int(x) for para in texts for x in CITE.findall(para)), default=0)
        return {
            "query": plan.query,
            "resolved_query": plan.resolved_query,
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
            "learned": plan.learned,
            "prefs": plan.prefs,
            "few_shot": [{"q": q, "intent": i, "sim": s} for q, i, s in plan.neighbors[:3]],
            "grounding": {"numeric_paragraphs": numeric, "uncited": ungrounded,
                          "citations": len(a.citations), "dangling_refs": max_ref > len(a.citations)},
            "timing_ms": {"understand": round(parse_ms, 1), "compose": round(compose_ms, 1)},
            "dataset": self.kb.meta["dataset_id"],
        }
