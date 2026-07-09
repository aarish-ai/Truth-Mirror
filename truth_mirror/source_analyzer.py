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
    def __init__(self, ollama_model: str = "qwen2.5:3b", ollama_base_url: str = None):
        self.model = ollama_model
        self.ollama_base_url = ollama_base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

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
            openrouter_failed = False
            
            if OPENROUTER_API_KEY:
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://truthmirror.app",
                    "X-Title": "Truth Mirror"
                }
                openrouter_payload = {
                    "model": "nvidia/nemotron-3-nano-30b-a3b:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }
                
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        timeout_cfg = aiohttp.ClientTimeout(total=20)
                        async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=openrouter_payload, timeout=timeout_cfg) as response:
                            if response.status == 429:
                                wait_time = (2 ** attempt) + 1
                                jitter = random.uniform(0.1, 1.0)
                                logger.warning(f"[SourceAnalyzer] Rate limited on attempt {attempt+1}. Waiting {wait_time + jitter:.2f}s before retry.")
                                await asyncio.sleep(wait_time + jitter)
                                if attempt == max_retries - 1:
                                    openrouter_failed = True
                                continue
                            response.raise_for_status()
                            data = await response.json()
                            content = data["choices"][0]["message"]["content"]
                            parsed = json.loads(content)
                            openrouter_failed = False
                            break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            logger.warning(f"OpenRouter failed for {url} ({e}), falling back to local Ollama.")
                            openrouter_failed = True
                            break
                        else:
                            await asyncio.sleep(1)
            else:
                logger.warning("OPENROUTER_API_KEY not set. Using local Ollama.")
                openrouter_failed = True
                
            if openrouter_failed:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 300
                    }
                }
                req_url = f"{self.ollama_base_url.rstrip('/')}/api/generate"
                timeout_cfg = aiohttp.ClientTimeout(total=300)
                async with session.post(req_url, json=payload, timeout=timeout_cfg) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    
                response_text = data.get("response", "").strip()
                try:
                    parsed = json.loads(response_text)
                except Exception:
                    start = response_text.find('{')
                    end = response_text.rfind('}')
                    if start != -1 and end != -1:
                        parsed = json.loads(response_text[start:end+1])
                    else:
                        raise ValueError("Could not parse JSON")
                    
            
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

    async def analyze_all(self, articles: List[EvidenceItem], claim: str, max_concurrent: int = 5) -> List[SourceAnalysis]:
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
