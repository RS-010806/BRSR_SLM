"""Company-level answers: a single metric, a full profile, the lens, what-if."""
from __future__ import annotations

import re

from ..analytics import median
from . import metrics as M
from .common import (bars, beat_share, change_tone, compact_value, eligible, fmt_short, fmt_value, kpi, rank_of,
                     rank_phrase, strip, yes_rate)
from .evidence import highlight, themes_in
from .fmt import lc, CO2, compact, join, num, pct, share, short_name

BOOL_PHRASE = {
    "232": ("has a policy covering NGRBC Principle 6 (environment)", "does not report a Principle 6 policy",
            "have a Principle 6 policy"),
    "241": ("has had its Principle 6 policy approved by the Board", "does not report Board approval of the policy",
            "report Board approval"),
    "250": ("provides a public web link to its policies", "does not provide a valid public policy link",
            "provide a valid policy link"),
    "259": ("has translated the policy into procedures", "does not report translating the policy into procedures",
            "report operational procedures"),
    "268": ("extends the policy to value chain partners", "does not extend the policy to value chain partners",
            "extend the policy to value chain partners"),
    "344": ("has had its policies independently assessed by an external agency",
            "has not had its policies independently assessed", "report an independent policy assessment"),
    "1329": ("reports GHG emissions and intensity as applicable", "marks the GHG emissions disclosure as not applicable",
             "report the GHG disclosure as applicable"),
    "1340": ("has had its GHG emissions independently assessed or assured by an external agency",
             "does not report independent assessment or assurance of its GHG emissions",
             "report independent GHG assurance"),
    "1341": ("has projects to reduce GHG emissions", "does not report GHG reduction projects",
             "report GHG reduction projects"),
    "1387": ("reports Scope 3 emissions", "does not report Scope 3 emissions", "report Scope 3 emissions"),
    "1560": ("has had its Scope 3 emissions independently assured", "does not report independent assurance of Scope 3",
             "report independent Scope 3 assurance"),
}
QTABLE = {"232": "1.1", "241": "1.2", "250": "1.3", "259": "1.4", "268": "1.5", "344": "1.11", "1340": "2.4",
          "1341": "2.1", "1387": "2.3"}

# What each outcome rating actually scores (the Rating sheet scores the change on
# some rows and the level against the industry on others).
RATING_LABEL = {
    "1330": "Scope 1: change vs FY 2023-24", "1332": "Scope 2: change vs FY 2023-24",
    "1388": "Scope 3: change vs FY 2023-24",
    "1334": "Intensity per rupee: level vs industry", "1335": "Intensity per rupee: change",
    "1336": "PPP intensity: level vs industry", "1337": "PPP intensity: change",
    "1338": "Physical intensity: level vs industry", "1339": "Physical intensity: change",
    "1390": "Scope 3 intensity: level vs industry", "1391": "Scope 3 intensity: change",
}

RATIO_RULE = re.compile(r"if \(Q(\d+)/Q(\d+)\)\s*(.*)$", re.I)


def friendly_rule(text: str | None) -> str | None:
    """Turn a Rating-sheet ratio rule into plain words (the original stays in the citation)."""
    if not text:
        return text
    m = RATIO_RULE.match(text.strip())
    if not m:
        return text.rstrip(".")
    cond = m.group(3).strip().lower()
    if cond.startswith("> 1.05"):
        return "rose by more than 5% year on year"
    if cond.startswith("between 1 to 1.05"):
        return "rose by up to 5% year on year"
    if cond.startswith("= 1"):
        return "unchanged year on year"
    if cond.startswith("between 0.95 to 1"):
        return "fell by up to 5% year on year"
    if cond.startswith("< 0.95"):
        return "fell by more than 5% year on year"
    return text


def rating_sentence(ctx, c, qid) -> str | None:
    a = ctx.a
    s = c["ratings"].get(qid)
    if s is None:
        return None
    q = ctx.kb.q(qid)
    level = next((l["text"] for l in (q.get("rubric") or []) if l["score"] == s), None)
    ratio_rule = (level or "").lower().startswith("if (q")
    what = "year-on-year movement" if ratio_rule else "disclosure"
    if "standard deviation" in (level or ""):
        what = "level against the industry mean"
    zero = ""
    if ratio_rule and s == 100:
        m = RATIO_RULE.match(level.strip())
        if m and c["values"].get(m.group(1)) == 0 and c["values"].get(m.group(2)) == 0:
            zero = ", because both years are reported as 0, which the Rating sheet scores as 100"
            return f"The Rating sheet scores this {what} **{s}/100**{zero} {a.c_rating(c, qid)}."
    return f"The Rating sheet scores this {what} **{s}/100** ({friendly_rule(level)}) {a.c_rating(c, qid)}."


