# 🪞 Truth Mirror — Development Journey

> A chronological log of how we built, broke, debugged, and improved this geopolitical intelligence engine from scratch.

---

## 🚀 Where We Started

We encountered a completely broken pipeline when testing the claim "US invaded Venezuela" due to the engine lacking current event awareness and generating poor search queries, which caused the system to return `OUT OF SCOPE` and pull irrelevant older articles. Then we did:
- Identified that the claim scope gate was rejecting real news events.
- Identified that queries were hardcoded with month/year, missing recent events.
- Identified that irrelevant sources like *Tenet (the movie)* were being pulled.
- Identified `NoneType` errors crashing the pipeline when APIs returned empty responses.

---

## ⚙️ Step 1 — Rate Limits & Key Rotation

We encountered severe API rate limiting due to all structural tasks (scope gate, decomposer, query generator) hitting the OpenRouter free tier simultaneously (~55-60 API calls per request). Then we did:
- Migrated structural tasks to Groq (`llama-3.3-70b-versatile`) to utilize its 14,400 req/day free tier.
- Converted source analysis to use batched REST API calls with `urllib` to avoid SDK timeouts.
- Added a thread-safe `key_rotator.py` using `RLock` to allow all modules to share one global key pool.
- Added support for a comma-separated `GEMINI_API_KEYS` list in `.env` to cycle through 5 provided keys.

---

## 🤖 Step 2 — The Multi-Agent Refactor

We encountered widespread systemic issues across multiple files due to repetitive logic and heavy local models downloading 500MB+ of weights at startup. Then we did:
- Launched a multi-agent team to refactor the codebase systemically.
- Removed all local HuggingFace models (`all-MiniLM-L6-v2`, `cross-encoder/nli-deberta-v3-large`).
- Created `embeddings.py` to use Gemini `text-embedding-004` instead of local sentence transformers.
- Wired `get_current_key()` from `key_rotator.py` into every single module.
- Fixed time-blindness by updating prompts to explicitly forbid specific dates, months, or years.
- Added safety filters to drop `None` results in `source_analyzer.py`.

---

## 🧠 Step 3 — The Smart Model Split & Mini-Batching

We encountered total daily quota exhaustion (hitting the 20 requests/day per key limit) due to the pipeline executing ~76 Gemini calls per run on `gemini-3.5-flash`. Then we did:
- Switched bulk classification tasks (source analysis, scope gate, stance) to `gemini-2.5-flash` which has a 1,500 req/day limit.
- Reserved the smarter `gemini-3.5-flash` exclusively for Intelligence Synthesis tasks (hidden stories, verdicts, orchestration).
- Implemented "True Mini-Batching" by splitting the 36 sources into chunks of 6, converting 36 API calls into just 6 batch calls.
- Enforced sequential mini-batch execution (1 concurrent task) to stay under the 15 requests per minute limit.
- Added a zero-cost Python regex Keyword Pre-Filter to drop completely irrelevant articles before they even touch the API.

---

## 🐛 Step 4 — OpenRouter Fallbacks & Concurrency Bugs

We encountered silent failures and 429 rate limits due to broken OpenRouter fallback models and aggressive parallelization overloading the APIs. Then we did:
- Replaced the non-existent OpenRouter fallback model with `qwen/qwen3-next-80b-a3b-instruct:free` across all synthesis modules.
- Removed duplicate `GoogleNewsRSSConnector` instances that were inflating data.
- Fixed an `UnboundLocalError` scoping bug in synthesizers where `gemini_client` wasn't initialized.
- Implemented a hard volume cap (15 articles max) for source analysis.
- Rewrote the fallback logic in `source_analyzer.py` to stop fanning out single requests when a batch failed.
- Added module-level `threading.Semaphore(1)` to stop hammering the OpenRouter free tier.

---

## 🔀 Step 5 — The Great Groq Migration

