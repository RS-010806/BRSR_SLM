"""Answer container with citation bookkeeping.

Prose may only contain numbers that come with a citation marker [n]. The
marker indexes into `citations`. A citation is one of:

  filing    a value or passage a company disclosed in its BRSR filing
  computed  arithmetic over disclosed values, whose inputs are themselves cited
  note      a short explanation of how something is shown

Citations name only what is public: the company, the disclosure item and the
financial year. How the data is stored is never part of an answer.
"""
from __future__ import annotations

import hashlib
import json

from .fmt import exact, short_name
from .public import FLAG_NOTE, item


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

    def c_filing(self, c: dict, qid: str, display: str | None = None) -> str:
        """A value or passage from the company's own BRSR filing."""
        label, fy, where = item(qid)
        raw = c["values"].get(qid)
        if display is not None:
            value = display
        elif isinstance(raw, bool):
            value = "Yes" if raw else "No"
        elif isinstance(raw, (int, float)):
            value = exact(float(raw))
        elif raw is None:
            value = "Not disclosed"
        else:
            value = str(raw)
        payload = {"kind": "filing", "company": c["name"], "company_id": c["id"], "item": label, "fy": fy,
                   "where": where, "value": value}
        if isinstance(raw, str) and len(raw) > 80:
            payload["text"] = raw
            payload["value"] = None
        return f"[{self._cite('f:' + c['id'] + ':' + qid, payload)}]"

    def c_calc(self, label: str, formula: str, inputs: list[str] | None = None, note: str | None = None) -> str:
        payload = {"kind": "computed", "label": label, "formula": formula, "inputs": inputs or [], "note": note}
        return f"[{self._cite('c:' + label + formula, payload)}]"

    def c_note(self, label: str, text: str) -> str:
        return f"[{self._cite('n:' + label, {'kind': 'note', 'label': label, 'text': text})}]"

    # ------------------------------------------------------------------ entities
    def company_ref(self, c: dict) -> dict:
        s = self.kb.sector_of(c)
        ref = {"id": c["id"], "name": c["name"], "short": short_name(c["name"]), "sector": s["name"], "sector_id": s["id"]}
        if not any(e["id"] == c["id"] for e in self.entities):
            self.entities.append(ref)
        return ref

    def flag_notes(self, c: dict, qids, name: bool = False):
        """Plain-language note when a disclosed value looks like it uses a different unit."""
        for f in c.get("flags", []):
            text = FLAG_NOTE.get(f["type"])
            if text and set(f["qids"]) & set(qids):
                self.note("data", f"{short_name(c['name'])}: {text[0].lower() + text[1:]}" if name else text)

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
