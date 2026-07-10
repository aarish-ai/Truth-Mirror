# Handoff Report — Codebase Inspection and Discovery

## 1. Observation

Direct observations of file paths, line numbers, and code blocks within the codebase:

### 1.1 Local HuggingFace Models

#### A. `sentence-transformers/all-MiniLM-L6-v2`
This model is loaded and used in three files:
*   **`truth_mirror/context_tracker.py`** (Lines 10-14, 25-30):
    ```python
    try:
        from sentence_transformers import SentenceTransformer, util
        HAS_SENTENCE_TRANSFORMERS = True
    except ImportError:
        HAS_SENTENCE_TRANSFORMERS = False
    ```
    ```python
            self.model = None
            if HAS_SENTENCE_TRANSFORMERS:
                try:
                    self.model = SentenceTransformer('all-MiniLM-L6-v2')
                except Exception as e:
                    logger.warning(f"Could not load SentenceTransformer: {e}")
    ```
*   **`truth_mirror/ranking.py`** (Lines 18-23):
    ```python
    def get_encoder():
        global _encoder
        if _encoder is None:
            from sentence_transformers import SentenceTransformer
            _encoder = SentenceTransformer("all-MiniLM-L6-v2")
        return _encoder
    ```
*   **`truth_mirror/vector_store.py`** (Lines 10-13):
    ```python
        def __init__(self, backend: str = "chroma", collection_name: str = "truth_mirror", persist_dir: str = "./.chroma"):
            self.backend = backend
            self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
    ```

#### B. `cross-encoder/nli-deberta-v3-large`
This model is loaded and used in:
*   **`truth_mirror/stance.py`** (Lines 15-34):
    ```python
    try:
        from transformers import pipeline  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        pipeline = None


    class StanceAnalyzer:
        def __init__(self) -> None:
            self._clf = None
            if pipeline is not None:
                try:
                    # If available locally, this improves over lexical matching.
                    self._clf = pipeline(
                        task="text-classification",
                        model="cross-encoder/nli-deberta-v3-large",
                        top_k=None,
                    )
                except Exception:
                    self._clf = None
    ```
    If `self._clf` fails to load, `StanceAnalyzer.detect` falls back to `self._fallback(...)` which uses lexical overlap and negations (Lines 79-80):
    ```python
            if self._clf is None:
                return self._fallback(claim, evidence_text)
    ```

---

### 1.2 API Key Configuration and Key Rotation

#### A. Key Checking & Environmental Variables
The codebase references several API keys for LLM access:
*   `GEMINI_API_KEYS` and `GEMINI_API_KEY`: Used to query the Gemini-3.5-flash model.
*   `OPENROUTER_API_KEY`: Used as a fallback LLM provider.
*   `GROQ_API_KEY`: Used in `claim_scope_gate.py` and `geo_query_generator.py` as an alternative provider.

#### B. `key_rotator.py` Mechanics
Located in **`truth_mirror/key_rotator.py`**:
*   `init_keys()`: Loads a list of unique API keys from `GEMINI_API_KEYS` (comma-separated). Falls back to `GEMINI_API_KEY` if not present. Sets up an iterator cycle `_gemini_key_cycle = itertools.cycle(_gemini_keys)` and stores the first key in `os.environ["GEMINI_API_KEY"]`.
*   `rotate_gemini_key()`: Obtains the next key in the cycle if multiple keys exist, updates `os.environ["GEMINI_API_KEY"]`, and returns `True`. Returns `False` if no rotation can be done.
*   `get_current_key()`: Returns the active key string, ensuring initialization.

#### C. Rotation Triggers (`rotate_gemini_key()` usage)
*   **`truth_mirror/claim_scope_gate.py`** (Line 152): Rotates key when the Gemini HTTP call gets a `429` rate limit status code.
*   **`truth_mirror/geo_orchestrator.py`** (Line 243): Rotates key when Gemini API request raises a rate limit exception.
*   **`truth_mirror/geo_synthesizer.py`** (Lines 221): Rotates key on rate limit error.
*   **`truth_mirror/hidden_story_extractor.py`** (Line 126): Rotates key on rate limit error.
*   **`truth_mirror/perspective_synthesizer.py`** (Line 104): Rotates key on rate limit error.
*   **`truth_mirror/source_analyzer.py`** (Lines 110, 374): Rotates key on `429` status code for individual/batch analysis.
*   **`truth_mirror/verdict_engine.py`** (Line 140): Rotates key on rate limit error.

---

### 1.3 Date-Sensitive Prompts

#### A. `truth_mirror/geo_query_generator.py`
Dynamically injects today's date and includes hardcoded future/past date examples:
*   Lines 26-27:
    ```python
            from datetime import datetime
            self.current_date_str = datetime.now().strftime("%d %B %Y")
    ```