def rubric_block(ctx, c, qid, members=None):
    q = ctx.kb.q(qid)
    rub = q.get("rubric")
    if not rub:
        return None
    dist = None
    if members:
        dist = {str(l["score"]): sum(1 for m in members if m["ratings"].get(qid) == l["score"]) for l in rub}
        dist["none"] = sum(1 for m in members if m["ratings"].get(qid) is None)
    return {"type": "rubric", "qid": qid, "question": q["label"], "score": c["ratings"].get(qid),
            "levels": [{"score": l["score"], "text": friendly_rule(l["text"]), "raw": l["text"]} for l in rub],
            "distribution": dist, "distribution_label": ctx.kb.sector_of(c)["name"] if members else None,
            "source": q.get("rating_rule_source"),
            "zero_note": "When both years are reported as 0, the Rating sheet assigns 100."
            if (l := (rub[0]["text"] or "")).lower().startswith("if (q") else None}


def flag_notes(ctx, c, qids):
    for f in c["flags"]:
        if set(f["qids"]) & set(qids):
            ctx.a.note("data_quality", f["text"])


def _sector_label(ctx, c):
    s = ctx.kb.sector_of(c)
    return s["name"], s


# --------------------------------------------------------------------------- numeric

def company_numeric(ctx, c, metric: M.Metric):
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    sname, sec = _sector_label(ctx, c)
    members = kb.members(c["sector"])
    a.kicker = f"{c['name']} · {sname}"
    a.title = metric.label
    v, pv, y = metric.value(c), metric.prev(c), metric.yoy(c) if metric.yoy else None

    if metric.id == "scope12":
        c_cy = a.c_derived(f"Scope 1+2, FY 2024-25 ({short_name(c['name'])})",
                           f"{num(c['values'].get('1330'))} + {num(c['values'].get('1332'))} = {num(v)} {CO2}",
                           [a.c_cell(c, "1330"), a.c_cell(c, "1332")])
        c_py = a.c_derived(f"Scope 1+2, FY 2023-24 ({short_name(c['name'])})",
                           f"{num(c['values'].get('1331'))} + {num(c['values'].get('1333'))} = {num(pv)} {CO2}",
                           [a.c_cell(c, "1331"), a.c_cell(c, "1333")])
    elif metric.kind == "intensity" and metric.comparable_levels:
        raw_cy, raw_py = c["values"].get(metric.cy_q), c["values"].get(metric.py_q)
        c_cy = a.c_derived(f"{metric.label} per crore, FY 2024-25", f"{num(raw_cy)} per rupee x 10,000,000 = {num(v)}",
                           [a.c_cell(c, metric.cy_q)]) if raw_cy is not None else a.c_cell(c, metric.cy_q)
        c_py = a.c_derived(f"{metric.label} per crore, FY 2023-24", f"{num(raw_py)} per rupee x 10,000,000 = {num(pv)}",
                           [a.c_cell(c, metric.py_q)]) if raw_py is not None else a.c_cell(c, metric.py_q)
    else:
        c_cy, c_py = a.c_cell(c, metric.cy_q), a.c_cell(c, metric.py_q)

    if v is None:
        a.status = "partial"
        a.p(f"**{c['name']}** did not report {lc(metric.label)} for FY 2024-25 {c_cy}. "
            f"Under the IIMB methodology, non-disclosure is itself treated as analytically meaningful "
            f"{a.c_report_text(METHOD_NONDISCLOSURE, 26, 'Chapter 2, Treatment of Errors and Non-Disclosure')}.")
        pairs = eligible(metric, members)
        a.p(f"In {sname}, {len(pairs)} of {len(members)} companies reported a comparable value.")
        a.block("callout", tone="missing", title="Not reported",
                text=f"The source cell for this company is blank. Nothing is estimated or filled in.")
        if pairs:
            a.block(**strip(f"{metric.label} across {sname}", pairs, metric, subtitle="Companies that did report"))
        a.follow(f"Show {short_name(c['name'])}'s E1 profile", f"Which {sname} companies report {lc(metric.label)}?")
        return

    s = f"**{c['name']}** reported **{lc(metric.label)} of {fmt_value(metric, v)}** in FY 2024-25 {c_cy}"
    if pv is not None:
        s += f", against {fmt_value(metric, pv)} in FY 2023-24 {c_py}"
        if y is not None:
            s += f", a change of **{pct(y)}**"
    a.p(s + ".")
    if not metric.comparable_levels and metric.note:
        a.note("method", metric.note)
    for q in metric.rating_q:
        rs = rating_sentence(ctx, c, q)
        if rs:
            a.p(rs)
    mag = next((f for f in c["flags"] if f["type"] == "magnitude_check" and set(f["qids"]) & set(metric.qids)), None)
    if mag and metric.kind == "abs":
        mc = a.c_derived("Magnitude check", f"{num(mag['value'])} / {num(mag['sector_median'])} (sector median) "
                                            f"< 0.001", note=mag["text"])
        a.p(f"**Data-quality flag:** the filed Scope 1+2 total is below 0.1% of the {sname} median, which suggests "
            f"a scaled unit (thousand or million {CO2}). The value is shown exactly as filed and is not ranked against "
            f"peers {mc}.")
    flag_notes(ctx, c, metric.qids)

    pairs = eligible(metric, members)
    blocks_after = []
    if metric.comparable_levels and metric.level_ok(c):
        r, n, ordered = rank_of(c, pairs, descending=True)
        med = median(v2 for _, v2 in pairs)
        beat, others = beat_share(v, pairs, c, metric.better)
        cm = a.c_derived(f"{sname} ranking on {lc(metric.label)}",
                         f"{n} companies with comparable values, sorted high to low; median {fmt_value(metric, med)}",
                         note="Ties broken alphabetically. Report exclusions and unit-check flags removed.")
        a.p(f"Among {n} {sname} companies with comparable data, that is **{rank_phrase(r, n)}** {cm}. "
            f"The sector median is {fmt_value(metric, med)}; "
            f"{short_name(c['name'])} is {'lower' if metric.better == 'lower' else 'higher'} than "
            f"{beat} of its {others} peers.")
        top = ordered[:10]
        if c["id"] not in [x["id"] for x, _ in top]:
            top = top + [(c, v)]
        rows = bars(f"{metric.label}: {sname}", top, metric, focus_ids={c["id"]}, median_v=med,
                    subtitle=f"FY 2024-25, top 10 of {n} plus {short_name(c['name'])}", log=metric.kind == "abs")
        for row in rows["rows"]:
            row["rank"] = next(i for i, (x, _) in enumerate(ordered, 1) if x["id"] == row["id"])
        blocks_after.append(rows)
        blocks_after.append(strip(f"Where {short_name(c['name'])} sits in {sname}", pairs, metric, focus_ids={c["id"]},
                                  subtitle=f"{n} companies, FY 2024-25"))
    if y is not None:
        ypairs = eligible(metric, members, by="yoy")
        ymed = median(v2 for _, v2 in ypairs)
        if ymed is not None:
            yc = a.c_derived(f"{sname} median change in {lc(metric.label)}",
                             f"median of {len(ypairs)} company-level year-on-year changes = {pct(ymed, digits=2)}")
            a.p(f"Its year-on-year change of {pct(y)} compares with a {sname} median change of {pct(ymed)} "
                f"across {len(ypairs)} companies {yc}.")
    tiles = [kpi("FY 2024-25", fmt_short(metric, v), sub=metric.unit, cite=c_cy),
             kpi("FY 2023-24", fmt_short(metric, pv), sub=metric.unit, cite=c_py)]
    if y is not None:
        tiles.append(kpi("Year on year", pct(y), sub="change vs FY 2023-24",
                         delta=("fell" if y < 0 else "rose" if y > 0 else "flat"), tone=change_tone(y, metric.better)))
    for q in metric.rating_q[:2]:
        sc = c["ratings"].get(q)
        if sc is not None:
            tiles.append(kpi(f"Rating Q{q}", f"{sc}", sub="out of 100", cite=a.c_rating(c, q)))
    a.block("kpis", items=tiles)
    a.blocks.extend(blocks_after)
    for q in metric.rating_q[:1]:
        rb = rubric_block(ctx, c, q, members)
        if rb:
            a.blocks.append(rb)
    if metric.note and metric.comparable_levels:
        a.note("method", metric.note)
    peer = _nearest_peer(c, pairs)
    a.follow(f"How does {short_name(c['name'])} compare with its peers?",
             f"Compare {short_name(c['name'])} and {short_name(peer['name'])} on {lc(metric.label)}" if peer else None,
             f"What if {short_name(c['name'])} cuts {metric.label.split(' (')[0]} by 10%?" if metric.kind in ("abs", "intensity") and metric.comparable_levels else None,
             f"Top 10 {sname} companies by {lc(metric.label)}")
    a.context.update({"metric": metric.id})


