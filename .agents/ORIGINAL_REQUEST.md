# Original User Request

## 2026-07-10T03:13:34Z

# Teamwork Project Prompt

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview

Refactor the Truth Mirror v2.2 pipeline to remove all local ML models, globally adopt API key rotation, fix time-blindness in query generation, and robustify the OpenRouter fallback logic. 

Working directory: c:\Users\DELL\.gemini\antigravity\scratch\Truth Mirror
Integrity mode: benchmark

## Requirements

### R1. Remove Local Models
Replace HuggingFace local models (`sentence-transformers/all-MiniLM-L6-v2` and `cross-encoder/nli-deberta-v3-large`) with external Embedding API calls (e.g., Gemini `text-embedding-004`). The system must run entirely on external APIs with no local model downloading or execution.

### R2. Global Key Rotation
Update all modules (specifically `gemini_analyzer.py` and `narrative_clusterer.py`) to use `get_current_key()` from `key_rotator.py` instead of checking for a singular `GEMINI_API_KEY` environment variable. Ensure the OpenRouter key is correctly loaded from the `.env` file.

### R3. Fix Query Generation Time-Blindness
Modify the prompts in `geo_query_generator.py` and `local_decomposer.py` to prevent the LLM from hardcoding the current month/year into search queries. Queries must be broad and timeline-agnostic to properly retrieve historical events.

### R4. Robust API Fallbacks
Add safety checks in `source_analyzer.py` to gracefully handle OpenRouter fallback failures without crashing (preventing `NoneType` attribute errors). Ensure the batch analyzer utilizes key rotation if a key hits its daily limit mid-batch.

## Acceptance Criteria

### Execution & Stability
- [ ] No local `.bin` or `.safetensors` model weights are downloaded at startup. Verified by running the pipeline and observing stdout/stderr.
- [ ] The pipeline successfully clusters narratives without throwing `GEMINI_API_KEY not found` errors.
- [ ] Generated search queries do not inappropriately append the current month/year (verified in logs).
- [ ] The system does not crash with a `NoneType` error if an API call returns empty/invalid responses.
- [ ] `test_run.py` or equivalent test scripts complete successfully from end-to-end without local model loading.
