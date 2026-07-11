"""Orchestrator for the Geopolitical Intelligence Engine."""

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from typing import List
import logging

logger = logging.getLogger(__name__)

from truth_mirror.geo_classifier import GeoClassifier
from truth_mirror.local_decomposer import LocalDecomposer
from truth_mirror.geo_query_generator import GeoQueryGenerator
from truth_mirror.retrieval_free import FreeSourceRetrieval
from truth_mirror.perspective_tagger import PerspectiveTagger
from truth_mirror.geo_synthesizer import GeoSynthesizer
from truth_mirror.eval_logger import EvalLogger
from truth_mirror.models import GeopoliticalResult, EvidenceItem
from truth_mirror.retrieval import RetrievalConfig

class GeopoliticalPipeline:
    """Pipeline orchestrator for the Geopolitical Intelligence Engine."""

    def __init__(self) -> None:
        self.classifier = GeoClassifier()
        self.decomposer = LocalDecomposer()
        self.query_generator = GeoQueryGenerator()
        
        # Configure the retriever (max_results per connector is also set to 8 by default)
        self.retriever = FreeSourceRetrieval(config=RetrievalConfig(max_results=8), disable_academic=True)
        
        self.perspective_tagger = PerspectiveTagger()
        self.synthesizer = GeoSynthesizer()
        self.eval_logger = EvalLogger()

        try:
            from truth_mirror.retrieval_news import GDELTConnector, GoogleNewsRSSConnector
            if hasattr(self.retriever, '_news_connectors'):
                self.retriever._news_connectors.append(GDELTConnector())
        except ImportError:
            pass

        try:
            from truth_mirror.retrieval_nonwestern import (
                AlJazeeraConnector,
                TASSConnector,
                CGTNConnector
            )
            connectors_to_inject = [AlJazeeraConnector, TASSConnector, CGTNConnector]
            
            # Optionally import DawnConnector if it exists
            try:
                from truth_mirror.retrieval_nonwestern import DawnConnector
                connectors_to_inject.append(DawnConnector)
            except ImportError:
                pass

            if hasattr(self.retriever, '_news_connectors'):
                for connector_cls in connectors_to_inject:
                    try:
                        self.retriever._news_connectors.append(connector_cls())
                    except Exception as e:
                        logger.warning(f"Failed to inject connector {connector_cls.__name__}: {e}")
        except ImportError as e:
            logger.warning(f"Failed to import non-western connectors: {e}")
            
        logger.info(f"[GeopoliticalPipeline] Initialized with {len(self.retriever._news_connectors)} news connectors and {len(self.retriever._acad_connectors)} academic connectors.")

    def _parallel_retrieve(self, queries: List[str], claim_subtype: str) -> List[EvidenceItem]:
        """
        Fetches evidence for all generated queries in parallel.
        Ensures that the retrieval pulls up to 8 items per query.
        """
        all_results = []
        max_results_per_query = 8
        
        # We cap workers at 10 to avoid overloading
        with ThreadPoolExecutor(max_workers=min(len(queries) + 1, 10)) as executor:
            future_to_query = {
                executor.submit(self.retriever.retrieve, q, claim_subtype): q
                for q in queries
            }
            for future in concurrent.futures.as_completed(future_to_query):
                try:
                    results = future.result()
                    # Up to 8 items per query
                    all_results.extend(results[:max_results_per_query])
                except Exception:
                    pass
                    
        return all_results

    def verify(self, claim: str, scope_gate=None) -> GeopoliticalResult:
        import asyncio
        return asyncio.run(self.run_async(claim, scope_gate))

    async def run_async(self, claim: str, scope_gate=None) -> GeopoliticalResult:
        import asyncio
        from datetime import datetime
        from truth_mirror.source_analyzer import SourceAnalyzer
        from truth_mirror.perspective_synthesizer import PerspectiveSynthesizer
        from truth_mirror.hidden_story_extractor import HiddenStoryExtractor
        from truth_mirror.verdict_engine import VerdictEngine
        
        # 1. Classification (now provided by scope gate)
        if scope_gate:
            involved_parties = scope_gate.involved_parties
            claim_subtype = scope_gate.claim_subtype
        else:
            involved_parties = []
            claim_subtype = "unknown"
            
        await asyncio.sleep(2)
        
        # 2. Decomposition
        sub_claims = self.decomposer.decompose(claim)
        
        await asyncio.sleep(2)
        
        # 3. Query Generation
        all_queries = []
        for sub_claim in sub_claims:
            all_queries.extend(self.query_generator.generate(sub_claim, involved_parties, claim_subtype))
            
        current_year = datetime.now().year
        perspective_queries = [
            f"{claim} Western media Reuters AP",
            f"{claim} Russian Chinese media TASS CGTN",
            f"{claim} Middle East Al Jazeera",
            f"{claim} official government statement"
        ]
        all_queries.extend(perspective_queries)
        
        # Parallel Retrieval
        all_evidence = self._parallel_retrieve(all_queries, claim_subtype)
        
        # Deduplicate evidence
        seen = set()
        deduped_evidence = []
        for item in all_evidence:
            key = (item.url_or_id or item.source_title).strip().lower()
            if key not in seen:
                seen.add(key)
                deduped_evidence.append(item)
                
        # Stage 2: Per-source stance analysis
        analyzer = SourceAnalyzer()
        source_analyses = await analyzer.analyze_all(deduped_evidence, claim, max_concurrent=3)
        source_analyses = [s for s in source_analyses if s.summary]
        
        consensus_points, disputed_points = compute_consensus_disputes(source_analyses)
        
        # Give Gemini RPM window time to recover before synthesis calls
        await asyncio.sleep(10)
        logger.info("[GeoOrchestrator] Waiting 10s before synthesis to protect Gemini RPM.")
        
        if not source_analyses:
            return None

        gemini_client = getattr(self.synthesizer, "client", None)
        
        # Stage 3: Perspective synthesis
        synthesizer = PerspectiveSynthesizer()
        perspective_groups = await synthesizer.synthesize(source_analyses, claim, gemini_client)
        await asyncio.sleep(15)
        
        # Stage 4: Hidden story extraction
        extractor = HiddenStoryExtractor()
        hidden_stories = await extractor.extract(source_analyses, perspective_groups, claim, gemini_client)
        await asyncio.sleep(15)
        
        # Stage 5: Verdict generation
        engine = VerdictEngine()
        verdict = await engine.generate(source_analyses, perspective_groups, hidden_stories, claim, gemini_client)
        await asyncio.sleep(15)
        
        # Stage 6: Generate background and current_situation narratives
        background, current_situation = await generate_background_narrative(claim, source_analyses, gemini_client)

        logger.info(f"[GeoOrchestrator] Completed synthesis for: {claim[:50]}...")
        
        result = GeopoliticalResult(
            claim=claim,
            original_claim=claim,
            is_geopolitical=True,
            source_analyses=[s.__dict__ for s in source_analyses],
            total_sources=len(source_analyses),
            perspective_groups=[p.__dict__ for p in perspective_groups],
            consensus_points=consensus_points,
            disputed_points=disputed_points,
            hidden_stories=[h.__dict__ for h in hidden_stories],
            verdict_data=verdict.__dict__,
            background=background,
            current_situation=current_situation,
            verdict=verdict.verdict,
            final_verdict=verdict.verdict,
            confidence=verdict.confidence
        )
        
        # self.eval_logger.log_geo_run(result)
        return result

