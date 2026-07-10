import os
import json
import logging
import asyncio
import aiohttp
import re
import urllib.request
import urllib.error
import random
from dataclasses import dataclass
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

from truth_mirror.source_registry import get_source_metadata
from truth_mirror.models import EvidenceItem

logger = logging.getLogger(__name__)

# Idea A: gemini-2.0-flash has 1500 RPD free (vs 20 RPD for 3.5-flash).
# Use it ONLY for bulk repetitive source-labelling. gemini-3.5-flash is reserved for synthesis.
BULK_ANALYSIS_MODEL = "gemini-2.0-flash"

# Idea B: mini-batch size - 6 sources per Gemini call instead of 1 or 36
MINI_BATCH_SIZE = 6

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
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices") or []
                if choices and choices[0].get("message", {}).get("content"):
                    return choices[0]["message"]["content"]
                return None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = (2 ** attempt) + random.uniform(0.5, 1.5)
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
    meta = get_source_metadata(url)
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
            meta = get_source_metadata(url)
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
        meta = get_source_metadata(url)
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

    def _process_mini_batch(self, batch: list, claim: str) -> list:
        prompt = _build_mini_batch_prompt(claim, batch)
        raw = _call_gemini_sync(prompt, BULK_ANALYSIS_MODEL, timeout=45)
        if raw:
            results = _parse_batch_response(raw, batch)
            if results:
                logger.info(f"[SourceAnalyzer] Mini-batch of {len(batch)} -> {len(results)} results (gemini-2.0-flash).")
                return results

        raw = _call_openrouter_sync(prompt, timeout=40)
        if raw:
            results = _parse_batch_response(raw, batch)
            if results:
                logger.info(f"[SourceAnalyzer] Mini-batch of {len(batch)} -> {len(results)} results (OpenRouter).")
                return results

        logger.warning(f"[SourceAnalyzer] Mini-batch failed. Falling back to per-article calls for {len(batch)} articles.")
        individual_results = []
        for article in batch:
            single_prompt = _build_single_prompt(article, claim)
            raw = _call_gemini_sync(single_prompt, BULK_ANALYSIS_MODEL, timeout=20)
            if not raw:
                raw = _call_openrouter_sync(single_prompt, timeout=25)
            if raw:
                result = _parse_single_response(raw, article)
                if result:
                    individual_results.append(result)
        return individual_results

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

        batches = [relevant[i: i + MINI_BATCH_SIZE] for i in range(0, len(relevant), MINI_BATCH_SIZE)]
        logger.info(
            f"[SourceAnalyzer] Processing {len(relevant)} articles in "
            f"{len(batches)} mini-batch(es) of up to {MINI_BATCH_SIZE} using {BULK_ANALYSIS_MODEL}."
        )

        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_batch_async(batch):
            async with semaphore:
                return await asyncio.to_thread(self._process_mini_batch, batch, claim)

        tasks = [process_batch_async(b) for b in batches]
        batch_results = await asyncio.gather(*tasks)

        all_results = []
        for r in batch_results:
            all_results.extend(r)

        logger.info(
            f"[SourceAnalyzer] Completed: {len(all_results)} succeeded out of "
            f"{len(relevant)} relevant sources ({len(dropped)} pre-filtered)."
        )
        return all_results

    async def _analyze_all_individual_fallback(self, articles: list, claim: str, max_concurrent: int = 5) -> list:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def sem_analyze(article, session):
            async with semaphore:
                return await self.analyze(article, claim, session)

        async with aiohttp.ClientSession() as session:
            tasks = [sem_analyze(art, session) for art in articles]
            raw_results = await asyncio.gather(*tasks)

        results = [r for r in raw_results if r is not None]
        logger.info(
            f"[SourceAnalyzer] Completed: {len(results)} succeeded, "
            f"{len(raw_results) - len(results)} failed out of {len(raw_results)} total sources."
        )
        return results