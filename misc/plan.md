# Truth Mirror: 3-Day Beta Launch Plan

> **Status**: 62/75 issues fixed (83%). 5 blockers remain + post-launch backlog.
> **Approach**: AI-assisted development — multiple fixes per day.

---

## Day 1 — Sunday, July 27 | Pre-Launch Fixes + Technical Audit + Launch Prep

### 1.1 🔴 BLOCKER: Remove Mock Data Fallbacks (C8)

**What**: When API keys are missing or requests fail, `retrieval_fact.py`, `retrieval_archival.py`, and `retrieval_quotes.py` return **fabricated mock evidence** silently. The verdict engine can base its analysis on fake data without any indication to the user.

**How**:
- In each file, find `_mock_fallback()` methods or any code that returns hardcoded dummy `EvidenceItem` objects when a real API call fails or a key is absent.
- Replace those mock returns with `return []` (empty list).
- Add a `logger.warning("API key missing for %s — skipping connector", connector_name)` before each early return.
- Ensure the module-level `logger = logging.getLogger(__name__)` exists at the top.

**Test**:
- Temporarily rename or unset one API key in `.env` (e.g., `GOOGLE_FACT_CHECK_API_KEY`).
- Run a claim through the pipeline.
- Verify: the verdict still completes (with fewer sources), no mock/dummy evidence appears in the response JSON, and the server logs show the warning message.

---

### 1.2 🔴 BLOCKER: Fix Substring Keyword Matching (H8)

**What**: In `retrieval_news.py` and `retrieval_acad.py`, keyword matching uses Python's `in` operator for substring checks. This means a search for "war" falsely matches articles containing "award", "forward", or "warning" — and in `retrieval_acad.py`, skip-keywords like "war" cause queries about "award" to be entirely skipped.

**How**:
- In both files, find all instances of `any(term in text for term in ...)` or `if kw in claim_lower`.
- Replace with regex word boundary matching:
  ```python
  import re
  any(re.search(rf'\b{re.escape(term)}\b', text, re.IGNORECASE) for term in query_terms)
  ```
- Apply the same fix to the skip-keyword check in `retrieval_acad.py`.

**Test**:
- Submit a claim containing the word "award" (e.g., "The Nobel Peace Prize award was controversial in 2025").
- Verify: academic retrieval returns results (not skipped due to "war" substring match).
- Submit a claim with "war" — verify it still correctly matches.

---

### 1.3 🔴 BLOCKER: Preserve Original URL in Wayback Substitution (H15)

**What**: In `verifiers.py`, when a Wayback Machine archive URL is found, `item.url_or_id = wb["url"]` permanently destroys the original source URL. Users lose the ability to see where the evidence originally came from.

**How**:
- Add an `archive_url` field to the `EvidenceItem` dataclass in `models.py`:
  ```python
  archive_url: str = ""
  ```
- In `verifiers.py`, change the Wayback substitution from:
  ```python
  item.url_or_id = wb["url"]
  ```
  to:
  ```python
  item.archive_url = wb["url"]
  ```
- In the frontend (`script.js`), if `archive_url` is present, show both links (original + archived).

**Test**:
- Submit a claim that references a known archived article.
- Verify: the response JSON contains both `url_or_id` (original) and `archive_url` (Wayback link).
- Verify: the frontend displays the original source URL, with the archive link as supplementary.

---

### 1.4 🔴 BLOCKER: Add `cachetools` to `requirements.txt`

**What**: `retrieval.py` now imports `cachetools.LRUCache` (from the H3 fix), but `cachetools` was never added to `requirements.txt`. **The Docker build will fail.**

**How**:
- Open `requirements.txt`.
- Add `cachetools` on a new line.

**Test**:
- Run `pip install -r requirements.txt` in a clean environment or run `docker compose build` — it should succeed without import errors.

---

### 1.5 🔴 BLOCKER: Cache INDEX_FILE in Memory

**What**: In `app.py`, every GET request to `/` reads the 56KB `static/index.html` file from disk. Under load, this is unnecessary I/O overhead.

**How**:
- At the top of `app.py` (after imports), read and cache the file content once:
  ```python
  _INDEX_CACHE = None
  def _get_index_html():
      global _INDEX_CACHE
      if _INDEX_CACHE is None:
          with open(INDEX_FILE, "rb") as f:
              _INDEX_CACHE = f.read()
      return _INDEX_CACHE
  ```
- In `do_GET`, replace `open(INDEX_FILE, "rb").read()` with `_get_index_html()`.
- Also cache `style.css` and `script.js` similarly (since the frontend was split into 3 files in L8).