async def generate_background_narrative(claim: str, source_analyses: list, gemini_client) -> tuple[str, str]:
    prompt = f"Analyze these sources and provide a brief background and current situation for this claim: {claim}\n"
    prompt += "Return JSON: {\"background\": \"...\", \"current_situation\": \"...\"}\n"
    
    import json
    import asyncio
    try:
        from google.genai import types
    except ImportError:
        types = None

    def run_sync():
        import os, json, urllib.request, re, time, random
        data = None
        gemini_client = None
        max_retries = 5
        for attempt in range(max_retries):
            try:
                import time
                if attempt > 0:
                    time.sleep(2)
                    
                from truth_mirror.key_rotator import get_current_key, rotate_gemini_key
                api_key = get_current_key()
                if api_key and types:
                    from google import genai
                    gemini_client = genai.Client(api_key=api_key)
                    
                if gemini_client and types:
                    try:
                        response = gemini_client.models.generate_content(
                            model="gemini-3.5-flash",
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                temperature=0.2,
                            )
                        )
                        raw_json = response.text
                        if raw_json.startswith("```json"):
                            raw_json = raw_json.strip("` \n").removeprefix("json")
                        data = json.loads(raw_json)
                        break
                    except Exception as e:
                        logger.warning(f"Gemini background generation failed on attempt {attempt+1}: {e}")
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                            logger.warning("Rotating Gemini key due to 429 in geo_orchestrator...")
                            rotate_gemini_key()
            except Exception:
                pass
                
        if data is None:
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if api_key and api_key != "your_openrouter_api_key_here":
                req_data = json.dumps({
                    "model": "qwen/qwen3-next-80b-a3b-instruct:free",
                    "messages": [{"role": "user", "content": prompt}]
                }).encode('utf-8')
                req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=req_data, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
                
                for attempt in range(4):
                    try:
                        with urllib.request.urlopen(req, timeout=30) as response:
                            resp_data = json.loads(response.read().decode('utf-8'))
                            raw_json = resp_data["choices"][0]["message"]["content"]
                            match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                            if match:
                                raw_json = match.group(0)
                            data = json.loads(raw_json)
                            break
                    except Exception as e:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"OpenRouter background generation failed on attempt {attempt+1}. Waiting {wait_time:.2f}s before retry. Error: {e}")
                        time.sleep(wait_time)
                        
        if data is None:
            logger.error("All API fallbacks failed for background generation.")
        return data

    try:
        data = await asyncio.to_thread(run_sync)
        if data:
            return data.get("background", ""), data.get("current_situation", "")
    except Exception:
        pass
    return "Background unavailable.", "Current situation unavailable."

def compute_consensus_disputes(source_analyses: list) -> tuple[list[str], list[str]]:
    claims_dict = {}
    for s in source_analyses:
        for claim in s.key_claims:
            claim_lower = claim.lower()
            found = False
            for existing in claims_dict.keys():
                if len(existing) > 10 and (existing in claim_lower or claim_lower in existing):
                    claims_dict[existing].append(s.stance)
                    found = True
                    break
            if not found:
                claims_dict[claim_lower] = [s.stance]
                
    consensus = []
    disputed = []
    
    total_sources = len(source_analyses)
    if total_sources == 0:
        return [], []
        
    for claim, stances in claims_dict.items():
        if len(stances) >= max(3, total_sources * 0.2):
            has_support = any(st in ["SUPPORTS", "PARTIALLY_SUPPORTS"] for st in stances)
            has_contradict = "CONTRADICTS" in stances
            if has_support and has_contradict:
                disputed.append(claim.capitalize())
            elif has_support or has_contradict:
                consensus.append(claim.capitalize())
                
    return consensus, disputed

