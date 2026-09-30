"""Application database: usage events, answer feedback and short share links.

Backend: Postgres when DATABASE_URL is set (Render), otherwise a local SQLite
file. Writes go through a background queue, so logging never adds latency to
an answer and a database outage never breaks one. Nothing identifying is
stored: no IP address, user agent, account or device id; only the question
text, how it was routed and how long it took.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("pramana.store")

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS events (
         id {pk}, ts TEXT NOT NULL, intent TEXT, status TEXT, latency_ms REAL, q TEXT,
         fingerprint TEXT, followup INTEGER)""",
    """CREATE TABLE IF NOT EXISTS feedback (
         id {pk}, ts TEXT NOT NULL, fingerprint TEXT, q TEXT, intent TEXT, rating INTEGER, note TEXT)""",
    """CREATE TABLE IF NOT EXISTS shares (
         code TEXT PRIMARY KEY, ts TEXT NOT NULL, q TEXT NOT NULL, ctx TEXT, fingerprint TEXT, hits INTEGER DEFAULT 0)""",
    "CREATE INDEX IF NOT EXISTS events_ts ON events (ts)",
]
ALPHABET = "23456789abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def share_code(q: str, ctx: dict) -> str:
    """Deterministic: the same question and context always get the same link."""
    h = int(hashlib.sha256(json.dumps([q.strip(), ctx], sort_keys=True).encode()).hexdigest(), 16)
    out = []
    for _ in range(9):
        h, r = divmod(h, len(ALPHABET))
        out.append(ALPHABET[r])
    return "".join(out)


