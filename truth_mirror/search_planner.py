import concurrent.futures
from typing import List, Tuple

from truth_mirror.models import EvidenceItem


class SearchPlanner:
    def __init__(self, retriever, query_generator):
        self.retriever = retriever
        self.query_generator = query_generator

    def retrieve_for_subclaim(
        self, 
        sub_claim: str, 
        claim_type: str, 
        has_date: bool, 
        max_results_per_query: int = 8
    ) -> Tuple[List[EvidenceItem], List[str]]:
        try:
            if hasattr(self.query_generator, "generate"):
                queries = self.query_generator.generate(sub_claim, claim_type, has_date)
            else:
                queries = self.query_generator(sub_claim, claim_type, has_date)
            
            # Ensure we have at most 3 queries as per spec
            if not queries:
                queries = [sub_claim]
            queries = queries[:3]
        except Exception as e:
            print(f"Query generation failed: {e}")
            queries = [sub_claim]
            
        all_results = []
        queries_used = list(queries)
        
        def fetch(query: str) -> List[EvidenceItem]:
            try:
                results = self.retriever.retrieve(query, claim_type=claim_type)
                return results[:max_results_per_query]
            except Exception as e:
                print(f"Error fetching for query '{query}': {e}")
                return []

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(fetch, q): q for q in queries}
                for future in concurrent.futures.as_completed(futures):
                    all_results.extend(future.result())
        except Exception as e:
            print(f"Parallel execution error: {e}")
            
        # Deduplicate by url_or_id keeping the first
        deduplicated_list = []
        seen_urls = set()
        
        for item in all_results:
            uid = item.url_or_id
            if not uid:
                deduplicated_list.append(item)
            elif uid not in seen_urls:
                seen_urls.add(uid)
                deduplicated_list.append(item)
                
        return deduplicated_list, queries_used
