"""
Centralized Groq model routing configuration.
All Groq model strings are defined here — never hardcoded in other files.
"""

# Simple structured tasks — 8b has more than enough capability
# Uses 8b's separate 500K TPD pool, preserving 70b quota for analysis
GROQ_SIMPLE_MODEL = "llama-3.1-8b-instant"

# Complex analysis tasks — requires understanding of nuance and context
GROQ_ANALYSIS_PRIMARY = "llama-3.3-70b-versatile"

# Fallback 1 for analysis: llama-4-scout is a MoE model that punches
# significantly above its parameter count. 500K TPD makes it a strong
# fallback. Quality loss versus 70b is minimal for stance detection.
GROQ_ANALYSIS_FALLBACK_1 = "meta-llama/llama-4-scout-17b-16e-instruct"

# Fallback 2 for analysis: 8b as absolute last resort.
# Quality will degrade noticeably for source analysis.
# Use only when both 70b and 4-scout are exhausted.
GROQ_ANALYSIS_FALLBACK_2 = "llama-3.1-8b-instant"

# Model metadata for logging
GROQ_MODEL_LABELS = {
    GROQ_SIMPLE_MODEL:        "llama-3.1-8b (simple tasks)",
    GROQ_ANALYSIS_PRIMARY:    "llama-3.3-70b (analysis)",
    GROQ_ANALYSIS_FALLBACK_1: "llama-4-scout-17b (analysis fallback 1)",
    GROQ_ANALYSIS_FALLBACK_2: "llama-3.1-8b (analysis fallback 2 — quality reduced)",
}

def get_model_label(model_id: str) -> str:
    return GROQ_MODEL_LABELS.get(model_id, model_id)
