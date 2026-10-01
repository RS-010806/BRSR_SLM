"""HTTP API and static hosting for Pramana.

Answering is stateless: conversation context (including what the conversation
has learned) travels with each request, so any instance can answer any turn.
The app database only records anonymous usage events, explicit feedback and
share links (see store.py).

What the browser receives is only what an end user should see: the answer,
its public sources and the context for the next turn. How a question was
understood, model details and data checks stay on the server and are
available only through the token-protected admin endpoints.
"""
from __future__ import annotations

import gzip
import json
import os
import threading
import time
from collections import OrderedDict, defaultdict, deque
from pathlib import Path

import orjson
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine.core import Engine
from .engine.common import yes, yes_count
from .engine.fmt import short_name
from .kb import get_kb
from .nlu.parser import ARTIFACTS
from .reconcile import run as reconcile
from .store import Store

ROOT = Path(__file__).resolve().parents[2]
WEB = Path(os.environ.get("PRAMANA_WEB", ROOT / "web" / "dist"))
ADMIN_TOKEN = os.environ.get("PRAMANA_ADMIN_TOKEN", "")

t_boot = time.perf_counter()
kb = get_kb()
engine = Engine(kb)
store = Store()
MODEL_CFG = {k: v for k, v in json.loads((ARTIFACTS / "config.json").read_text()).items() if k != "known_words"}
EVAL = json.loads((ARTIFACTS / "eval_report.json").read_text()) if (ARTIFACTS / "eval_report.json").exists() else None

app = FastAPI(title="Pramana API", version="3.0.0", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)


class J(Response):
    media_type = "application/json"

    def render(self, content) -> bytes:
        return orjson.dumps(content)


class Ctx(BaseModel):
    intent: str | None = None
    companies: list[str] = Field(default_factory=list)
    sector: str | None = None
    metric: str | None = None
    tech: list[str] = Field(default_factory=list)
    lens: str | None = None
    prefs: dict | None = None
    pending: dict | None = None


class AskBody(BaseModel):
    q: str = Field(..., max_length=600)
    context: Ctx | None = None


class FeedbackBody(BaseModel):
    fingerprint: str = Field(..., max_length=64)
    q: str = Field(..., max_length=600)
    intent: str | None = Field(None, max_length=40)
    rating: int
    note: str | None = Field(None, max_length=1000)


class ShareBody(BaseModel):
    q: str = Field(..., max_length=600)
    context: Ctx | None = None
    fingerprint: str | None = Field(None, max_length=64)


# ------------------------------------------------------------------ limits & cache
_hits: dict[str, deque] = defaultdict(deque)
RATE = int(os.environ.get("PRAMANA_RATE_PER_MIN", "150"))


def _limit(request: Request, weight: int = 1):
    ip = request.client.host if request.client else "anon"
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE:
        raise HTTPException(429, "Too many requests. Please wait a moment.")
    for _ in range(weight):
        q.append(now)


class LRU(OrderedDict):
    """Cache of finished answers. Safe because answers are deterministic."""

    def __init__(self, n):
        super().__init__()
        self.n = n
        self.lock = threading.Lock()

    def get2(self, k):
        with self.lock:
            if k in self:
                self.move_to_end(k)
                return self[k]
        return None

    def put(self, k, v):
        with self.lock:
            self[k] = v
            self.move_to_end(k)
            while len(self) > self.n:
                self.popitem(last=False)


cache = LRU(1024)


def _clean_ctx(ctx: Ctx | None) -> dict:
    d = ctx.model_dump() if ctx else {}
    return {k: v for k, v in d.items() if v not in (None, [], {})}


def _answer(q: str, ctx: dict):
    """(full answer, public json bytes, gzipped bytes), computed once per distinct question + context."""
    key = orjson.dumps([q.strip(), ctx], option=orjson.OPT_SORT_KEYS)
    hit = cache.get2(key)
    if hit is None:
        t = time.perf_counter()
        a = engine.ask(q, ctx)
        a["trace"]["timing_ms"]["total"] = round((time.perf_counter() - t) * 1000, 2)
        raw = orjson.dumps({k: v for k, v in a.items() if k != "trace"})   # the trace never leaves the server
        hit = (a, raw, gzip.compress(raw, 6))
        cache.put(key, hit)
        intents.put(a["fingerprint"], a["trace"]["final_intent"])
    return hit


intents = LRU(4096)   # answer id -> how it was routed, for feedback records

WARM = ["What are NTPC's GHG emissions?", "How does ACC compare with its peers?",
        "Examples of GHG reduction projects from cement companies", "Give me an overview of the power sector",
        "What if NTPC cuts Scope 1 by 10%?", "Which companies mention green hydrogen?", "What can you do?",
        "Top 10 emitters", "Which sector emits the most?", "Make an infographic for UltraTech"]
for _q in WARM:
    _answer(_q, {})
BOOT_MS = round((time.perf_counter() - t_boot) * 1000)


