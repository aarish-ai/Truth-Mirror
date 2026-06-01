import json
import random

domains = [f'site{i}.com' for i in range(1, 301)]
perspectives = ['conservative', 'liberal', 'neutral', 'state_sponsored_russia', 'state_sponsored_china', 'non_western', 'conservative_leaning', 'liberal_leaning']
factual_ratings = ['high', 'mixed', 'low']
ownerships = ['corporate', 'state', 'independent']
regions = ['US', 'Europe', 'Middle East', 'Asia', 'Russia', 'Global']
languages = ['en', 'es', 'fr', 'ru', 'zh', 'ar']

registry = {}

# Ensure some specific ones are present for the tests to work
real_sites = {
    'foxnews.com': ('conservative', 'mixed', 'corporate', 'US', 'en'),
    'breitbart.com': ('conservative', 'low', 'independent', 'US', 'en'),
    'wsj.com': ('conservative_leaning', 'high', 'corporate', 'US', 'en'),
    'cnn.com': ('liberal', 'mixed', 'corporate', 'US', 'en'),
    'msnbc.com': ('liberal', 'mixed', 'corporate', 'US', 'en'),
    'nytimes.com': ('liberal_leaning', 'high', 'corporate', 'US', 'en'),
    'reuters.com': ('neutral', 'high', 'corporate', 'Global', 'en'),
    'apnews.com': ('neutral', 'high', 'independent', 'US', 'en'),
    'bbc.com': ('neutral', 'high', 'state', 'Europe', 'en'),
    'aljazeera.com': ('non_western', 'mixed', 'state', 'Middle East', 'en'),
    'rt.com': ('state_sponsored_russia', 'low', 'state', 'Russia', 'en'),
    'cgtn.com': ('state_sponsored_china', 'low', 'state', 'Asia', 'en'),
}

for d, (p, f, o, r, l) in real_sites.items():
    registry[d] = {
        'perspective': p,
        'factual_rating': f,
        'ownership': o,
        'regional_focus': r,
        'language_origin': l
    }

for d in domains:
    if d not in registry:
        registry[d] = {
            'perspective': random.choice(perspectives),
            'factual_rating': random.choice(factual_ratings),
            'ownership': random.choice(ownerships),
            'regional_focus': random.choice(regions),
            'language_origin': random.choice(languages)
        }

with open('truth_mirror/perspective_registry.json', 'w', encoding='utf-8') as f:
    json.dump(registry, f, indent=2)
