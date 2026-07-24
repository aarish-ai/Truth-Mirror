import requests
import json
import time

def test_claim(claim_text):
    print(f"\n--- Testing: {claim_text} ---")
    start = time.time()
    try:
        resp = requests.post(
            "http://127.0.0.1:8080/api/verify",
            json={"claim": claim_text},
            auth=("user", "tmirror2024"),
            timeout=300
        )
        data = resp.json()
        print(f"Status Code: {resp.status_code}")
        
        # We want to check the verdict and the temporal classification
        verdict = data.get("verdict_data", {}).get("verdict", "N/A")
        print(f"Verdict: {verdict}")
        
        # Check generated queries (to ensure no double-dates)
        queries = data.get("search_queries", [])
        print(f"Generated Queries: {json.dumps(queries, indent=2)}")
        
        # Check source analyses to see if historical ones were dismissed
        analyses = data.get("source_analyses", [])
        print(f"Analyzed {len(analyses)} sources.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print(f"Elapsed: {time.time() - start:.2f}s")

if __name__ == "__main__":
    test_claim("India is attacking Pakistan as of July 2026")
    test_claim("India is attacking Pakistan")