**Test**:
- Start the server and load the page in a browser — it should render identically.
- Restart the server, load the page again — verify content is served correctly from cache.

---

### 1.6 🟠 Technical Audit: ReAct Agent Stuck Detection (H13)

**What**: In `agent.py`, if the LLM response contains neither an action nor a final answer, a long generic observation is appended to the prompt. If the LLM gets stuck in a loop, this rapidly consumes the entire context window and hangs the pipeline.

**How**:
- Add a counter variable before the main loop:
  ```python
  stuck_count = 0
  ```
- Inside the loop, when a generic observation is appended (the "neither action nor final answer" branch), increment `stuck_count`.
- When a valid action or final answer is found, reset `stuck_count = 0`.
- After the increment, check:
  ```python
  if stuck_count >= 3:
      return "Analysis could not be completed — the reasoning agent was unable to reach a conclusion."
  ```

**Test**:
- Mock the LLM to return gibberish (no action/answer pattern) for 5 consecutive calls.
- Verify: the agent exits gracefully after 3 stuck iterations with the fallback message, instead of looping forever.

---

### 1.7 🟠 Technical Audit: Fix Batch Index Matching (H18)

**What**: In `source_analyzer.py`, when parsing batch LLM responses, `idx = int(raw_item.get("article_index", 0)) - 1` trusts the LLM to mirror indices perfectly. If the LLM hallucinates, skips, or reorders indices, stances get applied to the wrong source articles.

**How**:
- Instead of matching by `article_index`, match each response item to its source article by **title similarity**:
  ```python
  def _match_by_title(raw_item, articles):
      resp_title = raw_item.get("title", "").lower().strip()
      best_match = max(articles, key=lambda a: _jaccard(resp_title, a["title"].lower()), default=None)
      return best_match
  ```
- Use a simple token Jaccard similarity for matching (already exists in `geo_orchestrator.py` — reuse or duplicate it).
- Fall back to index-based matching only if title matching produces a Jaccard score below 0.3.

**Test**:
- Manually craft a batch LLM response where `article_index` values are shuffled (e.g., indices [3, 1, 2] instead of [1, 2, 3]).
- Verify: stances are correctly attributed to the right articles by title, not by the incorrect indices.

---

### 1.8 🟠 Technical Audit: Fix Deduplication in `retrieval.py` (H20)

**What**: In `retrieval.py`, the `_dedupe` function falls back to `source_title` when `url_or_id` is absent. Generic titles like "Report" cause distinct articles to be incorrectly discarded.

**How**:
- When `url_or_id` is empty, generate a content hash as the dedup key:
  ```python
  import hashlib
  dedup_key = item.url_or_id or hashlib.md5((item.snippet or item.source_title or "")[:200].encode()).hexdigest()
  ```
- This matches the approach already used in `search_planner.py` (which was partially fixed).

**Test**:
- Create two `EvidenceItem` objects with empty `url_or_id`, same `source_title` ("Report"), but different snippets.
- Pass them through `_dedupe()`.
- Verify: both items are retained (not collapsed into one).

---

### 1.9 🟡 Remaining Medium Fixes (batch)

Since you're coding with AI, bundle these small remaining medium fixes together:

#### M7 — Cache Context Tracker Embeddings
**What**: `context_tracker.py` computes Gemini embeddings synchronously for all related claims on every call, degrading performance as history grows.
**How**: Store pre-computed embeddings alongside claims in the JSON history file. On each new claim, compute its embedding once and store it. For similarity search, load cached embeddings instead of recomputing.
**Test**: Run two claims sequentially. Verify the second claim's tracking runs faster than the first (no redundant embedding calls).

