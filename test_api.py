import json
import urllib.request

url = "http://127.0.0.1:8080/api/verify"
payload = json.dumps({"claim": "US invaded venezuela"}).encode("utf-8")
req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

print("Sending request to verify...")
try:
    with urllib.request.urlopen(req, timeout=120) as response:
        data = json.loads(response.read().decode('utf-8'))
        
        print("\n--- SOURCES ---")
        for s in data.get("source_analyses", []):
            print(f"[{s.get('alignment')}] {s.get('source_name')}: {s.get('stance')}")
            
        print("\n--- BLOC ANALYSIS ---")
        for g in data.get("perspective_groups", []):
            print(f"Bloc: {g.get('group_label')} - {g.get('collective_stance')}")
            print(f"Narrative: {g.get('collective_narrative')}")
            
        print("\n--- HIDDEN STORIES ---")
        for h in data.get("hidden_stories", []):
            print(f"Title: {h.get('title')}")
            print(f"Explanation: {h.get('explanation')}")
            
        print("\n--- VERDICT ---")
        print(data.get("verdict_data", {}).get("verdict"))
        print(data.get("verdict_data", {}).get("full_reasoning"))
        
except Exception as e:
    print(f"Error: {e}")
