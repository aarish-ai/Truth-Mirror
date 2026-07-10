# Plan — Truth Mirror Refactoring

This plan outlines the steps for refactoring the Truth Mirror pipeline to transition fully to external APIs, adopt key rotation globally, and resolve temporal bias and API fallback issues.

## Detailed Milestone Execution Steps

### Milestone 1: Replace HF Models with Gemini Embedding API
1. Create or identify an API client method for calling Gemini's `text-embedding-004` model. Since we use standard `urllib.request` or `requests` elsewhere, we should design a clean HTTP helper for `text-embedding-004` that uses the rotated keys.
2. Refactor `context_tracker.py`: Replace `SentenceTransformer('all-MiniLM-L6-v2')` usage. Make it call the Gemini embedding API.
3. Refactor `ranking.py`: Replace `get_encoder()` returning `SentenceTransformer` with a function that generates embeddings via Gemini.
4. Refactor `vector_store.py`: Replace `SentenceTransformer("all-MiniLM-L6-v2")` with the Gemini embedding API.
5. Refactor `stance.py`: Remove `transformers.pipeline` and `cross-encoder/nli-deberta-v3-large` entirely. Use a simple Gemini API call to determine stance (e.g. support, dispute, neutral) or use lexical fallback if API key is missing.

### Milestone 2: Global API Key Rotation & Rotator Load
1. Check `key_rotator.py` to ensure it is correctly loading the `OPENROUTER_API_KEY` from the `.env` file or environment.
2. In `gemini_analyzer.py` and `narrative_clusterer.py`, replace direct checking of `GEMINI_API_KEY` with `get_current_key()` from `key_rotator.py`. Ensure these files correctly initialize the keys if needed.

### Milestone 3: Fix Prompt Time-Blindness
1. In `geo_query_generator.py`, remove dynamic insertion of `current_date_str` and instructions to write date-scoped queries like "June 2026". Make queries broad and timeline-agnostic.
2. In `local_decomposer.py`, modify example prompts to exclude explicit dates like "June 2026" or "July 2016", replacing them with neutral examples.

### Milestone 4: Robust API Fallbacks & Batch Rate Limits
1. In `source_analyzer.py`:
   - Add safety checks to handle `None` / empty OpenRouter responses gracefully, preventing `NoneType` attribute errors.
   - Update `_call_gemini_batch` or batch analyzer logic to rotate keys if a daily rate limit is hit mid-batch.

### Milestone 5: Verification & Hardening
1. Execute pytest suite.
2. Execute individual integration test scripts (`test_geo_pipeline.py`, `test_run.py`, etc.).
3. Verify that no local ML weights are downloaded during run.

## Verification Protocol
For each milestone, the worker must run the verification scripts and report passing results, ensuring no code crashes or unexpected behavior.