def _nearest_peer(c, pairs):
    v = next((x for cc, x in pairs if cc["id"] == c["id"]), None)
    if v is None:
        return None
    others = sorted(((abs(x - v), cc["name"].lower(), cc) for cc, x in pairs if cc["id"] != c["id"]), key=lambda t: (t[0], t[1]))
    return others[0][2] if others else None


# --------------------------------------------------------------------------- yes / no

def company_bool(ctx, c, qid):
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    sname, sec = _sector_label(ctx, c)
    members = kb.members(c["sector"])
    q = kb.q(qid)
    a.kicker = f"{c['name']} · {sname}"
    a.title = q["label"]
    score = c["ratings"].get(qid)
    raw = c["values"].get(qid)
    yes = score == 100 if score is not None else bool(raw)
    pos, neg, plural = BOOL_PHRASE.get(qid, (f"reports {lc(q['label'])}", f"does not report {lc(q['label'])}",
                                              f"report {lc(q['label'])}"))
    ev = a.c_cell(c, qid)
    rc = a.c_rating(c, qid)
    a.p(f"**{'Yes' if yes else 'No'}.** {c['name']} {pos if yes else neg} {ev}{'' if ev == rc else ' ' + rc}.")
    if qid == "250" and isinstance(raw, str):
        urls = re.findall(r"https?://\S+", raw)
        if urls:
            a.block("links", items=[u.rstrip(".,;)") for u in urls[:4]], title="Links as disclosed")
    y, n = yes_rate(members, qid)
    Y, N = yes_rate(kb.companies, qid)
    tcite = a.c_table(QTABLE[qid], sname if QTABLE[qid] in ("2.1", "2.3", "2.4") else None) if qid in QTABLE else \
        a.c_derived(f"Q{qid} across companies", f"companies with Rating-sheet score 100: {y} of {n} in {sname}, {Y} of {N} overall")
    a.p(f"In {sname}, {y} of {n} companies ({share(y, n)}) {plural}; across all {N} companies the figure is "
        f"{Y} ({share(Y, N)}) {tcite}.".replace(" .", "."))
    comp = M.COMPANION_TEXT.get(qid)
    if comp and comp != qid and c["values"].get(comp):
        text_quote(ctx, c, comp, title=kb.q(comp)["label"])
    a.block("kpis", items=[kpi(q["label"], "Yes" if yes else "No", sub=f"Rating {score if score is not None else 'n/a'}/100",
                               tone="good" if yes else "bad", cite=rc, big=True),
                           kpi(f"{sname}", share(y, n), sub=f"{y} of {n} companies"),
                           kpi("All companies", share(Y, N), sub=f"{Y} of {N} companies")])
    a.block("stack", title=f"{q['label']}: {short_name(sname) if len(sname) > 30 else sname} vs all companies",
            rows=[{"label": sname, "segments": [{"label": "Yes", "value": y, "tone": "pos"},
                                                  {"label": "No / NA / blank", "value": n - y, "tone": "neg"}]},
                  {"label": "All companies", "segments": [{"label": "Yes", "value": Y, "tone": "pos"},
                                                           {"label": "No / NA / blank", "value": N - Y, "tone": "neg"}]}])
    peers = sorted(members, key=lambda m: (m["ratings"].get(qid) != 100, m["name"].lower()))
    a.block("table", title=f"{sname} peers", columns=[{"key": "company", "label": "Company"},
                                                      {"key": "answer", "label": q["label"]}],
            rows=[{"company": short_name(m["name"]), "id": m["id"], "answer": "Yes" if m["ratings"].get(qid) == 100 else "No / NA",
                   "highlight": m["id"] == c["id"]} for m in peers], compact=True)
    a.follow(f"Show {short_name(c['name'])}'s E1 profile", f"Which {sname} companies {plural.replace('report ', 'lack ') if not yes else plural}?",
             f"Best practices on {lc(q['label'])}" if qid in ("1340", "1341") else None)


