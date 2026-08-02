import json

with open("truth_mirror/perspective_registry.json", "r", encoding="utf-8") as f:
    data = json.load(f)

new_data = {k: v for k, v in data.items() if not k.startswith("news-source-")}

with open("truth_mirror/perspective_registry.json", "w", encoding="utf-8") as f:
    json.dump(new_data, f, indent=2)
