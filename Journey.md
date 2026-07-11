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
- Switched bulk classification tasks (source analysis, scope gate, stance) to `gemini-2.0-flash` which has a 1,500 req/day limit.
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