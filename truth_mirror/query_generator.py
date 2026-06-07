import json
import re
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "in", "on", "at", "to", "from", "by",
    "with", "about", "for", "of", "as", "that", "this", "these",
    "those", "it", "its", "has", "have", "had", "not", "does", "do", "did"
}

class QueryGenerator:
    def __init__(self, ollama_model="qwen2.5:3b", ollama_base_url="http://localhost:11434"):
        self.ollama_model = ollama_model
        self.ollama_base_url = ollama_base_url
        self.current_date_str = datetime.now().strftime("%B %Y")

    def _fallback_queries(self, sub_claim: str, has_date: bool) -> list[str]:
        date_suffix = f" {self.current_date_str}" if not has_date else ""
        return [
            f"{sub_claim}{date_suffix}",
            f"{sub_claim} news{date_suffix}",
            f"{sub_claim} latest{date_suffix}",
        ]

    def _call_ollama(self, prompt: str) -> str | None:
        try:
            url = f"{self.ollama_base_url}/api/generate"
            payload = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 300
                }
            }
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json().get("response")
        except Exception as e:
            logger.warning(f"Ollama generation failed: {e}")
            return None

    def _parse_queries(self, llm_output: str, sub_claim: str, has_date: bool) -> list[str]:
        fallbacks = self._fallback_queries(sub_claim, has_date)
        
        # Strip markdown fences
        clean_out = llm_output.strip()
        if clean_out.startswith("```"):
            lines = clean_out.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_out = "\n".join(lines).strip()
            
        parsed_list = []
        try:
            parsed = json.loads(clean_out)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, str) and item.strip():
                        if 1 <= len(item.split()) <= 20: # Just a basic sanity check before guardrails
                            parsed_list.append(item.strip())
        except json.JSONDecodeError:
            pass
            
        if not parsed_list:
            return fallbacks
            
        # We need exactly 3
        results = []
        for q in parsed_list:
            if q not in results:
                results.append(q)
            if len(results) == 3:
                break
                
        while len(results) < 3:
            for f in fallbacks:
                if f not in results:
                    results.append(f)
                    break
            if len(results) >= 3:
                break

        # GUARDRAIL 1: At least one significant word (length > 3, excluding stopwords) from the sub-claim must appear in at least 2 queries.
        words_in_claim = set(w.lower() for w in re.findall(r'\b\w+\b', sub_claim))
        significant_words = {w for w in words_in_claim if len(w) > 3 and w not in STOPWORDS}
        
        if significant_words:
            sig_word_found_in_queries = {w: 0 for w in significant_words}
            for q in results:
                q_words = set(w.lower() for w in re.findall(r'\b\w+\b', q))
                for sw in significant_words:
                    if sw in q_words:
                        sig_word_found_in_queries[sw] += 1
                        
            if not any(count >= 2 for count in sig_word_found_in_queries.values()):
                logger.warning(f"Guardrail 1 failed for claim '{sub_claim}'. Returning fallbacks.")
                return fallbacks

        # Apply Guardrails 2 and 3 element-wise
        bad_prefixes = (
            r"^causes\s+of\b", r"^symptoms\s+of\b", r"^what\s+is\b",
            r"^how\s+does\b", r"^definition\s+of\b", r"^history\s+of\s+\w+$",
            r"^types\s+of\b", r"^effects\s+of\b"
        )
        
        final_results = []
        for i, q in enumerate(results):
            # GUARDRAIL 2
            is_bad_prefix = False
            for pattern in bad_prefixes:
                if re.match(pattern, q, re.IGNORECASE):
                    is_bad_prefix = True
                    break
                    
            # GUARDRAIL 3
            word_count = len(q.split())
            is_bad_length = not (3 <= word_count <= 15)
            
            if is_bad_prefix or is_bad_length:
                # Replace specific bad query with the fallback for that position
                final_results.append(fallbacks[i % len(fallbacks)])
            else:
                final_results.append(q)
                
        return final_results

    def generate_queries(self, sub_claim: str, has_date: bool, claim_type: str = "mixed or ambiguous claim") -> list[str]:
        CLAIM_TYPE_HINTS = {
            "breaking news / recent event":
                "news articles and recent reports",
            "historical fact":
                "factual encyclopedia and historical sources",
            "quote attribution":
                "direct quotes, speeches, and official statements",
            "statistic / numeric claim":
                "official data, reports, and statistics",
            "policy / legal claim":
                "legal records, government documents, and policy news",
            "scientific / medical claim":
                "peer-reviewed studies and health authority statements",
            "opinion dressed as fact":
                "news analysis and editorial fact-checks",
            "historical fact":
                "encyclopedia, historical records, and official biographies",
            "mixed or ambiguous claim":
                "news articles and factual sources",
        }
        search_target = CLAIM_TYPE_HINTS.get(
            claim_type, "news articles and factual sources"
        )
        date_instruction = (
            "The claim already has a date. Respect it."
            if has_date else
            f"Add '{self.current_date_str}' to queries needing current information."
        )

        prompt = f"""Generate 3 search queries to find {search_target}
that verify or contradict this claim.

Claim: "{sub_claim}"
{date_instruction}

Rules:
- Focus on the specific ENTITIES (people, places, organizations)
- Do NOT generate queries about general topics or definitions
- Queries must find NEWS or FACTS about the specific claim
- Each query must be different (vary entity focus, date, angle)
- Return ONLY a JSON array. No explanation. No markdown.

Example:
Claim: "Donald Trump is Dead"
Output: ["Donald Trump alive June 2026", "Donald Trump health news 2026", "Donald Trump latest news status"]

Claim: "Imran Khan is in jail as of June 2026"
Output: ["Imran Khan imprisonment June 2026", "Imran Khan jail sentence 2026", "Imran Khan PTI custody latest news"]

Claim: "{sub_claim}"
Output:"""

        llm_output = self._call_ollama(prompt)
        if not llm_output:
            return self._fallback_queries(sub_claim, has_date)
            
        return self._parse_queries(llm_output, sub_claim, has_date)
