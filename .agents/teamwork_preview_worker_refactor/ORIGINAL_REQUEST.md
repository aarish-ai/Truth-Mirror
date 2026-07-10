## 2026-07-10T03:31:22Z
Refactor the Truth Mirror pipeline codebase to fulfill requirements R1, R2, R3, and R4 as follows:

1. Create a new module `truth_mirror/embeddings.py` that implements:
   - `get_gemini_embedding(text: str) -> list[float]`
     It must make a synchronous HTTP POST call to Gemini's embedding API (`text-embedding-004`) using `urllib.request`.
     Url: `https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key=<api_key>`
     It must use the rotated keys via `get_current_key()`.
     If it gets a `429` or `403` HTTPError, it must call `rotate_gemini_key()` and retry.
     If it fails, it must return a fallback vector of 768 zeros.
   - `get_gemini_embeddings(texts: list[str]) -> list[list[float]]`

2. Refactor `truth_mirror/context_tracker.py`:
   - Remove `from sentence_transformers import SentenceTransformer, util` and `HAS_SENTENCE_TRANSFORMERS`.
   - Implement `ContextTracker.__init__` to not load SentenceTransformer.
   - In `track_claim()`, replace `self.model.encode(...)` with `get_gemini_embedding` and `get_gemini_embeddings`.
   - Calculate cosine similarity using a pure Python helper instead of PyTorch `util.cos_sim`.

3. Refactor `truth_mirror/ranking.py`:
   - Remove all imports from `sentence_transformers`.
   - Replace `_semantic_similarity(a: str, b: str) -> float` to call `get_gemini_embedding(a)` and `get_gemini_embedding(b)` and compute cosine similarity in pure Python.

4. Refactor `truth_mirror/vector_store.py`:
   - Remove `from sentence_transformers import SentenceTransformer`.
   - In `__init__`, set `self.dimension = 768` instead of checking `self.encoder`.
   - In `store()` and `search()` for ChromaDB, call `get_gemini_embedding` and pass the results to the `embeddings`/`query_embeddings` arguments of `collection.add`/`collection.query`. This prevents ChromaDB from downloading default local model weights.
   - In `store()` and `search()` for FAISS, generate embeddings via `get_gemini_embedding` and convert them to numpy float32.

5. Refactor `truth_mirror/stance.py`:
   - Remove `from transformers import pipeline` and the cross-encoder NLI initialization.
   - Implement `StanceAnalyzer.detect()` to use a synchronous HTTP POST call to Gemini `gemini-3.5-flash` via `urllib.request` to determine stance.
   - Prompt layout should request a JSON output with the key "stance" (one of "supports", "contradicts", "neutral", "insufficient").
   - If rate-limited (HTTP 429 or 403), rotate the key using `rotate_gemini_key()` and retry.
   - If the API fails or key is missing, fall back to `self._fallback(claim, evidence_text)`.

6. Refactor `truth_mirror/key_rotator.py`:
   - Call `load_dotenv()` at the top of the file or inside `init_keys()` so that environment variables from the `.env` file are loaded before checking keys.

7. Globally adopt API key rotation via `get_current_key()` from `key_rotator.py` in all modules:
   - Refactor `truth_mirror/gemini_analyzer.py` and `truth_mirror/narrative_clusterer.py` to use `get_current_key()` instead of checking `os.getenv("GEMINI_API_KEY")` in `__init__`.
   - Ensure they dynamically get the current key and instantiate `genai.Client(api_key=current_key)` when executing API requests, so they don't use stale keys if rotation occurred.
   - Check if the OpenRouter key is correctly loaded. In all lookups, ensure `load_dotenv()` is run.

8. Fix time-blindness in prompts:
   - In `truth_mirror/geo_query_generator.py`, remove dynamic insertion of `self.current_date_str` and instructions to write date-scoped queries. Make queries broad and timeline-agnostic.
   - In `truth_mirror/local_decomposer.py`, modify example prompts to remove specific dates (like "June 2026"), instructing the model to remain timeline-agnostic.

9. Robust fallbacks in `truth_mirror/source_analyzer.py`:
   - Add safety checks in `analyze()` to check if `data` is a valid dict, has "choices", and "message" is populated before parsing OpenRouter response. Initialize `parsed = {}` to prevent unbound variable crashes.
   - In `_call_gemini_batch()`, verify response candidate/part existence before accessing indexes.
   - In both individual `analyze` and batch `_call_gemini_batch`, rotate keys on HTTP 403 in addition to 429 to handle daily limits.

MANDATORY INTEGRITY WARNING: DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

After making these changes, run `python -m pytest` and `python test_geo_pipeline.py` to verify that all tests pass.
Document the exact modifications made and verification results in handoff.md in your working folder c:\Users\DELL\.gemini\antigravity\scratch\Truth Mirror\.agents\teamwork_preview_worker_refactor\ and report back.
