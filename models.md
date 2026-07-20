# Truth Mirror — Model Architecture & Usage

This document outlines the exact AI models used throughout the Truth Mirror
pipeline. Truth Mirror employs a multi-provider strategy (Groq, Google Gemini,
OpenRouter) to maximize reliability and optimize API quotas.

**Key Principle:** Before downgrading to a weaker model, all available API keys
are exhausted on the stronger model first. Quality is preserved as long as
possible.

---

## 1. Claim Classification & Routing (`ClaimScopeGate`)
Determines whether a claim is geopolitical and within scope (2015–present).

* **Primary:** `llama-3.1-8b-instant` (Groq — Key 1, then Key 2)
* **Secondary:** `llama3-8b-8192` (Groq — Key 1, then Key 2)
* **Fallback 1:** `gemini-2.5-flash` (Google Gemini — key rotation)
* **Fallback 2:** `qwen/qwen3-next-80b-a3b-instruct:free` (OpenRouter)
* **Fallback 3:** Regex keyword matching (zero-cost local fallback)

---

## 2. Temporal Intent Classification (`TemporalClassifier`)
Determines whether search queries should include the current date.

* **Primary:** `llama-3.1-8b-instant` (Groq — Key 1, then Key 2)
* **Secondary:** `llama3-8b-8192` (Groq — Key 1, then Key 2)
* **Fallback:** Keyword-based heuristic in normalization.py

---

## 3. Claim Decomposition (`LocalDecomposer`)
Breaks compound claims into atomic verifiable sub-claims.

* **Primary:** `llama-3.1-8b-instant` (Groq — Key 1, then Key 2)
* **Secondary:** `llama3-8b-8192` (Groq — Key 1, then Key 2)
* **Fallback:** Returns original claim as single-element list

---

## 4. Search Query Generation (`GeoQueryGenerator`)
Generates targeted search queries per sub-claim across multiple perspectives.

* **Primary:** `llama-3.1-8b-instant` (Groq — Key 1, then Key 2)
* **Secondary:** `llama3-8b-8192` (Groq — Key 1, then Key 2)
* **Fallback:** Deterministic fallback queries in `_get_fallback_queries()`

---

## 5. Geopolitical Source Classification (`GeoClassifier`)
Determines if a claim is geopolitical and identifies involved parties and subtype.
Used by the scope gate before routing to GeopoliticalPipeline.

* **Primary:** `llama-3.1-8b-instant` (Groq — Key 1, then Key 2)
* **Secondary:** `llama3-8b-8192` (Groq — Key 1, then Key 2)
* **Fallback 1:** `qwen/qwen3-next-80b-a3b-instruct:free` (OpenRouter)
* **Fallback 2:** Regex keyword matching (`_regex_fallback()`)

---

## 6. Bulk Source Analysis (`SourceAnalyzer`)
The highest-volume stage. Analyzes each retrieved article for stance, key
claims, emphasis, omissions, and hidden implications relative to the claim.

* **Primary:** `llama-3.3-70b-versatile` (Groq — Key 1, then Key 2)
  Top-tier reasoning model. Exhausts both keys before any downgrade.
* **Fallback 1:** `llama-3.3-70b-specdec` (Groq — Key 1, then Key 2)
  Fast speculative decoding variant of 70b. Same quality, separate quota.
* **Fallback 2:** `qwen-2.5-32b` (Groq — Key 1, then Key 2)
  Strong mid-tier model with separate quota.
* **Fallback 3:** `llama-3.1-8b-instant` (Groq — Key 1, then Key 2)
  Quality reduction is logged as WARNING. Used only when larger models are exhausted.
* **Fallback 4:** `gemini-3.5-flash` (Google Gemini — key rotation)
  Activated only if all four Groq model tiers are exhausted on all keys. Uses json_repair for robustness.

---

## 7. Perspective Synthesis (`PerspectiveSynthesizer`)
Groups source analyses by geopolitical alignment bloc and characterizes each
bloc's collective narrative, stance, and omissions.

* **Primary:** `gemini-3.5-flash` (Google Gemini — key rotation)
  Chosen for large context window and structured JSON instruction-following.
* **Fallback 1:** `llama-3.3-70b-versatile` (Groq — Key 1, then Key 2)
* **Fallback 2:** `qwen/qwen3-next-80b-a3b-instruct:free` (OpenRouter)

---

## 8. Hidden Story Extraction (`HiddenStoryExtractor`)
Identifies narratives that emerge from reading between the lines across blocs —
what is collectively omitted, who is suppressing what, and why.

* **Primary:** `gemini-3.5-flash` (Google Gemini — key rotation)
* **Fallback 1:** `llama-3.3-70b-versatile` (Groq — Key 1, then Key 2)
* **Fallback 2:** `qwen/qwen3-next-80b-a3b-instruct:free` (OpenRouter)

---

## 9. Final Verdict Generation (`VerdictEngine`)
Synthesizes all source analyses, perspective groups, and hidden stories into
a structured final intelligence verdict.

* **Primary:** `gemini-3.5-flash` (Google Gemini — key rotation)
* **Fallback 1:** `llama-3.3-70b-versatile` (Groq — Key 1, then Key 2)
* **Fallback 2:** `qwen/qwen3-next-80b-a3b-instruct:free` (OpenRouter)

---

## 10. Background Narrative Generation (`generate_background_narrative`)
Produces contextual background and current situation narrative for the result.

* **Primary:** `gemini-3.5-flash` (Google Gemini — key rotation)
* **Fallback 1:** `llama-3.3-70b-versatile` (Groq — Key 1, then Key 2)
* **Fallback 2:** `qwen/qwen3-next-80b-a3b-instruct:free` (OpenRouter)

---

## Rate Limit Architecture

| Model | RPM | RPD | TPM | TPD | Keys |
|-------|-----|-----|-----|-----|------|
| llama-3.3-70b-versatile | 30 | 1K | 12K | 100K | ×2 → 200K TPD effective |
| llama-3.3-70b-specdec | 30 | 1K | 12K | 100K | ×2 → 200K TPD effective |
| qwen-2.5-32b | 30 | 1K | 18K | 250K | ×2 → 500K TPD effective |
| llama-3.1-8b-instant | 30 | 14.4K | 6K | 500K | ×2 → 1M TPD effective |
| llama3-8b-8192 | 30 | 14.4K | 6K | 500K | ×2 → 1M TPD effective |

Gemini: 5 project keys in rotation. Each project is independent quota.
OpenRouter: Last resort only. Free tier is heavily contested.

---

## Ollama Policy

**Ollama is not used anywhere in this pipeline.** It was removed entirely.
No code path depends on a local Ollama instance — not even as a last resort.
All tasks route to Groq, Gemini, or OpenRouter.
