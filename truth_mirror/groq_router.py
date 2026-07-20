"""
Centralized Groq model routing configuration.
All Groq model strings are defined here — never hardcoded in other files.
Fallback Chain for Analysis: 70b-versatile -> 70b-specdec -> qwen-2.5-32b -> 8b-instant
"""

import os
import logging
import requests
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# Simple structured tasks — 8b has more than enough capability
# Uses 8b's separate 500K TPD pool, preserving 70b quota for analysis
GROQ_SIMPLE_MODEL = "llama-3.1-8b-instant"
GROQ_SIMPLE_FALLBACK = "llama3-8b-8192"

# Complex analysis tasks — requires understanding of nuance and context
GROQ_ANALYSIS_PRIMARY = "llama-3.3-70b-versatile"

# Fallback 1 for analysis: 70b-specdec. Same model, separate API pool.
GROQ_ANALYSIS_FALLBACK_1 = "llama-3.3-70b-specdec"

# Fallback 2 for analysis: qwen-2.5-32b.
GROQ_ANALYSIS_FALLBACK_2 = "qwen-2.5-32b"

# Fallback 3 for analysis: 8b as absolute last resort on Groq.
# Quality will degrade noticeably for source analysis.
GROQ_ANALYSIS_FALLBACK_3 = "llama-3.1-8b-instant"

# Model metadata for logging
GROQ_MODEL_LABELS = {
    GROQ_SIMPLE_MODEL:        "llama-3.1-8b (simple tasks)",
    GROQ_SIMPLE_FALLBACK:     "llama3-8b-8192 (simple fallback)",
    GROQ_ANALYSIS_PRIMARY:    "llama-3.3-70b (analysis)",
    GROQ_ANALYSIS_FALLBACK_1: "llama-3.3-70b-specdec (analysis fallback 1)",
    GROQ_ANALYSIS_FALLBACK_2: "qwen-2.5-32b (analysis fallback 2)",
    GROQ_ANALYSIS_FALLBACK_3: "llama-3.1-8b-instant (analysis fallback 3 — quality reduced)",
}

def get_model_label(model_id: str) -> str:
    return GROQ_MODEL_LABELS.get(model_id, model_id)

# ── GROQ KEY MANAGEMENT ───────────────────────────────────────────────

def get_groq_keys() -> list[str]:
    """
    Returns ordered list of Groq API keys.
    Key 1 (GROQ_API_KEY_1) is always checked first.
    Key 2 (GROQ_API_KEY_2) is the backup.
    Deduplicates — if both env vars point to same key, returns only one.
    """
    key1 = os.getenv("GROQ_API_KEY_1", "").strip()
    key2 = os.getenv("GROQ_API_KEY_2", "").strip()

    keys = []
    seen = set()
    for k in [key1, key2]:
        if k and k not in seen:
            keys.append(k)
            seen.add(k)

    if not keys:
        # Final fallback: try the original single-key env var
        fallback = os.getenv("GROQ_API_KEY", "").strip()
        if fallback:
            keys.append(fallback)

    return keys

def call_groq_with_key_rotation(
    payload: dict,
    timeout: int = 60,
    log_prefix: str = "[GroqRouter]"
) -> tuple[str | None, str]:
    """
    Makes a Groq API call, trying each key in order before giving up.
    Returns (response_content, status) where status is one of:
      "success"       — call succeeded
      "rate_limited"  — all keys returned 429 for this model
      "failed"        — all keys returned non-429 errors

    The caller is responsible for deciding what to do with each status.
    This function handles ONLY key rotation within a single model.
    Model fallback is handled by the caller (source_analyzer.py etc.).

    payload must be a complete Groq chat completion payload dict
    with "model" already set.
    """
    import json

    keys = get_groq_keys()
    if not keys:
        logger.error(f"{log_prefix} No Groq API keys available.")
        return None, "failed"

    model_name = payload.get("model", "unknown")
    all_rate_limited = True   # assume rate limited until proven otherwise

    for key_index, api_key in enumerate(keys, 1):
        try:
            logger.info(
                f"{log_prefix} Trying model={get_model_label(model_name)} "
                f"key={key_index}/{len(keys)}"
            )
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=timeout
            )

            if response.status_code == 429:
                logger.warning(
                    f"{log_prefix} Key {key_index} rate limited (429) "
                    f"for model {get_model_label(model_name)}."
                )
                # Continue to next key — all_rate_limited stays True
                continue

            if response.status_code != 200:
                logger.warning(
                    f"{log_prefix} Key {key_index} returned HTTP "
                    f"{response.status_code} for model {model_name}."
                )
                all_rate_limited = False   # This is NOT a rate limit
                continue

            # Success
            content = response.json()["choices"][0]["message"]["content"]
            logger.info(
                f"{log_prefix} Success with key {key_index}, "
                f"model={get_model_label(model_name)}"
            )
            return content, "success"

        except Exception as e:
            logger.warning(
                f"{log_prefix} Key {key_index} exception for model "
                f"{model_name}: {e}"
            )
            all_rate_limited = False   # Exception is not a rate limit

    # All keys exhausted
    if all_rate_limited:
        logger.warning(
            f"{log_prefix} All {len(keys)} keys rate limited for "
            f"model {get_model_label(model_name)}. Model exhausted."
        )
        return None, "rate_limited"
    else:
        logger.error(
            f"{log_prefix} All {len(keys)} keys failed (non-rate-limit errors) "
            f"for model {model_name}."
        )
        return None, "failed"
