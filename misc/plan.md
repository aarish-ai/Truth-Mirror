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

## Day 4 — Testing and Validation
1. **3-Tab Stress Test**: Open three incognito tabs and submit complex claims simultaneously. Verify that statuses don't cross-wire, databases don't lock, and runs log correctly.
2. **End-to-End Live Test**: Run a single live geopolitical claim and verify the dashboard populates flawlessly across all panels without JS errors.
3. **API Capacity Check**: Count the exact model calls made during the live test to guarantee the daily Gemini ceiling won't be breached by the small beta group.

## Day 5 — Deploy and Invite
1. **Deployment**: Deploy the Docker container to a VPS (e.g., DigitalOcean).
2. **Launch**: Share the URL and the Basic Auth password with the whitelist.
3. **Monitor**: Watch `misc/testing.md` and server logs closely for the first 24 hours to catch any edge-case crashes.
