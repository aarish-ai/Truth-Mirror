import urllib.parse
import urllib.request
import json
from datetime import datetime, timezone
from typing import List
import arxiv

from truth_mirror.models import EvidenceItem
from truth_mirror.retrieval import RetrievalConfig

class SemanticScholarConnector:
    def __init__(self, config: RetrievalConfig | None = None):
        self.config = config or RetrievalConfig()
    
    def search(self, query: str) -> List[EvidenceItem]:
        url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode({
            "query": query,
            "limit": self.config.max_results,
            "fields": "title,authors,year,url,abstract,venue"
        })
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TruthMirror/0.1"})
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []
        
        items = []
        for p in payload.get("data", []):
            title = p.get("title", "")
            if not title: continue
            authors = p.get("authors", [])
            author_names = ", ".join([a.get("name", "") for a in authors[:3]]) if authors else "unknown"
            year = p.get("year")
            date = f"{year}-01-01" if year else datetime.now(timezone.utc).date().isoformat()
            venue = p.get("venue") or "Semantic Scholar"
            
            items.append(EvidenceItem(
                source_title=title,
                source_type="academic",
                publisher=venue,
                date=date,
                url_or_id=p.get("url", ""),
                excerpt=(p.get("abstract") or "Semantic Scholar academic paper metadata.")[:500],
                author=author_names,
                language="en",
                independence_key=f"semanticscholar:{venue.lower()}"
            ))
        return items

class ArxivConnector:
    def __init__(self, config: RetrievalConfig | None = None):
        self.config = config or RetrievalConfig()
        
    def search(self, query: str) -> List[EvidenceItem]:
        # Skip arXiv for non-scientific claims (political, social, current events)
        skip_keywords = [
            'president', 'minister', 'election', 'dead', 'alive', 'died',
            'killed', 'arrested', 'jailed', 'war', 'attack', 'protest',
            'resign', 'government', 'party', 'leader', 'politician'
        ]
        claim_lower = query.lower()
        if any(kw in claim_lower for kw in skip_keywords):
            return []

        items = []
        try:
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=self.config.max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            for result in client.results(search):
                authors = ", ".join([a.name for a in result.authors[:3]]) if result.authors else "unknown"
                date = result.published.date().isoformat() if result.published else datetime.now(timezone.utc).date().isoformat()
                
                items.append(EvidenceItem(
                    source_title=result.title,
                    source_type="academic",
                    publisher="arXiv",
                    date=date,
                    url_or_id=result.entry_id,
                    excerpt=(result.summary or "arXiv preprint metadata.")[:500],
                    author=authors,
                    language="en",
                    independence_key="arxiv:preprint"
                ))
        except Exception:
            pass
        return items

class PubMedConnector:
    def __init__(self, config: RetrievalConfig | None = None):
        self.config = config or RetrievalConfig()
        
    def search(self, query: str) -> List[EvidenceItem]:
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode({
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": self.config.max_results
        })
        try:
            req = urllib.request.Request(search_url, headers={"User-Agent": "TruthMirror/0.1"})
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []
            
        id_list = payload.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []
            
        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + urllib.parse.urlencode({
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "json"
        })
        try:
            req = urllib.request.Request(summary_url, headers={"User-Agent": "TruthMirror/0.1"})
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                summary_payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []
            
        items = []
        result = summary_payload.get("result", {})
        for uid in id_list:
            item = result.get(uid)
            if not item: continue
            title = item.get("title", "")
            if not title: continue
            authors = [a.get("name") for a in item.get("authors", [])]
            author_names = ", ".join(authors[:3]) if authors else "unknown"
            pubdate = item.get("pubdate", "")
            source = item.get("source", "PubMed")
            
            items.append(EvidenceItem(
                source_title=title,
                source_type="academic",
                publisher=source,
                date=pubdate or datetime.now(timezone.utc).date().isoformat(),
                url_or_id=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                excerpt="PubMed academic paper metadata.",
                author=author_names,
                language="en",
                independence_key=f"pubmed:{source.lower()}"
            ))
            
        return items
