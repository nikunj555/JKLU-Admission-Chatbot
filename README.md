# JKLU University Information Agent

A Retrieval-Augmented-Generation (RAG) assistant that answers questions about JK Lakshmipat University
(admissions, fees, scholarships, hostel, examinations, programmes, contacts, notices) **only from JKLU's
official website and PDFs**, cites its sources, and - as required by the synopsis - decides whether the
evidence is sufficient to **answer**, ask for **clarification**, or **escalate** to a university office.

## Run it (one command)

```bash
python run.py
```

That single command: installs missing packages -> crawls jklu.edu.in (or uses the bundled cache if you are
offline) -> cleans + chunks -> embeds -> builds the FAISS index -> starts the API and opens the web chat UI at
http://127.0.0.1:8000 (the API serves the UI itself; everything is bundled, so the page works offline). Re-running is fast (PDFs and the index are cached and only rebuilt when data changes).

| Command | What it does |
|---|---|
| `python run.py` | everything + web UI |
| `python run.py --cli` | chat in the terminal |
| `python run.py --eval` | also run the evaluation -> `results/evaluation_report.md` |
| `python run.py --calibrate` | evaluation + suggested evidence thresholds for your embedding model |
| `python run.py --offline` | never use the network (cached/bundled data) |
| `python run.py --refresh` | re-download PDFs even if cached |
| `python run.py --skip-ingest` | reuse `data/processed/chunks.jsonl` (fast start) |
| `python run.py --rebuild` | force a vector-index rebuild |
| `python run.py --api` | API + web UI without opening a browser (API docs at /docs) |
| `python run.py --streamlit` | use the older Streamlit UI instead of the web UI |
| `python run.py --selftest` | run the built-in tests |

**First run needs internet once**: to crawl the site and to download the `all-MiniLM-L6-v2` model (~90 MB).
Without it the system still works (cached data + lexical retrieval) and upgrades automatically next time.

**Generated answers (optional)**: copy `.env.example` to `.env` and set `OPENAI_API_KEY` or
`ANTHROPIC_API_KEY`. With no key the agent returns extractive answers (best matching sentences + citations).
If the LLM call ever fails the agent falls back to the extractive answer - it never errors out.

## The web UI (React + TypeScript + Vite + Tailwind)

`python run.py` serves the compiled UI from `frontend/dist/` at http://127.0.0.1:8000. **No Node.js is needed to run it.**
Source code lives in `frontend/ui/`; the earlier plain-JS UI is still available at `/classic`.

* Midnight-navy and slate design system with crisp, native Light (`bg-slate-50`) and Dark (`dark:bg-slate-950`) modes.
* Welcome screen with composer and suggested-question cards; every card sends a real question to the RAG backend.
* Safe Markdown answers (tables, lists), inline `[1]` citations that open the matching source, an expandable
  "Sources and references" panel (title, official URL, page, year), copy / helpful / not-helpful, retry on failure.
* **Honest evidence indicator** from the backend status: *Sources found*, *More information needed*,
  *Could not verify this information*. No confidence percentages are shown.
* Clarification chips, escalation cards with the official contacts parsed from jklu.edu.in, a Stop button that
  cancels the in-flight request, conversation history (stored only in your browser, searchable, deletable),
  Settings (passages, topic scope, clear history, system status) and a feedback dialog.
* Keyboard shortcuts: `/` focuses the composer, `Esc` closes dialogs.

### API used by the UI
`POST /api/chat`, `GET /api/health`, `GET /api/categories`, `POST /api/feedback` (stored in `data/feedback.jsonl`:
rating, request id, the question text and an optional comment; answers are not stored). Each chat response contains
`status` (`answer` | `clarify` | `escalate` | `smalltalk`), `answer`, `sources[]`, `suggestions[]`, `contacts[]`,
`contact_page`, `request_id`. Source links are only rendered for `jklu.edu.in` hosts.

### Changing the UI (needs Node.js 18+)
```bash
cd frontend/ui
npm install
npm run dev          # http://localhost:5173 (proxies /api to the backend on :8000; start `python run.py --api` first)
npm run dev:mock     # UI-only development with clearly labelled mock data (no backend)
npm run build        # type-check + production build into ../dist
```
`frontend/ui/.env.example` lists the optional variables (`VITE_API_BASE_URL`, `VITE_USE_MOCK`); never put secrets there.

## How it works

```
jklu.edu.in pages + PDFs ──► ingest.py ──► clean documents ──► chunking.py ──► chunks.jsonl
                                 │  (cache, retries, offline fallback, manual docs)
chunks ──► Sentence-Transformers ──► FAISS ─┐
chunks ──► BM25 keyword index ──────────────┴─► hybrid retrieval (RRF + category routing)
                                                      │
                                       evidence.py: answer | clarify | escalate
                                                      │
                                 llm.py (OpenAI / Anthropic / extractive) ──► answer + [n] sources
                                                      │
                                         FastAPI  /chat  ──► Streamlit UI
```

