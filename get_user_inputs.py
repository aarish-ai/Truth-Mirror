import json
with open(r'C:\Users\DELL\.gemini\antigravity\brain\ac8ed01b-1eb5-4cf1-a4c8-3816e2c4ab40\.system_generated\logs\transcript.jsonl', 'r', encoding='utf-8') as f, open('user_requests.txt', 'w', encoding='utf-8') as out:
    for line in f:
        d = json.loads(line)
        if d.get('type') == 'USER_INPUT':
            out.write(d.get('content') + '\n---\n')

