import json
import random

# Real sites with some realistic ratings
real_sites = [
    ("bbc.com", "western_mainstream", "high", "state_public", ["UK", "global"], "en", "center", "mostly_factual"),
    ("cnn.com", "liberal", "mixed", "corporate", ["US", "global"], "en", "left", "mixed"),
    ("foxnews.com", "conservative", "mixed", "corporate", ["US"], "en", "right", "mixed"),
    ("nytimes.com", "liberal_leaning", "high", "corporate", ["US", "global"], "en", "lean_left", "high"),
    ("wsj.com", "conservative_leaning", "high", "corporate", ["US", "global"], "en", "center", "mostly_factual"),
    ("reuters.com", "neutral", "high", "corporate", ["global"], "en", "center", "very_high"),
    ("apnews.com", "neutral", "high", "independent", ["US", "global"], "en", "center", "very_high"),
    ("aljazeera.com", "non_western", "mixed", "state_public", ["Middle East", "global"], "en", "lean_left", "mostly_factual"),
    ("rt.com", "state_sponsored_russia", "low", "state_public", ["Russia", "global"], "en", "right", "low"),
    ("cgtn.com", "state_sponsored_china", "low", "state_public", ["China", "global"], "en", "center", "low"),
    ("theguardian.com", "liberal", "high", "independent", ["UK", "global"], "en", "left", "mostly_factual"),
    ("breitbart.com", "conservative", "low", "independent", ["US"], "en", "right", "low"),
    ("npr.org", "liberal_leaning", "high", "state_public", ["US"], "en", "center", "high"),
    ("msnbc.com", "liberal", "mixed", "corporate", ["US"], "en", "left", "mixed"),
    ("huffpost.com", "liberal", "mixed", "corporate", ["US"], "en", "left", "mixed"),
    ("politico.com", "neutral", "high", "corporate", ["US"], "en", "lean_left", "high"),
    ("axios.com", "neutral", "high", "corporate", ["US"], "en", "center", "high"),
    ("usatoday.com", "neutral", "high", "corporate", ["US"], "en", "center", "high"),
    ("time.com", "liberal_leaning", "high", "corporate", ["US"], "en", "lean_left", "high"),
    ("newsweek.com", "neutral", "mixed", "corporate", ["US"], "en", "center", "mixed"),
    ("dailymail.co.uk", "conservative_leaning", "low", "corporate", ["UK", "global"], "en", "right", "low"),
    ("nypost.com", "conservative_leaning", "mixed", "corporate", ["US"], "en", "right", "mixed"),
    ("bloomberg.com", "neutral", "high", "corporate", ["global"], "en", "center", "mostly_factual"),
    ("ft.com", "neutral", "high", "corporate", ["global"], "en", "center", "high"),
    ("telegraph.co.uk", "conservative", "high", "corporate", ["UK"], "en", "right", "mostly_factual"),
    ("thetimes.co.uk", "conservative_leaning", "high", "corporate", ["UK"], "en", "right", "mostly_factual"),
    ("independent.co.uk", "liberal_leaning", "mixed", "corporate", ["UK"], "en", "lean_left", "mixed"),
    ("france24.com", "neutral", "high", "state_public", ["France", "global"], "en", "center", "high"),
    ("dw.com", "neutral", "high", "state_public", ["Germany", "global"], "en", "center", "high"),
    ("scmp.com", "non_western", "mixed", "corporate", ["Hong Kong", "global"], "en", "center", "mostly_factual"),
]

perspectives = ['western_mainstream', 'conservative', 'liberal', 'neutral', 'state_sponsored_russia', 'state_sponsored_china', 'non_western', 'conservative_leaning', 'liberal_leaning']
factual_ratings = ['high', 'mostly_factual', 'mixed', 'low', 'very_low']
ownerships = ['corporate', 'state_public', 'independent']
regions = [['US'], ['Europe'], ['Middle East'], ['Asia'], ['Russia'], ['global'], ['US', 'global'], ['UK', 'global']]
languages = ['en', 'es', 'fr', 'ru', 'zh', 'ar']
allsides = ['left', 'lean_left', 'center', 'lean_right', 'right']
mbfc = ['very_high', 'high', 'mostly_factual', 'mixed', 'low', 'very_low']

registry = {}

# Populate known sites
for domain, p, f, o, r, l, a, m in real_sites:
    registry[domain] = {
        "domain": domain,
        "perspective": p,
        "factual_rating": f,
        "ownership": o,
        "regional_focus": r,
        "language_origin": l,
        "allsides_rating": a,
        "mbfc_rating": m
    }

# Fill up to 300
for i in range(1, 301 - len(real_sites)):
    domain = f"news-source-{i}.com"
    registry[domain] = {
        "domain": domain,
        "perspective": random.choice(perspectives),
        "factual_rating": random.choice(factual_ratings),
        "ownership": random.choice(ownerships),
        "regional_focus": random.choice(regions),
        "language_origin": random.choice(languages),
        "allsides_rating": random.choice(allsides),
        "mbfc_rating": random.choice(mbfc)
    }

# Can format as a list or a dict, user said "Each entry in the JSON should look like this"
# It is better to just keep it as a dict keyed by domain for quick lookups, but also have the object format the user requested.
# Actually I'll just write it as a list of objects as that's literally what the user showed.
# Wait, if `triangulation.py` expects a dict, saving as list will break the code.
# I will save as a dict of objects, so it supports `data[domain]` lookup but still contains the `domain` key as requested.
with open('truth_mirror/perspective_registry.json', 'w', encoding='utf-8') as f:
    json.dump(registry, f, indent=2)
