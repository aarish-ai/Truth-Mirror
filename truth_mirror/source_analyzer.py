import os
import json
import logging
import asyncio
import aiohttp
from dataclasses import dataclass
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv
import random

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

from truth_mirror.source_registry import get_source_metadata
from truth_mirror.models import EvidenceItem

logger = logging.getLogger(__name__)

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
    
    key_claims: list[str]           
    what_emphasized: str            
    what_omitted: str               
    hidden_implication: str         

class SourceAnalyzer:
    def __init__(self):
        pass

    async def analyze(self, article: EvidenceItem, claim: str, session: aiohttp.ClientSession) -> SourceAnalysis:
        url = article.url_or_id or ""
        title = article.source_title or ""
        snippet = article.excerpt or ""
        
        meta = get_source_metadata(url)
        
        # Build prompt
        prompt = f"""You are an intelligence analyst. Analyze the following news article in relation to the given claim.

CLAIM: {claim}

SOURCE: {meta['name']} ({meta['country']}, {meta['alignment']})
ARTICLE TITLE: {title}
ARTICLE TEXT:
{snippet[:800]}

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
- Be specific. Do not say "the source mentions X" — say what X actually is.
"""
        
        try:
            parsed = None
            gemini_failed = False
            
            if GEMINI_API_KEY:
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
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
                        timeout_cfg = aiohttp.ClientTimeout(total=20)
                        async with session.post(gemini_url, json=gemini_payload, timeout=timeout_cfg) as response:
                            if response.status == 429:
                                wait_time = (2 ** attempt) + 1
                                jitter = random.uniform(0.1, 1.0)
                                logger.warning(f"[SourceAnalyzer] Gemini rate limited on attempt {attempt+1}. Waiting {wait_time + jitter:.2f}s before retry.")
                                await asyncio.sleep(wait_time + jitter)
                                if attempt == max_retries - 1:
                                    gemini_failed = True
                                continue
                            response.raise_for_status()
                            data = await response.json()
                            content = data["candidates"][0]["content"]["parts"][0]["text"]
                            parsed = json.loads(content)
                            gemini_failed = False
                            break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            logger.warning(f"Gemini failed for {url} ({e}), falling back to OpenRouter.")
                            gemini_failed = True
                            break
                        else:
                            await asyncio.sleep(1)
            else:
                logger.warning("GEMINI_API_KEY not set. Using OpenRouter.")
                gemini_failed = True
                
            if gemini_failed:
                if not OPENROUTER_API_KEY:
                    logger.error("No API keys available for SourceAnalyzer.")
                    return None
                    
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://truthmirror.app",
                    "X-Title": "Truth Mirror"
                }
                openrouter_payload = {
                    "model": "qwen/qwen3-next-80b-a3b-instruct:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        timeout_cfg = aiohttp.ClientTimeout(total=30)
                        async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=openrouter_payload, timeout=timeout_cfg) as response:
                            if response.status == 429:
                                wait_time = (2 ** attempt) + 1
                                jitter = random.uniform(0.1, 1.0)
                                logger.warning(f"[SourceAnalyzer] OpenRouter rate limited on attempt {attempt+1}. Waiting {wait_time + jitter:.2f}s before retry.")
                                await asyncio.sleep(wait_time + jitter)
                                continue
                            response.raise_for_status()
                            data = await response.json()
                            content = data["choices"][0]["message"]["content"]
                            parsed = json.loads(content)
                            break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            logger.warning(f"OpenRouter failed for {url} ({e}).")
                            raise ValueError(f"All API fallbacks failed: {e}")
                        else:
                            await asyncio.sleep(1)
                    
            
            stance = parsed.get("stance", "INCONCLUSIVE")
            logger.info(f"Successfully analyzed source: {url} -> stance={stance}")
            return SourceAnalysis(
                url=url,
                title=title,
                source_name=meta["name"],
                source_category=meta["category"],
                source_country=meta["country"],
                alignment=meta["alignment"],
                reliability_tier=meta["tier"],
                snippet=snippet,
                summary=parsed.get("summary", ""),
                stance=stance,
                stance_confidence=float(parsed.get("stance_confidence", 0.0)),
                stance_reasoning=parsed.get("stance_reasoning", ""),
                key_claims=parsed.get("key_claims", []),
                what_emphasized=parsed.get("what_emphasized", ""),
                what_omitted=parsed.get("what_omitted", ""),
                hidden_implication=parsed.get("hidden_implication", "")
            )
            
        except Exception as e:
            logger.warning(f"[SourceAnalyzer] All retries failed for {url}: {e}")
            return None

    async def _analyze_all_individual_fallback(self, articles: List[EvidenceItem], claim: str, max_concurrent: int = 5) -> List[SourceAnalysis]:
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
            f"{len(raw_results) - len(results)} failed out of "
            f"{len(raw_results)} total sources."
        )
        return results

    async def analyze_all(self, articles: list, claim: str, max_concurrent: int = 5) -> list:
        if not articles:
            logger.warning("[SourceAnalyzer] No articles to analyze.")
            return []

        logger.info(
            f"[SourceAnalyzer] Starting BATCH Gemini analysis of "
            f"{len(articles)} articles for claim: {claim[:80]}"
        )

        batch_prompt = self._build_batch_prompt(claim, articles)
        import asyncio
        results = await asyncio.to_thread(self._call_gemini_batch, claim, articles, batch_prompt)

        if results is not None:
            logger.info(
                f"[SourceAnalyzer] Batch complete: {len(results)} analyses "
                f"returned from {len(articles)} articles."
            )
            return results

        logger.warning(
            "[SourceAnalyzer] Gemini batch failed. Falling back to "
            "per-source OpenRouter calls."
        )
        return await self._analyze_all_individual_fallback(articles, claim, max_concurrent)

    def _build_batch_prompt(self, claim: str, articles: list) -> str:
        articles_text = ""
        for i, article in enumerate(articles, 1):
            if hasattr(article, 'url_or_id'):
                url = article.url_or_id or ""
                title = article.source_title or ""
                excerpt = (article.excerpt or "")[:800]
                publisher = article.publisher or ""
                source_type = article.source_type or ""
            else:
                url = article.get("url_or_id", article.get("url", ""))
                title = article.get("source_title", article.get("title", ""))
                excerpt = article.get("excerpt", article.get("snippet", ""))[:800]
                publisher = article.get("publisher", "")
                source_type = article.get("source_type", "")

            try:
                from truth_mirror.source_registry import get_source_metadata
                meta = get_source_metadata(url)
                alignment = meta.get("alignment", "unknown")
                country = meta.get("country", "Unknown")
                source_name = meta.get("name", publisher or "Unknown")
            except Exception:
                alignment = "unknown"
                country = "Unknown"
                source_name = publisher or "Unknown"

            articles_text += (
                f"\n--- ARTICLE {i} ---\n"
                f"URL: {url}\n"
                f"Source: {source_name} | Country: {country} | "
                f"Alignment: {alignment}\n"
                f"Title: {title}\n"
                f"Text: {excerpt}\n"
            )

        prompt = f"""You are an intelligence analyst performing multi-source
geopolitical analysis. You will be given {len(articles)} news articles
and a claim to verify. For EACH article, produce a structured analysis.

CLAIM BEING VERIFIED: "{claim}"

ARTICLES:
{articles_text}

For each article, produce one JSON object with these exact fields:
{{
  "article_index": <integer, 1-based, matching the ARTICLE N number above>,
  "url": "<the URL from the article header>",
  "source_name": "<source name from the article header>",
  "alignment": "<alignment from the article header>",
  "summary": "<1-2 sentence summary of what this article says about the claim>",
  "stance": "<exactly one of: SUPPORTS, CONTRADICTS, PARTIALLY_SUPPORTS, INCONCLUSIVE, BACKGROUND_ONLY>",
  "stance_confidence": <float between 0.0 and 1.0>,
  "stance_reasoning": "<one sentence explaining why you assigned this stance>",
  "key_claims": ["<specific factual claim made by this source>", "..."],
  "what_emphasized": "<what facts or framings does this source push prominently>",
  "what_omitted": "<what relevant information does this source notably leave out>",
  "hidden_implication": "<any subtext, bias, or implied narrative; empty string if none>"
}}

Stance definitions:
- SUPPORTS: article directly confirms the claim is true
- CONTRADICTS: article directly denies or disproves the claim
- PARTIALLY_SUPPORTS: article confirms some but not all aspects of the claim
- INCONCLUSIVE: article is related but neither confirms nor denies the claim
- BACKGROUND_ONLY: article provides only historical context, not current verification

Rules:
- Analyze EVERY article. Return exactly {len(articles)} objects in the array.
- Do not skip any article even if the excerpt is short or irrelevant.
  Set stance to INCONCLUSIVE for irrelevant articles.
- Be specific. Reference actual content from the article text, not generic descriptions.
- For what_omitted: think about what a source with this alignment WOULD be
  expected to mention if the claim were true, and note if it is absent.
- For hidden_implication: consider the SOURCE's known alignment and how their
  framing choices reveal narrative bias.

Return ONLY a JSON object with this structure, no other text:
{{
  "analyses": [
    {{ ...article 1 analysis... }},
    {{ ...article 2 analysis... }}
  ]
}}"""
        return prompt

    def _call_gemini_batch(self, claim: str, articles: list, prompt: str) -> list | None:
        try:
            import os
            from dotenv import load_dotenv
            load_dotenv()

            from google import genai
            from google.genai import types

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning(
                    "[SourceAnalyzer] GEMINI_API_KEY not set. "
                    "Cannot run batch analysis."
                )
                return None

            client = genai.Client(api_key=api_key)

            logger.info(
                "[SourceAnalyzer] Sending batch prompt to Gemini 2.5 Flash. "
                f"Prompt length: ~{len(prompt)//4} tokens estimated."
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                )
            )

            raw = response.text
            parsed = json.loads(raw)

            if "analyses" not in parsed:
                logger.warning(
                    "[SourceAnalyzer] Gemini batch response missing "
                    "'analyses' key. Keys found: "
                    f"{list(parsed.keys())}"
                )
                return None

            analyses_raw = parsed["analyses"]
            if not isinstance(analyses_raw, list):
                logger.warning(
                    "[SourceAnalyzer] Gemini batch 'analyses' is not a list."
                )
                return None

            results = []
            for raw_item in analyses_raw:
                if not isinstance(raw_item, dict):
                    continue
                try:
                    idx = int(raw_item.get("article_index", 0)) - 1
                    original = articles[idx] if 0 <= idx < len(articles) else None

                    if original is not None:
                        if hasattr(original, 'url_or_id'):
                            pub = original.publisher or ""
                            src_type = original.source_type or "journalism"
                            excerpt = (original.excerpt or "")[:500]
                            date = getattr(original, 'date', "")
                            url = original.url_or_id or raw_item.get("url", "")
                            title = original.source_title or raw_item.get("source_name", "")
                        else:
                            pub = original.get("publisher", "")
                            src_type = original.get("source_type", "journalism")
                            excerpt = original.get("excerpt", "")[:500]
                            date = original.get("date", "")
                            url = original.get("url_or_id", raw_item.get("url", ""))
                            title = original.get("source_title", raw_item.get("source_name", ""))
                    else:
                        pub = raw_item.get("source_name", "")
                        src_type = "journalism"
                        excerpt = ""
                        date = ""
                        url = raw_item.get("url", "")
                        title = raw_item.get("source_name", "")

                    analysis = SourceAnalysis(
                        url=url,
                        title=title,
                        source_name=raw_item.get("source_name", pub),
                        source_category=src_type,
                        source_country="",
                        alignment=raw_item.get("alignment", "unknown"),
                        reliability_tier=2,
                        snippet=excerpt,
                        summary=raw_item.get("summary", ""),
                        stance=raw_item.get("stance", "INCONCLUSIVE"),
                        stance_confidence=float(raw_item.get("stance_confidence", 0.5)),
                        stance_reasoning=raw_item.get("stance_reasoning", ""),
                        key_claims=raw_item.get("key_claims", []),
                        what_emphasized=raw_item.get("what_emphasized", ""),
                        what_omitted=raw_item.get("what_omitted", ""),
                        hidden_implication=raw_item.get("hidden_implication", ""),
                    )
                    results.append(analysis)
                except Exception as e:
                    logger.warning(f"[SourceAnalyzer] Failed to parse one batch item: {e}")
                    continue

            logger.info(f"[SourceAnalyzer] Batch parsed successfully: {len(results)} SourceAnalysis objects created.")
            return results if results else None

        except json.JSONDecodeError as e:
            logger.warning(f"[SourceAnalyzer] Gemini batch JSON parse failed: {e}.")
            return None
        except Exception as e:
            logger.warning(f"[SourceAnalyzer] Gemini batch call failed entirely: {e}")
            return None
