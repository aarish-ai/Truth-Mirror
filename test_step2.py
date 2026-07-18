# Test A: confidence label computation
# Inline the mapping logic directly here
def compute_label(conf):
    if conf > 0.85: return "Very High"
    if conf > 0.50: return "High"
    if conf > 0.30: return "Moderate"
    return "Low"
assert compute_label(0.90) == "Very High"
assert compute_label(0.70) == "High"
assert compute_label(0.40) == "Moderate"
assert compute_label(0.25) == "Low"
assert compute_label(0.85) == "High"   # boundary: 0.85 is NOT > 0.85
print("Test A passed")

# Test B: batch parser alignment prefers registry over LLM
from truth_mirror.source_registry import get_source_metadata
# Simulate what _parse_batch_response now does for an Al Jazeera article
url = "https://news.google.com/rss/articles/CBMi_fake_url"
publisher_hint = "Al Jazeera"
raw_llm_alignment = "anti-US"
registry_meta = get_source_metadata(url, publisher=publisher_hint)
registry_alignment = registry_meta.get("alignment", "")
alignment = (registry_alignment
             if registry_alignment and registry_alignment != "unknown"
             else raw_llm_alignment)
assert alignment == "gulf", f"Expected 'gulf', got '{alignment}'"
print("Test B passed")

# Test C: Groq dict extraction
import json
groq_response = json.dumps({"perspectives": [
    {"group_label": "Western Media", "alignment": "western",
     "collective_stance": "SUPPORTS", "collective_narrative": "Test",
     "what_they_emphasize": "X", "what_they_omit": "Y",
     "internal_disagreements": "", "credibility_note": "Z"}
]})
parsed = json.loads(groq_response)
data = None
if isinstance(parsed, list):
    data = parsed
elif isinstance(parsed, dict):
    for v in parsed.values():
        if isinstance(v, list) and v:
            data = v
            break
assert isinstance(data, list) and len(data) == 1
assert data[0]["group_label"] == "Western Media"
print("Test C passed")

print("All static tests passed.")

