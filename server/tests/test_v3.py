"""Regression tests for the review feedback: public-only content, short answers, the user's
company, peers, infographics and exports."""
import json
import os
import re
import tempfile

import pytest

from helpers import leaks, public
from pramana.engine.core import Engine
from pramana.kb import get_kb

TCI = {"lens": "tci-express-limited"}


@pytest.fixture(scope="module")
def eng():
    return Engine(get_kb())


def walk(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from walk(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk(v)


# ---------------------------------------------------------------- "your company" works however it is phrased
MINE = [
    ("what is my company ghg emissions", "company_metric"), ("what are my company's ghg emissions", "company_metric"),
    ("what are my emissions", "company_metric"), ("what are our scope 1 emissions", "company_metric"),
    ("my ghg emissions", "company_metric"), ("ghg emissions", "company_metric"), ("scope 3", "company_metric"),
    ("what are scope 1 and scope 2 emissions", "company_metric"), ("what is our emission intensity", "company_metric"),
    ("do we have assurance", "company_metric"), ("what are my targets", "company_metric"),
    ("our ghg reduction projects", "company_metric"), ("who are my peers", "peer_list"), ("show my peers", "peer_list"),
    ("list my competitors", "peer_list"), ("how do we compare with our peers", "peer_benchmark"),
    ("tell me about my company", "company_profile"), ("how am i doing", "company_profile"),
    ("what if we cut scope 1 by 20%", "simulate"), ("make an infographic of my emissions", "infographic"),
    ("what are the best practices we can adopt", "best_practice"),
]


@pytest.mark.parametrize("q,intent", MINE)
def test_my_company_is_understood(eng, q, intent):
    a = eng.ask(q, TCI)
    assert a["trace"]["final_intent"] == intent, a["trace"]["rules"]
    assert any(e["id"] == "tci-express-limited" for e in a["entities"]), (q, a["title"])
    assert a["status"] == "answered"


def test_my_company_plus_a_named_one_is_a_comparison(eng):
    a = eng.ask("compare us with blue dart", TCI)
    assert a["trace"]["final_intent"] == "compare"
    assert [e["id"] for e in a["entities"]] == ["tci-express-limited", "blue-dart-express-limited"]


def test_a_named_company_is_never_replaced_by_mine(eng):
    a = eng.ask("what are NTPC's emissions", TCI)
    assert [e["id"] for e in a["entities"]] == ["ntpc-limited"]


def test_market_questions_stay_market_questions(eng):
    for q in ("top 10 emitters", "how many companies report scope 3", "total ghg emissions", "which sector emits the most"):
        a = eng.ask(q, TCI)
        assert not any(e["id"] == "tci-express-limited" for e in a["entities"]), q


def test_without_a_company_it_asks_instead_of_guessing(eng):
    for q in ("what are my emissions", "who are my peers", "how do we compare with our peers", "our targets",
              "make an infographic of my emissions"):
        a = eng.ask(q)
        assert a["status"] == "clarify" and a["trace"]["final_intent"] == "need_company", q
        assert any(b["type"] == "action" and b["action"] == "set_company" for b in a["blocks"])


def test_setting_and_clearing_the_company(eng):
    a = eng.ask("my company is Blue Dart")
    assert a["context"]["lens"] == "blue-dart-express-limited"
    b = eng.ask("my company is Blue Dart", TCI)           # an explicit statement wins over the current company
    assert b["context"]["lens"] == "blue-dart-express-limited"
    c = eng.ask("clear my company", TCI)
    assert c["context"]["lens"] == ""
    d = eng.ask("what are NTPC's emissions", TCI)          # ordinary answers leave it alone
    assert "lens" not in d["context"]


# ---------------------------------------------------------------- answers are short and to the point
def test_emissions_answer_is_direct(eng):
    a = eng.ask("what is my company ghg emissions", TCI)
    assert [b["type"] for b in a["blocks"]] == ["kpis"]          # no charts, no peer comparison unless asked
    assert len(a["lead"]) <= 3
    assert "peer" not in " ".join(a["lead"]).lower() and "median" not in " ".join(a["lead"]).lower()


def test_scope1_and_scope2_are_separate_figures(eng):
    for q, ctx in (("what are scope 1 and scope 2 emissions", TCI), ("What are NTPC's Scope 1 and Scope 2 emissions?", {})):
        a = eng.ask(q, ctx)
        lead = a["lead"][0]
        assert "Scope 1 emissions of" in lead and "Scope 2 emissions of" in lead
        labels = [k["label"] for k in a["blocks"][0]["items"]]
        assert labels[:2] == ["Scope 1", "Scope 2"]
    t = eng.ask("what are scope 1 and scope 2 emissions", TCI)["blocks"][0]["items"]
    assert t[0]["value"] == "394.25" and t[1]["value"] == "0.85"


def test_simple_questions_get_no_charts(eng):
    charts = {"bars", "strip", "grouped", "stack", "treemap"}
    for q in ("What are NTPC's Scope 1 emissions?", "does infosys have assurance", "What are Infosys's targets?",
              "what is NTPC's emission intensity", "What are NTPC's GHG emissions?"):
        a = eng.ask(q)
        assert not charts & {b["type"] for b in a["blocks"]}, q
        assert len(a["lead"]) <= 3, q
    # a profile and a count show the answer itself as one share bar, and nothing about other companies
    assert [b["type"] for b in eng.ask("tell me about ACC")["blocks"]] == ["kpis", "stack", "checklist"]
    assert [b["type"] for b in eng.ask("How many companies report Scope 3 emissions?")["blocks"]] == ["stack"]


def test_definitions(eng):
    a = eng.ask("what are scope 1 and scope 2 emissions")        # no company set: explain the terms
    assert a["trace"]["final_intent"] == "explain" and {b["type"] for b in a["blocks"]} <= {"points"}   # points, never charts
    assert "direct" in a["lead"][0] and "electricity" in a["lead"][1]
    b = eng.ask("what does scope 1 mean", TCI)                    # an explicit definition request is honoured
    assert b["trace"]["final_intent"] == "explain" and not b["entities"]
    assert eng.ask("what is brsr")["title"] == "BRSR"


# ---------------------------------------------------------------- peers
def test_who_are_my_peers_is_a_list_of_names(eng):
    a = eng.ask("who are my peers", TCI)
    assert [b["type"] for b in a["blocks"]] == ["names"]
    assert len(a["blocks"][0]["items"]) == 34
    assert "35 companies" in a["lead"][0] and "34 peers" in a["lead"][0]
    assert set(a["blocks"][0]["items"][0]) == {"id", "name"}       # names only, no figures


def test_peer_comparison_is_visual_and_has_no_ranks(eng):
    a = eng.ask("how do we compare with our peers", TCI)
    assert [b["type"] for b in a["blocks"]] == ["points", "position", "bars"]
    pos = a["blocks"][1]
    assert [r["label"] for r in pos["rows"]][:3] == ["Scope 1 emissions", "Scope 2 emissions", "Scope 3 emissions"]
    row = pos["rows"][0]
    assert row["relation"] in ("Below median", "Above median", "Same as median")
    assert (row["n"], row["of"]) == (30, 34)                        # how many peers disclosed the figure
    assert sum(1 for p in row["points"] if p.get("focus")) == 1 and len(row["points"]) == 31
    assert all("rank" not in r for r in a["blocks"][2]["rows"])     # the named chart carries no rank numbers
    assert any(r["highlight"] for r in a["blocks"][2]["rows"])
    text = json.dumps(public(a)).lower()
    assert not re.search(r"\brank|percentile|\d+(st|nd|rd|th) (highest|lowest|of)\b|beats|outperform", text)
    b = eng.ask("how do we compare with peers on scope 1", TCI)
    assert "peer median" in b["lead"][0] and [x["type"] for x in b["blocks"]] == ["strip", "bars"]


@pytest.mark.parametrize("q", [
    "how well does ntpc do with respect to peers", "how is ntpc doing against its competitors", "is NTPC better than its peers",
    "NTPC vs peers", "where does NTPC stand among its peers", "ntpc relative to peers", "how does ntpc stack up",
    "ntpc versus the industry", "competitor analysis for NTPC"])
def test_asking_how_a_company_does_against_peers_is_a_comparison(eng, q):
    a = eng.ask(q)
    assert a["trace"]["final_intent"] == "peer_benchmark", (q, a["trace"]["rules"])
    assert a["blocks"][1]["type"] == "position"


@pytest.mark.parametrize("q", ["who are NTPC's peers", "peers of NTPC", "NTPC peers", "list competitors of NTPC",
                               "how many peers does NTPC have"])
def test_asking_who_the_peers_are_is_a_list(eng, q):
    a = eng.ask(q)
    assert a["trace"]["final_intent"] == "peer_list", (q, a["trace"]["rules"])
    assert len(a["blocks"][0]["items"]) == 19


def test_comparative_answers_carry_visuals(eng):
    assert [b["type"] for b in eng.ask("Compare ACC and Ambuja")["blocks"]] == ["points", "grouped", "compare"]
    assert [b["type"] for b in eng.ask("Give me an overview of the power sector")["blocks"]] == ["kpis", "bars", "stack"]
    assert [b["type"] for b in eng.ask("What are the key highlights?")["blocks"]] == ["kpis", "points", "treemap"]


def test_sector_count_is_the_full_sector(eng):
    a = eng.ask("list all services companies")
    assert "35 companies" in a["lead"][0] and len(a["blocks"][0]["rows"]) == 35


# ---------------------------------------------------------------- nothing internal is shown
@pytest.mark.parametrize("ctx", [TCI, {"lens": "hindustan-unilever-limited"}, {"lens": "tata-steel-limited"}])
def test_no_internal_terms_with_a_company_set(eng, ctx):
    probes = [q for q, _ in MINE] + [
        "How is Q1330 scored?", "what does the IIMB report say about scope 3", "show me the rubric for targets",
        "how was this dataset built", "what is your model", "where does your data come from", "summarise E1",
        "who are the laggards in steel", "which company is the dirtiest in the power sector", "rank cement companies",
        "Is Bosch a leader or a laggard among auto component makers?", "Percentile position of Havells within consumer durables"]
    for q in probes:
        a = eng.ask(q, ctx)
        found = leaks(a, get_kb())
        if a["trace"]["final_intent"] == "no_scores":
            found = [f for f in found if not re.match(r"'(scores?|ratings?)'", f, re.I)]
        assert not found, (q, found)


def test_scores_and_ratings_are_declined(eng):
    for q in ("what is the ESG score of Infosys", "show the rating of NTPC", "top 5 companies by E1 score",
              "which companies score 100 on targets", "How is the scope 1 rating calculated?"):
        a = eng.ask(q)
        assert a["status"] == "out_of_scope" and a["title"] == "Scores and ratings are not available", q
        assert not a["blocks"]


def test_sources_name_only_the_public_filing(eng):
    a = eng.ask("what is my company ghg emissions", TCI)
    kinds = {c["kind"] for c in a["citations"]}
    assert kinds <= {"filing", "computed", "note"}
    f = a["citations"][0]
    assert f["kind"] == "filing" and f["company"] == "TCI Express Limited" and f["fy"] == "FY 2024-25"
    assert f["item"] == "Total Scope 1 emissions" and f["value"] == "394.25"
    banned = {"cell", "sheet", "qid", "score", "rubric", "rule_source", "table", "pdf_page", "base_row", "rating_cite"}
    for q in ("what is my company ghg emissions", "tell me about my company", "what are our targets",
              "Examples of GHG reduction projects from cement companies", "Which companies mention green hydrogen?",
              "Compare ACC and Ambuja", "how do we compare with our peers", "Top 10 emitters"):
        for d in walk(public(eng.ask(q, TCI))):
            assert not banned & set(d), (q, banned & set(d))


def test_wording_is_neutral(eng):
    for q in ("who are the laggards in steel", "which company is the dirtiest in the power sector",
              "Which is greener, HDFC Bank or ICICI Bank?", "Is Bosch a leader or a laggard among auto component makers?",
              "How far behind its sector is Vodafone Idea?"):
        a = public(eng.ask(q))
        text = " ".join([a["title"], *a["lead"], *[n["text"] for n in a["notes"]], *a["followups"]]).lower()
        assert not re.search(r"laggard|dirtiest|beat|outperform|worse|worst|weak|poor|behind", text), (q, text[:200])


def test_not_available_answers_do_not_point_at_internal_documents(eng):
    a = eng.ask("What is Infosys's water consumption?")
    assert a["status"] == "out_of_scope" and "not available yet" in a["lead"][0]
    assert "chapter" not in json.dumps(public(a)).lower()
    assert a["followups"]                                            # related help is offered


# ---------------------------------------------------------------- infographics and exports
def test_infographic_for_company_sector_and_market(eng):
    a = eng.ask("make an infographic of my emissions", TCI)
    b = a["blocks"][0]
    assert b["type"] == "infographic" and b["kind"] == "company" and b["title"] == "TCI Express"
    assert [s["label"] for s in b["stats"]][:3] == ["Scope 1", "Scope 2", "Scope 3"]
    assert b["hero"]["value"] == "395.1" and b["quote"]["text"]
    quote = b["quote"]["text"].rstrip("…")
    assert quote in " ".join(get_kb().by_id["tci-express-limited"]["values"]["286"].split())   # the company's own words
    assert eng.ask("infographic for the power sector")["blocks"][0]["kind"] == "sector"
    assert eng.ask("make an infographic")["blocks"][0]["kind"] == "market"
    ctx = eng.ask("What are ACC's Scope 1 emissions?")["context"]
    assert eng.ask("make an infographic", ctx)["blocks"][0]["title"] == "ACC"       # follows the conversation


def test_exports_are_spreadsheet_ready(eng):
    qs = ["what is my company ghg emissions", "how do we compare with our peers", "who are my peers", "Top 10 emitters",
          "tell me about my company", "What are the key highlights?", "how many cement companies have assurance",
          "Give me an overview of the power sector", "Which sector emits the most?", "Compare ACC and Ambuja",
          "compare infosys and tcs on emissions", "Which companies mention green hydrogen?", "list all services companies"]
    for q in qs:
        a = eng.ask(q, TCI)
        exports = [b["export"] for b in a["blocks"] if b.get("export")]
        assert exports, q
        for x in exports:
            assert x["title"] and x["columns"] and x["rows"], q
            for h in x["columns"]:
                assert h.isascii(), (q, h)                           # no subscript or currency glyphs in headers
                assert not re.search(r"rank|rating|score|index", h, re.I), (q, h)
            for r in x["rows"]:
                assert len(r) == len(x["columns"]), (q, r)
                for v in r:
                    # a figure is a number in its own cell, never text with a unit attached
                    assert v is None or isinstance(v, (int, float)) or not re.search(r"\d\s*(tCO|%)", v), (q, v)
    x = eng.ask("Top 10 emitters")["blocks"][0]["export"]
    assert "Scope 1 (tCO2e)" in x["columns"] and "Scope 2 (tCO2e)" in x["columns"]
    assert isinstance(x["rows"][0][x["columns"].index("Scope 1 (tCO2e)")], float)


def test_count_questions(eng):
    a = eng.ask("how many companies increased their emissions?")
    assert a["trace"]["final_intent"] == "screen" and re.match(r"\*\*\d+ of 982\*\* companies raised", a["lead"][0])
    b = eng.ask("How many companies have science based targets?")
    assert b["trace"]["final_intent"] == "text_search" and "SBTi" in b["title"]


def test_what_if_to_the_median(eng):
    a = eng.ask("How much would Infosys need to cut scope 2 to reach the sector median")
    assert any("To match the peer median" in p for p in a["lead"])
    b = eng.ask("Run a scenario where Titan halves its scope 2")
    assert b["blocks"][-1]["pct"] == 50.0
    assert set(b["blocks"][-1]) == {"type", "company", "metric", "unit", "cy", "py", "pct"}


# ---------------------------------------------------------------- the API sends only public information
@pytest.fixture(scope="module")
def client():
    tmp = tempfile.mkdtemp()
    os.environ["PRAMANA_APP_DB"] = os.path.join(tmp, "app.db")
    os.environ["PRAMANA_ADMIN_TOKEN"] = "test-token"
    os.environ.pop("DATABASE_URL", None)
    from fastapi.testclient import TestClient
    from pramana import app as appmod
    return TestClient(appmod.app), appmod


def test_api_payload_is_public(client):
    c, _ = client
    r = c.post("/api/ask", json={"q": "what are my emissions", "context": TCI})
    body = r.json()
    assert set(body) == {"status", "title", "kicker", "lead", "blocks", "citations", "followups", "notes", "entities",
                         "fingerprint", "context"}
    assert body["entities"][0]["id"] == "tci-express-limited"
    assert set(c.get("/api/meta").json()) == {"name", "companies", "period", "sectors"}
    d = c.get("/api/directory").json()[0]
    assert not {"index", "targets", "flags", "rating"} & set(d)
    assert "median_index" not in c.get("/api/sectors").json()[0]


def test_internal_endpoints_are_closed(client):
    c, _ = client
    for path in ("/api/stats", "/api/docs", "/api/openapi.json", "/files/report.pdf", "/api/export/companies.csv",
                 "/api/admin/summary", "/api/admin/diagnostics", "/api/admin/trace?q=hi"):
        assert c.get(path).status_code == 404, path
    assert c.get("/api/admin/diagnostics?token=test-token").json()["reconciliation"]["matched"] >= 420
    assert c.get("/api/admin/trace?token=test-token&q=top 10 emitters").json()["final_intent"] == "ranking"