class Store:
    def __init__(self):
        self.enabled = True
        self.log_queries = os.environ.get("PRAMANA_LOG_QUERIES", "1") != "0"
        self.kind = "sqlite"
        self._lock = threading.Lock()
        url = os.environ.get("DATABASE_URL", "")
        self._pg = None
        if url.startswith(("postgres://", "postgresql://")):
            try:
                import psycopg
                self._pg = psycopg.connect(url, autocommit=True, connect_timeout=5)
                self.kind = "postgres"
            except Exception as e:  # never block startup on the database
                log.warning("Postgres unavailable (%s); using SQLite", e)
        if self._pg is None:
            path = Path(os.environ.get("PRAMANA_APP_DB", Path(__file__).resolve().parents[2] / "data" / "app" / "app.db"))
            path.parent.mkdir(parents=True, exist_ok=True)
            self._sq = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
            self._sq.execute("PRAGMA journal_mode=WAL")
        pk = "BIGSERIAL PRIMARY KEY" if self.kind == "postgres" else "INTEGER PRIMARY KEY AUTOINCREMENT"
        for stmt in SCHEMA:
            self._exec(stmt.format(pk=pk))
        self._q: queue.Queue = queue.Queue(maxsize=5000)
        threading.Thread(target=self._worker, daemon=True, name="pramana-store").start()

    # ------------------------------------------------------------------ low level
    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.kind == "postgres" else sql

    def _exec(self, sql: str, args: tuple = (), fetch: bool = False):
        with self._lock:
            try:
                if self.kind == "postgres":
                    with self._pg.cursor() as cur:
                        cur.execute(self._sql(sql), args)
                        return cur.fetchall() if fetch else None
                cur = self._sq.execute(sql, args)
                return cur.fetchall() if fetch else None
            except Exception as e:
                log.warning("store error: %s", e)
                if self.kind == "postgres":
                    self._reconnect()
                return [] if fetch else None

    def _reconnect(self):
        try:
            import psycopg
            self._pg = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, connect_timeout=5)
        except Exception as e:
            log.warning("reconnect failed: %s", e)

    def _worker(self):
        while True:
            sql, args = self._q.get()
            self._exec(sql, args)

    def _enqueue(self, sql: str, args: tuple):
        try:
            self._q.put_nowait((sql, args))
        except queue.Full:
            pass

    # ------------------------------------------------------------------ writes
    def log_event(self, q: str, answer: dict, latency_ms: float):
        if not self.log_queries:
            return
        t = answer.get("trace", {})
        self._enqueue("INSERT INTO events (ts, intent, status, latency_ms, q, fingerprint, followup) VALUES (?,?,?,?,?,?,?)",
                      (_now(), t.get("final_intent"), answer.get("status"), round(latency_ms, 2), q[:300],
                       answer.get("fingerprint"), int(bool(t.get("used_context")))))

    def add_feedback(self, fingerprint: str, q: str, intent: str | None, rating: int, note: str | None):
        self._enqueue("INSERT INTO feedback (ts, fingerprint, q, intent, rating, note) VALUES (?,?,?,?,?,?)",
                      (_now(), fingerprint[:32], q[:300], (intent or "")[:40], 1 if rating > 0 else -1, (note or "")[:1000]))

    def create_share(self, q: str, ctx: dict, fingerprint: str | None) -> str:
        code = share_code(q, ctx)
        if self.kind == "postgres":
            sql = "INSERT INTO shares (code, ts, q, ctx, fingerprint) VALUES (?,?,?,?,?) ON CONFLICT (code) DO NOTHING"
        else:
            sql = "INSERT OR IGNORE INTO shares (code, ts, q, ctx, fingerprint) VALUES (?,?,?,?,?)"
        self._exec(sql, (code, _now(), q[:600], json.dumps(ctx, sort_keys=True), fingerprint))
        return code

    # ------------------------------------------------------------------ reads
    def get_share(self, code: str) -> dict | None:
        rows = self._exec("SELECT q, ctx, fingerprint FROM shares WHERE code = ?", (code,), fetch=True)
        if not rows:
            return None
        self._enqueue("UPDATE shares SET hits = hits + 1 WHERE code = ?", (code,))
        q, ctx, fp = rows[0]
        return {"q": q, "ctx": json.loads(ctx or "{}"), "fingerprint": fp}

    def public_stats(self) -> dict:
        tot = self._exec("SELECT COUNT(*), AVG(latency_ms) FROM events", fetch=True) or [(0, None)]
        by_status = dict(self._exec("SELECT status, COUNT(*) FROM events GROUP BY status", fetch=True) or [])
        by_intent = dict(self._exec("SELECT intent, COUNT(*) FROM events GROUP BY intent ORDER BY 2 DESC", fetch=True) or [])
        fb = dict(self._exec("SELECT rating, COUNT(*) FROM feedback GROUP BY rating", fetch=True) or [])
        n = tot[0][0] or 0
        answered = by_status.get("answered", 0)
        return {"backend": self.kind, "questions": n, "answered_share": round(100 * answered / n, 1) if n else None,
                "avg_latency_ms": round(tot[0][1], 2) if tot[0][1] is not None else None,
                "by_status": by_status, "by_intent": by_intent,
                "feedback": {"up": fb.get(1, 0), "down": fb.get(-1, 0)}}

    def admin_summary(self, limit: int = 50) -> dict:
        top = self._exec("SELECT q, COUNT(*) FROM events GROUP BY q ORDER BY 2 DESC LIMIT ?", (limit,), fetch=True)
        gaps = self._exec("SELECT q, status, COUNT(*) FROM events WHERE status <> 'answered' GROUP BY q, status "
                          "ORDER BY 3 DESC LIMIT ?", (limit,), fetch=True)
        fb = self._exec("SELECT ts, rating, q, intent, note FROM feedback ORDER BY id DESC LIMIT ?", (limit,), fetch=True)
        return {"top_questions": [{"q": a, "n": b} for a, b in top],
                "not_fully_answered": [{"q": a, "status": b, "n": c} for a, b, c in gaps],
                "recent_feedback": [{"ts": a, "rating": b, "q": c, "intent": d, "note": e} for a, b, c, d, e in fb]}

    def flush(self, timeout: float = 2.0):
        end = time.time() + timeout
        while not self._q.empty() and time.time() < end:
            time.sleep(0.02)
