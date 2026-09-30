"""Recompute every table in the IIMB E1 chapter from the raw workbook and
compare it cell by cell with the published figures.

The result is served by /api/meta so users can see exactly which report
figures the engine reproduces, and it runs as a test in CI.
"""
from __future__ import annotations

import re

from .analytics import band_counts, category_counts, median, rating_distribution, sector_sum, yes_count
from .kb import KB


def num(s: str) -> float | None:
    s = s.strip().replace(",", "").replace("%", "").replace("−", "-")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def sector_rows(table):
    """Yield (sector_id_or_total, cells) for the per-sector report tables."""
    for r in table["rows"]:
        m = re.match(r"^S(\d+)\s*-", r[0])
        if m:
            yield f"S{m.group(1)}", r
        elif r[0].startswith("Total"):
            yield "TOTAL", r


class Recon:
    def __init__(self):
        self.checks = []

    def check(self, table, label, reported, computed, tol=0.0):
        ok = reported is not None and computed is not None and abs(reported - computed) <= tol
        self.checks.append({"table": table, "cell": label, "reported": reported,
                            "computed": None if computed is None else round(computed, 6), "match": ok})
        return ok


def run(kb: KB) -> dict:
    R = Recon()
    allc = kb.companies
    n = len(allc)
    T = kb.tables

    # ---- Section 1: yes/no tables
    for tid, qid in (("1.1", "232"), ("1.2", "241"), ("1.3", "250"), ("1.4", "259"), ("1.5", "268"), ("1.11", "344")):
        y, no = yes_count(allc, qid)
        rows = T[tid]["rows"]
        R.check(tid, rows[1][0], num(rows[1][1]), y)
        R.check(tid, rows[2][0], num(rows[2][1]), no)
        if len(rows[1]) > 2 and rows[1][2]:
            R.check(tid, rows[1][0] + " (%)", num(rows[1][2]), round(100 * y / n, 1), tol=0.05)

    # ---- 1.9 / 1.10 governance categories
    lv = category_counts(allc, "308", ["Director", "Committee of the Board", "Any other Committee"])
    for r in T["1.9"]["rows"][1:5]:
        key = "Blank" if r[0].startswith("Other") else r[0]
        R.check("1.9", r[0], num(r[1]), lv[key])
    fq = category_counts(allc, "326", ["Annually", "Half Yearly", "Quarterly", "Any other"])
    for r in T["1.10"]["rows"][1:6]:
        key = "Blank" if r[0].startswith("Other") else r[0]
        R.check("1.10", r[0], num(r[1]), fq[key])

    # ---- 2.1 / 2.4 yes by sector
    for tid, qid in (("2.1", "1341"), ("2.4", "1340")):
        for sid, r in sector_rows(T[tid]):
            members = allc if sid == "TOTAL" else kb.members(sid)
            y, no = yes_count(members, qid)
            R.check(tid, f"{r[0]} Yes", num(r[1]), y)
            R.check(tid, f"{r[0]} No/NA", num(r[2]), no)
            R.check(tid, f"{r[0]} Total", num(r[3]), len(members))

    # ---- 2.3 Scope 3 reporting counts
    for sid, r in sector_rows(T["2.3"]):
        members = allc if sid == "TOTAL" else kb.members(sid)
        cy = yes_count(members, "1387")[0]
        py = sum(1 for c in members if (c["values"].get("1389") or 0) > 0)
        R.check("2.3", f"{r[0]} current year", num(r[2]), cy)
        R.check("2.3", f"{r[0]} previous year", num(r[3]), py)

    # ---- 3.1 absolute Scope 1 and 2 by sector
    for sid, r in sector_rows(T["3.1"]):
        members = allc if sid == "TOTAL" else kb.members(sid)
        s1, s2 = sector_sum(members, "1330"), sector_sum(members, "1332")
        R.check("3.1", f"{r[0]} Scope 1", num(r[1]), round(s1), tol=1)
        R.check("3.1", f"{r[0]} Scope 2", num(r[2]), round(s2), tol=1)
        R.check("3.1", f"{r[0]} Scope 1+2", num(r[3]), round(s1 + s2), tol=1)
        R.check("3.1", f"{r[0]} ratio", num(r[4]), round(s1 / s2, 1) if s2 else None, tol=0.051)

    # ---- 3.2 year-on-year totals
    for sid, r in sector_rows(T["3.2"]):
        members = allc if sid == "TOTAL" else kb.members(sid)
        cy = sector_sum(members, "1330") + sector_sum(members, "1332")
        py = sector_sum(members, "1331") + sector_sum(members, "1333")
        R.check("3.2", f"{r[0]} CY", num(r[1]), cy, tol=0.01)
        R.check("3.2", f"{r[0]} PY", num(r[2]), py, tol=0.01)
        R.check("3.2", f"{r[0]} YoY %", num(r[3]), round((cy - py) / py * 100, 2), tol=0.006)

    # ---- 3.3 company-wise direction
    for sid, r in sector_rows(T["3.3"]):
        members = allc if sid == "TOTAL" else kb.members(sid)
        dirs = [c["derived"]["scope12_direction"] for c in members]
        R.check("3.3", f"{r[0]} decreased", num(r[1]), dirs.count("decreased"))
        R.check("3.3", f"{r[0]} increased", num(r[2]), dirs.count("increased"))
        R.check("3.3", f"{r[0]} not available", num(r[3]), dirs.count("not_available"))

    # ---- 3.4-3.7, 3.9-3.10 intensity bands and medians
    def band_table(tid, key):
        vals = [c["derived"][key] for c in allc if c["derived"][key] is not None]
        bc = band_counts(vals)
        rows = T[tid]["rows"]
        for i in range(5):
            R.check(tid, rows[i + 1][0], num(rows[i + 1][1]), bc[i])
        R.check(tid, "Total", num(rows[6][1]), len(vals))
        R.check(tid, "Median %", num(rows[6][2]), round(median(vals), 2), tol=0.006)

    band_table("3.4", "intensity_yoy_pct")
    band_table("3.6", "intensity_phys_yoy_pct")
    band_table("3.9", "scope3_intensity_yoy_pct")

    for tid, key, level in (("3.5", "intensity_yoy_pct", "intensity_cr_cy"),
                            ("3.7", "intensity_phys_yoy_pct", None),
                            ("3.10", "scope3_intensity_yoy_pct", None)):
        for sid, r in sector_rows(T[tid]):
            members = allc if sid == "TOTAL" else kb.members(sid)
            md = median(c["derived"][key] for c in members)
            if num(r[1]) is not None:
                R.check(tid, f"{r[0]} median YoY %", num(r[1]), round(md, 2) if md is not None else None, tol=0.006)
            if level:
                ml = median(c["derived"][level] for c in members)
                R.check(tid, f"{r[0]} median per crore", num(r[2]), round(ml, 1), tol=0.051)

    # ---- 3.8 Scope 3 sums
    for sid, r in sector_rows(T["3.8"]):
        members = allc if sid == "TOTAL" else kb.members(sid)
        R.check("3.8", f"{r[0]} CY", num(r[1]), sector_sum(members, "1388"), tol=0.01)
        R.check("3.8", f"{r[0]} PY", num(r[2]), sector_sum(members, "1389"), tol=0.01)

    # ---- AI-scored quality scales: the Rating sheet was re-scored after the
    # report tables were produced, so these are reported side by side rather
    # than asserted.
    divergent = {}
    for tid, qid in (("1.6", "277"), ("1.7", "286"), ("1.8", "295")):
        rows = T[tid]["rows"][1:6]
        dist = rating_distribution(allc, qid)
        divergent[tid] = {"qid": qid, "levels": [
            {"label": r[0], "report": int(num(r[1])), "rating_sheet": dist[s]}
            for r, s in zip(rows, ("0", "25", "50", "75", "100"))]}
    t22 = T["2.2"]["rows"]
    total_row = next(r for r in t22 if r[0].startswith("Total"))
    dist = rating_distribution(allc, "1342")
    labels = ["High Impact Projects", "Projects are well defined", "Projects have some measurable reduction",
              "Projects are small in scale", "No Projects"]
    divergent["2.2"] = {"qid": "1342", "levels": [
        {"label": lab, "report": int(num(total_row[i + 1])), "rating_sheet": dist[s]}
        for i, (lab, s) in enumerate(zip(labels, ("100", "75", "50", "25", "0")))]}

    total = len(R.checks)
    matched = sum(1 for c in R.checks if c["match"])
    by_table = {}
    for c in R.checks:
        t = by_table.setdefault(c["table"], {"checks": 0, "matched": 0})
        t["checks"] += 1
        t["matched"] += int(c["match"])
    return {"total": total, "matched": matched, "by_table": by_table,
            "mismatches": [c for c in R.checks if not c["match"]], "ai_scored_divergence": divergent}