We encountered persistent quota contention because high-volume source analysis and low-volume deep reasoning were both still competing for the same Gemini limits. Then we did:
- Migrated the entire high-volume source analysis stage to Groq (`llama-3.3-70b-versatile`).
- Shrunk batch sizes from 6 to 3 articles to respect Groq's Tokens-Per-Minute limit.
- Restructured the source analysis fallback cascade to: `Groq → Gemini`, completely stripping OpenRouter from this stage.
- Deployed Groq as a robust secondary fallback in the synthesis engines (Gemini → Groq → OpenRouter).
- Enforced aggressive `asyncio.sleep` pacing: 10 seconds before synthesis begins, and 15 seconds between each synthesis module, ensuring Gemini limits are respected.
- Fixed a final `UnboundLocalError` in the synthesizers caused by inner-function `import os` statements shadowing global variables.

---

## 🛠️ Step 6 — Quality, Reliability & UX Improvements

We encountered source alignment bugs, Wikinews rate limiting, JSON parse failures due to truncated LLM responses, crashes on non-dict JSON responses, and a static frontend loader that didn't reflect the backend accurately. Then we did:
- Added `PUBLISHER_NAME_MAP` to correctly resolve Google RSS publishers.
- Limited Wikinews API parallel connections to only the first two queries.
- Integrated `json-repair` to gracefully handle improperly formatted LLM responses.
- Removed all stale fallback logic referencing the deprecated Ollama pipeline.
- Added `isinstance` defensive guards to iterative loops in the synthesis engines.
- Built a dynamic polling system for the frontend that checks `/api/status` and displays cyclical fun messages to avoid the perception of a hung pipeline.

---

## ⏳ Step 7 — Groq-Powered Temporal Context Classifier

We encountered poor query generation because the pipeline appended the current date to all queries regardless of context (e.g. "US invaded Iraq" would erroneously receive "as of July 2026", returning no results). Then we did:
- Built `TemporalClassifier` using Groq to assign claims a temporal taxonomy (`current_state`, `recent_development`, `historical_completed`, `specific_incident`).
- Placed the classifier just before query generation in `geo_orchestrator.py` to inform all subsequent search queries for a run.
- Passed `temporal_context` into `GeoQueryGenerator` so queries explicitly append dates only for ongoing and recent developments, while leaving historical and specific events timeline-agnostic.
- Demoted the naive keyword-based `inject_temporal_context()` function to a secondary fallback.

---

## ⚡ Step 8 — Caching, Model Routing & Prompt Compression

We encountered high API costs and frequent rate limiting because identical claims were re-analyzed redundantly and simple cognitive tasks were using an expensive, top-tier model. Then we did:
- Built `caching.py` to cache the full `GeopoliticalResult` object based on normalized claim strings, saving 100% of API calls on identical repeat queries.
- Defined adaptive TTLs (Time-To-Live) for cached results based on temporal classification (e.g., 6 hours for current events, 72 hours for historical).
- Centralized model configuration in `groq_router.py` to prevent hardcoded model references.
- Downgraded simple reasoning tasks (Scope, Decomposition, Temporal, Query Gen) to use the 5x larger quota of `llama-3.1-8b-instant`.
- Built a fallback chain (`llama-3.3-70b` → `llama-3.3-70b-specdec` → `qwen-2.5-32b` → `llama-3.1-8b`) inside `source_analyzer.py` for maximal robustness under high volume.
- Compressed prompts significantly by lowering article excerpts from 800 to 500 characters and tightening instructions, yielding ~25% fewer tokens without quality loss.

---

## 🔍 Step 9 — Dual Groq Keys, Logging & UI Bug Fixes

We encountered rate limits on Groq despite its high capacity, needed better visibility into pipeline runs without digging through console logs, and found minor bugs in how confidence labels and alignments were displayed. Then we did:
- Implemented **Dual Groq Key rotation** (`GROQ_API_KEY_1` and `GROQ_API_KEY_2`) to double our structural task capacity.
- Built a comprehensive `testing_logger.py` that outputs a beautifully formatted `testing.md` tracking all models used, status outcomes, runtimes, and the full text of the synthesized analysis for every run.
- Replaced confusing numerical confidence scores (e.g., `98%`) with clear qualitative text labels (`Very High`, `Low`, etc.) across the UI and logs.
- Fixed JSON parsing crashes in `perspective_synthesizer.py` by adding defensive extraction for arrays wrapped inside dictionaries.
- Forced `source_analyzer.py` to prioritize the hardcoded alignments in `source_registry.py` instead of relying on the LLM's occasionally hallucinated source labels.