# ------------------------------------------------------------------ static caching
@app.middleware("http")
async def cache_headers(request: Request, call_next):
    resp = await call_next(request)
    path = request.url.path
    if path.startswith("/assets/"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif not path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-cache")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    return resp


# ------------------------------------------------------------------ routes
@app.get("/api/health")
def health():
    return J({"ok": True, "store": store.kind, "boot_ms": BOOT_MS})


@app.get("/api/meta")
def meta():
    return J({
        "name": "Pramana",
        "companies": len(kb.companies),
        "period": "FY 2024-25",
        "sectors": [{k: s[k] for k in ("id", "name", "short", "n")} for s in kb.sectors],
    })


@app.get("/api/companies")
def companies():
    return J([{"id": c["id"], "name": c["name"], "short": short_name(c["name"]), "sector": c["sector"],
               "sector_name": c["sector_name"]} for c in kb.companies])


def _directory():
    """One row per company with the figures it disclosed. Nothing derived from internal scoring."""
    rows = []
    for c in kb.companies:
        d, v = c["derived"], c["values"]
        differs = any(f["type"] in ("magnitude_check", "report_exclusion") for f in c["flags"])
        rows.append({
            "id": c["id"], "name": c["name"], "short": short_name(c["name"]), "sector": c["sector"],
            "sector_name": c["sector_name"],
            "s1": v.get("1330"), "s2": v.get("1332"), "s12": d["scope12_cy"], "s12_yoy": d["scope12_yoy_pct"],
            "s3": v.get("1388"), "intensity": d["intensity_cr_cy"] if d["intensity_level_ok"] else None,
            "assured": yes(c, "1340"), "scope3": yes(c, "1387"), "projects": yes(c, "1341"),
            "unit_note": differs,
        })
    return rows


def _sectors():
    from .analytics import median, sector_sum
    out = []
    grand = sector_sum(kb.companies, "1330") + sector_sum(kb.companies, "1332")
    for s in kb.sectors:
        m = kb.members(s["id"])
        s1, s2 = sector_sum(m, "1330"), sector_sum(m, "1332")
        py = sector_sum(m, "1331") + sector_sum(m, "1333")
        out.append({
            "id": s["id"], "name": s["name"], "short": s["short"], "n": s["n"],
            "s1": s1, "s2": s2, "s12": s1 + s2, "share": (s1 + s2) / grand * 100,
            "yoy": (s1 + s2 - py) / py * 100 if py else None,
            "median_intensity": median(c["derived"]["intensity_cr_cy"] for c in m if c["derived"]["intensity_level_ok"]),
            "assured": yes_count(m, "1340")[0], "scope3": yes_count(m, "1387")[0], "projects": yes_count(m, "1341")[0],
        })
    return out


DIRECTORY = orjson.dumps(_directory())
SECTORS = orjson.dumps(_sectors())


@app.get("/api/directory")
def directory():
    return Response(DIRECTORY, media_type="application/json", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/sectors")
def sectors():
    return Response(SECTORS, media_type="application/json", headers={"Cache-Control": "public, max-age=3600"})


@app.post("/api/ask")
def ask(body: AskBody, request: Request):
    prefetch = request.headers.get("x-pramana-prefetch") == "1"
    _limit(request)
    ctx = _clean_ctx(body.context)
    t = time.perf_counter()
    a, raw, gz = _answer(body.q, ctx)
    if not prefetch:
        store.log_event(body.q, a, (time.perf_counter() - t) * 1000)
    headers = {"X-Answer-Id": a["fingerprint"], "Cache-Control": "no-store", "Vary": "Accept-Encoding"}
    if "gzip" in request.headers.get("accept-encoding", ""):
        headers["Content-Encoding"] = "gzip"
        return Response(gz, media_type="application/json", headers=headers)
    return Response(raw, media_type="application/json", headers=headers)


@app.post("/api/feedback")
def feedback(body: FeedbackBody, request: Request):
    _limit(request)
    store.add_feedback(body.fingerprint, body.q, intents.get2(body.fingerprint) or body.intent, body.rating, body.note)
    return J({"ok": True})


@app.post("/api/share")
def share(body: ShareBody, request: Request):
    _limit(request)
    code = store.create_share(body.q, _clean_ctx(body.context), body.fingerprint)
    return J({"code": code, "path": f"/s/{code}"})


@app.get("/api/share/{code}")
def share_get(code: str):
    s = store.get_share(code[:16])
    if not s:
        raise HTTPException(404, "Unknown or expired link")
    return J(s)


def _admin(token: str):
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(404)


@app.get("/api/admin/summary")
def admin_summary(token: str = ""):
    _admin(token)
    return J({**store.admin_summary(), "usage": {**store.public_stats(), "cache_entries": len(cache)}})


@app.get("/api/admin/diagnostics")
def admin_diagnostics(token: str = ""):
    """Model, data checks and reconciliation. Internal: never shown in the product."""
    _admin(token)
    recon = reconcile(kb)
    return J({
        "dataset": kb.meta,
        "reconciliation": {k: recon[k] for k in ("total", "matched", "by_table")},
        "model": MODEL_CFG,
        "eval": {k: v for k, v in (EVAL or {}).items() if k != "failures"},
        "few_shot_exemplars": len(engine.parser.exemplars),
        "flags": {t: sum(1 for c in kb.companies if any(f["type"] == t for f in c["flags"]))
                  for t in ("report_exclusion", "unit_check", "magnitude_check", "classification")},
        "store": store.kind, "boot_ms": BOOT_MS,
    })


@app.get("/api/admin/trace")
def admin_trace(q: str, token: str = "", lens: str = ""):
    """How a question was understood and routed. Internal."""
    _admin(token)
    a, _, _ = _answer(q, {"lens": lens} if lens else {})
    return J(a["trace"])


if WEB.exists():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith(("api/", "files/")):
            raise HTTPException(404)
        f = WEB / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(WEB / "index.html")
