"""Read-only knowledge base loaded once at startup from data/build/*.json."""
from __future__ import annotations

import json
import os
from functools import cached_property
from pathlib import Path

BUILD_DIR = Path(os.environ.get("PRAMANA_DATA", Path(__file__).resolve().parents[2] / "data" / "build"))


class KB:
    def __init__(self, build_dir: Path = BUILD_DIR):
        kb = json.loads((build_dir / "kb.json").read_text())
        self.meta = kb["meta"]
        self.sections = kb["sections"]
        self.questions = {q["qid"]: q for q in kb["questions"]}
        self.sectors = kb["sectors"]
        self.sector_by_id = {s["id"]: s for s in self.sectors}
        self.companies = kb["companies"]
        self.by_id = {c["id"]: c for c in self.companies}
        self.report = json.loads((build_dir / "report.json").read_text())
        self.corpus = json.loads((build_dir / "corpus.json").read_text())
        self.tables = {t["id"]: t for t in self.report["tables"]}
        self.aliases = kb["aliases"]
        self.exec_summary = kb["exec_summary"]

    # ------------------------------------------------------------------ helpers
    def members(self, sector_id: str | None):
        if sector_id is None:
            return self.companies
        return [self.by_id[i] for i in self.sector_by_id[sector_id]["members"]]

    def sector_of(self, c) -> dict:
        return self.sector_by_id[c["sector"]]

    def q(self, qid: str) -> dict:
        return self.questions[qid]

    @cached_property
    def sector_order(self):
        return [s["id"] for s in self.sectors]


_KB: KB | None = None


def get_kb() -> KB:
    global _KB
    if _KB is None:
        _KB = KB()
    return _KB
