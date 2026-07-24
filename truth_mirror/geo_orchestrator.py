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
from truth_mirror.caching import EvidenceCache
from dataclasses import asdict
from truth_mirror.rate_limiter import rate_limiter

def _dict_to_geo_result(d: dict) -> "GeopoliticalResult":
    """Reconstruct a GeopoliticalResult from a cached dictionary."""
    from truth_mirror.models import GeopoliticalResult
    d.pop("_from_cache", None)
    try:
        return GeopoliticalResult(**{
            k: v for k, v in d.items()
            if k in GeopoliticalResult.__dataclass_fields__
        })
    except Exception as e:
        logger.warning(f"Cache reconstruction failed: {e}. Returning raw dict.")
        # Fallback: create minimal GeopoliticalResult
        return GeopoliticalResult(
            original_claim=d.get("original_claim", ""),
            is_geopolitical=d.get("is_geopolitical", True),
            verdict=d.get("verdict", "Unclear"),
            **{k: d[k] for k in [
                "source_analyses", "perspective_groups", "hidden_stories",
                "verdict_data", "total_sources", "confidence"
            ] if k in d}
        )

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

        self._result_cache = EvidenceCache()
        # Cleanup expired entries on startup (non-blocking, cheap)
        try:
            deleted = self._result_cache.cleanup_expired_results()
            if deleted > 0:
                logger.info(f"[GeoOrchestrator] Cleaned up {deleted} expired result cache entries.")
        except Exception as e:
            logger.warning(f"[GeoOrchestrator] Cache cleanup failed: {e}")

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
            future_to_query = {}
            for idx, q in enumerate(queries):
                use_wikinews = (idx < 2)
                future = executor.submit(
                    self.retriever.retrieve, q, claim_subtype, use_wikinews
                )
                future_to_query[future] = q

            for future in concurrent.futures.as_completed(future_to_query):
                try:
                    results = future.result()
                    # Up to 8 items per query
                    all_results.extend(results[:max_results_per_query])
                except Exception:
                    pass
                    
        return all_results

    def verify(self, claim: str, scope_gate=None, request_id: str = '__global__') -> GeopoliticalResult:
        import asyncio
        return asyncio.run(self.run_async(claim, scope_gate, request_id=request_id))

    async def run_async(self, claim: str, scope_gate=None, request_id: str = '__global__') -> GeopoliticalResult:
        import asyncio
        from datetime import datetime
        from truth_mirror.source_analyzer import SourceAnalyzer
        from truth_mirror.perspective_synthesizer import PerspectiveSynthesizer
        from truth_mirror.hidden_story_extractor import HiddenStoryExtractor
        from truth_mirror.verdict_engine import VerdictEngine
        from truth_mirror.pipeline_status import set_stage
        from truth_mirror.temporal_classifier import TemporalClassifier
        from truth_mirror.run_tracker import tracker
        from truth_mirror.testing_logger import TestingLogger
        import time

        tracker.set_current(request_id)
        try:
            tracker.reset(claim)
            start_time = time.time()

            # ── CACHE LOOKUP ──────────────────────────────────────────────────────
            cache_key = EvidenceCache.normalize_claim_key(claim)
            cached_result = self._result_cache.get_result(cache_key)
            if cached_result:
                logger.info(f"[GeoOrchestrator] Cache HIT for claim: '{claim[:60]}...'")
                # Reconstruct GeopoliticalResult from cached dict
                # Return it as a dict directly — to_json() already handles dict
                cached_result["_from_cache"] = True
                res = _dict_to_geo_result(cached_result)
                tracker.record("cache", "cache", "local", "success")
                events = tracker.get_stage_summary()
                test_logger = TestingLogger()
                test_logger.log_run(claim, res, events, time.time() - start_time)
                tracker.reset("")
                return res
            logger.info(f"[GeoOrchestrator] Cache MISS for claim: '{claim[:60]}...'")
            # ── END CACHE LOOKUP ──────────────────────────────────────────────────

            # 1. Classification (now provided by scope gate)
            if scope_gate:
                involved_parties = scope_gate.involved_parties
                claim_subtype = scope_gate.claim_subtype
            else:
                involved_parties = []
            # 2. Decomposition
            set_stage("decomposing", request_id=request_id)
            sub_claims = self.decomposer.decompose(claim)

            # Classify temporal intent of the ORIGINAL claim (not sub-claims)
            # One Groq call here informs ALL query generation for this pipeline run
            set_stage("classifying_temporal", request_id=request_id)
            temporal_classifier = TemporalClassifier()
            temporal_context = temporal_classifier.classify(claim)
            logger.info(
                f"[GeoOrchestrator] Temporal classification: type={temporal_context.temporal_type}, "
                f"needs_date={temporal_context.needs_date}, "
                f"qualifier='{temporal_context.date_qualifier}', "
                f"reasoning='{temporal_context.reasoning}'"
            )

            # 3. Query Generation
            set_stage("querying", request_id=request_id)
            all_queries = []
            for sub_claim in sub_claims:
                if sub_claim.lower().startswith("the period in question") or sub_claim.lower().startswith("the action is currently"):
                    continue
                queries = self.query_generator.generate(
                    sub_claim, 
                    involved_parties, 
                    claim_subtype,
                    temporal_context=temporal_context
                )
                all_queries.extend(queries)

            current_year = datetime.now().year
            if temporal_context.needs_date and temporal_context.date_qualifier:
                dq = temporal_context.date_qualifier
                if dq.lower() in claim.lower():
                    dq_suffix = ""
                else:
                    dq_suffix = f" {dq}"
                perspective_queries = [
                    f"{claim}{dq_suffix} Western media Reuters AP",
                    f"{claim}{dq_suffix} Russian Chinese media TASS CGTN",
                    f"{claim}{dq_suffix} Middle East Al Jazeera",
                    f"{claim}{dq_suffix} official government statement"
                ]
            else:
                perspective_queries = [
                    f"{claim} Western media Reuters AP",
                    f"{claim} Russian Chinese media TASS CGTN",
                    f"{claim} Middle East Al Jazeera",
                    f"{claim} official government statement"
                ]
            all_queries.extend(perspective_queries)

            # Parallel Retrieval
            set_stage("retrieving", request_id=request_id)
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
            set_stage("analyzing_sources", request_id=request_id)
            analyzer = SourceAnalyzer()
            source_analyses = await analyzer.analyze_all(deduped_evidence, claim, max_concurrent=3, temporal_context=temporal_context)
            source_analyses = [s for s in source_analyses if s.summary]

            consensus_points, disputed_points = compute_consensus_disputes(source_analyses)

            # Give Gemini RPM window time to recover before synthesis calls
            await rate_limiter.wait_if_needed("gemini")
            logger.info("[GeoOrchestrator] Waited adaptively before synthesis to protect Gemini RPM.")

            if not source_analyses:
                logger.error(
                    f"[GeoOrchestrator] ALL source analysis batches failed for: "
                    f"'{claim[:60]}'. All Groq models rate-limited or unreachable "
                    f"and Gemini fallback also failed. Returning infrastructure "
                    f"failure result."
                )
                _INFRA_FAILURE_VERDICT = (
                    "All available AI models (Groq 70b, 70b-specdec, Qwen-32b, 8b) "
                    "were simultaneously rate-limited or unreachable during source "
                    "analysis, and the Gemini fallback also failed. This is a "
                    "temporary infrastructure capacity issue, not an analytical "
                    "finding about the claim itself."
                )
                res = GeopoliticalResult(
                    claim=claim,
                    original_claim=claim,
                    is_geopolitical=True,
                    source_analyses=[],
                    total_sources=0,
                    perspective_groups=[],
                    consensus_points=[],
                    disputed_points=[],
                    hidden_stories=[],
                    verdict_data={
                        "verdict": "ANALYSIS_FAILED",
                        "confidence": 0.0,
                        "confidence_label": "N/A",
                        "one_line_verdict": (
                            "Analysis could not be completed — API limits exhausted. "
                            "Please wait a few minutes and try again."
                        ),
                        "full_reasoning": _INFRA_FAILURE_VERDICT,
                        "what_is_true": "N/A — source analysis could not be completed.",
                        "what_is_false": "N/A — source analysis could not be completed.",
                        "what_is_unclear": "N/A — source analysis could not be completed.",
                        "strongest_evidence_for": "N/A",
                        "strongest_evidence_against": "N/A",
                        "source_quality_note": (
                            "No sources were analyzed. Please retry your claim in "
                            "a few minutes when API capacity is restored."
                        ),
                    },
                    background=_INFRA_FAILURE_VERDICT,
                    current_situation="Retry the claim in a few minutes.",
                    verdict="ANALYSIS_FAILED",
                    final_verdict="ANALYSIS_FAILED",
                    confidence=0.0,
                )
                events = tracker.get_stage_summary()
                test_logger = TestingLogger()
                test_logger.log_run(claim, res, events, time.time() - start_time)
                tracker.reset("")
                return res

            gemini_client = getattr(self.synthesizer, "client", None)

            # Stage 3: Perspective synthesis
            set_stage("synthesizing_perspectives", request_id=request_id)
            synthesizer = PerspectiveSynthesizer()
            perspective_groups = await synthesizer.synthesize(source_analyses, claim, gemini_client, temporal_context=temporal_context)
            await rate_limiter.wait_if_needed("gemini")

            # Stage 4: Hidden story extraction
            set_stage("extracting_stories", request_id=request_id)
            extractor = HiddenStoryExtractor()
            hidden_stories = await extractor.extract(source_analyses, perspective_groups, claim, gemini_client, temporal_context=temporal_context)
            await rate_limiter.wait_if_needed("gemini")

            # Stage 5: Verdict generation
            set_stage("generating_verdict", request_id=request_id)
            engine = VerdictEngine()
            verdict = await engine.generate(source_analyses, perspective_groups, hidden_stories, claim, gemini_client, temporal_context=temporal_context)
            await rate_limiter.wait_if_needed("gemini")

            # Stage 6: Generate background and current_situation narratives
            background, current_situation = await self.generate_background_narrative(claim, source_analyses, gemini_client, temporal_context=temporal_context)

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
                confidence=verdict.confidence,
                temporal_type=temporal_context.temporal_type if temporal_context else "",
                temporal_qualifier=temporal_context.date_qualifier if temporal_context else ""
            )

            # ── CACHE STORE ───────────────────────────────────────────────────────
            temporal_type = getattr(temporal_context, "temporal_type", "current_state")
            try:
                if (not result.source_analyses or
                    not result.verdict_data or
                    result.verdict in ["Unclear", "UNVERIFIABLE"]):
                    logger.info("[GeoOrchestrator] Skipping cache for incomplete/unclear result.")
                else:
                    result_dict = asdict(result)
                    self._result_cache.set_result(cache_key, result_dict, temporal_type)
                    logger.info(
                        f"[GeoOrchestrator] Result cached for {temporal_type} claim "
                        f"(TTL based on type)."
                    )
            except Exception as e:
                logger.warning(f"[GeoOrchestrator] Failed to cache result: {e}")
            # ── END CACHE STORE ───────────────────────────────────────────────────

            # self.eval_logger.log_geo_run(result)

            elapsed = time.time() - start_time
            events = tracker.get_stage_summary()
            test_logger = TestingLogger()
            test_logger.log_run(claim, result, events, elapsed)
            tracker.reset("")

            return result
        finally:
            tracker.clear_current()
            tracker.remove(request_id)

    @staticmethod
    async def generate_background_narrative(claim: str, source_analyses: list, gemini_client, temporal_context=None) -> tuple[str, str]:
        claim_with_context = claim
        if temporal_context and hasattr(temporal_context, 'date_qualifier') and temporal_context.date_qualifier:
            claim_with_context = f"{claim} (Timeframe: {temporal_context.date_qualifier})"

        prompt = f"Analyze these sources and provide a brief background and current situation for this claim: {claim_with_context}\n"
        prompt += "Return JSON: {\"background\": \"...\", \"current_situation\": \"...\"}\n"

        import json
        import asyncio
        try:
            from google.genai import types
        except ImportError:
            types = None

        async def run_async_inner():
            import os, json, re, time, random
            import aiohttp
            data = None
            gemini_client = None
            max_retries = 5
            
            def _call_gemini_sync_sdk():
                from truth_mirror.key_rotator import get_current_key, rotate_gemini_key
                api_key = get_current_key()
                if not (api_key and types): return None
                from google import genai
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model="gemini-3.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    )
                )
                return response.text
                
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        await asyncio.sleep(2)
                        
                    raw_json = await asyncio.to_thread(_call_gemini_sync_sdk)
                    if raw_json is not None:
                        if raw_json.startswith("```json"):
                            raw_json = raw_json.strip("` \n").removeprefix("json")
                        data = json.loads(raw_json)
                        if data is not None:
                            from truth_mirror.run_tracker import tracker
                            tracker.record("background_generation", "gemini-3.5-flash", "gemini", "success")
                        break
                except Exception as e:
                    logger.warning(f"Gemini background generation failed on attempt {attempt+1}: {e}")
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        logger.warning("Rotating Gemini key due to 429 in geo_orchestrator...")
                        from truth_mirror.run_tracker import tracker
                        tracker.record("background_generation", "gemini-3.5-flash", "gemini", "rate_limited")
                        from truth_mirror.key_rotator import rotate_gemini_key
                        rotate_gemini_key()
                        
            if data is None:
                api_key = os.environ.get("OPENROUTER_API_KEY")
                if api_key and api_key != "your_openrouter_api_key_here":
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    payload = {
                        "model": "qwen/qwen3-next-80b-a3b-instruct:free",
                        "messages": [{"role": "user", "content": prompt}]
                    }
                    
                    for attempt in range(4):
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.post(
                                    "https://openrouter.ai/api/v1/chat/completions",
                                    headers=headers,
                                    json=payload,
                                    timeout=aiohttp.ClientTimeout(total=30)
                                ) as response:
                                    if response.status != 200:
                                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                                        await asyncio.sleep(wait_time)
                                        continue
                                        
                                    resp_data = await response.json()
                                    raw_json = resp_data["choices"][0]["message"]["content"]
                                    match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                                    if match:
                                        raw_json = match.group(0)
                                    data = json.loads(raw_json)
                                    if data is not None:
                                        from truth_mirror.run_tracker import tracker
                                        tracker.record("background_generation", "qwen/qwen3-next-80b-a3b-instruct:free", "openrouter", "fallback_used")
                                    break
                        except Exception as e:
                            wait_time = (2 ** attempt) + random.uniform(0, 1)
                            logger.warning(f"OpenRouter background generation failed on attempt {attempt+1}. Waiting {wait_time:.2f}s before retry. Error: {e}")
                            await asyncio.sleep(wait_time)
                            
            if data is None:
                from truth_mirror.run_tracker import tracker
                tracker.record("background_generation", "ALL_FAILED", "none", "failed")
                logger.error("All API fallbacks failed for background narrative.")
            return data

        try:
            data = await run_async_inner()
            if data:
                return data.get("background", ""), data.get("current_situation", "")
        except Exception:
            pass
        return "Background unavailable.", "Current situation unavailable."

