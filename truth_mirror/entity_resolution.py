import urllib.request
import urllib.parse
import json
import logging
from typing import List

from truth_mirror.models import Entity

logger = logging.getLogger(__name__)

class EntityResolver:
    """Disambiguates and extracts entities from claims using DBpedia Spotlight or Wikidata API."""
    def __init__(self, use_dbpedia: bool = True):
        self.use_dbpedia = use_dbpedia

    def resolve_entities(self, text: str) -> List[Entity]:
        """Resolves entities in the given text."""
        if not text.strip():
            return []
            
        if self.use_dbpedia:
            entities = self._resolve_dbpedia(text)
            if entities:
                return entities
            # Fallback to Wikidata if DBpedia fails
            return self._resolve_wikidata(text)
        else:
            return self._resolve_wikidata(text)

    def _resolve_dbpedia(self, text: str) -> List[Entity]:
        url = "https://api.dbpedia-spotlight.org/en/annotate"
        data = urllib.parse.urlencode({'text': text, 'conf': '0.35'}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode())
                resources = result.get('Resources', [])
                entities = []
                for res in resources:
                    uri = res.get('@URI', '')
                    name = res.get('@surfaceForm', '')
                    types = res.get('@types', '')
                    types_list = types.split(',') if types else []
                    score = float(res.get('@similarityScore', 0.0))
                    if uri and name:
                        entities.append(Entity(
                            name=name,
                            uri=uri,
                            types=types_list,
                            score=score
                        ))
                return entities
        except Exception as e:
            logger.warning(f"DBpedia Spotlight resolution failed: {e}")
            return []

    def _resolve_wikidata(self, text: str) -> List[Entity]:
        """Fallback to Wikidata entity search (only searches for full text as query, which is limited)."""
        # Wikidata WB Search Entities API
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": text, # Might not work well for long sentences
            "language": "en",
            "format": "json",
            "limit": 3
        }
        
        query_string = urllib.parse.urlencode(params)
        req_url = f"{url}?{query_string}"
        
        # We construct a request with a User-Agent, as Wikidata requires it
        req = urllib.request.Request(req_url, headers={
            'User-Agent': 'TruthMirror/1.0 (MVP Entity Resolver)',
            'Accept': 'application/json'
        })
        
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode())
                search_results = result.get('search', [])
                entities = []
                for res in search_results:
                    uri = res.get('concepturi', '')
                    name = res.get('label', '')
                    description = res.get('description', '')
                    if uri and name:
                        entities.append(Entity(
                            name=name,
                            uri=uri,
                            description=description,
                            score=0.5 # Default score for wikidata fallback
                        ))
                return entities
        except Exception as e:
            logger.warning(f"Wikidata resolution failed: {e}")
            return []