# --------------------------------------------------------------------------- narrative

def text_quote(ctx, c, qid, title=None, k=3):
    a = ctx.a
    text = c["values"].get(qid)
    if not text:
        return None
    segs = ctx.index.by_cell.get((c["id"], qid), [])
    hl = highlight(segs, k=k)
    item = {"company": c["name"], "company_id": c["id"], "short": short_name(c["name"]),
            "sector": ctx.kb.sector_of(c)["name"], "qid": qid, "question": title or ctx.kb.q(qid)["label"],
            "score": c["ratings"].get(qid), "text": text, "segments": hl, "themes": ctx.kb.themes(c["id"], qid),
            "cite": a.c_cell(c, qid), "cell": c["cells"].get(qid)}
    a.block("quotes", items=[item], title=title)
    return item


def company_text(ctx, c, qid):
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    sname, sec = _sector_label(ctx, c)
    members = kb.members(c["sector"])
    q = kb.q(qid)
    a.kicker = f"{c['name']} · {sname}"
    a.title = q["label"]
    text = c["values"].get(qid)
    if qid == "1342":
        has = c["ratings"].get("1341") == 100
        a.p(f"{c['name']} {'reports' if has else 'does not report'} projects to reduce GHG emissions "
            f"{a.c_cell(c, '1341')}.")
    if not text:
        a.status = "partial"
        a.p(f"The disclosure on {lc(q['label'])} is blank for {c['name']} {a.c_cell(c, qid)}. "
            f"Nothing is inferred in its place.")
        a.block("callout", tone="missing", title="No disclosure text",
                text="The source cell is empty. The rating for a blank response is shown where one exists.")
    else:
        item = text_quote(ctx, c, qid, title=q["label"])
        n_hl = sum(1 for s in item["segments"] if s["highlight"])
        a.p(f"Below is the disclosure exactly as filed {item['cite']}"
            + (f", with the {n_hl} most specific sentences highlighted (those carrying quantities, years or baselines)"
               if n_hl else "") + ".")
        if item["themes"]:
            a.p(f"Practices named in the text: {join([t.lower() for t in item['themes']])}.")
    rs = rating_sentence(ctx, c, qid)
    if rs:
        a.p(rs)
    top = sum(1 for m in members if m["ratings"].get(qid) == 100)
    tc = a.c_derived(f"Q{qid} scores of 100 in {sname}", f"{top} of {len(members)} companies (Rating sheet row {q.get('rating_row')})")
    a.p(f"In {sname}, {top} of {len(members)} companies score 100 on this question {tc}.")
    rb = rubric_block(ctx, c, qid, members)
    if rb:
        a.blocks.append(rb)
    if q.get("ai_rated"):
        a.note("method", "This question is scored with the report's quality scale (AI-assisted). Company scores come "
                         "from the Rating sheet; the report's aggregate table was produced from an earlier scoring run, "
                         "so its counts differ slightly. Both are shown on aggregate questions.")
    topic = {"286": "targets", "295": "performance against targets", "1342": "GHG reduction projects",
             "277": "certifications"}.get(qid, lc(q["label"]))
    a.follow(f"Best practices on {topic} in {sname}", f"How does {short_name(c['name'])} compare with its peers?",
             f"Show {short_name(c['name'])}'s E1 profile")