def _jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two lowercased token sets."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    # Remove very common words for better signal
    stop = {"the", "a", "an", "is", "are", "was", "were", "has", "have", "had",
            "in", "on", "of", "to", "and", "or", "that", "this", "it", "for",
            "with", "by", "from", "as", "at", "be", "been"}
    tokens_a -= stop
    tokens_b -= stop
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def compute_consensus_disputes(
    source_analyses: list,
    similarity_threshold: float = 0.45
) -> tuple[list[str], list[str]]:
    """
    Cluster key claims from source analyses using Jaccard token similarity,
    then determine consensus vs disputed claims based on stance distribution.
    """
    if not source_analyses:
        return [], []

    # Build list of (canonical_claim, [stances])
    # Each new claim is compared against existing clusters
    clusters: list[tuple[str, list[str]]] = []

    for s in source_analyses:
        for claim in s.key_claims:
            claim_lower = claim.lower().strip()
            if not claim_lower:
                continue

            matched = False
            for i, (canonical, stances) in enumerate(clusters):
                # Check substring match first (fast path)
                if len(canonical) > 10 and (canonical in claim_lower or claim_lower in canonical):
                    stances.append(s.stance)
                    matched = True
                    break
                # Then check Jaccard similarity (semantic clustering)
                if _jaccard_similarity(canonical, claim_lower) >= similarity_threshold:
                    stances.append(s.stance)
                    # Keep the longer/more descriptive version as canonical
                    if len(claim_lower) > len(canonical):
                        clusters[i] = (claim_lower, stances)
                    matched = True
                    break

            if not matched:
                clusters.append((claim_lower, [s.stance]))

    consensus = []
    disputed = []
    total_sources = len(source_analyses)

    for claim, stances in clusters:
        if len(stances) >= max(3, total_sources * 0.2):
            has_support = any(st in ["SUPPORTS", "PARTIALLY_SUPPORTS"] for st in stances)
            has_contradict = "CONTRADICTS" in stances
            if has_support and has_contradict:
                disputed.append(claim.capitalize())
            elif has_support or has_contradict:
                consensus.append(claim.capitalize())

    return consensus, disputed

