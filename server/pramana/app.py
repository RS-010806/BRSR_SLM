"""HTTP API and static hosting for Pramana.

Answering is stateless: conversation context (including what the conversation
has learned) travels with each request, so any instance can answer any turn.
The app database only records anonymous usage events, explicit feedback and
share links (see store.py).
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import os
import threading
import time
from collections import OrderedDict, defaultdict, deque
from pathlib import Path

import orjson
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine.core import Engine
from .engine.fmt import short_name
from .kb import get_kb
from .nlu.parser import ARTIFACTS
from .reconcile import run as reconcile
from .store import Store

ROOT = Path(__file__).resolve().parents[2]
WEB = Path(os.environ.get("PRAMANA_WEB", ROOT / "web" / "dist"))
PDF = ROOT / "data" / "raw" / "IIMB_BRSR_Report_FY2024-25.pdf"
ADMIN_TOKEN = os.environ.get("PRAMANA_ADMIN_TOKEN", "")

t_boot = time.perf_counter()
kb = get_kb()
engine = Engine(kb)
RECON = reconcile(kb)
store = Store()
MODEL_CFG = {k: v for k, v in json.loads((ARTIFACTS / "config.json").read_text()).items() if k != "known_words"}
EVAL = json.loads((ARTIFACTS / "eval_report.json").read_text()) if (ARTIFACTS / "eval_report.json").exists() else None

app = FastAPI(title="Pramana API", version="2.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
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
    """(answer dict, raw json bytes, gzipped bytes), computed once per distinct question + context."""
    key = orjson.dumps([q.strip(), ctx], option=orjson.OPT_SORT_KEYS)
    hit = cache.get2(key)
    if hit is None:
        t = time.perf_counter()
        a = engine.ask(q, ctx)
        a["trace"]["timing_ms"]["total"] = round((time.perf_counter() - t) * 1000, 2)
        raw = orjson.dumps(a)
        hit = (a, raw, gzip.compress(raw, 6))
        cache.put(key, hit)
    return hit


WARM = ["What are Tata Steel's Scope 1 and Scope 2 emissions?", "How does ACC compare with its peers?",
        "Best practices for GHG reduction projects in cement", "Give me an overview of the power sector",
        "What if NTPC cuts Scope 1 by 10%?", "Which companies mention green hydrogen?", "What can you do?",
        "What are the key findings of the E1 report?", "Top 10 emitters", "Which sector emits the most?"]
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
    elif not path.startswith("/api/") and not path.startswith("/files/"):
        resp.headers.setdefault("Cache-Control", "no-cache")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    return resp


# ------------------------------------------------------------------ routes
@app.get("/api/health")
def health():
    return J({"ok": True, "dataset": kb.meta["dataset_id"], "store": store.kind, "boot_ms": BOOT_MS})


@app.get("/api/meta")
def meta():
    return J({
        "name": "Pramana",
        "dataset": kb.meta,
        "sectors": [{k: s[k] for k in ("id", "name", "short", "nse_code", "n")} for s in kb.sectors],
        "questions": [{k: q.get(k) for k in ("qid", "label", "section", "type", "unit", "ask", "report_tables",
                                             "ai_rated", "no_data", "rating_only")} for q in kb.questions.values()],
        "reconciliation": {k: RECON[k] for k in ("total", "matched", "by_table", "ai_scored_divergence")},
        "model": MODEL_CFG,
        "eval": {k: v for k, v in (EVAL or {}).items() if k != "failures"},
        "few_shot_exemplars": len(engine.parser.exemplars),
        "flags": {
            "report_exclusions": sum(1 for c in kb.companies if any(f["type"] == "report_exclusion" for f in c["flags"])),
            "unit_checks": sum(1 for c in kb.companies if any(f["type"] == "unit_check" for f in c["flags"])),
            "magnitude_checks": sum(1 for c in kb.companies if any(f["type"] == "magnitude_check" for f in c["flags"])),
            "classification": sum(1 for c in kb.companies if any(f["type"] == "classification" for f in c["flags"])),
        },
        "database": {"knowledge_base": "SQLite (read-only, FTS5)", "app": store.kind},
    })


@app.get("/api/companies")
def companies():
    return J([{"id": c["id"], "name": c["name"], "short": short_name(c["name"]), "sector": c["sector"],
               "sector_name": c["sector_name"]} for c in kb.companies])


def _directory():
    rows = []
    for c in kb.companies:
        d = c["derived"]
        abs_ok = d.get("abs_level_ok", True) and not any(f["type"] == "report_exclusion" for f in c["flags"])
        rows.append({
            "id": c["id"], "name": c["name"], "short": short_name(c["name"]), "sector": c["sector"],
            "sector_name": c["sector_name"],
            "s12": d["scope12_cy"], "s12_yoy": d["scope12_yoy_pct"], "abs_ok": abs_ok,
            "intensity": d["intensity_cr_cy"] if d["intensity_level_ok"] else None,
            "s3": c["values"].get("1388"), "assured": c["ratings"].get("1340") == 100,
            "scope3": c["ratings"].get("1387") == 100, "projects": c["ratings"].get("1341") == 100,
            "targets": c["ratings"].get("286"), "index": d["index"]["overall"],
            "flags": [f["type"] for f in c["flags"]],
        })
    return rows


def _sectors():
    from .analytics import median, sector_sum, yes_count
    out = []
    grand = sector_sum(kb.companies, "1330") + sector_sum(kb.companies, "1332")
    for s in kb.sectors:
        m = kb.members(s["id"])
        cy = sector_sum(m, "1330") + sector_sum(m, "1332")
        py = sector_sum(m, "1331") + sector_sum(m, "1333")
        out.append({
            "id": s["id"], "name": s["name"], "short": s["short"], "nse_code": s["nse_code"], "n": s["n"],
            "s12": cy, "share": cy / grand * 100, "yoy": (cy - py) / py * 100 if py else None,
            "median_intensity": median(c["derived"]["intensity_cr_cy"] for c in m),
            "assured": yes_count(m, "1340")[0], "scope3": yes_count(m, "1387")[0], "projects": yes_count(m, "1341")[0],
            "median_index": median(c["derived"]["index"]["overall"] for c in m),
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
    store.add_feedback(body.fingerprint, body.q, body.intent, body.rating, body.note)
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


@app.get("/api/stats")
def stats():
    return J({**store.public_stats(), "cache_entries": len(cache)})


@app.get("/api/admin/summary")
def admin_summary(token: str = ""):
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(404)
    return J(store.admin_summary())


@app.get("/api/export/companies.csv")
def export_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["company", "sector", "scope1_fy25_tco2e", "scope2_fy25_tco2e", "scope12_fy25_tco2e", "scope12_yoy_pct",
                "intensity_fy25_tco2e_per_crore", "scope3_fy25_tco2e", "ghg_assured", "reports_scope3",
                "ghg_projects", "targets_score", "e1_index_derived", "flags"])
    for c in kb.companies:
        d, v, r = c["derived"], c["values"], c["ratings"]
        w.writerow([c["name"], c["sector_name"], v.get("1330"), v.get("1332"), d["scope12_cy"],
                    None if d["scope12_yoy_pct"] is None else round(d["scope12_yoy_pct"], 4),
                    None if d["intensity_cr_cy"] is None else round(d["intensity_cr_cy"], 6), v.get("1388"), r.get("1340") == 100, r.get("1387") == 100,
                    r.get("1341") == 100, r.get("286"), d["index"]["overall"],
                    ";".join(sorted({f["type"] for f in c["flags"]}))])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=pramana_e1_companies.csv"})


@app.get("/files/report.pdf")
def report_pdf():
    if not PDF.exists():
        raise HTTPException(404)
    return FileResponse(PDF, media_type="application/pdf", headers={"Cache-Control": "public, max-age=86400"})


if WEB.exists():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = WEB / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(WEB / "index.html")
