# Truth Mirror: 5-Day Beta Launch Plan

## API Capacity Reality Check (Prerequisite)
The system is heavily bottlenecked by the Gemini synthesis stage. The absolute limit is roughly 25 fresh claims per day across all users. This quota must be communicated to users, or rate-limited via auth, to prevent `ANALYSIS_FAILED` errors.

---

## Day 1 — Fix the Structural Bugs
These are genuine blockers that could corrupt user sessions or crash the server under concurrent load.

1. **Per-Request Pipeline Status**: Replace the global status dictionary with a UUID-keyed dictionary. Thread the `request_id` through the pipeline so concurrent users do not overwrite each other's loading screens.
2. **SQLite WAL Mode**: Enable Write-Ahead Logging and set a busy timeout in `caching.py`. This allows concurrent reads and serializes writes, preventing "database is locked" errors.
3. **Frontend Null Guards**: Audit `index.html` and add safe fallbacks to UI rendering logic. This ensures the frontend doesn't crash to a white screen if an LLM hallucinates or drops a JSON key.
4. **Hard Pipeline Timeout**: Wrap the pipeline execution in `app.py` with a 5-minute timeout. This ensures hanging API calls fail gracefully with a "system under heavy load" message instead of spinning forever.

## Day 2 — Auth, Docker, Contact, Terms
1. **Basic Authentication**: Implement a simple HTTP Basic Auth using a shared password from the environment (`.env`). This is non-negotiable to protect the API quota.
2. **Dockerization**: Create a lightweight `Dockerfile` and `docker-compose.yml` with persistent data volumes for the database, ensuring clean and reproducible cloud deployment.
3. **Contact Link**: Add a small contact link (WhatsApp or Email) to the top bar for beta user feedback.
4. **Terms Banner**: Implement a dismissible banner informing users that claims are processed by AI APIs, results are experimental, and processing takes 2–4 minutes.

## Day 3 — Mobile UX & Loading Experience
1. **Mobile Responsiveness**: Add CSS media queries to refactor the dense source analysis table into a mobile-friendly card layout. Ensure the top-bar search wraps cleanly.
2. **Visual Loading Progress**: Enhance the loading UI with a visual stage progress indicator (e.g., dots lighting up sequentially) to give users a spatial sense of pipeline progress.
3. **Screen Wake Lock**: Implement the browser Screen Wake Lock API during verification to prevent mobile devices from sleeping and killing the request during the 3-minute run.

## Day 4 — In-Depth Technical Audit & Optimization
A thorough review of the entire codebase from architectural, concurrency, algorithmic, performance, and reliability angles reveals several critical areas for optimization. These will be addressed today to ensure production readiness.

1. **Extreme Latency Bottleneck: Hardcoded Artificial Delays**
   - **Location**: `geo_orchestrator.py`, `source_analyzer.py`
   - **What we need to do**: Eliminate over 67–90 seconds of static sleeping per analysis run.
   - **How we will do it**: Remove fixed `await asyncio.sleep(...)` calls. Replace them with adaptive rate-limiters (e.g., token bucket / leaky bucket per API provider) or standard exponential backoff retries on HTTP 429 (Rate Limit) responses.

2. **Thread-Safety & Global State Race Conditions under Concurrent Load**
   - **Location**: `run_tracker.py`, `app.py`, `key_rotator.py`
   - **What we need to do**: Prevent global states from cross-wiring when multiple users make requests concurrently, and stop dynamic environment variable mutations.
   - **How we will do it**: Refactor `RunTracker` to be a per-request context instance passed through `request_id`. Stop mutating `os.environ["GEMINI_API_KEY"]` dynamically; instead, pass the rotated API key directly in memory to API clients and SDK instantiations.

3. **Algorithmic Data Loss in Pre-Filtering & Keyword Extraction**
   - **Location**: `source_analyzer.py`
   - **What we need to do**: Stop silently dropping critical 2-3 letter geopolitical acronyms (e.g., US, UK, UN, EU, IDF) during keyword pre-filtering.
   - **How we will do it**: Replace naive length checking (`len(t) > 3`) with an explicit entity preservation list, or use named entity recognition (NER) / dictionary lookup for geopolitical acronyms to retain them.

4. **Primitive Substring Matching for Consensus & Dispute Aggregation**
   - **Location**: `geo_orchestrator.py`
   - **What we need to do**: Fix fragmented consensus outputs caused by synonymous claims failing exact substring checks.
   - **How we will do it**: Refactor `compute_consensus_disputes()` to use semantic similarity (e.g., embedding cosine similarity or simple standard token Jaccard similarity) to cluster equivalent key claims before checking stance support/contradiction.

5. **Synchronous Blocking I/O inside Async Event Loops**
   - **Location**: `geo_orchestrator.py`, `source_analyzer.py`, `verdict_engine.py`
   - **What we need to do**: Prevent thread pool exhaustion and high memory usage caused by spawning blocking synchronous `urllib` HTTP calls inside `asyncio.to_thread`.
   - **How we will do it**: Refactor HTTP calls in all fallback routines (`_call_gemini_sync`, `_call_openrouter_sync`) to use native async HTTP clients like `aiohttp` or `httpx.AsyncClient`.

6. **Deprecated Timezone Handling & File I/O Overhead**
   - **Location**: `caching.py`, `app.py`
   - **What we need to do**: Fix subtle comparison bugs caused by naive datetime objects and eliminate redundant disk reads on every GET request.
   - **How we will do it**: Update `datetime.utcnow()` to `datetime.now(timezone.utc)` globally. Cache the content of `INDEX_FILE` in memory on startup in `app.py` so it's only read from disk once.

## Day 5 — Deploy and Invite
1. **Deployment**: Deploy the Docker container to a VPS (e.g., DigitalOcean).
2. **Launch**: Share the URL and the Basic Auth password with the whitelist.
3. **Monitor**: Watch `misc/testing.md` and server logs closely for the first 24 hours to catch any edge-case crashes.
