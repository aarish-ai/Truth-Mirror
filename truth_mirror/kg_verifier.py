"""
Knowledge Graph Verifier using Wikidata SPARQL queries.
Provides fact-checking via 25+ templates and an LLM-based query selector.
"""

import logging
import urllib.parse
import urllib.request
import json
from typing import Optional, Dict, Any, List, Tuple
import re

from .models import EvidenceItem

logger = logging.getLogger(__name__)

# Define 25+ common properties for Wikidata fact-checking
WIKIDATA_PROPERTIES = {
    "head_of_state": ("P64", "Get the head of state of a country or region (e.g. President, Monarch)."),
    "head_of_government": ("P6", "Get the head of government of a country or region (e.g. Prime Minister)."),
    "birth_date": ("P569", "Get the birth date of a person."),
    "death_date": ("P570", "Get the death date of a person."),
    "population": ("P1082", "Get the population of a city, country, or region."),
    "capital": ("P36", "Get the capital city of a country or region."),
    "area": ("P2046", "Get the total area of a geographic location."),
    "currency": ("P38", "Get the official currency used by a country."),
    "official_language": ("P37", "Get the official language(s) of a country or region."),
    "author": ("P50", "Get the author of a book or written work."),
    "director": ("P57", "Get the director of a film or movie."),
    "cast_member": ("P161", "Get the actors or cast members of a film or television show."),
    "publication_date": ("P577", "Get the publication date of a book, movie, or work."),
    "discoverer_inventor": ("P61", "Get the discoverer or inventor of an entity or concept."),
    "headquarters_location": ("P159", "Get the headquarters location of a company or organization."),
    "elevation": ("P2044", "Get the elevation above sea level of a geographic location."),
    "cause_of_death": ("P509", "Get the medical cause of death of a person."),
    "spouse": ("P26", "Get the spouse (husband/wife) of a person."),
    "child": ("P40", "Get the children of a person."),
    "educated_at": ("P69", "Get the educational institution attended by a person."),
    "employer": ("P108", "Get the employer or company a person works for."),
    "award_received": ("P166", "Get the awards or honors received by a person or work."),
    "member_of_sports_team": ("P54", "Get the sports team a person plays for."),
    "position_held": ("P39", "Get the political or professional position held by a person."),
    "country_of_citizenship": ("P27", "Get the country of citizenship for a person."),
    "developer": ("P178", "Get the developer of a software or hardware product."),
    "manufacturer": ("P176", "Get the manufacturer of a product."),
    "highest_point": ("P610", "Get the highest point of a geographical location."),
    "election_winner": ("P991", "Get the successful candidate or winner of an election."),
    "political_party": ("P102", "Get the political party of a politician."),
    "inception": ("P571", "Get the inception or creation date of an organization or artifact."),
    "participant": ("P710", "Get the participants in an event or war."),
    "location": ("P276", "Get the location of an event or object.")
}

def build_sparql_query(entity_name: str, property_id: str) -> str:
    """
    Builds a robust SPARQL query that searches for the entity by name
    and retrieves the requested property.
    """
    return f"""
SELECT ?objectLabel WHERE {{
  SERVICE wikibase:mwapi {{
      bd:serviceParam wikibase:endpoint "www.wikidata.org";
                      wikibase:api "EntitySearch";
                      mwapi:search "{entity_name}";
                      mwapi:language "en".
      ?subject wikibase:apiOutputItem mwapi:item.
  }}
  ?subject wdt:{property_id} ?object.
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}} LIMIT 5
"""

class KGVerifier:
    def __init__(self):
        self.endpoint_url = "https://query.wikidata.org/sparql"

    def query_wikidata(self, sparql_query: str) -> List[str]:
        """Executes a SPARQL query against Wikidata and returns a list of result labels."""
        headers = {
            'User-Agent': 'TruthMirrorBot/1.0 (Python urllib)',
            'Accept': 'application/sparql-results+json'
        }
        url = self.endpoint_url + '?query=' + urllib.parse.quote(sparql_query)
        req = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            results = []
            for binding in data.get('results', {}).get('bindings', []):
                if 'objectLabel' in binding:
                    results.append(binding['objectLabel']['value'])
            return results
        except Exception as e:
            logger.error(f"Wikidata query failed: {e}")
            return []

    def _select_template(self, claim: str) -> Tuple[Optional[str], Optional[str]]:
        claim_lower = claim.lower()
        entity_regex = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'

        if re.search(r'\b(president|prime minister|pm|head of)\b', claim_lower):
            match = re.search(r'\b(?:of|in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', claim)
            if match:
                return "head_of_government", match.group(1)

        if re.search(r'\b(born|birth|birthdate)\b', claim_lower):
            match = re.search(entity_regex, claim)
            if match:
                return "birth_date", match.group(1)

        if re.search(r'\b(died|death|passed away)\b', claim_lower):
            match = re.search(entity_regex, claim)
            if match:
                return "death_date", match.group(1)

        if re.search(r'\b(population|people|residents)\b', claim_lower):
            match = re.search(entity_regex, claim)
            if match:
                return "population", match.group(1)

        if re.search(r'\b(capital|capital city)\b', claim_lower):
            match = re.search(entity_regex, claim)
            if match:
                return "capital", match.group(1)

        if re.search(r'\bwon\b', claim_lower) and re.search(r'\b(election|vote)\b', claim_lower):
            match = re.search(entity_regex, claim)
            if match:
                return "election_winner", match.group(1)

        if re.search(r'\b(nobel|award|prize)\b', claim_lower):
            match = re.search(entity_regex, claim)
            if match:
                return "award_received", match.group(1)

        return None, None

    def verify_claim(self, claim: str) -> Optional[EvidenceItem]:
        """
        Selects a query template deterministically and extracts the entity.
        Then executes the query and returns an EvidenceItem.
        """
        template_key, entity_name = self._select_template(claim)
        
        if not template_key or not entity_name or template_key not in WIKIDATA_PROPERTIES:
            return None
            
        property_id, description = WIKIDATA_PROPERTIES[template_key]
        
        try:
            # Execute query
            sparql_query = build_sparql_query(entity_name, property_id)
            results = self.query_wikidata(sparql_query)
            
            if not results:
                return None
                
            # Format results into evidence
            formatted_results = ", ".join(results)
            excerpt = f"According to Wikidata, for the entity '{entity_name}' regarding {template_key.replace('_', ' ')}: {formatted_results}."
            
            return EvidenceItem(
                source_title=f"Wikidata Query ({template_key})",
                source_type="database",
                publisher="Wikidata",
                date="",
                url_or_id=f"wikidata:{property_id}",
                excerpt=excerpt,
                relevance_score=0.9,
                credibility_score=0.95
            )

        except Exception as e:
            logger.error(f"KG verification failed: {e}")
            return None
