import concurrent.futures
from typing import List
from dataclasses import asdict

from truth_mirror.models import EvidenceItem
from truth_mirror.retrieval import RetrievalConfig, EvidenceRetriever

try:
    from truth_mirror.retrieval_acad import SemanticScholarConnector, ArxivConnector, PubMedConnector
except ImportError:
    SemanticScholarConnector = None
    ArxivConnector = None
    PubMedConnector = None

try:
    from truth_mirror.retrieval_news import NewsConnector
except ImportError:
    NewsConnector = None

try:
    from truth_mirror.retrieval_fact import FactCheckConnector
except ImportError:
    FactCheckConnector = None

class FreeSourceRetrieval(EvidenceRetriever):
    """
    Unified orchestrator for retrieving evidence from free academic, news, and fact-checking sources.
    """
    def __init__(self, cache_path: str = ".tm_cache.json", config: RetrievalConfig | None = None):
        super().__init__(cache_path=cache_path, config=config)
        self.connectors = []
        
        if SemanticScholarConnector: self.connectors.append(SemanticScholarConnector(self.config))
        if ArxivConnector: self.connectors.append(ArxivConnector(self.config))
        if PubMedConnector: self.connectors.append(PubMedConnector(self.config))
        if NewsConnector: self.connectors.append(NewsConnector(self.config))
        if FactCheckConnector: self.connectors.append(FactCheckConnector(self.config))

    def retrieve(self, query: str) -> List[EvidenceItem]:
        key = query.strip().lower()
        if key in self._cache:
            return [self._normalize_cached_item(EvidenceItem(**item)) for item in self._cache[key]]

        # Get base results from parent EvidenceRetriever
        results = (
            self._query_wikipedia(query)
            + self._query_wikinews(query)
            + self._query_crossref(query)
        )
        
        # Get connector results in parallel
        def fetch(connector):
            try:
                return connector.search(query)
            except Exception:
                return []

        if self.connectors:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.connectors)) as executor:
                future_to_connector = {executor.submit(fetch, c): c for c in self.connectors}
                for future in concurrent.futures.as_completed(future_to_connector):
                    results.extend(future.result())

        results = self._dedupe(results)
        self._cache[key] = [asdict(item) for item in results]
        self._save_cache()
        return results