---

## 📍 Where We Are Now

| Component | Before | After |
|---|---|---|
| Local model downloads | Downloaded 500MB+ at startup | Zero — pure API calls |
| Source analysis | 36 individual calls on gemini-3.5-flash | 5 mini-batch calls on Groq (Llama 3.3 70B) |
| Daily API budget | ~100 calls/day (burned in 1 run) | 14,400 req/day (Groq) + 7,500 calls/day (Gemini 2.5) |
| Noise articles | Tenet movie, football scores hitting the API | Pre-filtered by keyword and hard-capped at 15 items |
| OpenRouter fallback | Calling a non-existent model | Repurposed as a tertiary fallback behind Groq (`qwen3-next`) |
| Time-blindness | Queries hardcoded with current month/year | Prompts explicitly say "timeline-agnostic" |
| Key management | Single key, crashes on 429 | Thread-safe rotation across 5 keys |
| Synthesis Pipeline | Failing silently on daily quota exhaustion | Proper fallback chain: Gemini → Groq → OpenRouter, with strict 15s delays |

---

## ⚠️ Known Remaining Limitation

- `gemini-3.5-flash` (used for synthesis) still has a **20 req/day per key** limit on the free tier.
- However, by shifting source analysis to Groq, `gemini-3.5-flash` now only receives a maximum of ~4 requests per pipeline run, drastically extending the daily threshold.
- **Long-term fix**: A paid Gemini API key removes this daily cap entirely — recommended for production deployment.

---

## 🛡️ Step 10 — Hardened Fallback Pipelines & UI Error Handling

We encountered pipeline crashes due to unexpected `None` responses when `llama-4-scout` (OpenRouter) returned 404s, leading to silent failures. We also suffered JSON parse failures due to Gemini sometimes wrapping responses in Markdown fences. Then we did:
- Rewrote the cascade logic in `source_analyzer.py` so that empty/None responses from hard API errors correctly cascade to the next fallback model.
- Built a robust 4-tier Groq fallback chain for `source_analyzer` (`llama-3.3-70b-versatile` → `llama-3.3-70b-specdec` → `qwen-2.5-32b` → `llama-3.1-8b-instant`), dropping the broken `llama-4-scout`.
- Explicitly established `llama3-8b-8192` as the `GROQ_SIMPLE_FALLBACK` for all structural tasks (scope, decomposition, temporal classification, query generation).
- Strengthened JSON parsing with robust Markdown fence-stripping before falling back to `json-repair` to handle Gemini outputs reliably.
- Added dynamic frontend error panels to gracefully communicate pipeline infrastructure failures to the user rather than leaving the UI hung.

---

## 🏗️ Step 11 — Beta Readiness: Stability & Concurrency

We encountered stability issues when running under concurrent load and faced UI crashes when language models hallucinated missing JSON keys. Then we did:
- Migrated the global pipeline status dictionary to use per-request UUIDs, successfully isolating concurrent loading screens.
- Enabled `WAL` (Write-Ahead Logging) journal mode with a 5-second busy timeout in SQLite, allowing concurrent reads and serialized writes without `database is locked` errors.
- Applied robust null-coalescing guards (`|| []`, `|| "N/A"`) across the frontend rendering logic to prevent the UI from crashing if models drop fields.
- Wrapped the main verification pipeline in a `ThreadPoolExecutor` with a strict 300-second (5 minute) hard timeout to catch and gracefully handle heavily congested upstream API conditions, returning a clean 503 instead of a hung pipeline.

---

## 🐳 Step 12 — Auth, Dockerization & User Feedback

We needed to protect the app for closed beta, host it consistently, and collect user feedback. Then we did:
- Implemented Basic HTTP Authentication directly inside the `BaseHTTPRequestHandler` using `python-dotenv` to secure the platform.
- Fully Dockerized the application using `python:3.12-slim` with a `docker-compose.yml` orchestrating persistent bind-mount volumes for SQLite and Vector Stores.
- Added a dismissible "Beta Notice" terms banner explaining that results are experimental and take 2-4 minutes.
- Integrated a secure WhatsApp feedback link dynamically populated from `.env` directly into the top bar UI.