| File | Role |
|---|---|
| `jklu/sources.py` | curated seed URLs (with fallback candidates), URL→category rules, crawl policy |
| `jklu/ingest.py` | polite parallel crawler, HTML/PDF extraction, tables, e-mail decoding, boilerplate removal, caching |
| `jklu/chunking.py` | sentence-aware ~190-word chunks, page ranges, section headings |
| `jklu/index.py` | embeddings, FAISS, BM25, hybrid fusion, freshness prior |
| `jklu/evidence.py` | ambiguity / year-support / IDF-coverage / cosine checks |
| `jklu/llm.py`, `jklu/agent.py` | prompt, providers, extractive fallback, follow-up handling, escalation contacts |
| `jklu/api.py` | FastAPI backend (`/api/*`); also serves the web UI |
| `frontend/ui/` | React + TypeScript source of the web UI (build output: `frontend/dist/`) |
| `frontend/web/` | the earlier plain-JS UI with Zero-G physics, served at `/classic` |
| `frontend/app.py` | optional Streamlit UI (`--streamlit`) |
| `jklu/evaluate.py` | keyword vs dense vs hybrid; hallucination-rejection metrics |
| `data/manual/` | drop extra PDFs/notes here (e.g. notices) |
| `data/test/test_questions.csv` | 41 labelled questions (direct, paraphrased, multi-part, irrelevant, unsupported, ambiguous) |

## What was fixed compared with the previous Phase 1-3 code

| Problem found | Fix |
|---|---|
| Hostel category had **0 chunks** (guessed PDF URL returned 404); examination 0, fees 1 | verified Hostel Life Policy URLs with automatic fallback candidates; fee-refund, grading, probation PDFs seeded explicitly |
| 580 of 617 chunks were "academics" (faculty/blog pages crawled) | curated seeds + allow/deny crawl rules; category assigned by rules, not inherited |
| 450-word chunks, but MiniLM truncates at ~256 tokens | 190-word sentence-aware chunks (+ title/section in the embedded text) |
| Chunks split at page borders; menus and "Lorem ipsum" in the text | cross-page chunking with page ranges; corpus-wide boilerplate removal |
| Fee tables flattened into word soup; e-mails shown as `[email protected]` | table rows become "Programme: B.Tech; Annual Fee: 2,84,000"; Cloudflare e-mails decoded |
| "B.Tech" did not match "Bachelor of Technology" | programme-name normalisation + synonym expansion |
| Pure vector search | hybrid dense + BM25, category routing, source-priority and stale-year prior |
| Evidence check = one similarity threshold; no clarify branch | coverage + year-support + ambiguity + cosine; real *answer / clarify / escalate* |
| `gpt-5.6-mini` hard-coded, OpenAI SDK mandatory, crashes without key | provider-agnostic, no SDK, extractive fallback |
| 3 separate folders, `sys.path` hacks, manual steps | one package, one command |

## Evaluation & Continuous Self-Agentic Improvement

### Automated Evaluation Suite (220 Questions)
The project includes a structured 220-question admission test dataset (`tests/data/jklu_admission_questions.jsonl`) and multi-layer evaluation framework:

```bash
# Run full evaluation across retrieval, supported claims, citations, and abstention
python -m tests.run_rag_evaluation --mode evaluate

# Diagnose root causes of retrieval or generation failures
python -m tests.run_rag_evaluation --mode diagnose

# Propose and test automated query expansion and synonym updates
python -m tests.run_rag_evaluation --mode improve

# Run the 20 critical Phase 11 regression test scenarios
python -m tests.run_rag_evaluation --mode regression

# Run unit tests across all pipeline modules
pytest tests/test_pipeline.py
```

### Self-Agentic Memory (`jklu/learning.py`)
- Learns verified query patterns into cluster memory (`data/learning/learned_memory.json`).
- Fast matrix phrasing vector matching with strict confidence tiers (`exact`, `strong`, `guidance`).
- Guardrails against memory poisoning and cross-entity corruption for person names and temporal years.

## Known limitations (be upfront about these in the viva)

* The **announcements/notices page is rendered by JavaScript**, so a plain HTTP crawl cannot read it. Put notice
  PDFs/text in `data/manual/notices/`, or add a headless-browser step later.
* Scanned (image-only) PDFs have no text layer; they are skipped and logged (no OCR).
* Evidence thresholds were tuned without the real embedding model. Run `python run.py --calibrate` once on your
  machine and copy the suggested values into `.env`.
* Information changes (fees, calendars): re-run `python run.py` to refresh. Every chunk stores its URL, page,
  fetch time and academic year; stale-year documents are down-weighted.
* Answers are only as good as the collected documents - check `data/processed/sources.json` after a crawl.

## Suggested team split
Data/KB: `sources.py`, `ingest.py`, `chunking.py` - Retrieval: `index.py`, `textproc.py` - Agent/LLM:
`evidence.py`, `llm.py`, `agent.py` - Backend/UI/Eval: `api.py`, `frontend/`, `evaluate.py`, test set.