def company_category(ctx, c, qids):
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    sname, _ = _sector_label(ctx, c)
    members = kb.members(c["sector"])
    a.kicker = f"{c['name']} · {sname}"
    a.title = kb.q(qids[0])["label"]
    rows = []
    for q in qids:
        v = c["values"].get(q)
        a.p(f"{kb.q(q)['label']}: **{v or 'blank'}** {a.c_cell(c, q)}.")
        cats = {}
        for m in members:
            key = m["values"].get(q) or "Blank"
            cats[key] = cats.get(key, 0) + 1
        rows.append({"label": kb.q(q)["label"], "segments": [{"label": k, "value": cats[k], "highlight": k == (v or "Blank")}
                                                            for k in sorted(cats, key=lambda k: (-cats[k], k))]})
        rs = rating_sentence(ctx, c, q)
        if rs:
            a.p(rs)
    a.block("stack", title=f"How {sname} companies answer", rows=rows, categorical=True)
    if qids[0] == "308":
        a.p(f"Across all companies, see Report Table 1.9 {a.c_table('1.9')}.")
    if qids[0] == "326":
        a.p(f"Across all companies, see Report Table 1.10 {a.c_table('1.10')}.")


def company_metric(ctx, c, mid):
    if mid in M.NUMERIC and mid != "index":
        return company_numeric(ctx, c, M.NUMERIC[mid])
    if mid == "index":
        return company_profile(ctx, c)
    if mid in M.TEXT_Q:
        return company_text(ctx, c, M.TEXT_Q[mid])
    if mid in M.CATEGORY_Q:
        return company_category(ctx, c, M.CATEGORY_Q[mid])
    if mid in M.BOOL_Q:
        return company_bool(ctx, c, M.BOOL_Q[mid])
    if mid == "green_credits":
        a = ctx.a
        a.company_ref(c)
        a.status = "partial"
        a.kicker = c["name"]
        a.title = "Green credits"
        a.p(f"Green credits are part of the E1 question set (Q2210 for the entity, Q2211 for its top ten value chain "
            f"partners), but **no company has values populated for these questions** in the dataset "
            f"{a.c_method('Green credits coverage', 'Rating sheet rows 45 and 46 (Q2210, Q2211) are empty for all 982 companies.')}.")
        a.block("callout", tone="missing", title="Not available in the dataset",
                text="Nothing can be reported for green credits without inventing numbers, so none are shown.")
        a.follow(f"Show {short_name(c['name'])}'s GHG reduction projects", f"Show {short_name(c['name'])}'s targets")
        return
    return company_profile(ctx, c)