#### M8 — Parallelize PubMed Calls
**What**: `retrieval_acad.py` makes two sequential HTTP calls (E-Search, then E-Summary).
**How**: Use `concurrent.futures.ThreadPoolExecutor` to run both calls in parallel, or restructure so E-Summary runs immediately after E-Search completes (they're dependent, so pipeline them — E-Search must finish first, but you can at least overlap with other connectors).
**Test**: Time a PubMed query before and after — should be ~1s faster.

#### M9 — Move Remaining Inline Imports to Top-Level
**What**: `orchestrator.py` still has inline imports for `logging` and `GoogleNewsRSSConnector`.
**How**: Move `import logging` to the top. Keep `GoogleNewsRSSConnector` import inside a try-except at the top level (since it's an optional dependency), but move it out of the function body.
**Test**: Run `python -c "from truth_mirror.orchestrator import TruthMirrorOrchestrator"` — should import without errors.

#### M17 — Remove Snopes `time.sleep(1.0)`
**What**: `retrieval_fact.py` blocks the thread for 1 second on every Snopes query.
**How**: Remove the `time.sleep(1.0)`. If rate limiting is needed, use a counter-based approach (every Nth request, sleep) or rely on the existing rate limiter.
**Test**: Time a Snopes-hitting claim before and after — should be ~1s faster.

---

### 1.10 🟡 Remaining Low Fixes (batch)

#### L12 — Document Google News `site:` Limitation
**What**: `retrieval_nonwestern.py` uses the `site:` operator in Google News RSS, which is unreliable.
**How**: Add a docstring/comment documenting this known limitation. No code change needed — this is a Google limitation, not a bug we can fix.
**Test**: N/A — documentation only.

#### L15 — Improve Routing Regex for Plurals
**What**: `routing.py` regex patterns may miss plurals ("centuries" vs "century").
**How**: Add common plural forms to the regex patterns, e.g., `r'\b(centur(?:y|ies))\b'`, `r'\b(treat(?:y|ies))\b'`.
**Test**: Submit claims with plural forms ("multiple treaties were signed") — verify correct routing classification.

#### L16 — Handle Neutral Stance in Consensus
**What**: `geo_orchestrator.py`'s `compute_consensus_disputes` drops claims with neither SUPPORTS nor CONTRADICTS stance.
**How**: Add a third category — `"neutral"` or `"insufficient_evidence"` — for claims that don't fall into consensus or disputed. Include them in the output JSON.
**Test**: Submit a claim where some sources are neutral. Verify the response includes a `neutral`/`insufficient` category alongside consensus and disputed.

---

### 1.11 🚀 Launch Preparation

After all fixes are committed:

1. **Rebuild Docker Image**:
   ```bash
   docker compose build --no-cache
   ```

2. **Local Smoke Test**:
   ```bash
   docker compose up -d
   ```
   Run 3 test claims through the UI:
   - A clear true claim: "France is a member of the European Union"
   - A clear false claim: "Brazil hosted the 2024 Olympics"
   - A nuanced geopolitical claim: "NATO expansion has destabilized Eastern Europe"
   
   Verify for each:
   - [ ] Page loads correctly (HTML/CSS/JS all served)
   - [ ] Loading progress indicator shows stages
   - [ ] Verdict returns within 5 minutes
   - [ ] No mock/dummy evidence in results
   - [ ] Source URLs are intact (not overwritten by Wayback)
   - [ ] Mobile layout works (use browser DevTools responsive mode)
   - [ ] Terms banner appears and is dismissible
   - [ ] Auth prompt appears when accessing without credentials

3. **Push to VPS**:
   ```bash
   git add -A && git commit -m "Pre-launch fixes: C8, H8, H13, H15, H18, H20 + tech audit"
   git push origin main
   ```

4. **Deploy to Production**:
   ```bash
   ssh user@vps
   cd truth-mirror
   git pull origin main
   docker compose down
   docker compose up -d --build
   ```

5. **Production Smoke Test**: Repeat the 3 test claims on the live URL.

---

## Day 2 — Monday, July 28 | Launch & Outreach

### 2.1 🚀 Go Live

1. **Final Health Check**:
   - Hit the live URL — confirm the page loads.
   - Submit one claim — confirm end-to-end verification works.
   - Check server logs: `docker compose logs -f --tail=100`
   - Verify no ERROR-level entries.

2. **Share Access**:
   - Send the URL + Basic Auth credentials to beta testers.
   - Include a brief usage guide:
     - "Enter any geopolitical claim and click Verify"
     - "Processing takes 2-4 minutes"
     - "Results are AI-generated and experimental"
     - "Daily limit: ~25 claims across all users"

### 2.2 📣 Outreach & Advertising

1. **Social Media Posts**:
   - Craft a launch post for LinkedIn/Twitter/X highlighting the core value: "Truth Mirror cross-references 15+ sources across geopolitical blocs to verify claims — including non-Western media and archival sources."
   - Include a screenshot of a completed verification result showing the perspective analysis.
   - Use relevant hashtags: #FactChecking #OSINT #Geopolitics #AI #Misinformation

2. **Direct Outreach**:
   - Message 10-15 people directly (journalists, researchers, geopolitics enthusiasts) with a personal note + access credentials.
   - Ask them to try 2-3 claims and share feedback via the contact link.

3. **Community Posts**:
   - Post in relevant subreddits (r/OSINT, r/geopolitics, r/factchecking) if appropriate.
   - Post in relevant Discord/Telegram communities.

### 2.3 📊 Monitoring

- Keep a terminal open with `docker compose logs -f` to watch for errors in real-time.
- Check the `.tm_cache.db` file size periodically to ensure the SQLite cache isn't growing excessively.
- If any user reports a crash or error, capture the server log and the claim text for debugging on Day 3.
- Track:
  - Number of claims processed
  - Any 500 errors or timeouts
  - API rate limit hits (429s in logs)
  - User feedback via contact link

---

## Day 3 — Tuesday, July 29 | Post-Launch Fixes & Polish

### 3.1 🐛 Triage Day 2 Feedback

- Review any crash reports, error logs, or user complaints from Day 2.
- Fix any **critical user-facing bugs** discovered during real usage first.
- If no critical bugs emerged, proceed to the backlog below.

---

### 3.2 Backlog: Async HTTP Migration (D4.5 — High Impact)

**What**: Sync `requests.get()` calls in the retrieval modules (`retrieval.py`, `retrieval_acad.py`, `retrieval_fact.py`, etc.) block thread pool workers. Under concurrent usage, this limits throughput.

**How**:
- Replace `requests.get()` with `aiohttp` in retrieval modules that are called from async contexts (geo_orchestrator).
- For modules called from sync contexts (regular orchestrator), keep `requests` but ensure they run inside `asyncio.to_thread()`.
- Create a shared `aiohttp.ClientSession` at the orchestrator level and pass it down.

**Test**:
- Submit 2 claims simultaneously (two browser tabs).
- Verify: both complete without timeout errors.
- Check logs: no socket exhaustion warnings.

---

### 3.3 Backlog: Semantic Consensus Clustering (D4.4 — Medium Impact)

**What**: `compute_consensus_disputes` in `geo_orchestrator.py` uses lexical Jaccard similarity to cluster equivalent claims. Synonymous claims ("US troops withdrew" vs "American forces pulled out") fail to cluster together.

**How**:
- Use the existing `get_embedding()` function from `embeddings.py` to compute embeddings for each key claim.
- Replace Jaccard similarity with cosine similarity between embeddings.
- Set a threshold (e.g., 0.85) for clustering equivalent claims.
- Fall back to Jaccard if embedding computation fails.

**Test**:
- Submit a claim that produces synonymous sub-claims from different sources.
- Verify: semantically equivalent claims are grouped together in the consensus output.

---

### 3.4 Backlog: Improve Sentinel Key Handling (L9 — Small)

**What**: `verdict_engine.py` removed the `"your_openrouter_api_key_here"` sentinel, but similar sentinels may exist in other geo-files.

**How**:
- Search the entire codebase: `grep -r "your_.*_key_here" truth_mirror/`
- Remove all sentinel placeholders and replace with proper `os.getenv()` checks that return `None` / empty string.

**Test**:
- Run `grep -r "your_.*_key_here" truth_mirror/` — should return zero results.

---

### 3.5 Backlog: Performance Monitoring Setup

**What**: Set up basic observability so you can track system health beyond Day 3.

**How**:
- Add a `/api/health` endpoint to `app.py` that returns:
  ```json
  {
    "status": "ok",
    "cache_size_mb": <sqlite_db_size>,
    "claims_processed_today": <count>,
    "uptime_seconds": <uptime>
  }
  ```
- Set up a simple uptime check (e.g., UptimeRobot free tier) to ping `/api/health` every 5 minutes and alert you if the server goes down.

**Test**:
- Hit `/api/health` — verify it returns valid JSON with correct stats.
- Kill the Docker container — verify you receive a down alert within 5-10 minutes.

---

### 3.6 Backlog: Collect & Prioritize User Feedback

- Review all feedback received via the contact link.
- Categorize into: bugs, feature requests, UX improvements.
- Add high-priority items to `misc/issues.txt` for the next development cycle.
- Reply to every beta tester thanking them for feedback.

---

## Post Day-3 Backlog (Future Iterations)

These items are tracked but not scheduled. Tackle them based on user feedback priority:

| Priority | Issue | Description |
|----------|-------|-------------|
| P1 | H13 | ReAct agent stuck detection (if agent feature is enabled) |
| P2 | M7 | Cache context tracker embeddings for performance |
| P3 | A1 | Create unified LLM client layer (architectural) |
| P4 | A2 | Consolidate all 3 caching mechanisms into SQLite |
| P5 | A6 | Fix import style for deployment (relative imports) |
| P6 | M8 | Parallelize PubMed calls |