---

## 📱 Step 13 — Mobile UX & Core Enhancements

We encountered issues with the dense UI breaking on smaller screens and mobile devices killing background processing when the screen locked. Then we did:
- Overhauled the core styling to use a glassmorphism responsive card layout for smaller viewports, collapsing the large horizontal data tables cleanly.
- Implemented the Screen Wake Lock API to prevent mobile browsers from sleeping and killing the 2-4 minute pipeline requests.
- Converted all CSS to robust variable-driven styling (`index.css`), removing hardcoded values and significantly upgrading the premium dark-mode aesthetic.

---

## ⏱️ Step 14 — Fixing "Time-Blind" Temporal Hallucinations

We discovered a critical logic flaw where the pipeline was entirely "Time-Blind". Claims about current events were being incorrectly marked as "PARTIALLY_SUPPORTED" because the LLMs pulled in matching articles from years ago and evaluated them as current. Furthermore, explicit date queries caused "double-date" duplication issues (e.g. `as of July 2026 as of July 2026`). Then we did:
- Implemented a `qualifier_already_present` logic guard inside `geo_query_generator.py` and `geo_orchestrator.py` to prevent duplicate date concatenation.
- Propagated a formal `temporal_context` object down through every pipeline stage (`SourceAnalyzer`, `PerspectiveSynthesizer`, `HiddenStoryExtractor`, `VerdictEngine`).
- Surgically injected strict temporal boundaries into all LLM prompts, explicitly instructing models to reject historical articles if the claim evaluated a present-day state.
- Updated `GeopoliticalResult` to expose `temporal_type` and `temporal_qualifier` to the client for full transparency.

---

## ⚡ Step 15 — Production Readiness & Performance Optimization

We conducted an in-depth technical audit to eliminate extreme latencies and stabilize the engine for concurrent user loads during beta launch. Then we did:
- Removed hardcoded 2–15s delays (`asyncio.sleep`) in `geo_orchestrator.py` and `source_analyzer.py`, replacing them with an adaptive token-bucket rate limiter.
- Refactored `run_tracker.py` to use `TrackerRegistry` and thread-local context (`request_id`), eliminating global state cross-wiring race conditions under concurrent `ThreadingHTTPServer` loads.
- Replaced blocking synchronous `urllib` calls inside `asyncio.to_thread` with native async `aiohttp` flows for `VerdictEngine` and API fallbacks, preventing thread pool exhaustion.
- Fixed the keyword extraction pre-filter to explicitly preserve critical 2-3 letter geopolitical acronyms (e.g., US, UK, UN) that were being dropped.
- Implemented Jaccard semantic similarity in `compute_consensus_disputes` to accurately cluster synonymous claims before stance evaluation.
- Fixed deprecated timezone logic (`datetime.utcnow()`) across caching layers to ensure Python 3.12+ compatibility and prevent subtle TTL expiration bugs.

---

## 🛠️ Step 16 — Codebase Audit Resolution: 14 Critical Bugs

We executed an autonomous agent team to systematically resolve 14 critical security, resource exhaustion, and logic flaws identified in a comprehensive codebase audit. Then we did:
- Sanitized graph entity inputs in `kg_verifier.py` to prevent SPARQL injection attacks.
- Switched to `defusedxml` for RSS parsing, entirely neutralizing XXE vulnerabilities in untrusted feed retrieval.
- Implemented robust `aiohttp` connection pooling and added explicit timeouts to all network requests to prevent socket exhaustion and pipeline stalling.
- Enforced strict basic authentication in `app.py`, ensuring empty passwords no longer bypass validation.
- Fixed race conditions in `search_planner.py` result ordering and secured class-level counters with threading locks in the `GeminiAnalyzer`.
- Expanded `test_integration.py` and the `tests/` directory with 14 programmatic assertions directly validating these fixes, leading to a 63/63 passing test suite.

---

*Truth Mirror — from broken Wikipedia summaries to a resilient, API-first geopolitical intelligence engine.*