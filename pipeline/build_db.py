"""Compile the verified JSON knowledge base into a single SQLite database.

    python -m pipeline.build_db          (run after pipeline.build_dataset)

The database is the runtime source of truth. Besides the structured tables it
stores everything that used to be recomputed on every request:

  segments        every disclosure / report sentence with its specificity score
  cell_evidence   per (company, question): evidence score and practice themes
  tech_hits       per technology keyword: every matching sentence and span
  fts_words       FTS5 index (unicode61) over all sentences
  fts_trigram     FTS5 trigram index for exact substring search

The precomputation calls the same functions the engine used at request time,
so answers are byte-identical; only the latency changes.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from pramana.engine.evidence import specificity, themes_in  # noqa: E402
from pramana.nlu.linker import TECH_TERMS  # noqa: E402

BUILD = ROOT / "data" / "build"
DB = BUILD / "pramana.db"
TOKEN = re.compile(r"[a-z0-9]+")

SCHEMA = """
PRAGMA journal_mode = OFF;
PRAGMA synchronous = OFF;
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sectors (id TEXT PRIMARY KEY, name TEXT, short TEXT, nse_code TEXT, n INTEGER, members TEXT);
CREATE TABLE questions (qid TEXT PRIMARY KEY, section TEXT, type TEXT, label TEXT, body TEXT);
CREATE TABLE companies (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, sector TEXT REFERENCES sectors(id), sector_name TEXT,
  base_row INTEGER, rating_col TEXT, derived TEXT, flags TEXT, ord INTEGER);
CREATE TABLE answers (cid TEXT, qid TEXT, value TEXT, cell TEXT, PRIMARY KEY (cid, qid));
CREATE TABLE ratings (cid TEXT, qid TEXT, score INTEGER, cell TEXT, PRIMARY KEY (cid, qid));
CREATE TABLE aliases (alias TEXT PRIMARY KEY, ids TEXT);
CREATE TABLE segments (
  id INTEGER PRIMARY KEY, kind TEXT, cid TEXT, qid TEXT, seg INTEGER, start INTEGER, "end" INTEGER,
  text TEXT, spec REAL, extra TEXT);
