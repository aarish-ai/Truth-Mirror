# Truth Mirror: Technology & Architecture

## 1. High-Level Overview for Technical Stakeholders

Truth Mirror is engineered as a robust, hybrid multi-agent pipeline designed for speed, resilience, and high availability. It functions similarly to a microservices architecture, where distinct intelligence tasks are routed to the most appropriate AI models and data connectors.

At a high level, the system employs:
- **A Hybrid LLM Strategy:** Fast, structural tasks (like decomposing claims and batch-analyzing sources) are routed to Groq's low-latency models (Llama-3). Deep reasoning, narrative detection, and final synthesis are handled by Google Gemini.
- **Real-Time Data Connectors:** Custom web scrapers and API connectors pull live data in parallel, ensuring the engine relies on up-to-the-minute web information rather than outdated LLM training weights.
- **Robust Caching Layers:** A Write-Ahead Logging (WAL) SQLite cache stores final results, while memory caches handle static assets and embeddings, effectively reducing redundant API costs to zero on repeated queries.

---

## 2. Engineering Deep Dive

### Multi-Agent Orchestration & LLM Roles
Truth Mirror avoids a monolithic "one-prompt-rules-all" design. Instead, the `orchestrator.py` dispatches discrete tasks:
- **Groq (llama-3.1-8b-instant / llama-3.3-70b-versatile):** Chosen for unparalleled token-per-second output. It powers `claim_scope_gate.py` for rapid request filtering and handles the heavy lifting of batch analyzing 15+ sources simultaneously in `source_analyzer.py`. 
- **Google Gemini (gemini-3.5-flash):** Serves as the primary synthesis engine in `geo_orchestrator.py`. It is responsible for clustering narratives, detecting geopolitical divergence, and generating the "Hidden Story".
- **OpenRouter (Qwen / Fallbacks):** Embedded inside our `truth_mirror/llm_fallback.py` chain. If both Groq and Gemini encounter rate limits, the system dynamically switches to OpenRouter endpoints to ensure 100% uptime.

### Concurrency & Asynchronous Design
Speed is critical when retrieving and analyzing dozens of sources in real-time.
- **Evidence Retrieval:** `GeoOrchestrator` utilizes `concurrent.futures.ThreadPoolExecutor` to execute multiple geographical queries (Western media, State media, Middle East media) in parallel.
- **Academic Pipelining:** Within `retrieval_acad.py`, the PubMed connector chunks E-Summary requests using a ThreadPoolExecutor. This maximizes throughput while strictly adhering to NIH API rate limits.
- **Global ThreadPool:** The backend server (`app.py`) leverages a module-level `ThreadPoolExecutor` to serve incoming HTTP requests concurrently without the overhead of spawning fresh pools on every connection.

### Algorithms & Data Structures
We utilize classic data science and NLP algorithms to ensure high data integrity:
- **Jaccard Similarity Matching:** In `source_analyzer.py`, when mapping batch LLM analyses back to their original source articles, we utilize Jaccard token similarity on the article titles. This prevents data desynchronization if the LLM hallucinates array indices.
- **MD5 Hash Deduplication:** To deduplicate retrieved evidence in `retrieval.py` when standard URLs are missing (e.g., from PDF reports or academic stubs), we generate a reliable MD5 hash from the first 200 characters of the excerpt and the title.
- **Regex Guardrails:** We employ strict regex boundaries (`\b`) in our news connectors (`retrieval_news.py`) to prevent false-positive substring matches (e.g., filtering for "war" without accidentally capturing "award").

### Data Stores & Caching
- **Vector Storage (FAISS):** `vector_store.py` utilizes Facebook AI Similarity Search (FAISS). We specifically wrap `IndexFlatL2` with `faiss.IndexIDMap` to support dictionary-based integer lookups. This architectural choice prevents vector misalignment when deleting stale items.
- **API Response Caching (SQLite):** To prevent duplicate processing of the same geopolitical claim, `caching.py` implements a persistent SQLite database running in WAL mode for high-concurrency reads/writes.
- **Memory Caching:** High-traffic static frontend files (like `index.html`, `style.css`, and `script.js`) are aggressively cached in memory within `app.py` upon initialization, drastically cutting down on filesystem I/O operations.

### Robustness & Resilience Engineering
- **ReAct Agent Stuck Detection:** Our optional ReAct agent (`agent.py`) features a robust safety circuit. If the LLM enters an infinite observation loop (failing to output a valid action), a `stuck_count` breaks the loop after 3 failed iterations, preserving the context window and returning a graceful failure.
- **Automatic Key Rotation:** To manage provider rate limits (HTTP 429), `key_rotator.py` monitors API exhaustion and dynamically swaps API keys in real-time without aborting the active request.
- **Archival URL Preservation:** When retrieving dead links, our `verifiers.py` seamlessly substitutes them using the Wayback Machine API, storing the `archive_url` within the dataclass to ensure users can still manually verify the primary source on the frontend.