# --------------------------------------------------------------------------- profile

def company_profile(ctx, c):
    a, kb = ctx.a, ctx.kb
    ref = a.company_ref(c)
    sname, sec = _sector_label(ctx, c)
    members = kb.members(c["sector"])
    a.kicker = f"{sname} · {sec['n']} companies in sector"
    a.title = c["name"]
    m12 = M.NUMERIC["scope12"]
    v, y = m12.value(c), m12.yoy(c)
    t22 = a.c_report_text("Table 2.2: Sector Coverage, NSE Classification and Company Distribution", 23, "Chapter 2")
    if v is not None and m12.level_ok(c):
        pairs = eligible(m12, members)
        r, n, _ = rank_of(c, pairs, True)
        cite = a.c_derived(f"Scope 1+2, FY 2024-25 ({short_name(c['name'])})",
                           f"{num(c['values'].get('1330'))} + {num(c['values'].get('1332'))} = {num(v)} {CO2}",
                           [a.c_cell(c, "1330"), a.c_cell(c, "1332")])
        a.p(f"**{c['name']}** is one of {sec['n']} companies in {sname} {t22}. In FY 2024-25 it reported **Scope 1+2 "
            f"emissions of {compact(v)} {CO2}** {cite}"
            + (f" ({pct(y)} year on year)" if y is not None else "")
            + f", {rank_phrase(r, n)} in its sector.")
    elif v is not None:
        cite = a.c_derived(f"Scope 1+2, FY 2024-25 ({short_name(c['name'])})",
                           f"{num(c['values'].get('1330'))} + {num(c['values'].get('1332'))} = {num(v)} {CO2}",
                           [a.c_cell(c, "1330"), a.c_cell(c, "1332")])
        a.p(f"**{c['name']}** is one of {sec['n']} companies in {sname} {t22}. It filed Scope 1+2 emissions of "
            f"{num(v)} {CO2} for FY 2024-25 {cite}"
            + (f" ({pct(y)} year on year)" if y is not None else "")
            + ", a figure that carries a data-quality flag (see the note above), so it is not ranked against peers.")
        flag_notes(ctx, c, ["1330", "1331", "1332", "1333"])
    else:
        a.p(f"**{c['name']}** is one of {sec['n']} companies in {sname} {t22}. It did not report Scope 1 and 2 emissions "
            f"for FY 2024-25 {a.c_cell(c, '1330')}.")

    strengths, gaps = [], []
    checks = [("1340", "independent GHG assurance"), ("1387", "Scope 3 reporting"), ("1341", "GHG reduction projects"),
              ("268", "policy extended to the value chain"), ("344", "independent policy assessment"),
              ("241", "Board-approved policy")]
    for q, lab in checks:
        (strengths if c["ratings"].get(q) == 100 else gaps).append(f"{lab} {a.c_rating(c, q)}")
    for q, lab in (("286", "targets"), ("295", "performance against targets"), ("1342", "project quality")):
        s = c["ratings"].get(q)
        if s is None:
            continue
        if s >= 75:
            strengths.append(f"{lab} scored {s}/100 {a.c_rating(c, q)}")
        elif s <= 25:
            gaps.append(f"{lab} scored {s}/100 {a.c_rating(c, q)}")
    if strengths:
        a.p(f"**Strengths:** {join(strengths)}.")
    if gaps:
        a.p(f"**Gaps:** {join(gaps)}.")

    idx = c["derived"]["index"]
    ipairs = [(m, m["derived"]["index"]["overall"]) for m in members if m["derived"]["index"]["overall"] is not None]
    if idx["overall"] is not None:
        r, n, _ = rank_of(c, ipairs, True)
        med = median(x for _, x in ipairs)
        a.p(f"Its derived E1 index is **{idx['overall']:.1f}/100**, {rank_phrase(r, n, 'highest', 'lowest')} in {sname} "
            f"(sector median {med:.1f}) {a.c_method('E1 index (derived)', M.NUMERIC['index'].note)}.")

    tiles = []
    for mid in ("scope1", "scope2", "scope3", "intensity"):
        m = M.NUMERIC[mid]
        val, yy = m.value(c), m.yoy(c)
        cite = a.c_cell(c, m.cy_q) if m.cy_q else None
        tiles.append(kpi(m.label.replace(" emissions", ""), fmt_short(m, val) if val is not None else "n/r",
                         sub=m.unit if val is not None else "not reported",
                         delta=pct(yy) + " YoY" if yy is not None else None, tone=change_tone(yy, m.better), cite=cite))
    a.block("kpis", items=tiles)

    # pillar scores vs sector median
    pil = []
    for p_key, p_label in (("governance", "Governance"), ("action", "Action"), ("performance", "Performance")):
        mine = idx["pillars"][p_key]["score"]
        med = median(m["derived"]["index"]["pillars"][p_key]["score"] for m in members)
        pil.append({"label": p_label, "values": [mine, med],
                    "displays": [f"{mine:.0f}" if mine is not None else "n/a", f"{med:.0f}" if med is not None else "n/a"]})
    a.block("grouped", title="Pillar scores vs sector median", subtitle="Average Rating-sheet score per pillar, 0 to 100",
            series=[short_name(c["name"]), f"{sname} median"], groups=pil, max=100)

    # question-level score grid
    grid = []
    for sec_key, sec_label in (("governance", "Policy and governance"), ("action", "Actions taken"),
                               ("outcome", "Performance outcomes")):
        for q in kb.questions.values():
            if q["section"] != sec_key or not q.get("rubric") or q["qid"] in ("1331", "1333", "1389"):
                continue
            s = c["ratings"].get(q["qid"])
            ms = [m["ratings"].get(q["qid"]) for m in members if m["ratings"].get(q["qid"]) is not None]
            grid.append({"section": sec_label, "qid": q["qid"], "label": RATING_LABEL.get(q["qid"], q["label"]), "score": s,
                         "median": median(ms), "n": len(ms)})
    a.block("scoregrid", title="Question-level ratings", subtitle=f"{short_name(c['name'])} vs {sname} median",
            rows=grid, company=short_name(c["name"]))

    checklist = []
    for q in ("232", "241", "250", "259", "268", "344", "1340", "1341", "1387", "1560"):
        s = c["ratings"].get(q)
        checklist.append({"label": kb.q(q)["label"], "value": None if s is None else s == 100, "cite": a.c_rating(c, q)})
    a.block("checklist", title="Disclosure checklist", items=checklist)

    for q, title in (("286", "Targets, in their own words"), ("1342", "GHG reduction projects, in their own words")):
        if c["values"].get(q):
            text_quote(ctx, c, q, title=title, k=2)
    flag_notes(ctx, c, ["1330", "1331", "1332", "1333", "1334", "1335", "1390", "1391"])
    a.follow(f"How does {short_name(c['name'])} compare with its peers?",
             f"What can {short_name(c['name'])} learn from the best in {sname}?",
             f"What if {short_name(c['name'])} cuts Scope 1 by 10%?",
             f"Show {short_name(c['name'])}'s GHG reduction projects")


