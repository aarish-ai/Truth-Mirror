import re
import json
import urllib.request
import logging
from dataclasses import dataclass
from truth_mirror.geo_classifier import GEO_KEYWORDS

logger = logging.getLogger(__name__)

@dataclass
class ClaimScopeResult:
    is_geopolitical: bool
    topic_reason: str
    involved_parties: list[str]
    claim_subtype: str
    estimated_timeframe: str
    in_temporal_scope: bool
    temporal_reason: str
    detected_years: list[int]
    is_in_scope: bool
    rejection_reason: str

def extract_years_mentioned(text: str) -> list[int]:
    matches = re.findall(r'\b(19[0-9]{2}|20[0-9]{2}|2100)\b', text)
    years = sorted([int(m) for m in matches])
    return years

def gate_claim(claim: str, ollama_model: str = "qwen2.5:3b") -> ClaimScopeResult:
    years = extract_years_mentioned(claim)
    if years and max(years) < 2015:
        return ClaimScopeResult(
            is_geopolitical=False,
            topic_reason="Unknown (short-circuited due to temporal scope)",
            involved_parties=[],
            claim_subtype="unknown",
            estimated_timeframe=str(max(years)),
            in_temporal_scope=False,
            temporal_reason=f"This claim refers to {max(years)}, which is before this tool's supported range (2015 onward).",
            detected_years=years,
            is_in_scope=False,
            rejection_reason=f"This claim refers to {max(years)}, which is before this tool's supported range (2015 onward)."
        )

    prompt = f"""You are a strict scope-classification gate for a geopolitical news verification tool. This tool ONLY processes:
1. Geopolitical claims: international relations, wars, military action, diplomacy, elections, sanctions, treaties, government actions, state actors, terrorism, geopolitical economics.
2. Events that occurred in the year 2015 or later.

It must REJECT:
- Non-geopolitical claims (science, math, personal life, sports, entertainment, general trivia, academic/medical facts, etc.)
- Geopolitical claims about events strictly before 2015 (e.g. World War 2, the 1979 Iranian Revolution, 9/11, the Cold War)

Claim: "{claim}"

Respond ONLY with this JSON, no other text:
{{
  "is_geopolitical": true,
  "topic_reason": "short reason",
  "involved_parties": ["country or org names mentioned, empty list if none"],
  "claim_subtype": "military | diplomatic | economic | domestic_politics | non_political",
  "estimated_timeframe": "best guess at time period, e.g. '2026', 'ongoing/current', '2015-2018', 'unspecified, likely current'",
  "estimated_year_low": null,
  "estimated_year_high": null,
  "in_temporal_scope": true,
  "temporal_reason": "short reason"
}}

Rules:
- If no explicit date is mentioned and the claim uses present tense or refers to ongoing/current matters, assume it is about CURRENT events and set in_temporal_scope to true.
- Only set in_temporal_scope to false if the claim is clearly and specifically about a historical period before 2015.
"""

    parsed = None
    import os
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    req_url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": ollama_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0}
    }

    try:
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(req_url, data=req_data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as response:
            resp_data = json.loads(response.read().decode("utf-8"))
            parsed = json.loads(resp_data.get("response", ""))
    except Exception as e:
        logger.warning(f"gate_claim LLM call failed: {e}")

    if parsed:
        is_geopol = bool(parsed.get("is_geopolitical", False))
        topic_reason = parsed.get("topic_reason", "")
        parties = parsed.get("involved_parties", [])
        subtype = parsed.get("claim_subtype", "unknown")
        est_time = parsed.get("estimated_timeframe", "")
        in_temp = bool(parsed.get("in_temporal_scope", True))
        temp_reason = parsed.get("temporal_reason", "")
    else:
        # Fallback
        is_geopol = bool(re.search(GEO_KEYWORDS, claim.lower()))
        topic_reason = "Fallback regex match." if is_geopol else "Failed fallback regex match."
        parties = []
        subtype = "unknown"
        est_time = "unknown"
        if not years or (years and max(years) >= 2015):
            in_temp = True
            temp_reason = "Fallback assumption: current or >= 2015."
        else:
            in_temp = False
            temp_reason = f"Fallback year detection found {max(years)}."

    # Defense in depth
    if years and max(years) < 2015:
        in_temp = False
        temp_reason = f"Explicit year {max(years)} detected, overriding LLM."

    is_in_scope = is_geopol and in_temp

    rej_reasons = []
    if not is_in_scope:
        if not is_geopol:
            rej_reasons.append(f"{topic_reason}")
        if not in_temp:
            rej_reasons.append(f"{temp_reason}")

    rejection_reason = "; ".join(rej_reasons) if rej_reasons else ""
    if not is_in_scope and rejection_reason:
        rejection_reason = f"This claim was not processed because: {rejection_reason}"

    return ClaimScopeResult(
        is_geopolitical=is_geopol,
        topic_reason=topic_reason,
        involved_parties=parties,
        claim_subtype=subtype,
        estimated_timeframe=est_time,
        in_temporal_scope=in_temp,
        temporal_reason=temp_reason,
        detected_years=years,
        is_in_scope=is_in_scope,
        rejection_reason=rejection_reason
    )
