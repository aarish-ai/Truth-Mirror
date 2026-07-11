# 🪞 Truth Mirror — Development Journey

> A chronological log of how we built, broke, debugged, and improved this geopolitical intelligence engine from scratch.

---

## 🚀 Where We Started

- **The Claim**: A user typed *"US invaded Venezuela"* — a real January 2026 event where US forces captured Venezuela's president in an anti-narcotics operation.
- **The Result**: The engine returned `OUT OF SCOPE` and then showed old Wikipedia articles with a note that "January 2026 is a future date."
- **The Problem**: A supposedly intelligent fact-checking engine had no awareness of current events, no real sources, and no analysis worth reading.

---

## 🔍 Step 1 — Diagnosing the Real Problems

- Identified **5 systemic bugs** causing the broken output:
  - The claim scope gate was rejecting real news events as "out of scope"
  - Queries were being generated with hardcoded month/year, missing recent events
  - Sources pulled were completely irrelevant — *Tenet (the movie)* and football match results
  - The system thought January 2026 was a "future date" — no awareness of the current date
  - `NoneType` errors were silently crashing the pipeline when APIs returned empty responses
- **Lesson learned**: A pipeline is only as smart as its weakest link. Every stage was failing independently.

---

## ⚙️ Step 2 — Fixing Rate Limits (First Round)

- **Problem**: All structural tasks (scope gate, decomposer, query generator) were hitting the same OpenRouter free tier simultaneously — ~55-60 API calls per request.
- **Fix**: Migrated structural tasks to **Groq** (`llama-3.3-70b-versatile`) which has a 14,400 req/day free tier.
- **Fix**: Source analysis was batch-called to Gemini using REST API with `urllib` to avoid SDK timeouts.
- Added **`key_rotator.py`** — a thread-safe key rotation system using `RLock` so all modules share one global key pool.
- User provided **5 Gemini API keys** — added to `.env` as a comma-separated `GEMINI_API_KEYS` list.
- **Lesson learned**: Never rely on a single API key or a single provider. Rotate aggressively.

---

## 🤖 Step 3 — Launching the Teamwork Multi-Agent Refactor

- Decided a systemic refactor was needed — too many files had the same problems independently.
- Used `/teamwork-preview` to launch a **multi-agent team**: Orchestrator → Explorer → Worker → Reviewers → Challengers → Auditor.
- **What the team accomplished**:
  - Removed all local HuggingFace models (`all-MiniLM-L6-v2`, `cross-encoder/nli-deberta-v3-large`) — no more model weight downloads
  - Created `embeddings.py` — a clean Gemini `text-embedding-004` API client replacing local sentence transformers
  - Wired `get_current_key()` from `key_rotator.py` into every single module
  - Fixed time-blindness — prompts in `geo_query_generator.py` and `local_decomposer.py` now explicitly say *"Do not include specific dates, months, or years"*
  - Added `[r for r in raw_results if r is not None]` safety filter in `source_analyzer.py`
- **Teamwork quota hit**: The verification swarm consumed the Antigravity platform quota mid-audit. We took over manually and verified all changes ourselves.
- **Lesson learned**: Multi-agent systems are powerful but consume quota fast. Have a manual fallback plan.

---

## 📉 Step 4 — Hitting the Gemini Daily Wall

- Ran the first full pipeline test — got `VERDICT: UNVERIFIABLE`, `CONFIDENCE: 0.1`, `HIDDEN STORIES: 0`.
- **Root cause discovered**: `gemini-3.5-flash` free tier = **20 requests/day per key**.
  - 5 keys × 20 = 100 total Gemini calls per day
  - One single analysis uses ~76 Gemini calls (36 sources + verdict + hidden stories + background)
  - One test run completely exhausted the entire day's budget
- **Lesson learned**: Never assume the newest model has the best quota. Older models often have far more generous free tiers.

---

## 🧠 Step 5 — The Smart Model Split (Ideas A–D)

After a focused discussion about the problem, we designed and implemented four concrete fixes:

- **Idea A — Switch bulk tasks to `gemini-2.0-flash`**
  - `gemini-2.0-flash` has **1,500 req/day** per key vs 20 for `gemini-3.5-flash`
  - Applied to: `source_analyzer`, `claim_scope_gate`, `stance` — all repetitive classification tasks
  - Result: 5 keys × 1,500 = **7,500 calls/day** budget for bulk work

- **Idea B — True Mini-Batching (6 sources per call)**
  - The original "batch" sent all 36 sources in one prompt — caused 503 timeout errors
  - The fallback was 36 individual calls — burned all quota in minutes
  - New approach: **split into batches of 6** — 6 API calls instead of 36, no timeout issues
  - Added sequential execution (1 at a time) to stay under the 15 RPM per-minute limit

