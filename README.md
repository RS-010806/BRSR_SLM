# Pramana: evidence-grounded BRSR climate intelligence

Pramana (Sanskrit: *means of valid knowledge, proof*) is a small, purpose-built language system that answers questions about the **E1 theme (GHG emissions and climate risk)** of BRSR filings by **982 listed Indian companies** for FY 2024-25. It works like a notebook-style assistant over the IIMB dataset: plain data, peer comparison, best practices, sector insight and what-if scenarios, each answer built from charts and tables, and **every figure linked to the exact workbook cell, rating, report table or report page it came from**.

Built for the TCI-IIMB Supply Chain Sustainability Lab, using the E1 workbook, the E1 chapter, and the report *Business Responsibility and Sustainability in India* (IIMB, FY 2024-25).

**Live:** https://pramana-brsr.onrender.com · **Features and design (PDF):** [docs/Pramana_Features.pdf](docs/Pramana_Features.pdf)

## Why it is built this way

The brief called for answers that are accurate, never hallucinated, and **identical every time the same question is asked**. A generative LLM cannot guarantee either property, so Pramana splits the problem:

| Stage | What happens | Why |
|---|---|---|
| Normalise | Unicode, possessives, "Scope 1/2/3", fiscal years and numbers are canonicalised | Same text in, same tokens out |
| Link | A token trie resolves 2,664 company aliases, 22 sectors, 38 questions and out-of-scope topics; typo-tolerant fuzzy matching; known-absent companies (ONGC, Tata Motors, Siemens...) are named, never substituted | Entities come from the data, not from a model |
| Understand | A **transformer trained from scratch** (custom BPE tokenizer, 2 layers, 464K parameters, pure-numpy inference) classifies intent and topic; deterministic rules override it where the text is explicit | Flexible phrasing without generation |
| Compute | Handlers compute values, ranks, medians, distributions and scenarios directly from the workbook, using the report's own conventions | Numbers are calculated, never recalled |
| Prove | Answers are assembled from fixed templates; every numeric statement must carry a citation, checked before the answer is returned; the answer carries a SHA-256 fingerprint | Verifiable and repeatable |

The model only ever outputs a label; it never writes text. That is what makes hallucination structurally impossible and answers deterministic.

## What's new in v2

* **Database-backed knowledge base.** The pipeline compiles everything into `data/build/pramana.db` (SQLite with FTS5): companies, answers, ratings, 26,576 pre-scored disclosure sentences, per-cell evidence scores and practice themes, a technology-mention index and trigram full-text search. Work that used to run per request now runs once at build time.
* **Latency.** Market-wide best-practice answers dropped from 1,504 ms to under 3 ms of compute (the slowest of 132 benchmark questions is now 2.6 ms), with **zero change to any answer's content** (identical fingerprints). Cached answers are served pre-compressed; the browser caches answers per question and context, prefetches follow-ups on hover, and the artificial thinking delay is gone.
  On the live free-tier server, the net zero examples question took 20.9 s in v1. In v2, first-time answers to heavy questions (best practices, net zero examples, text search, peer benchmarks) take 4 to 55 ms of server time and about 0.3 s end to end, which is mostly network. Server boot fell from 71 s to 6 s after pinning numpy's math library to one thread; on a CPU-quota container the default thread pool had been costing about a second per query.
* **In-context learning.** The conversation learns peer groups ("my peers are ACC, Ambuja and UltraTech"), definitions ("by emissions I mean Scope 1"), defaults ("always show the top 5") and clarification choices, and applies them to later questions. Preferences are part of the conversation context, so answers stay deterministic; they show as chips above the input and can be removed.
* **Few-shot memory.** 100 labelled example questions, embedded with the model's own encoder, steady the classifier when it is unsure; the nearest examples appear in the reasoning trace.
* **App database.** Postgres on Render (SQLite fallback) stores anonymous usage events, answer feedback (thumbs up or down with an optional note) and deterministic short share links (`/s/<code>`). Writes are queued in the background and can never slow down or break an answer.
* **Contrast-safe charts.** Every fill has a paired text colour chosen by computed WCAG contrast in each theme. `web/scripts/contrast-audit.js` measures every visible text element against what is actually rendered behind it; 51 views across both themes and mobile pass at 4.5:1 or better.
* **More data-quality checks.** Implausibly low intensities (below 0.1% of the sector median, or from scaled-unit filings) are flagged and kept out of level rankings, and a flagged sector classification is noted wherever that company appears.
* Company-name autocomplete, CSV export of the company table, lazily loaded explore pages, and live anonymous usage figures on the Method page.

## Verified against the report

`server/pramana/reconcile.py` recomputes every table in the E1 chapter from the raw workbook: **597 of 597 published figures match exactly** (Tables 1.1 to 3.10). Along the way it reverse-engineered and documented the report's conventions:

* Yes/No counts use the Rating sheet (score 100 = Yes). Two Base Data columns (Q241, Q268) carry headers from other principles, so their answers come from the Rating sheet.
* Sector emission totals exclude SIS Limited and Patel Engineering's previous-year Scope 2 (implausible billion-tonne values), exactly as the report does.
* Company-wise direction counts CY = PY as "increased" (Table 3.3). Change bands are `< -10`, `[-10, -5)`, `[-5, +5]`, `(+5, +10]`, `> +10`.
* The Rating sheet's year-on-year rubric is reproduced for 100% of rated cases; when both years are reported as 0 it assigns 100 (disclosed wherever it matters).
* AI-scored questions (Tables 1.6, 1.7, 1.8, 2.2) were re-scored in the Rating sheet after the report tables were produced; company answers use the Rating sheet, aggregate answers quote the report and show the recount.

