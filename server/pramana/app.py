"""HTTP API and static hosting for Pramana.

Stateless by design: conversation context travels with each request, so any
instance can answer any turn and nothing about the user is stored.
"""
from __future__ import annotations

import json
import os
import time
from collections import OrderedDict, defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine.core import Engine
from .engine.fmt import short_name
from .kb import get_kb
from .nlu.parser import ARTIFACTS
from .reconcile import run as reconcile

ROOT = Path(__file__).resolve().parents[2]
WEB = Path(os.environ.get("PRAMANA_WEB", ROOT / "web" / "dist"))
PDF = ROOT / "data" / "raw" / "IIMB_BRSR_Report_FY2024-25.pdf"

kb = get_kb()
engine = Engine(kb)
RECON = reconcile(kb)
MODEL_CFG = {k: v for k, v in json.loads((ARTIFACTS / "config.json").read_text()).items() if k != "known_words"}
EVAL = json.loads((ARTIFACTS / "eval_report.json").read_text()) if (ARTIFACTS / "eval_report.json").exists() else None

app = FastAPI(title="Pramana API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=1024)


class Ctx(BaseModel):
    intent: str | None = None
    companies: list[str] = Field(default_factory=list)
    sector: str | None = None
    metric: str | None = None
    tech: list[str] = Field(default_factory=list)
    lens: str | None = None


class AskBody(BaseModel):
    q: str = Field(..., max_length=600)
    context: Ctx | None = None


# ------------------------------------------------------------------ limits & cache
_hits: dict[str, deque] = defaultdict(deque)
RATE = int(os.environ.get("PRAMANA_RATE_PER_MIN", "90"))


def _limit(ip: str):
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE:
        raise HTTPException(429, "Too many requests. Please wait a moment.")
    q.append(now)


class LRU(OrderedDict):
    def __init__(self, n):
        super().__init__()
        self.n = n

    def get2(self, k):
        if k in self:
            self.move_to_end(k)
            return self[k]
        return None

    def put(self, k, v):
        self[k] = v
        self.move_to_end(k)
        while len(self) > self.n:
            self.popitem(last=False)


cache = LRU(512)


# ------------------------------------------------------------------ routes
@app.get("/api/health")
def health():
    return {"ok": True, "dataset": kb.meta["dataset_id"]}


@app.get("/api/meta")
def meta():
    return {
        "name": "Pramana",
        "dataset": kb.meta,
        "sectors": [{k: s[k] for k in ("id", "name", "short", "nse_code", "n")} for s in kb.sectors],
        "questions": [{k: q.get(k) for k in ("qid", "label", "section", "type", "unit", "ask", "report_tables",
                                             "ai_rated", "no_data", "rating_only")} for q in kb.questions.values()],
        "reconciliation": {k: RECON[k] for k in ("total", "matched", "by_table", "ai_scored_divergence")},
        "model": MODEL_CFG,
        "eval": {k: v for k, v in (EVAL or {}).items() if k != "failures"},
        "flags": {
            "report_exclusions": sum(1 for c in kb.companies if any(f["type"] == "report_exclusion" for f in c["flags"])),
            "unit_checks": sum(1 for c in kb.companies if any(f["type"] == "unit_check" for f in c["flags"])),
            "magnitude_checks": sum(1 for c in kb.companies if any(f["type"] == "magnitude_check" for f in c["flags"])),
        },
    }


@app.get("/api/companies")
def companies():
    return [{"id": c["id"], "name": c["name"], "short": short_name(c["name"]), "sector": c["sector"],
             "sector_name": c["sector_name"]} for c in kb.companies]


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


DIRECTORY = _directory()
SECTORS = _sectors()


@app.get("/api/directory")
def directory():
    return DIRECTORY


@app.get("/api/sectors")
def sectors():
    return SECTORS


@app.post("/api/ask")
def ask(body: AskBody, request: Request):
    _limit(request.client.host if request.client else "anon")
    ctx = body.context.model_dump() if body.context else {}
    key = json.dumps([body.q.strip(), ctx], sort_keys=True)
    hit = cache.get2(key)
    if hit is None:
        hit = engine.ask(body.q, ctx)
        cache.put(key, hit)
    return JSONResponse(hit)


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
