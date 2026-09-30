"""v2 regression tests: database-backed KB, in-context learning, app store, API."""
import json
import os
import tempfile
import time

import pytest

from pramana.engine.core import Engine
from pramana.kb import get_kb


@pytest.fixture(scope="module")
def eng():
    return Engine(get_kb())


# ---------------------------------------------------------------- knowledge base
def test_kb_loaded_from_sqlite():
    kb = get_kb()
    assert kb.db_path.name == "pramana.db"
    assert len(kb.companies) == 982 and len(kb.sectors) == 22
    assert len([d for d in kb.corpus if d["kind"] == "disclosure"]) > 25000
    # every disclosure sentence carries its precomputed specificity
    assert all(d.get("spec") is not None for d in kb.corpus if d["kind"] == "disclosure")


def test_heavy_answers_are_fast(eng):
    for q in ["What are leading companies doing to reduce emissions?", "Show me good examples of net zero targets",
              "Which companies mention green hydrogen?"]:
        eng.ask(q)
        t = time.perf_counter()
        eng.ask(q)
        assert (time.perf_counter() - t) * 1000 < 60, q


def test_quoted_phrase_search_uses_trigram_index(eng):
    a = eng.ask('Which companies mention "carbon neutral"?')
    assert a["trace"]["final_intent"] == "text_search"
    assert "mention" in a["lead"][0] and "carbon neutral" in a["lead"][0]


# ---------------------------------------------------------------- in-context learning
def test_peer_group_is_learned_and_used(eng):
    a = eng.ask("My peers are Ambuja, UltraTech and Shree Cement", {"lens": "acc-limited"})
    assert a["trace"]["final_intent"] == "set_pref"
    assert a["context"]["prefs"]["peers"] == ["ambuja-cements-limited", "ultratech-cement-limited", "shree-cement-limited"]
    b = eng.ask("How do we compare with our peers?", {**a["context"], "lens": "acc-limited"})
    assert b["title"] == "Against your 3 chosen peers"
    assert any("peer group you set earlier" in n["text"] for n in b["notes"])


def test_emissions_definition_is_learned(eng):
    a = eng.ask("By emissions I mean scope 1")
    assert a["context"]["prefs"] == {"emissions": "scope1"}
    b = eng.ask("What are NTPC's emissions?", a["context"])
    assert b["title"] == "Scope 1 emissions"
    c = eng.ask("What are NTPC's scope 1 and 2 emissions?", a["context"])
    assert c["title"] == "Scope 1+2 emissions"  # explicit scope wins over the learned default


def test_default_n_is_learned(eng):
    a = eng.ask("From now on always show the top 5")
    b = eng.ask("Top emitters in cement", a["context"])
    assert b["title"].startswith("Top 5")


def test_clarification_is_remembered(eng):
    a = eng.ask("dalmia bharat intensity")
    assert a["status"] == "clarify" and a["context"]["pending"]["text"] == "dalmia bharat"
    b = eng.ask("Dalmia Bharat Limited intensity", a["context"])
    assert b["context"]["prefs"]["aliases"] == {"dalmia bharat": "dalmia-bharat-limited"}
    c = eng.ask("dalmia bharat scope 1", b["context"])
    assert c["status"] == "answered" and c["entities"][0]["id"] == "dalmia-bharat-limited"


def test_forget_clears_preferences(eng):
    a = eng.ask("Forget my preferences", {"prefs": {"n": 5, "emissions": "scope1"}})
    assert a["context"]["prefs"] == {}


def test_learned_answers_are_deterministic(eng):
    ctx = {"prefs": {"emissions": "scope1", "peers": ["ambuja-cements-limited"]}, "lens": "acc-limited"}
    assert eng.ask("How do we compare with our peers?", ctx)["fingerprint"] == \
        Engine(get_kb()).ask("How do we compare with our peers?", ctx)["fingerprint"]


def test_few_shot_memory(eng):
    a = eng.ask("gimme the lowdown on Asian Paints")
    assert a["trace"]["final_intent"] == "company_profile"
    assert a["trace"]["few_shot"] and a["trace"]["few_shot"][0]["intent"] == "company_profile"


def test_classification_note_follows_the_company(eng):
    a = eng.ask("Who reduced emissions the most in the steel sector?")
    assert any("Hindustan Unilever" in n["text"] for n in a["notes"])


def test_today_is_not_a_web_request(eng):
    a = eng.ask("What are leading companies doing to reduce emissions today?")
    assert a["status"] != "out_of_scope"


# ---------------------------------------------------------------- app store and API
@pytest.fixture(scope="module")
def client():
    tmp = tempfile.mkdtemp()
    os.environ["PRAMANA_APP_DB"] = os.path.join(tmp, "app.db")
    os.environ["PRAMANA_ADMIN_TOKEN"] = "test-token"
    os.environ.pop("DATABASE_URL", None)
    from fastapi.testclient import TestClient
    from pramana import app as appmod
    return TestClient(appmod.app), appmod


def test_share_links_are_deterministic(client):
    c, _ = client
    a = c.post("/api/share", json={"q": "How does ACC compare with its peers?"}).json()
    b = c.post("/api/share", json={"q": "How does ACC compare with its peers?"}).json()
    assert a == b and a["path"].startswith("/s/")
    got = c.get(f"/api/share/{a['code']}").json()
    assert got["q"] == "How does ACC compare with its peers?"


def test_ask_is_gzipped_and_logged(client):
    c, appmod = client
    r = c.post("/api/ask", json={"q": "Top 10 emitters"}, headers={"accept-encoding": "gzip"})
    assert r.status_code == 200 and r.headers["content-encoding"] == "gzip"
    assert r.headers["x-answer-id"] == r.json()["fingerprint"]
    c.post("/api/feedback", json={"fingerprint": r.json()["fingerprint"], "q": "Top 10 emitters", "rating": -1, "note": "x"})
    appmod.store.flush()
    s = c.get("/api/stats").json()
    assert s["questions"] >= 1 and s["feedback"]["down"] >= 1


def test_prefetch_is_not_logged(client):
    c, appmod = client
    appmod.store.flush()
    before = c.get("/api/stats").json()["questions"]
    c.post("/api/ask", json={"q": "Which sector emits the most?"}, headers={"x-pramana-prefetch": "1"})
    appmod.store.flush()
    assert c.get("/api/stats").json()["questions"] == before


def test_admin_requires_token(client):
    c, _ = client
    assert c.get("/api/admin/summary").status_code == 404
    assert c.get("/api/admin/summary?token=test-token").status_code == 200


def test_csv_export(client):
    c, _ = client
    r = c.get("/api/export/companies.csv")
    assert r.status_code == 200 and r.text.count("\n") == 983
