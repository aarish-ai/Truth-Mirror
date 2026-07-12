import os
import json
import logging
import asyncio
import aiohttp
import re
import urllib.request
import urllib.error
import random
import threading
from dataclasses import dataclass
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
_openrouter_semaphore = threading.Semaphore(1)

from truth_mirror.source_registry import get_source_metadata
from truth_mirror.models import EvidenceItem

logger = logging.getLogger(__name__)

# Idea A: gemini-2.0-flash has 1500 RPD free (vs 20 RPD for 3.5-flash).
# Use it ONLY for bulk repetitive source-labelling. gemini-3.5-flash is reserved for synthesis.
BULK_ANALYSIS_MODEL = "gemini-2.0-flash"

# Idea B: mini-batch size - 3 sources per Groq/Gemini call
MINI_BATCH_SIZE = 3

_STOPWORDS = {
    "the", "a", "an", "in", "on", "at", "to", "of", "and", "or", "is",
    "was", "are", "were", "be", "been", "being", "it", "its", "this",
    "that", "for", "with", "from", "by", "as", "not", "but", "also",
}


@dataclass
class SourceAnalysis:
    url: str
    title: str
    source_name: str
    source_category: str
    source_country: str
    alignment: str
    reliability_tier: int
    snippet: str
    summary: str
    stance: str
    stance_confidence: float
    stance_reasoning: str
    key_claims: list
    what_emphasized: str
    what_omitted: str
    hidden_implication: str


# Idea C - keyword pre-filter
def _extract_claim_keywords(claim: str) -> set:
    tokens = re.findall(r"[a-zA-Z]+", claim.lower())
    return {t for t in tokens if len(t) > 3 and t not in _STOPWORDS}


def _is_relevant(article, claim_keywords: set) -> bool:
    if not claim_keywords:
        return True
    title = (article.source_title or "").lower()
    snippet = (article.excerpt or "").lower()
    text = title + " " + snippet
    article_tokens = set(re.findall(r"[a-zA-Z]+", text))
    return bool(claim_keywords & article_tokens)


