# Truth Mirror — Model Architecture & Usage

This document outlines the exact AI models used throughout the Truth Mirror pipeline, detailing their specific roles and fallback sequences. Truth Mirror employs a multi-provider strategy (Groq, Google Gemini, OpenRouter, and Local Ollama) to maximize reliability, maintain high processing speeds, and optimize API quotas.

## 1. Claim Classification & Routing (`ClaimScopeGate`)
Determines the geographical and topical scope of the user's claim to route it to the appropriate search connectors.

* **Primary:** `llama-3.1-8b-instant` (via Groq) - Selected for extreme speed and sufficient reasoning for basic classification.
* **Fallback 1:** `gemini-2.5-flash` (via Google Gemini) - Highly reliable if Groq rate limits are hit.
* **Fallback 2:** `qwen/qwen3-next-80b-a3b-instruct:free` (via OpenRouter)
* **Fallback 3:** `qwen2.5:3b` (via Local Ollama) - Absolute last resort ensuring local operation if all cloud APIs fail.

## 2. Search Query Generation (`GeoQueryGenerator` / `SearchPlanner`)
Translates the user's claim into optimized Boolean search queries tailored for specific news/academic connectors.

* **Primary:** `llama-3.1-8b-instant` (via Groq)
* **Fallback 1:** `qwen/qwen3-next-80b-a3b-instruct:free` (via OpenRouter)

## 3. Bulk Source Analysis & Labeling (`SourceAnalyzer`)
The core engine that processes dozens of search results concurrently. It extracts stances, confidence scores, and hidden implications from each article against the main claim.

* **Primary:** `llama-3.3-70b-versatile` (via Groq) - Top-tier reasoning model for deep nuance extraction.
* **Fallback 1:** `meta-llama/llama-4-scout-17b-16e-instruct` (via Groq) - A highly capable MoE model with a separate rate limit pool, used when 70b hits limits.
* **Fallback 2:** `llama-3.1-8b-instant` (via Groq) - Quality degrades slightly, but used to keep the pipeline moving if Scout is exhausted.
* **Fallback 3:** `gemini-2.5-flash` (via Google Gemini) - Activated if all Groq models are rate-limited. Handles batch processing reliably.
* **Single-Article Fallback:** `qwen/qwen3-next-80b-a3b-instruct:free` (via OpenRouter) - Occasionally used for isolated article analysis retries.

## 4. Geopolitical Source Classification (`GeoClassifier`)
Categorizes media sources into geographical blocs (e.g., Western, Global South, State Media) to ensure diverse perspectives.

* **Primary:** `qwen2.5:3b` (via Local Ollama) - Runs completely locally by default to save cloud API credits on repetitive classification tasks.
* **Fallback 1:** `qwen/qwen3-next-80b-a3b-instruct:free` (via OpenRouter) - Activated if Ollama is not running or the model is missing.

## 5. Synthesis & Final Verdict Generation
This is the most critical and complex phase. It includes `PerspectiveSynthesizer`, `HiddenStoryExtractor`, `GeoSynthesizer`, and `VerdictEngine`. These engines consume all the structured data produced by the `SourceAnalyzer` to write the final reports and verdicts.

* **Primary:** `gemini-3.5-flash` (via Google Gemini) - Chosen for its massive context window (essential for synthesizing dozens of articles) and superior instruction-following for complex JSON array/object structures.
* **Fallback 1:** `llama-3.3-70b-versatile` (via Groq) - Highly capable reasoning model if Gemini is unavailable.
* **Fallback 2:** `qwen/qwen3-next-80b-a3b-instruct:free` (via OpenRouter) - Final safety net to ensure the pipeline always completes.

---
*Note: This architecture is designed to dynamically shift traffic across providers during high-load scenarios, ensuring Truth Mirror almost never fails midway through an analysis.*
