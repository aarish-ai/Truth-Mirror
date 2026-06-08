"""Orchestrator for the Geopolitical Intelligence Engine."""

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from typing import List

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
        self.retriever = FreeSourceRetrieval(config=RetrievalConfig(max_results=8))
        
        self.perspective_tagger = PerspectiveTagger()
        self.synthesizer = GeoSynthesizer()
        self.eval_logger = EvalLogger()

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

    def verify(self, claim: str) -> GeopoliticalResult:
        """
        Executes the geopolitical pipeline and returns a GeopoliticalResult.
        """
        # 1. Classification
        class_res = self.classifier.classify(claim)
        if not class_res.get("is_geopolitical", False):
            result = GeopoliticalResult(
                original_claim=claim,
                is_geopolitical=False,
                rejection_reason=class_res.get("reason", "Not classified as geopolitical.")
            )
            self.eval_logger.log_geo_run(result)
            return result
            
        involved_parties = class_res.get("involved_parties", [])
        claim_subtype = class_res.get("claim_subtype", "unknown")
        
        # 2. Decomposition
        sub_claims = self.decomposer.decompose(claim)
        
        # 3. Query Generation & Retrieval
        all_evidence = []
        for sub_claim in sub_claims:
            queries = self.query_generator.generate(sub_claim, involved_parties, claim_subtype)
            evidence = self._parallel_retrieve(queries, claim_subtype)
            all_evidence.extend(evidence)
            
        # Deduplicate evidence based on URL or title
        seen = set()
        deduped_evidence = []
        for item in all_evidence:
            key = (item.url_or_id or item.source_title).strip().lower()
            if key not in seen:
                seen.add(key)
                deduped_evidence.append(item)
        all_evidence = deduped_evidence
        
        # 4. Perspective Tagging
        self.perspective_tagger.tag(all_evidence, involved_parties)
        
        # Group by perspective
        by_perspective = {}
        for item in all_evidence:
            by_perspective.setdefault(item.perspective_label, []).append(item)
            
        # Format for synthesizer
        lines = []
        for perspective, items in by_perspective.items():
            lines.append(f"[{perspective.upper()}]")
            for idx, item in enumerate(items, 1):
                lines.append(f"  {idx}. {item.source_title} ({item.publisher}) - {item.url_or_id}")
                if item.excerpt:
                    excerpt_trunc = item.excerpt[:300] + ("..." if len(item.excerpt) > 300 else "")
                    lines.append(f"     Excerpt: {excerpt_trunc}")
        
        evidence_by_perspective_str = "\n".join(lines) if lines else "No evidence retrieved."
        
        # 5. Synthesis
        parties_str = ", ".join(involved_parties) if involved_parties else "Unknown"
        result = self.synthesizer.synthesize(
            claim=claim,
            claim_subtype=claim_subtype,
            involved_parties=parties_str,
            evidence_by_perspective=evidence_by_perspective_str,
            evidence_count=len(all_evidence),
            sub_claims=sub_claims
        )
        
        # 6. Logging
        self.eval_logger.log_geo_run(result)
        
        return result
