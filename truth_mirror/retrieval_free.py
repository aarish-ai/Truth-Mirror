import concurrent.futures
from typing import List
from dataclasses import asdict

from truth_mirror.models import EvidenceItem
from truth_mirror.retrieval import RetrievalConfig, EvidenceRetriever
from truth_mirror.routing import NEWS_FIRST_CLAIM_TYPES

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
    Unified orchestrator for retrieving evidence from free academic, news, and
    fact-checking sources.

    For biographical, political, and current-event claims the connector order is
    rearranged so that news/fact-check sources run first and arXiv is skipped
    entirely.  For all other claim types the original order is preserved.
    """

    def __init__(self, cache_path: str = ".tm_cache.json", config: RetrievalConfig | None = None):
        super().__init__(cache_path=cache_path, config=config)

        # Build typed connector pools so we can reorder on demand.
        self._news_connectors: list = []
        self._acad_connectors: list = []

        if NewsConnector:
            self._news_connectors.append(NewsConnector(self.config))
        if FactCheckConnector:
            self._news_connectors.append(FactCheckConnector(self.config))

        if SemanticScholarConnector:
            self._acad_connectors.append(SemanticScholarConnector(self.config))
        # ArxivConnector is intentionally omitted for news-first claim types;
        # for academic claims it is included last.
        if ArxivConnector:
            self._acad_connectors.append(ArxivConnector(self.config))
        if PubMedConnector:
            self._acad_connectors.append(PubMedConnector(self.config))

    def _ordered_connectors(self, claim_type: str) -> list:
        """Return connectors in the correct priority order for *claim_type*."""
        if claim_type in NEWS_FIRST_CLAIM_TYPES:
            # News + fact-check first; skip arXiv (keep SemanticScholar/PubMed
            # only in case they have relevant material).
            acad_no_arxiv = [
                c for c in self._acad_connectors
                if not (ArxivConnector and isinstance(c, ArxivConnector))
            ]
            return self._news_connectors + acad_no_arxiv
        else:
            # Original order: academic first, then news.
            return self._acad_connectors + self._news_connectors

    def retrieve(self, query: str, claim_type: str = "mixed or ambiguous claim") -> List[EvidenceItem]:
        cache_key = f"{claim_type}::{query.strip().lower()}"
        if cache_key in self._cache:
            return [self._normalize_cached_item(EvidenceItem(**item)) for item in self._cache[cache_key]]

        # Base results: Wikipedia and Wikinews are always included.
        # For news-first claim types also skip Crossref (academic bibliography).
        if claim_type in NEWS_FIRST_CLAIM_TYPES:
            results = (
                self._query_wikipedia(query)
                + self._query_wikinews(query)
            )
        else:
            results = (
                self._query_wikipedia(query)
                + self._query_wikinews(query)
                + self._query_crossref(query)
            )

        # Get connector results in priority order, in parallel.
        connectors = self._ordered_connectors(claim_type)

        def fetch(connector):
            try:
                return connector.search(query)
            except Exception:
                return []

        if connectors:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(connectors)) as executor:
                future_to_connector = {executor.submit(fetch, c): c for c in connectors}
                for future in concurrent.futures.as_completed(future_to_connector):
                    results.extend(future.result())

        results = self._dedupe(results)
        self._cache[cache_key] = [asdict(item) for item in results]
        self._save_cache()
        return results