- **Idea C — Keyword Pre-Filter**
  - Before any API call, extract meaningful keywords from the claim (`"US invaded Venezuela"` → `{invaded, venezuela}`)
  - Drop any article whose title + snippet share **zero keywords** with the claim
  - Verified working: Correctly drops *Tenet (the movie)*, football results, and other noise before they ever touch an API
  - Zero cost — pure Python regex, no API calls needed

- **Idea D — Reserve `gemini-3.5-flash` for Intelligence Synthesis Only**
  - The smarter (but quota-scarce) model is now exclusively used for:
    `hidden_story_extractor`, `verdict_engine`, `geo_orchestrator`, `geo_synthesizer`, `narrative_clusterer`, `perspective_synthesizer`
  - These are the tasks that genuinely need deeper reasoning
  - Lesson learned: Use the right tool for the right job. Not every task needs the smartest model.

---

## 🐛 Step 6 — Bonus Bugs Caught During Testing

- **Broken OpenRouter fallback model**: All synthesis modules had `nvidia/nemotron-3-ultra-550b-a55b:free` as their fallback — a model that **does not exist** on OpenRouter. When Gemini failed, the fallback silently failed too, producing `HIDDEN STORIES: 0` with no error.
  - Fix: Replaced with `qwen/qwen3-next-80b-a3b-instruct:free` (the proven working model)
  - Affected files: `verdict_engine`, `hidden_story_extractor`, `geo_orchestrator`, `geo_synthesizer`, `perspective_synthesizer`

- **Concurrent mini-batches overloading RPM**: Running 3 mini-batches simultaneously hit the 15 req/min limit across all 5 keys at once.
  - Fix: Changed `max_concurrent` from 3 → 1 (sequential). Since each call handles 6 sources, sequential is fast enough.

---

## 🛠️ Step 7 — API Rate Limit, Concurrency & Bug Fixes

- **Problem:** The system was double-initializing connectors, throwing scoping errors for API clients, and aggressively hammering Gemini and OpenRouter with parallel requests causing severe rate-limiting chains.
- **Fix:**
  - Removed duplicate `GoogleNewsRSSConnector` instances.
  - Pruned dead code stranded in `orchestrator.py`.
  - Fixed an `UnboundLocalError` scoping bug in synthesizers where `gemini_client` wasn't initialized prior to API failures.
  - Implemented hard volume capping (15 articles max) and **sequential batch processing** for source analysis, interspersed with sleep intervals to respect API token buckets.
  - Re-wrote the fallback logic in `source_analyzer.py` to stop fanning out single requests when a batch failed.
  - Implemented module-level `threading.Semaphore(1)` and geometric backoff scaling to stop hammering the OpenRouter free tier.

---

## 🔀 Step 8 — The Great Groq Migration

- **Problem:** Gemini was being used for both high-volume repetitive tasks (Source Analysis) and low-volume deep reasoning (Synthesis). Even with mini-batches, the quota contention between these two stages frequently crippled the pipeline.
- **Fix:**
  - Migrated the entire high-volume source analysis stage to **Groq** (`llama-3.3-70b-versatile`). 
  - Shrunk batch sizes from 6 to 3 articles to respect Groq's Tokens-Per-Minute limit.
  - Restructured the primary fallback cascade in source analysis to: `Groq → Gemini`. OpenRouter was entirely stripped from this stage.
  - Deployed Groq as a robust synthesis buffer: the deep-reasoning engines now fall back to Groq before resorting to OpenRouter if Gemini gets rate-limited.
  - Enforced aggressive `asyncio.sleep` pacing: 10 seconds before synthesis begins, and 15 seconds between each synthesis module, ensuring Gemini limits are respected.
- **Bug Caught:** Fixing the synthesizers exposed an `UnboundLocalError` due to inner-function `import os` statements shadowing global variables. Fixed by cleanly hoisting all necessary imports to the top of the function blocks.

---

## 📦 What Got Committed to GitHub

| Commit | Message | What it contained |
|---|---|---|
| `2c3463a` | `Fixing Rate Limits . . .` | Groq integration, key rotator, batch REST calls |
| `aa151a0` | `Fixing Gemini Usage, Added Mini Batching, and Keyword Filtering` | Model split, mini-batching, keyword filter, fixed OpenRouter fallbacks |
| `86ca9ca` | `Fixing A lot of things . . .` | Rate-limit spacing, sequential batches, UnboundLocalError scoping fixes |
| `4e1cf10` | `I trusted you Gemini . . .` | Groq migration for source analysis, batch resizing to 3, synthesis API fallback cascade |

---

## 📍 Where We Are Now

| Component | Before | After |
|---|---|---|
| Local model downloads | Downloaded 500MB+ at startup | Zero — pure API calls |
| Source analysis | 36 individual calls on gemini-3.5-flash | 5 mini-batch calls on Groq (Llama 3.3 70B) |
| Daily API budget | ~100 calls/day (burned in 1 run) | 14,400 req/day (Groq) + 7,500 calls/day (Gemini 2.0) |
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

*Truth Mirror — from broken Wikipedia summaries to a resilient, API-first geopolitical intelligence engine.*