# Pramana

Pramana (Sanskrit for *proof*) answers questions about the GHG emissions and climate disclosures of **982 listed Indian companies**, using what each company filed in its BRSR for FY 2024-25. It is built for a company user: set your company once, then ask about "our emissions", "our peers" or "our targets".

**Live:** https://pramana-brsr.onrender.com · **Features (PDF):** [docs/Pramana_Features.pdf](docs/Pramana_Features.pdf)

> This README is for the team that maintains the tool. The product itself shows end users only what companies have publicly disclosed. Internal scoring, the internal analysis and how the data is stored never appear in an answer, an export or the interface.

## What a user can do

| Ask | What comes back |
|---|---|
| "What are our GHG emissions?" | Scope 1 and Scope 2 as two separate figures, the combined total, the change from last year, and Scope 3 if disclosed. Two or three sentences and one row of figures. |
| "Who are our peers?" | The names of the other companies in the sector. Nothing else. |
| "How do we compare with our peers?" (or "how well does NTPC do with respect to peers") | Key points, measure by measure, then a chart for each measure with one dot per company, yours highlighted and a line at the peer median, plus a bar chart naming the largest companies in the group. It says whether you are above or below the median and how many peers disclosed each figure. No ranks or percentiles. |
| "What are our targets?" / "Show our projects" | The disclosure exactly as filed, with the most specific points highlighted. |
| "Best practices for setting GHG targets" / "Examples of GHG reduction projects from cement companies" | A short summary in bullet points: what strong disclosures state and what companies commonly do, each with one named example in the company's own words. The full disclosures open on request. |
| "Did our emissions go up?" / "Our emissions last year" | The change between the two years, or the previous year's figures, stated first. |
| "Which peers emit less than us?" / "Who is the best in our sector?" | The peers that are lower, higher or closest, or the leaders in the company's own sector, with the company picked out. |
| "How to improve our disclosures?" | A checklist of what the company has and has not disclosed, with how many peers disclose each item. |
| "Give me an overview of the power sector" / "Top 10 emitters" | Totals and charts. Charts appear for questions about peers, sectors, comparisons and rankings; a plain question about one figure stays short. |
| "Make an infographic of our emissions" | A one-page, post-style image for a company, a sector or all companies, with a Download button. |
| "What if we cut Scope 1 by 20%?" | The resulting figure, with a slider to try other cuts. |
| "What is Scope 3?" | The definition, then four short points: what it covers, why it matters, an example and what the data shows. With a company set, its own figure is added as a closing point. |

Other things worth knowing:

* **Your company.** Set it from the button under the question box or by saying "my company is ...". It is stored only in the browser. No sign-in.
* **Sources.** Each answer lists its sources once, underneath: the company, the BRSR disclosure item, the financial year and the value as disclosed. There are no numbered reference links in the text.
* **Exports.** Any answer downloads as an Excel workbook (real numbers in cells, units in the headers) or as a PDF.
* **Not available.** If something is not covered (water, energy, financials, forecasts, scores or ratings), the answer says so plainly and offers what is available.
* **Same question, same answer.** Nothing is generated freely, so answers do not vary between runs.
* **Chats** are listed in the sidebar by date, can be searched, renamed and deleted, and stay in the browser.

## How it works

| Stage | What happens |
|---|---|
| Normalise | Scope names, fiscal years, numbers and punctuation are made canonical. |
| Personalise | With a company set, "we", "our" and "my company" are replaced by that company before anything else runs. |
| Link | A token trie resolves company names and aliases, sectors and measures, with typo tolerance. Ambiguous names (for example "Adani", "TCI") ask which one is meant. |
| Understand | A small transformer trained from scratch (custom BPE tokenizer, 2 layers, 464K parameters, numpy inference) classifies the kind of question. Explicit rules take over where the wording is unambiguous. The model only outputs a label; it never writes text. |
| Compute | Handlers calculate the answer from the disclosed figures in a read-only SQLite knowledge base. |
| Cite and check | Sentences are assembled from templates. Every numeric statement must carry a citation; this is checked before the answer is returned. |

Because the model never writes text and every number is looked up or calculated, an answer cannot contain an invented figure.

## What changed in v3 (after the review meeting)

| Feedback | Change |
|---|---|
| Internal material was visible (ratings, question numbers, rankings, the internal analysis, test figures) | Removed from every answer, source, export and screen. Tests scan every generated string for internal terms: 135 questions with no company set and 33 probing questions with three different companies set. Scores and ratings are declined politely. |
| Answers were too long; basic questions came back with peer charts and tables | A plain question now gets the figure asked for, the previous year and nothing else. Comparisons and charts are offered as follow-up suggestions. |
| Scope 1 and Scope 2 were added together | They are always shown as two figures, with the combined total alongside. |
| The lens did not work | It failed on most natural phrasings ("my emissions", "who are my peers", "how am I doing"). All of these now work; it is renamed "Your company"; the separate company search bar is gone. |
| Peers showed too much | "Who are my peers" is a list of names. A question about how a company does against its peers gets a chart against the peer median. |
| Services showed 31 companies, not 35 | The sector has 35 companies; 31 disclosed Scope 1 and Scope 2. Answers now state the full count and, separately, how many disclosed each figure. |
| Chat history was hard to reach | The sidebar is laid out like ChatGPT: New chat, Search chats, then a chat list grouped by date that takes the remaining height and scrolls on its own. |
| Too many things on screen ("E1 intelligence", "597 of 597", Method and sources, both Ask and New question) | Removed. One "New chat" button. |
| No infographic support | Added for companies, sectors and all companies, downloadable as an image. |
| Excel and PDF exports leaked internal columns and garbled units | Exports are rebuilt: real `.xlsx` files with numeric cells and units in headers; the PDF contains only the answer and its public sources. |
| Wording such as "beats X% of peers" | Replaced with neutral wording ("below the peer median"). |