Data-quality safeguards (values are always shown as filed, never corrected):

* **Magnitude check**: 14 companies (for example Tata Steel, 61 tCO2e Scope 1) report Scope 1+2 below 0.1% of their sector median, almost certainly in thousand or million tonnes. They count in sector totals as in the report but are not ranked on level. Year-on-year change still compares, since a ratio is unit-invariant.
* **Unit check**: per-rupee intensities implying more than 10,000 tCO2e per crore are flagged and kept out of level rankings.
* Physical-output intensity uses company-specific units, so only its change is compared.

## Features

* **Plain data** for any company and any of the 38 E1 questions, with the Rating-sheet score and where it sits on the rubric.
* **Peer benchmarking** on seven dimensions with percentile positions, and full sector rankings.
* **Best practices** quoted verbatim from top-rated disclosures, with the most specific sentences highlighted and the practices that distinguish leaders quantified.
* **Personal lens**: say "I work at ACC" (no sign-in) and "how do we compare with our peers?" or "what can we learn from the leaders?" become about your company, including a grounded gap analysis.
* **What-if simulator**: drag a reduction and watch the rating band, sector rank and gap to the median update.
* **Sector and cross-sector views**, report key insights, disclosure search ("which companies mention green hydrogen?"), screens ("power companies without assurance").
* **Evidence drawer**: click any citation to see the sheet and cell, the full disclosure text, the rubric, the report table with the row highlighted, or the formula with its inputs; report citations open the PDF at the right page.
* **Memory**: conversations and follow-ups ("and Scope 3?", "what about Ambuja?") persist in the browser; the server is stateless and stores nothing about users.
* **Guardrails**: other ESG themes are refused with a pointer to the right report chapter and its executive-summary finding; financial data, forecasts, investment advice, web lookups and prompt-injection attempts are refused; ambiguous names ask for clarification.
* Share links that reproduce the exact answer, copy with sources, print or save to PDF, CSV export for every chart, light and dark themes, keyboard palette (Cmd/Ctrl+K), mobile layout.

## Repository layout

```
data/raw/            source files (workbook, E1 chapter, published report)
data/build/          pramana.db: the verified knowledge base (SQLite + FTS5) generated by the pipeline
pipeline/            build_dataset.py (xlsx/docx/pdf -> verified JSON), build_db.py (JSON -> SQLite with
                     precomputed evidence), slm/ (grammar, training, evaluation)
server/pramana/      FastAPI app, knowledge base, analytics, reconciliation
  nlu/               normaliser, lexicon, aliases, linker, BPE tokenizer, numpy transformer, parser
  engine/            answer handlers, citations, evidence extraction, formatting
server/tests/        195 regression tests (reconciliation, determinism, grounding, guardrails, v2 features)
web/                 React + TypeScript client with hand-built SVG charts
```

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cd web && npm ci && npm run build && cd ..
uvicorn pramana.app:app --app-dir server --port 8000
```

Open http://localhost:8000. For frontend development run `npm run dev` in `web/` (proxies `/api` to port 8000).

Rebuild everything from the source files:

```bash
python -m pipeline.build_dataset       # xlsx + docx + pdf -> data/build/*.json (intermediate, not committed)
python -m pipeline.build_db            # -> data/build/pramana.db
python -m pipeline.slm.train           # trains tokenizer + model (about 2.5 minutes on a laptop CPU)
python -m pipeline.slm.evaluate --write
cd server && python -m pytest tests -q
```

## Deploy on Render

The repository includes `render.yaml` and a multi-stage `Dockerfile`. In Render, choose **New > Blueprint**, connect this repository, and apply. The blueprint creates the web service and a free Postgres database and wires `DATABASE_URL` automatically; `PRAMANA_ADMIN_TOKEN` is generated for the anonymous usage summary at `/api/admin/summary?token=...`. The service runs on the free plan (about 150 MB of memory). Free instances sleep when idle, so the first request after a pause takes longer. Render's free Postgres expires after 30 days unless upgraded; the app then falls back to SQLite on its own and keeps answering.

## Privacy

No sign-in, no cookies for tracking. Conversations, the company lens and learned preferences stay in the browser. The server records anonymous question text, how it was routed and how long it took (no IP address, user agent or device identifier), plus feedback users choose to send. Set `PRAMANA_LOG_QUERIES=0` to disable question logging.

## Evaluation

* Synthetic validation: intent 99.3%, topic 98.4%.
* 110 hand-written queries covering all 16 intents: intent, company, sector and metric resolution all 100%. These were written alongside the grammar, so they measure coverage rather than independent generalisation; 22 further adversarial queries are part of the test suite.
* numpy runtime matches the PyTorch model to within 2.4e-7.

## Limitations

* Covers the E1 theme only. Questions on the other 20 ESG parameters are answered with a pointer to the relevant chapter of the report.
* The query model understands the phrasings covered by its grammar well; unusual phrasings fall back to clarification rather than a guess.
* The E1 index is a navigation aid derived from Rating-sheet scores (equal-weighted pillars). It is not an official IIMB score.
