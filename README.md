# Truth Mirror

Truth Mirror is an MVP claim-verification product that returns an evidence-based verdict with citations, confidence, and explicit uncertainty handling.

## Architectural Evolution

Truth Mirror has undergone significant architectural enhancements, transitioning from a basic MVP to a sophisticated verification pipeline:

- **Phases 1-4 (Retrieval Expansion)**: Integrated external connectors including GDELT, RSS feeds, Fact-checkers (Google Fact Check Tools), and Semantic Scholar.
- **Phase 5 (Advanced Decomposition)**: Capable of splitting complex, multi-faceted claims into precise, atomic sub-claims.
- **Phase 6 (Entity Disambiguation)**: Enhances evidence retrieval by accurately resolving and clarifying entities within claims.
- **Phase 7 (Triangulation, Scoring & Uncertainty)**: Employs robust evidence triangulation across multiple sources, advanced scoring metrics, and explicit uncertainty handling to minimize overconfident errors.
- **Tier 1 (Temporal Validation)**: Catches impossible historical or future dates immediately before wasting time on retrieval.
- **Tier 2 (Lowered Abstention)**: Reduced the strictness of the heuristic fallback to provide verdicts more consistently when evidence is adequate.
- **Tier 3 (Gemini Integration)**: Incorporates the Gemini LLM for intelligent, human-like evidence synthesis and reasoning (if enabled).
- **Phase 8 (ReAct Agentic Architecture)**: Implements a ReAct (Reason, Act) agentic loop for dynamic, iterative evidence gathering and reasoning.
- **Phase 9 (Perspective & Geo-Narrative Capabilities)**: Introduces geo-narrative divergence tracking and an expanded 300+ domain credibility registry for cross-cultural bias analysis.
- **Phase 10 (Hybrid Deterministic Pipeline)**: Restructured the orchestrator to use a fully deterministic evidence pipeline with exactly one Gemini API call per query for final synthesis. Local LLM (Ollama) is used only for claim decomposition. All retrieval, ranking, stance detection, and triangulation are pure Python with no LLM dependency. ReAct agent preserved as opt-in feature for large models.

## Core Features

- Accepts a natural-language claim
- Normalizes and decomposes into sub-claims
- Routes claim type with type-specific hints
- Retrieves evidence from multiple connectors (Wikipedia, Wikinews, Crossref, GDELT, Semantic Scholar, RSS, Fact-checkers)
- Ranks evidence by relevance, credibility registry, recency, and independence penalty
- Performs stronger stance detection:
  - optional transformer zero-shot NLI classifier
  - robust heuristic fallback when model is unavailable
- Produces final verdict:
  - `Supported`
  - `Partially supported`
  - `Contradicted`
  - `Unsupported`
  - `Unclear`
- Returns structured JSON plus a readable web view
- Abstains (`Unclear`) using calibrated sufficiency/conflict signals

## Project Structure

- `truth_mirror/normalization.py` claim cleanup + lightweight entity/date/quantity parsing
- `truth_mirror/decomposition.py` split complex claims into atomic sub-claims
- `truth_mirror/routing.py` claim-type detection
- `truth_mirror/retrieval.py` multi-source retrieval + dedup + cache
- `truth_mirror/credibility.py` source credibility registry loader
- `truth_mirror/credibility_registry.json` source quality priors
- `truth_mirror/ranking.py` evidence scoring and ordering
- `truth_mirror/stance.py` NLI-style stance layer (model + fallback)
- `truth_mirror/abstention.py` abstention calibration module
- `truth_mirror/verdict.py` verdict aggregation with abstain gating
- `truth_mirror/orchestrator.py` end-to-end pipeline orchestration
- `pipeline.py` CLI entry point
- `app.py` minimal local web server API + UI

## Configuration & API Keys

Truth Mirror integrates external APIs to pull authoritative data and fact-checks. You must provide your API keys and configuration in a `.env` file at the root of the project.

Create a `.env` file with the following format:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_FACT_CHECK_API_KEY=your_google_api_key_here
FRED_API_KEY=your_fred_api_key_here
GOVINFO_API_KEY=your_govinfo_key_here
CORE_API_KEY=your_core_key_here
SEMANTIC_SCHOLAR_API_KEY=your_ss_key_here
OPENCALAIS_API_KEY=your_opencalais_key_here
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_FALLBACK_MODEL=gemma2:2b
GEMINI_MODEL=gemini-2.5-flash
LLM_PROVIDER=ollama
VECTOR_STORE_PATH=.tm_vectorstore
ENABLE_REACT_AGENT=false
ENABLE_OLLAMA_DECOMPOSITION=true
ENABLE_KG_VERIFICATION=true
ENABLE_NARRATIVE_CLUSTERING=false
ENABLE_NON_WESTERN_SOURCES=true
MAX_GEMINI_CALLS_PER_QUERY=1
```

> **Note**: Several internal tools (Wikipedia, Wikidata, DBpedia, Open Library, arXiv, PubMed, etc.) rely on free public endpoints and do not require API keys. OpenStreetMap Nominatim is also free but enforces strict rate limits.

## Run (CLI)

```bash
python pipeline.py
```

## Run (Web UI)

```bash
python app.py
```

Then open [http://127.0.0.1:8080](http://127.0.0.1:8080).

## Core Technologies & Dependencies

Truth Mirror utilizes the following key machine learning and infrastructure libraries:
- **Ollama**: For local LLM inference (strictly used for claim decomposition by default).
- **Google GenAI SDK**: Used exactly once per query for final intelligent evidence synthesis.
- **ChromaDB**: Local vector database for semantic search and evidence caching.
- **spaCy**: Advanced NLP for entity extraction, normalization, and linguistic analysis.
- **sentence-transformers**: Dense vector embeddings for semantic similarity and retrieval.
- **cross-encoders**: High-precision stance detection, NLI mapping, and evidence reranking.

## API Call Budget

To guarantee fast execution and avoid API quotas, Truth Mirror enforces a strict LLM budget:
- **1 Gemini call per query**: Exclusively for final synthesis of collected evidence.
- **1 Ollama call per query**: Used optionally for atomic claim decomposition.
- **0 LLM calls for retrieval**: Retrieval, ranking, stance, and triangulation are all deterministic Python.
- **0 LLM calls for KG**: Knowledge Graph verification uses direct SPARQL keyword matching.

To install dependencies and enable stronger model-backed stance inference:

```bash
pip install -r requirements.txt
```

If unavailable, Truth Mirror automatically falls back to heuristic stance scoring.

## Current Constraints and Limitations

- **External API Reliance**: The system's retrieval capability depends heavily on the uptime and availability of external APIs.
- **Rate Limits & IP Bans**: Aggressive scraping or API querying may result in temporary rate limits or IP bans.
- **Scraping Brittleness**: Custom scrapers can break when target websites update their layout or DOM structures.
- **LLM Reasoning Ceiling**: While the new Gemini integration provides deep reasoning, it requires an active API key. Without it, the system falls back to a heuristic NLI approach which may struggle with highly abstract logic.
- **Connector Coverage**: Connectors may have sparse coverage for niche or localized claims. Crossref returns metadata (and abstracts when available), but not always full text.
- **Assisting Nature**: Confidence and abstention are calibrated to assist users. For high-stakes claims, this tool provides assistive analysis, not final authoritative rulings.
