import requests
import json

api_key = None
with open(".env", "r") as f:
    for line in f:
        if line.startswith("GROQ_API_KEY="):
            api_key = line.split("=", 1)[1].strip().strip("'\"")
            break

if not api_key:
    print("GROQ_API_KEY not found in .env")
    exit(1)

url = "https://api.groq.com/openai/v1/models"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    print(json.dumps(response.json(), indent=2))
else:
    print(f"Error {response.status_code}: {response.text}")