def _call_gemini_sync(prompt: str, model: str, timeout: int = 45) -> Optional[str]:
    from truth_mirror.key_rotator import get_current_key, rotate_gemini_key
    import time

    max_attempts = 5
    for attempt in range(max_attempts):
        api_key = get_current_key()
        if not api_key:
            logger.error("[SourceAnalyzer] No Gemini API key available.")
            return None

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        }
        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=req_data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                return raw["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 403):
                wait = (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(
                    f"[SourceAnalyzer] Gemini {model} HTTP {e.code} on attempt "
                    f"{attempt + 1}. Rotating key, waiting {wait:.1f}s."
                )
                rotate_gemini_key()
                time.sleep(wait)
                continue
            else:
                logger.warning(f"[SourceAnalyzer] Gemini HTTP {e.code}: {e.reason}")
                return None
        except Exception as e:
            logger.warning(f"[SourceAnalyzer] Gemini call exception: {e}")
            return None

    logger.error(f"[SourceAnalyzer] Exhausted all {max_attempts} Gemini attempts for {model}.")
    return None


def _call_openrouter_sync(prompt: str, timeout: int = 30) -> Optional[str]:
    if not OPENROUTER_API_KEY:
        return None
    import time

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://truthmirror.app",
        "X-Title": "Truth Mirror",
    }
    payload = {
        "model": "qwen/qwen3-next-80b-a3b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=req_data,
                headers=headers,
            )
            with _openrouter_semaphore:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    choices = data.get("choices") or []
                    if choices and choices[0].get("message", {}).get("content"):
                        return choices[0]["message"]["content"]
                    return None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 15 * (attempt + 1)
                logger.warning(
                    f"[SourceAnalyzer] OpenRouter 429 on attempt {attempt + 1}. "
                    f"Waiting {wait:.1f}s."
                )
                time.sleep(wait)
                continue
            else:
                logger.warning(f"[SourceAnalyzer] OpenRouter HTTP {e.code}: {e.reason}")
                return None
        except Exception as e:
            logger.warning(f"[SourceAnalyzer] OpenRouter exception: {e}")
            return None
    return None


def _build_single_prompt(article, claim: str) -> str:
    url = article.url_or_id or ""
    title = article.source_title or ""
    snippet = (article.excerpt or "")[:800]
    publisher_hint = getattr(article, 'publisher', '') if hasattr(article, 'publisher') else ''
    meta = get_source_metadata(url, publisher=publisher_hint)
    return f"""You are an intelligence analyst. Analyze the following news article in relation to the given claim.

CLAIM: {claim}

SOURCE: {meta['name']} ({meta['country']}, {meta['alignment']})
ARTICLE TITLE: {title}
ARTICLE TEXT:
{snippet}

Respond ONLY in this exact JSON format, no other text:
{{
  "summary": "One or two sentence summary of what this source says about the claim.",
  "stance": "SUPPORTS | CONTRADICTS | PARTIALLY_SUPPORTS | INCONCLUSIVE | BACKGROUND_ONLY",
  "stance_confidence": 0.0,
  "stance_reasoning": "One sentence explaining the stance.",
  "key_claims": ["claim 1", "claim 2", "claim 3"],
  "what_emphasized": "What this source highlights or frames prominently.",
  "what_omitted": "What relevant information this source does not mention.",
  "hidden_implication": "Any subtext, framing bias, or implied narrative. Empty string if none."
}}

Rules:
- SUPPORTS: source directly confirms the claim is true
- CONTRADICTS: source directly denies or disproves the claim
- PARTIALLY_SUPPORTS: source confirms some but not all aspects of the claim
- INCONCLUSIVE: source is related but neither confirms nor denies
- BACKGROUND_ONLY: source provides only historical context, not current verification
"""


def _build_mini_batch_prompt(claim: str, batch: list) -> str:
    articles_text = ""
    for i, article in enumerate(batch, 1):
        url = article.url_or_id or ""
        title = article.source_title or ""
        excerpt = (article.excerpt or "")[:600]
        try:
            publisher_hint = getattr(article, 'publisher', '') if hasattr(article, 'publisher') else ''
            meta = get_source_metadata(url, publisher=publisher_hint)
            source_name = meta.get("name", article.publisher or "Unknown")
            country = meta.get("country", "Unknown")
            alignment = meta.get("alignment", "unknown")
        except Exception:
            source_name = article.publisher or "Unknown"
            country = "Unknown"
            alignment = "unknown"
        articles_text += (
            f"\n--- ARTICLE {i} ---\n"
            f"URL: {url}\n"
            f"Source: {source_name} | Country: {country} | Alignment: {alignment}\n"
            f"Title: {title}\n"
            f"Text: {excerpt}\n"
        )

    return f"""You are an intelligence analyst performing multi-source geopolitical analysis.
You will be given {len(batch)} news articles and a claim to verify.
For EACH article, produce a structured analysis.

CLAIM BEING VERIFIED: "{claim}"

ARTICLES:
{articles_text}

For each article, produce one JSON object. Return ONLY a JSON object:
{{
  "analyses": [
    {{
      "article_index": <1-based integer>,
      "url": "<URL from header>",
      "source_name": "<source name>",
      "alignment": "<alignment>",
      "summary": "<1-2 sentence summary>",
      "stance": "<SUPPORTS|CONTRADICTS|PARTIALLY_SUPPORTS|INCONCLUSIVE|BACKGROUND_ONLY>",
      "stance_confidence": <0.0 to 1.0>,
      "stance_reasoning": "<one sentence>",
      "key_claims": ["<claim>"],
      "what_emphasized": "<what this source highlights>",
      "what_omitted": "<what relevant info is missing>",
      "hidden_implication": "<subtext or empty string>"
    }}
  ]
}}

Analyze EVERY article. Return exactly {len(batch)} objects. Set stance to INCONCLUSIVE for irrelevant articles."""


def _parse_batch_response(raw_text: str, batch: list) -> list:
    results = []
    try:
        parsed = json.loads(raw_text)
        analyses_raw = parsed.get("analyses", [])
        if not isinstance(analyses_raw, list):
            return results
        for raw_item in analyses_raw:
            if not isinstance(raw_item, dict):
                continue
            try:
                idx = int(raw_item.get("article_index", 0)) - 1
                original = batch[idx] if 0 <= idx < len(batch) else None
                if original is not None:
                    url = original.url_or_id or raw_item.get("url", "")
                    title = original.source_title or raw_item.get("source_name", "")
                    excerpt = (original.excerpt or "")[:500]
                    src_type = original.source_type or "journalism"
                else:
                    url = raw_item.get("url", "")
                    title = raw_item.get("source_name", "")
                    excerpt = ""
                    src_type = "journalism"
                results.append(SourceAnalysis(
                    url=url, title=title,
                    source_name=raw_item.get("source_name", ""),
                    source_category=src_type, source_country="",
                    alignment=raw_item.get("alignment", "unknown"),
                    reliability_tier=2, snippet=excerpt,
                    summary=raw_item.get("summary", ""),
                    stance=raw_item.get("stance", "INCONCLUSIVE"),
                    stance_confidence=float(raw_item.get("stance_confidence", 0.5)),
                    stance_reasoning=raw_item.get("stance_reasoning", ""),
                    key_claims=raw_item.get("key_claims", []),
                    what_emphasized=raw_item.get("what_emphasized", ""),
                    what_omitted=raw_item.get("what_omitted", ""),
                    hidden_implication=raw_item.get("hidden_implication", ""),
                ))
            except Exception as e:
                logger.warning(f"[SourceAnalyzer] Failed to parse one batch item: {e}")
    except Exception as e:
        logger.warning(f"[SourceAnalyzer] Batch JSON parse failed: {e}")
    return results


def _parse_single_response(raw_text: str, article) -> Optional[SourceAnalysis]:
    try:
        parsed = json.loads(raw_text)
        url = article.url_or_id or ""
        title = article.source_title or ""
        snippet = (article.excerpt or "")[:500]
        publisher_hint = getattr(article, 'publisher', '') if hasattr(article, 'publisher') else ''
        meta = get_source_metadata(url, publisher=publisher_hint)
        return SourceAnalysis(
            url=url, title=title,
            source_name=meta.get("name", article.publisher or ""),
            source_category=article.source_type or "journalism",
            source_country=meta.get("country", ""),
            alignment=meta.get("alignment", "unknown"),
            reliability_tier=meta.get("tier", 2),
            snippet=snippet,
            summary=parsed.get("summary", ""),
            stance=parsed.get("stance", "INCONCLUSIVE"),
            stance_confidence=float(parsed.get("stance_confidence", 0.5)),
            stance_reasoning=parsed.get("stance_reasoning", ""),
            key_claims=parsed.get("key_claims", []),
            what_emphasized=parsed.get("what_emphasized", ""),
            what_omitted=parsed.get("what_omitted", ""),
            hidden_implication=parsed.get("hidden_implication", ""),
        )
    except Exception as e:
        logger.warning(f"[SourceAnalyzer] Single-article parse failed: {e}")
        return None


class SourceAnalyzer:
    def __init__(self):
        pass

    async def analyze(self, article, claim: str, session: aiohttp.ClientSession) -> Optional[SourceAnalysis]:
        prompt = _build_single_prompt(article, claim)
        raw = await asyncio.to_thread(_call_gemini_sync, prompt, BULK_ANALYSIS_MODEL)
        if raw:
            result = _parse_single_response(raw, article)
            if result:
                logger.info(f"Successfully analyzed source: {article.url_or_id} -> stance={result.stance}")
                return result
        raw = await asyncio.to_thread(_call_openrouter_sync, prompt)
        if raw:
            result = _parse_single_response(raw, article)
            if result:
                return result
        logger.warning(f"[SourceAnalyzer] All retries failed for {article.url_or_id}")
        return None

    def _call_groq_batch(self, claim: str, articles: list, prompt: str) -> list | None:
        import os, json
        import requests as req_lib
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            logger.warning("[SourceAnalyzer] GROQ_API_KEY not set. Cannot use Groq for batch analysis.")
            return None
            
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "max_tokens": 2048
        }
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = req_lib.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            if response.status_code == 429:
                logger.warning("[SourceAnalyzer] Groq 429 rate limit on batch call.")
                return None
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            
            results = _parse_batch_response(content, articles)
            return results if results else None
        except Exception as e:
            logger.warning(f"[SourceAnalyzer] Groq batch call failed: {e}")
            return None

    def _call_gemini_batch(self, claim: str, batch: list, prompt: str) -> list | None:
        raw = _call_gemini_sync(prompt, BULK_ANALYSIS_MODEL, timeout=45)
        if raw:
            results = _parse_batch_response(raw, batch)
            return results if results else None
        return None

    async def analyze_all(self, articles: list, claim: str, max_concurrent: int = 1) -> list:
        if not articles:
            logger.warning("[SourceAnalyzer] No articles to analyze.")
            return []

        claim_keywords = _extract_claim_keywords(claim)
        relevant, dropped = [], []
        for a in articles:
            if _is_relevant(a, claim_keywords):
                relevant.append(a)
            else:
                dropped.append(a)

        logger.info(
            f"[SourceAnalyzer] Pre-filter: {len(relevant)} relevant, "
            f"{len(dropped)} dropped from {len(articles)} total. "
            f"Claim keywords: {claim_keywords}"
        )
        if dropped:
            dropped_titles = [getattr(a, "source_title", "") or "" for a in dropped[:5]]
            logger.info(f"[SourceAnalyzer] Dropped articles (sample): {dropped_titles}")

        if not relevant:
            logger.warning("[SourceAnalyzer] All articles were filtered out.")
            return []

        relevant = relevant[:15]

        batches = [relevant[i: i + MINI_BATCH_SIZE] for i in range(0, len(relevant), MINI_BATCH_SIZE)]
        logger.info(f"[SourceAnalyzer] Processing {len(relevant)} articles in "
            f"{len(batches)} mini-batch(es) of up to {MINI_BATCH_SIZE} (Groq primary, Gemini fallback).")

        all_results = []
        for batch in batches:
            prompt = _build_mini_batch_prompt(claim, batch)
            
            # Step 1 - Try Groq
            result = await asyncio.to_thread(self._call_groq_batch, claim, batch, prompt)
            if result is not None:
                all_results.extend(result)
                logger.info(f"[SourceAnalyzer] Groq batch succeeded. ({len(result)} analyses)")
                await asyncio.sleep(5)
                continue
                
            # Step 2 - Try Gemini fallback
            logger.warning(f"[SourceAnalyzer] Groq batch failed. Trying Gemini as fallback.")
            result = await asyncio.to_thread(self._call_gemini_batch, claim, batch, prompt)
            if result is not None:
                all_results.extend(result)
                logger.info(f"[SourceAnalyzer] Gemini fallback batch succeeded. ({len(result)} analyses)")
                await asyncio.sleep(10)
                continue
                
            # Step 3 - Both failed
            logger.warning(f"[SourceAnalyzer] Both Groq and Gemini failed for batch of {len(batch)} articles. Skipping.")
            await asyncio.sleep(5)
            continue

        logger.info(
            f"[SourceAnalyzer] Completed: {len(all_results)} succeeded out of "
            f"{len(relevant)} relevant sources ({len(dropped)} pre-filtered)."
        )
        return all_results

    # _analyze_all_individual_fallback removed as part of fallback simplification.