# --------------------------------------------------------------------------- lens

def set_lens(ctx, c):
    a = ctx.a
    a.company_ref(c)
    sname, sec = _sector_label(ctx, c)
    a.kicker = "Personalisation"
    a.title = f"Your lens: {short_name(c['name'])}"
    t22 = a.c_report_text("Table 2.2: Sector Coverage, NSE Classification and Company Distribution", 23, "Chapter 2")
    a.p(f"Answers will now be framed around **{c['name']}** ({sname}, {sec['n']} companies {t22}). Ask things like "
        f"\"how do we compare with our peers?\" or \"what can we learn from the leaders?\" and I will use this company.")
    a.p("The lens is stored only in this browser. No account, name or email is collected, and you can clear it at any time.")
    a.context["lens"] = c["id"]
    idx = c["derived"]["index"]["overall"]
    m = M.NUMERIC["scope12"]
    a.block("kpis", items=[kpi("Sector", sname, sub=f"{sec['n']} companies"),
                           kpi("Scope 1+2", fmt_short(m, m.value(c)) if m.value(c) is not None else "n/r", sub=CO2,
                               delta=pct(m.yoy(c)) + " YoY" if m.yoy(c) is not None else None,
                               tone=change_tone(m.yoy(c))),
                           kpi("E1 index", f"{idx:.1f}" if idx is not None else "n/a", sub="derived, out of 100")])
    a.follow("How do we compare with our peers?", f"What can we learn from the best in {sname}?",
             "Show our targets", "What if we cut Scope 1 by 10%?")


# --------------------------------------------------------------------------- simulate

