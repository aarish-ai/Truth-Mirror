# Project: Truth Mirror Pipeline Refactoring

## Architecture
- `key_rotator.py`: API key loading and rotation iterator.
- `context_tracker.py`, `ranking.py`, `vector_store.py`: Semantic similarity modules using embeddings.
- `stance.py`: Stance analysis comparing claims against evidence.
- `geo_query_generator.py`: Generates search queries for verifying geopolitical claims.
- `local_decomposer.py`: Decomposes claims into atomic sub-claims.
- `source_analyzer.py`: Calls external APIs (Gemini and OpenRouter) to evaluate claims.
- `app.py` / `pipeline.py`: User-facing API server and CLI pipeline.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Truth Mirror v2.2 Refactoring | Implement all refactoring requirements (R1, R2, R3, R4) in a single consolidated pass. | None | IN_PROGRESS |
| 2 | Verification & Audit | Verify implementation with pytest, ad-hoc scripts, and Forensic Auditor. | M1 | PLANNED |

## Interface Contracts
### Embedding Service
- Input: list of strings (texts) or single string.
- Output: list of floats (embedding vector) or list of list of floats.
- Error handling: fallback to dummy/lexical overlap or handle exception cleanly without crash.

## Code Layout
- `truth_mirror/context_tracker.py`
- `truth_mirror/ranking.py`
- `truth_mirror/vector_store.py`
- `truth_mirror/stance.py`
- `truth_mirror/key_rotator.py`
- `truth_mirror/geo_query_generator.py`
- `truth_mirror/local_decomposer.py`
- `truth_mirror/source_analyzer.py`
- `truth_mirror/gemini_analyzer.py`
- `truth_mirror/narrative_clusterer.py`