CREATE INDEX segments_cell ON segments (cid, qid, seg);
CREATE TABLE cell_evidence (cid TEXT, qid TEXT, evidence REAL, themes TEXT, PRIMARY KEY (cid, qid));
CREATE TABLE tech_hits (term TEXT, cid TEXT, qid TEXT, seg_id INTEGER, spans TEXT);
CREATE INDEX tech_hits_term ON tech_hits (term);
CREATE VIRTUAL TABLE fts_words USING fts5(text, content='segments', content_rowid='id');
CREATE VIRTUAL TABLE fts_trigram USING fts5(text, content='segments', content_rowid='id', tokenize='trigram');
"""


def tech_regex(term: str) -> re.Pattern:
    phs = TECH_TERMS[term]
    pats = [r"\b" + re.escape(p).replace(r"\ ", r"[\s-]+") + r"\b" for p in phs]
    return re.compile("|".join(pats), re.I)


def main():
    t0 = time.time()
    kb = json.loads((BUILD / "kb.json").read_text())
    report = json.loads((BUILD / "report.json").read_text())
    corpus = json.loads((BUILD / "corpus.json").read_text())
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)

    meta = {"meta": kb["meta"], "sections": kb["sections"], "exec_summary": kb["exec_summary"], "report": report}
    # BM25 statistics over the whole corpus, so report retrieval ranks exactly as before
    df: dict[str, int] = {}
    total_len = 0
    for d in corpus:
        toks = TOKEN.findall(d["text"].lower())
        total_len += len(toks)
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    meta["bm25"] = {"n": len(corpus), "avgdl": total_len / max(len(corpus), 1), "df": df}
    con.executemany("INSERT INTO meta VALUES (?, ?)", [(k, json.dumps(v, ensure_ascii=False)) for k, v in meta.items()])

    con.executemany("INSERT INTO sectors VALUES (?,?,?,?,?,?)",
                    [(s["id"], s["name"], s["short"], s["nse_code"], s["n"], json.dumps(s["members"])) for s in kb["sectors"]])
    con.executemany("INSERT INTO questions VALUES (?,?,?,?,?)",
                    [(q["qid"], q["section"], q["type"], q["label"], json.dumps(q, ensure_ascii=False)) for q in kb["questions"]])
    rows_c, rows_a, rows_r = [], [], []
    for i, c in enumerate(kb["companies"]):
        rows_c.append((c["id"], c["name"], c["sector"], c["sector_name"], c["base_row"], c["rating_col"],
                       json.dumps(c["derived"]), json.dumps(c["flags"], ensure_ascii=False), i))
        for qid, v in c["values"].items():
            rows_a.append((c["id"], qid, json.dumps(v, ensure_ascii=False), c["cells"].get(qid)))
        for qid, cell in c["cells"].items():
            if qid not in c["values"]:
                rows_a.append((c["id"], qid, None, cell))
        for qid, s in c["ratings"].items():
            rows_r.append((c["id"], qid, s, c["rating_cells"].get(qid)))
    con.executemany("INSERT INTO companies VALUES (?,?,?,?,?,?,?,?,?)", rows_c)
    con.executemany("INSERT INTO answers VALUES (?,?,?,?)", rows_a)
    con.executemany("INSERT INTO ratings VALUES (?,?,?,?)", rows_r)
    con.executemany("INSERT INTO aliases VALUES (?,?)", [(a, json.dumps(ids)) for a, ids in kb["aliases"].items()])

    # segments, in corpus order (ids preserve order for deterministic tie-breaks)
    seg_rows = []
    for i, d in enumerate(corpus, start=1):
        extra = {k: v for k, v in d.items() if k not in ("kind", "cid", "qid", "seg", "start", "end", "text")}
        spec = specificity(d["text"]) if d["kind"] == "disclosure" else None
        seg_rows.append((i, d["kind"], d.get("cid"), d.get("qid"), d.get("seg"), d.get("start"), d.get("end"),
                         d["text"], spec, json.dumps(extra, ensure_ascii=False) if extra else None))
    con.executemany('INSERT INTO segments VALUES (?,?,?,?,?,?,?,?,?,?)', seg_rows)
    con.execute("INSERT INTO fts_words(rowid, text) SELECT id, text FROM segments")
    con.execute("INSERT INTO fts_trigram(rowid, text) SELECT id, text FROM segments WHERE kind = 'disclosure'")

    # per-cell evidence: identical to engine.h_practice._evidence_score and evidence.themes_in
    by_cell: dict[tuple, list] = {}
    for sid, kind, cid, qid, seg, s, e, text, spec, extra in seg_rows:
        if kind == "disclosure":
            by_cell.setdefault((cid, qid), []).append(spec)
    ev_rows = []
    for c in kb["companies"]:
        for qid, v in c["values"].items():
            if not isinstance(v, str):
                continue
            scores = sorted(by_cell.get((c["id"], qid), []), reverse=True)
            ev_rows.append((c["id"], qid, round(sum(scores[:3]), 3), json.dumps(themes_in(v))))
    con.executemany("INSERT INTO cell_evidence VALUES (?,?,?,?)", ev_rows)

    # technology keyword index (same patterns the search handler compiles)
    hit_rows = []
    for term in TECH_TERMS:
        rx = tech_regex(term)
        for sid, kind, cid, qid, seg, s, e, text, spec, extra in seg_rows:
            if kind != "disclosure":
                continue
            spans = [(m.start(), m.end()) for m in rx.finditer(text)]
            if spans:
                hit_rows.append((term, cid, qid, sid, json.dumps(spans)))
    con.executemany("INSERT INTO tech_hits VALUES (?,?,?,?,?)", hit_rows)

    con.execute("INSERT INTO fts_words(fts_words) VALUES ('optimize')")
    con.execute("INSERT INTO fts_trigram(fts_trigram) VALUES ('optimize')")
    con.commit()
    con.execute("VACUUM")
    con.close()
    digest = hashlib.sha256(DB.read_bytes()).hexdigest()[:12]
    print(f"pramana.db: {DB.stat().st_size / 1e6:.1f} MB, {len(rows_c)} companies, {len(seg_rows)} segments, "
          f"{len(ev_rows)} evidence cells, {len(hit_rows)} technology hits, sha {digest}, {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
