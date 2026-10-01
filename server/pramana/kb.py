"""Read-only knowledge base, loaded from the SQLite database built by the pipeline.

The structured data (982 companies, their answers and ratings) is materialised
into plain dicts at startup because handlers touch it on every request. The
database additionally provides precomputed evidence (sentence specificity,
practice themes, technology hits) and FTS5 indexes for keyword search.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from functools import cached_property
from pathlib import Path

BUILD_DIR = Path(os.environ.get("PRAMANA_DATA", Path(__file__).resolve().parents[2] / "data" / "build"))
DB_PATH = BUILD_DIR / "pramana.db"


class KB:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._con = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True, check_same_thread=False)
        self._lock = threading.Lock()
        con = self._con
        meta = {k: json.loads(v) for k, v in con.execute("SELECT key, value FROM meta")}
        self.meta = meta["meta"]
        self.sections = meta["sections"]
        self.exec_summary = meta["exec_summary"]
        self.report = meta["report"]
        self.bm25_stats = meta["bm25"]
        self.tables = {t["id"]: t for t in self.report["tables"]}

        self.sectors = [{"id": i, "name": n, "short": sh, "nse_code": code, "n": k, "members": json.loads(m)}
                        for i, n, sh, code, k, m in con.execute("SELECT * FROM sectors ORDER BY rowid")]
        self.sector_by_id = {s["id"]: s for s in self.sectors}
        self.questions = {qid: json.loads(body) for qid, body in con.execute("SELECT qid, body FROM questions ORDER BY rowid")}

        companies = {}
        for cid, name, sector, sector_name, base_row, rating_col, derived, flags, _ in con.execute(
                "SELECT * FROM companies ORDER BY ord"):
            companies[cid] = {"id": cid, "name": name, "sector_name": sector_name, "base_row": base_row,
                              "rating_col": rating_col, "values": {}, "cells": {}, "ratings": {}, "rating_cells": {},
                              "derived": json.loads(derived), "flags": json.loads(flags), "sector": sector}
        for cid, qid, value, cell in con.execute("SELECT cid, qid, value, cell FROM answers ORDER BY rowid"):
            c = companies[cid]
            if value is not None:
                c["values"][qid] = json.loads(value)
            if cell is not None:
                c["cells"][qid] = cell
        for cid, qid, score, cell in con.execute("SELECT cid, qid, score, cell FROM ratings ORDER BY rowid"):
            companies[cid]["ratings"][qid] = score
            companies[cid]["rating_cells"][qid] = cell
        self.companies = list(companies.values())
        self.by_id = companies
        self.aliases = {a: json.loads(ids) for a, ids in con.execute("SELECT alias, ids FROM aliases ORDER BY alias")}

        self.corpus = []
        for sid, kind, cid, qid, seg, start, end, text, spec, extra in con.execute("SELECT * FROM segments ORDER BY id"):
            d = {"id": sid, "kind": kind, "text": text}
            if kind == "disclosure":
                d.update(cid=cid, qid=qid, seg=seg, start=start, end=end, spec=spec)
            else:
                if seg is not None:
                    d["seg"] = seg
                if extra:
                    d.update(json.loads(extra))
            self.corpus.append(d)
        self.evidence = {(cid, qid): ev for cid, qid, ev, _ in con.execute("SELECT * FROM cell_evidence")}
        self.cell_themes = {(cid, qid): json.loads(t) for cid, qid, _, t in con.execute("SELECT * FROM cell_evidence")}
        self.tech_hits: dict[str, list[tuple]] = {}
        for term, cid, qid, seg_id, spans in con.execute("SELECT * FROM tech_hits ORDER BY seg_id"):
            self.tech_hits.setdefault(term, []).append((seg_id, cid, qid, [tuple(s) for s in json.loads(spans)]))

    # ------------------------------------------------------------------ helpers
    def members(self, sector_id: str | None):
        if sector_id is None:
            return self.companies
        return [self.by_id[i] for i in self.sector_by_id[sector_id]["members"]]

    def sector_of(self, c) -> dict:
        return self.sector_by_id[c["sector"]]

    def q(self, qid: str) -> dict:
        return self.questions[qid]

    def themes(self, cid: str, qid: str) -> list[str]:
        return self.cell_themes.get((cid, qid), [])

    def evidence_score(self, cid: str, qid: str):
        return self.evidence.get((cid, qid), 0)

    def substring_segments(self, needle: str, qids: set[str], cids: set[str] | None) -> list[int]:
        """Disclosure segment ids containing `needle` (case-insensitive), via the trigram index."""
        like = "%" + needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        with self._lock:
            rows = self._con.execute(
                "SELECT rowid FROM fts_trigram WHERE text LIKE ? ESCAPE '\\' ORDER BY rowid", (like,)).fetchall() \
                if len(needle) >= 3 else [(d["id"],) for d in self.corpus
                                          if d["kind"] == "disclosure" and needle.lower() in d["text"].lower()]
        out = []
        for (sid,) in rows:
            d = self.corpus[sid - 1]
            if d["kind"] == "disclosure" and d["qid"] in qids and (cids is None or d["cid"] in cids):
                out.append(sid)
        return out

    @cached_property
    def sector_order(self):
        return [s["id"] for s in self.sectors]


_KB: KB | None = None


def get_kb() -> KB:
    global _KB
    if _KB is None:
        _KB = KB()
    return _KB
