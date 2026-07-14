import re
import json
import urllib.request
import logging
from dataclasses import dataclass
from truth_mirror.geo_classifier import GEO_KEYWORDS
from truth_mirror.groq_router import GROQ_SIMPLE_MODEL, get_model_label

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
2. Events that occurred in the year 2015 or later. The current year is 2026. Claims about events in 2025 and 2026 are CURRENT/RECENT events, not future events.

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

    import os
    from dotenv import load_dotenv
    import time
    
    load_dotenv()
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    def _call_groq(prompt_str: str) -> dict | None:
        import requests
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            return None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": GROQ_SIMPLE_MODEL,
                        "messages": [{"role": "user", "content": prompt_str}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                        "max_tokens": 512
                    },
                    timeout=25
                )
                if response.status_code == 429:
                    wait = (2 ** attempt) + 1
                    logger.warning(
                        f"[ClaimScopeGate] Groq rate limited attempt "
                        f"{attempt+1}. Waiting {wait}s."
                    )
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                parsed_json = json.loads(content)
                logger.info("[ClaimScopeGate] Groq call succeeded.")
                return parsed_json
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.warning(f"[ClaimScopeGate] Groq failed: {e}")
                    return None
                continue
        return None

    parsed = None
    logger.info(f"[ClaimScopeGate] Attempting Groq ({get_model_label(GROQ_SIMPLE_MODEL)}) for scope classification.")
    parsed = _call_groq(prompt)

    from truth_mirror.key_rotator import get_current_key, rotate_gemini_key
    api_key = get_current_key()
    if parsed is None and api_key:
        try:
            gemini_payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json"
                }
            }
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    api_key = get_current_key()
                    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
                    req_data = json.dumps(gemini_payload).encode("utf-8")
                    req = urllib.request.Request(gemini_url, data=req_data, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=20) as response:
                        resp_data = json.loads(response.read().decode("utf-8"))
                        content = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                        parsed = json.loads(content)
                        break
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        wait_time = (2 ** attempt) + 1
                        logger.warning(f"[ClaimScopeGate] Gemini Rate limited on attempt {attempt+1}. Rotating key and waiting {wait_time}s.")
                        rotate_gemini_key()
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.warning(f"Gemini HTTP Error ({e.code}) in gate_claim.")
                        break
                except Exception as e:
                    logger.warning(f"Gemini failed ({e}) in gate_claim.")
                    break
        except Exception as e:
            logger.warning(f"Gemini setup failed: {e}")

    if parsed is None and OPENROUTER_API_KEY:
        openrouter_payload = {
            "model": "qwen/qwen3-next-80b-a3b-instruct:free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://truthmirror.app",
            "X-Title": "Truth Mirror"
        }
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                req_data = json.dumps(openrouter_payload).encode("utf-8")
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions", 
                    data=req_data, 
                    headers=headers
                )
                with urllib.request.urlopen(req, timeout=30) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    content = resp_data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait_time = (2 ** attempt) + 1
                    logger.warning(f"[ClaimScopeGate] OpenRouter Rate limited on attempt {attempt+1}. Waiting {wait_time}s.")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.warning(f"OpenRouter HTTP Error ({e.code}) in fallback.")
                    break
            except Exception as e:
                logger.warning(f"OpenRouter fallback failed ({e}).")
                break
    else:
        logger.warning("OPENROUTER_API_KEY not set for fallback.")

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