*   Line 44:
    ```python
            date_instruction = f"Today's date is {self.current_date_str}. Generate queries that prioritize the most recent reporting and events up to this date. For claims about recent or ongoing events, include date-scoped queries (e.g. \"Iran Israel June 2026\", \"Trump Iran strikes cancelled June 2026\").\n\n"
    ```

#### B. `truth_mirror/local_decomposer.py`
Prompt template has hardcoded temporal example inputs and outputs (Lines 26-42):
```python
        prompt = f"""Break this claim into simple sub-claims, separating temporal elements from core factual elements.
Return ONLY a JSON array. Do not wrap it in a JSON object. Do not include markdown formatting or conversational text.

Ensure the temporal context evaluates the truthfulness for that specific date. Explicitly note if the action is currently ongoing versus historical, making it a "tense-aware" decomposition.

Example input: "Donald Trump is president of USA in June 2026"
Example output: ["Donald Trump is president of the USA", "The period in question is June 2026"]

Example input: "Donald Trump was president in July 2016"
Example output: ["Donald Trump is president of the USA", "The period in question is July 2016"]

Example input: "A war is happening today"
Example output: ["A war is happening", "The action is currently ongoing"]

Claim: "{claim}"

Output:"""
```

---

### 1.4 OpenRouter Fallback Handling and Batch Key Rotation

#### A. OpenRouter Fallback in `source_analyzer.py`
In `SourceAnalyzer.analyze()` (Lines 91-171):
1.  **Primary Attempt**: Calls the Gemini endpoint using `get_current_key()`. If a `429` status is received, it executes `rotate_gemini_key()` and retries up to 3 times.
2.  **Fallback Trigger**: If Gemini retries fail, or if `GEMINI_API_KEY` is completely missing from the environment, it sets `gemini_failed = True` (Lines 123-130).
3.  **OpenRouter Execution**: If `gemini_failed`, it checks if `OPENROUTER_API_KEY` is present. If it is, it issues a POST request to `https://openrouter.ai/api/v1/chat/completions` using the model `qwen/qwen3-next-80b-a3b-instruct:free` with a timeout of 30 seconds (Lines 133-148).
4.  **OpenRouter Retry & Rate-Limiting**: It retries up to 3 times. If a `429` is returned, it sleeps with exponential backoff and jitter. For other failures, it sleeps 1s and retries.

#### B. Batch Key Rotation in `source_analyzer.py`
In `SourceAnalyzer._call_gemini_batch()` (Lines 341-387):
1.  **Retries Loop**: Up to `max_batch_retries = 5`.
2.  **Key Retrieval**: Obtains the key using `get_current_key()`.
3.  **HTTP Request**: Calls the Gemini API using `urllib.request`.
4.  **429 Handling**:
    ```python
                    except urllib.error.HTTPError as e:
                        if e.code == 429:
                            logger.warning(f"[SourceAnalyzer] Gemini batch 429 rate limit. Rotating key...")
                            rotated = rotate_gemini_key()
                            if not rotated:
                                logger.error("No more keys to rotate to or single key exhausted.")
                                return None
                            continue
    ```
    If rotation succeeds, the loop continues to the next attempt using the new current key. Any other HTTPError or generic exception causes an immediate return of `None` (falling back to per-source calls).

---

### 1.5 Project Execution and Test Suite

#### A. Project Execution
The project has two main entry points:
1.  **Web Server (`app.py`)**: Runs a standard library `ThreadingHTTPServer` on `http://127.0.0.1:8080`.
    *   GET requests to `/` or `/index.html` serve the static page `static/index.html`.
    *   POST requests to `/api/verify` parse JSON payload `{"claim": "..."}` and pass it to `TruthMirrorPipeline().verify(claim)`.
2.  **CLI Interface (`pipeline.py`)**: Runs a standard prompt `input("Enter a claim to verify: ")`, executes the pipeline, and dumps the JSON result to the console.

#### B. Test Suite Structure
Tests are split into two categories:
1.  **Pytest Unit Tests** (located in the `tests/` directory):
    *   `tests/test_free_sources.py`: Validates the scoring of various evidence source types.
    *   `tests/test_pipeline_v2.py`: Validates `TruthMirrorPipeline().verify()` against a series of non-geopolitical claims.
