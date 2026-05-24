import json

with open(r'C:\Users\DELL\.gemini\antigravity\brain\8875dec5-6ca0-4cb0-96e3-cb5ffbaf1aaa\.system_generated\logs\transcript.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        if data.get('step_index') == 360:
            with open(r'c:\Users\DELL\.gemini\antigravity\scratch\Truth Mirror\step_360_full.txt', 'w', encoding='utf-8') as out:
                out.write(data['content'])
            break
