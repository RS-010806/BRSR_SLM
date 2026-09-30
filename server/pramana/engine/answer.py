"""Answer container with citation bookkeeping.

Prose may only contain numbers that come with a citation marker [n]. The
marker indexes into `citations`, each of which points at an exact source:
a workbook cell, a Rating-sheet score, a report table row with its PDF page,
a verbatim report sentence, or a derived formula whose inputs are themselves
cited.
"""
from __future__ import annotations

import hashlib
import json

from .fmt import num, short_name


class Answer:
    def __init__(self, kb, plan):
        self.kb = kb
        self.plan = plan
        self.status = "answered"      # answered | partial | not_found | out_of_scope | clarify
        self.title = ""
        self.kicker = ""
        self.lead: list[str] = []
        self.blocks: list[dict] = []
        self.citations: list[dict] = []
        self._keys: dict[str, int] = {}
        self.followups: list[str] = []
        self.notes: list[dict] = []
        self.context: dict = {}
        self.entities: list[dict] = []

    # ------------------------------------------------------------------ text
    def p(self, text: str):
        self.lead.append(text)

    def block(self, typ: str, **kw):
        self.blocks.append({"type": typ, **kw})

    def note(self, kind: str, text: str):
        if not any(n["text"] == text for n in self.notes):
            self.notes.append({"kind": kind, "text": text})

    def follow(self, *qs: str):
        for q in qs:
            if q and q not in self.followups and len(self.followups) < 4:
                self.followups.append(q)

    # ------------------------------------------------------------------ citations
    def _cite(self, key: str, payload: dict) -> int:
        if key in self._keys:
            return self._keys[key]
        payload["id"] = len(self.citations) + 1
        self.citations.append(payload)
        self._keys[key] = payload["id"]
        return payload["id"]

    def c_cell(self, c: dict, qid: str, display: str | None = None) -> str:
        q = self.kb.q(qid)
        cell = c["cells"].get(qid)
        if cell is None or not q.get("raw_reliable", True) or q.get("rating_only"):
            return self.c_rating(c, qid)
        raw = c["values"].get(qid)
        payload = {
            "kind": "cell", "sheet": "Base Data", "cell": cell, "company": c["name"], "company_id": c["id"],
            "qid": qid, "question": q["label"], "brsr": q.get("brsr_element"),
            "value": display if display is not None else (num(raw) if isinstance(raw, float) else
                                                           ("blank" if raw is None else str(raw) if not isinstance(raw, bool)
                                                            else ("true" if raw else "false"))),
        }
        if q["type"] in ("text", "url") and isinstance(raw, str):
            payload["text"] = raw
        return f"[{self._cite('cell:' + c['id'] + ':' + qid, payload)}]"

    def c_rating(self, c: dict, qid: str) -> str:
        q = self.kb.q(qid)
        score = c["ratings"].get(qid)
        rub = q.get("rubric") or []
        level = next((l["text"] for l in rub if l["score"] == score), None)
        payload = {"kind": "rating", "sheet": "Rating", "cell": c["rating_cells"].get(qid), "company": c["name"],
                   "company_id": c["id"], "qid": qid, "question": q["label"], "score": score, "level": level,
                   "rubric": rub, "rule_source": q.get("rating_rule_source")}
        return f"[{self._cite('rating:' + c['id'] + ':' + qid, payload)}]"

    def c_table(self, tid: str, row: str | None = None, note: str | None = None) -> str:
        t = self.kb.tables[tid]
        payload = {"kind": "report_table", "table": tid, "title": t["title"], "pdf_page": t["pdf_page"],
                   "printed_page": t["printed_page"], "row": row, "note": note,
                   "columns": t["rows"][0], "rows": t["rows"][1:]}
        return f"[{self._cite('table:' + tid + ':' + str(row), payload)}]"

    def c_report_text(self, text: str, pdf_page: int | None, where: str) -> str:
        payload = {"kind": "report_text", "text": text, "pdf_page": pdf_page,
                   "printed_page": pdf_page - 6 if pdf_page else None, "where": where}
        key = "rt:" + hashlib.md5(text.encode()).hexdigest()[:10]
        return f"[{self._cite(key, payload)}]"

    def c_derived(self, label: str, formula: str, inputs: list[str] | None = None, note: str | None = None) -> str:
        payload = {"kind": "derived", "label": label, "formula": formula, "inputs": inputs or [], "note": note}
        return f"[{self._cite('d:' + label + formula, payload)}]"

    def c_method(self, label: str, text: str) -> str:
        return f"[{self._cite('m:' + label, {'kind': 'method', 'label': label, 'text': text})}]"

    # ------------------------------------------------------------------ entities
    def company_ref(self, c: dict) -> dict:
        s = self.kb.sector_of(c)
        ref = {"id": c["id"], "name": c["name"], "short": short_name(c["name"]), "sector": s["name"], "sector_id": s["id"]}
        if not any(e["id"] == c["id"] for e in self.entities):
            self.entities.append(ref)
        return ref

    # ------------------------------------------------------------------ output
    def payload(self) -> dict:
        body = {
            "status": self.status, "title": self.title, "kicker": self.kicker, "lead": self.lead,
            "blocks": self.blocks, "citations": self.citations, "followups": self.followups, "notes": self.notes,
            "entities": self.entities,
        }
        canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        body["fingerprint"] = hashlib.sha256((self.kb.meta["dataset_id"] + canonical).encode()).hexdigest()[:16]
        body["context"] = self.context
        return body