2.  **Ad-hoc Standalone Test Scripts** (located in the project root directory):
    *   `test_geo_pipeline.py`: Tests the pipeline against a geopolitical and non-geopolitical claim, patching external network request endpoints (`arxiv`, `requests`).
    *   `test_run.py`: Basic test script verifying out-of-scope and in-scope claims.
    *   `test_direct.py`: Instantiates the pipeline and prints results for "US invaded venezuela".
    *   `test_option1.py`: Tests the scope gate, local decomposer, and geopolitical query generator modules.
    *   `test_verify.py`: Runs verification on three hypothetical geopolitical blockades/engagements.
    *   `test_api.py`: Directly calls the running API server `/api/verify` endpoint via HTTP POST.

#### C. Test Run Verification Output
Executing `python -m pytest` yielded the following output:
```
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Users\DELL\.gemini\antigravity\scratch\Truth Mirror
plugins: anyio-4.13.0
collected 2 items

tests\test_free_sources.py .                                             [ 50%]
tests\test_pipeline_v2.py .                                              [100%]

============================== warnings summary ===============================
... (Deprecation warnings for _UnionGenericAlias and torch.jit.script) ...
================== 2 passed, 8 warnings in 778.50s (0:12:58) ==================
```

---

## 2. Logic Chain

1.  **HF Models**: Grep results for `SentenceTransformer` and `pipeline` pointed directly to `context_tracker.py`, `ranking.py`, `vector_store.py`, and `stance.py`. Inspecting these files confirmed that `all-MiniLM-L6-v2` is eagerly or lazily loaded using `SentenceTransformer`, and `nli-deberta-v3-large` is loaded via `transformers.pipeline`. If the NLI classifier is unavailable, a robust fallback lexical analyzer (`_fallback`) handles stance detection.
2.  **API Keys and Rotation**: A grep for `API_KEY` showed that the code references `GEMINI_API_KEYS`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, and `GROQ_API_KEY`. Inspecting `key_rotator.py` revealed it acts as a synchronized cycle manager (`itertools.cycle`) that modifies `os.environ["GEMINI_API_KEY"]` dynamically. Any module executing Gemini calls and receiving a `429` rate limit invokes `rotate_gemini_key()`.
3.  **Date-Sensitive Prompts**: Grepping for date-related values found `datetime.now().strftime("%d %B %Y")` in `geo_query_generator.py` and hardcoded timeline references to `June 2026` / `July 2016` in `geo_query_generator.py` and `local_decomposer.py`. Inspecting these prompt strings showed that they instruct the model to produce tense-aware queries and sub-claims relative to the current date.
4.  **OpenRouter Fallback and Batch Key Rotation**: Inspecting `source_analyzer.py` revealed that if `api_key` (Gemini key) is absent or fails after 3 rate-limit retries, it switches to OpenRouter using `qwen/qwen3-next-80b-a3b-instruct:free` as long as `OPENROUTER_API_KEY` is populated. For batch calls, `_call_gemini_batch` manages up to 5 retries, invoking `rotate_gemini_key()` only on `429` status codes.
5.  **Execution & Testing**: Finding `app.py` and `pipeline.py` identified the web-server and CLI interfaces, respectively. Listing the `tests` directory and root files showed the division between pytest test cases and ad-hoc scripts. Running `python -m pytest` verified the test execution process.

---

## 3. Caveats

*   **Network Dependency**: Pytest and CLI pipeline tests make live HTTP calls to external APIs or require mock structures. Under CODE_ONLY mode, live external calls to non-cached endpoints will fail, though mock overrides (like those in `test_geo_pipeline.py`) can bypass this.
*   **HuggingFace Downloading**: Running the models locally requires downloading weights from HuggingFace. If the models are not pre-cached on the host machine, the initial run will attempt a network download, which will fail or hang in a sandboxed offline environment.

---

## 4. Conclusion

The project is structured as a geopolitical fact-checking pipeline that is highly resilient to API rate-limiting via dynamic key rotation and fallback strategies (switching to OpenRouter's free Qwen model). It utilizes local HuggingFace embeddings (`all-MiniLM-L6-v2`) and NLI model classification (`nli-deberta-v3-large`) for offline semantic matching and stance determination, falling back to lexical heuristics if libraries or weights are missing. Temporal awareness is achieved by injecting the active host system's current date directly into query generation and decomposition prompts.

---

## 5. Verification Method

To verify the observations independently:
1.  **Test Execution**: Run `python -m pytest` to execute the formal test suite, or run `python test_geo_pipeline.py` to run patched pipeline checks.
2.  **API Server Verification**: Start the server via `python app.py` and execute the client requests via `python test_api.py`.
3.  **Inspect Files**:
    *   Check `truth_mirror/key_rotator.py` to confirm the iterator setup.
    *   Check `truth_mirror/source_analyzer.py` to inspect the batch `429` and OpenRouter fallback blocks.
    *   Check `truth_mirror/geo_query_generator.py` to inspect the `datetime` format and prompt examples.