def simulate(ctx, c, mid, pct_cut):
    a, kb = ctx.a, ctx.kb
    a.company_ref(c)
    sname, sec = _sector_label(ctx, c)
    if mid not in ("scope1", "scope2", "scope12", "scope3", "intensity", "scope3_intensity"):
        mid = "scope12"
    metric = M.NUMERIC[mid]
    members = kb.members(c["sector"])
    v, pv = metric.value(c), metric.prev(c)
    a.kicker = f"{c['name']} · What-if"
    a.title = f"Scenario: lower {lc(metric.label)}"
    if v is None or (metric.level_ok and not metric.level_ok(c)):
        a.status = "partial"
        a.p(f"A scenario needs a reported, comparable {lc(metric.label)} value, and {c['name']} "
            f"{'did not report one' if v is None else 'has a value flagged for data quality'} {a.c_cell(c, metric.cy_q or '1330')}.")
        a.follow(f"Show {short_name(c['name'])}'s E1 profile")
        return
    p = pct_cut if pct_cut is not None else 10.0
    p = max(0.0, min(p, 100.0))
    new = v * (1 - p / 100)
    pairs = eligible(metric, members)
    r0, n, _ = rank_of(c, pairs, True)
    pairs_new = [(x, new if x["id"] == c["id"] else val) for x, val in pairs]
    r1, _, _ = rank_of(c, pairs_new, True)
    med = median(val for _, val in pairs)
    need = (1 - med / v) * 100 if med is not None and v > med else 0.0

    def score(ratio):
        if ratio > 1.05:
            return 0
        if ratio > 1:
            return 25
        if ratio == 1:
            return 50
        if ratio >= 0.95:
            return 75
        return 100

    rq = {"scope1": "1330", "scope2": "1332", "scope3": "1388", "intensity": "1335", "scope3_intensity": "1391"}.get(mid)
    cur_score = c["ratings"].get(rq) if rq else None
    ratio0 = v / pv if pv else None
    ratio1 = new / pv if pv else None
    base = a.c_cell(c, metric.cy_q) if metric.cy_q else a.c_derived("Scope 1+2 baseline", f"{num(v)} {CO2}",
                                                                   [a.c_cell(c, '1330'), a.c_cell(c, '1332')])
    s = (f"If {c['name']}'s FY 2024-25 {lc(metric.label)} had been **{p:g}% lower**, it would be "
         f"**{fmt_value(metric, new)}** instead of {fmt_value(metric, v)} {base}.")
    a.p(s)
    if ratio1 is not None and rq:
        a.p(f"Against FY 2023-24 ({fmt_value(metric, pv)}), the year-on-year ratio would move from {ratio0:.3f} to "
            f"**{ratio1:.3f}**, which the Rating-sheet rubric for Q{rq} scores **{score(ratio1)}/100** "
            f"(currently {cur_score if cur_score is not None else 'n/a'}) {a.c_rating(c, rq)}.")
    sc = a.c_derived("Scenario arithmetic", f"{num(v)} x (1 - {p:g}%) = {num(new)}; re-ranked against {n - 1} unchanged peers; "
                                            f"sector median {num(med)}")
    a.p(f"Its rank among {n} {sname} companies would move from {rank_phrase(r0, n)} to **{rank_phrase(r1, n)}** "
        f"(rank 1 is the highest value) {sc}. "
        + (f"Reaching the sector median of {fmt_value(metric, med)} would take a cut of about **{need:.1f}%**."
           if need > 0 else f"It is already at or below the sector median of {fmt_value(metric, med)}."))
    a.note("method", "Hypothetical arithmetic on reported figures, holding every other company (and, for intensity, "
                     "turnover) constant. This is not a forecast.")
    a.block("simulator", company=short_name(c["name"]), company_id=c["id"], metric=metric.label, unit=metric.unit,
            kind=metric.kind, cy=v, py=pv, pct=p, rating_q=rq, current_score=cur_score,
            peers=[{"id": x["id"], "label": short_name(x["name"]), "value": val} for x, val in pairs],
            median=med, sector=sname, need_pct=round(need, 2))
    a.context.update({"metric": mid})
    a.follow(f"What if {short_name(c['name'])} cuts it by {int(min(p * 2, 50))}%?",
             f"Best practices on GHG reduction projects in {sname}",
             f"How does {short_name(c['name'])} compare with its peers?")


METHOD_NONDISCLOSURE = ("Companies that did not report information for a particular parameter were categorised as "
                        "“non-disclosing” for the relevant indicator. Non-disclosure was treated as analytically "
                        "meaningful, as it may indicate gaps in ESG governance, limitations in internal data systems, "
                        "or evolving reporting maturity.")