Also fixed: ONGC was wrongly reported as not covered. It is in the data and now answers normally.

## Repository layout

```
data/build/          pramana.db: the knowledge base (SQLite + FTS5) generated by the pipeline
data/raw/            source files used by the pipeline (internal)
pipeline/            build_dataset.py, build_db.py, slm/ (grammar, training, evaluation)
server/pramana/      FastAPI app, knowledge base, analytics
  nlu/               normaliser, lexicon, aliases, linker, tokenizer, transformer, parser
  engine/            answer handlers, citations, public source labels, formatting
server/tests/        381 tests
web/                 React + TypeScript client: hand-built SVG charts, canvas infographics, xlsx writer
```

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cd web && npm ci && npm run build && cd ..
uvicorn pramana.app:app --app-dir server --port 8000
```

Open http://localhost:8000. For frontend development run `npm run dev` in `web/` (proxies `/api` to port 8000).

Rebuild from the source files and test:

```bash
python -m pipeline.build_dataset       # source files -> data/build/*.json (intermediate, not committed)
python -m pipeline.build_db            # -> data/build/pramana.db
python -m pipeline.build_wordlist      # -> ordinary-word list used to tell words from company names (needs /usr/share/dict/words)
python -m pipeline.slm.evaluate --write
cd server && python -m pytest tests -q
```

Retraining the question model (`python -m pipeline.slm.train`, about 2.5 minutes on a laptop CPU) is only needed if the grammar in `pipeline/slm/` changes.

## Tests

381 tests cover:

* **Public-only content:** no internal term in any generated string, citation or export, for every evaluation question and with different companies set.
* **Your company:** 21 phrasings resolve to the set company; market questions stay market questions; with no company set the tool asks instead of guessing.
* **Short answers:** plain questions return no comparison charts and at most three sentences; Scope 1 and Scope 2 are separate figures.
* **Peers:** names only for "who are my peers"; nine ways of asking how a company does against its peers all return the visual comparison; no rank or percentile wording; full sector counts.
* **Grounding:** every numeric sentence carries a citation and every citation resolves.
* **Determinism:** the same question gives a byte-identical answer on a fresh engine.
* **Exports:** headers are plain text with units, cells are numbers.
* **API:** the browser never receives how a question was routed; internal endpoints return 404 without the admin token.
* **The answer matches the question:** trends, previous-year figures, shares, peer filters, sector-level questions, advice and follow-ups each get the answer to what was asked, including after a definition or a refusal in the same chat.
* **Companies not covered:** a name that is not among the companies is reported as such, never answered with totals for everyone else; ordinary words are not mistaken for company names.
* **Data integrity (internal):** totals computed here still match the source analysis for the published figures, except in the sectors whose membership was corrected (see below).

The contrast audit (`web/scripts/contrast-audit.js`) measures every visible text element against what is rendered behind it: 54 views across light and dark pass at 4.5:1 or better.

Question understanding on 110 hand-written questions: route, company, sector and measure all resolve correctly. These were written alongside the grammar, so they measure coverage, not independent generalisation.

## Deploy on Render

The repository includes `render.yaml` and a multi-stage `Dockerfile`. In Render choose **New > Blueprint**, connect the repository and apply. The blueprint creates the web service and a free Postgres database, and generates `PRAMANA_ADMIN_TOKEN`. Pushing to `main` redeploys.

* Free instances sleep when idle, so the first request after a pause takes longer. Once awake, answers come back in under a second.
* Render's free Postgres expires after 30 days unless upgraded. The app then falls back to SQLite on its own and keeps answering; feedback and share links stored there are lost on redeploy.

## For maintainers only

These need `?token=<PRAMANA_ADMIN_TOKEN>` (see the service's environment in Render). Without it they return 404.

| Endpoint | Shows |
|---|---|
| `/api/admin/summary` | Most asked questions, questions that were not fully answered, recent feedback, usage counts |
| `/api/admin/trace?q=...&lens=<company id>` | How a question was understood and routed |
| `/api/admin/diagnostics` | Model details, data checks, reconciliation against the source analysis |

## Privacy

No sign-in and no tracking cookies. Chats, your company and anything a chat was asked to remember stay in the browser. The server records the question text, how it was routed and how long it took, with no IP address, user agent or device identifier, plus feedback users choose to send. Set `PRAMANA_LOG_QUERIES=0` to turn question logging off.

## Limitations

* Covers GHG emissions and climate disclosures only. Other topics are answered with "not available yet".
* Figures are shown exactly as companies disclosed them. A few appear to be in a different unit (for example Tata Steel's Scope 1 of 61 tCO2e); these are shown with a note and left out of comparisons and totals.
* Sector classification is taken from the source data, with corrections listed in `pipeline/registry.py` (`SECTOR_CORRECTIONS`): the sector column was displaced by one row for the fifteen consecutive companies from Hi-Tech Pipes to Hindware Home Innovation (so Hindalco is now under Metals & Mining and Hindustan Unilever under FMCG), and Punjab & Sind Bank is under Financial Services. A few other entries may still be wrong and should be checked against an authoritative list.
* Company names filed in capitals are shown in ordinary title case with acronyms kept (NTPC Limited, Wipro Limited, ICICI Bank Limited); a few brand casings are listed in `server/pramana/engine/fmt.py`.
* Unusual phrasings may be routed to the closest known kind of question; ambiguous company names ask for clarification rather than guessing.
