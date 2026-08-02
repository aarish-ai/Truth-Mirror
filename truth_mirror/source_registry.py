SOURCE_REGISTRY = {
    "reuters.com":        {"name": "Reuters",           "category": "wire_service",   "country": "International", "alignment": "western",      "tier": 1},
    "apnews.com":         {"name": "AP News",            "category": "wire_service",   "country": "International", "alignment": "western",      "tier": 1},
    "bbc.com":            {"name": "BBC",                "category": "western_msm",    "country": "UK",            "alignment": "western",      "tier": 1},
    "bbc.co.uk":          {"name": "BBC",                "category": "western_msm",    "country": "UK",            "alignment": "western",      "tier": 1},
    "theguardian.com":    {"name": "The Guardian",       "category": "western_msm",    "country": "UK",            "alignment": "western",      "tier": 1},
    "nytimes.com":        {"name": "New York Times",     "category": "western_msm",    "country": "USA",           "alignment": "western",      "tier": 1},
    "washingtonpost.com": {"name": "Washington Post",    "category": "western_msm",    "country": "USA",           "alignment": "western",      "tier": 1},
    "cnn.com":            {"name": "CNN",                "category": "western_msm",    "country": "USA",           "alignment": "western",      "tier": 2},
    "foxnews.com":        {"name": "Fox News",           "category": "western_msm",    "country": "USA",           "alignment": "western",      "tier": 2},
    "politico.com":       {"name": "Politico",           "category": "western_msm",    "country": "USA",           "alignment": "western",      "tier": 2},
    "france24.com":       {"name": "France 24",          "category": "western_msm",    "country": "France",        "alignment": "western",      "tier": 2},
    "dw.com":             {"name": "Deutsche Welle",     "category": "western_msm",    "country": "Germany",       "alignment": "western",      "tier": 2},
    "aljazeera.com":      {"name": "Al Jazeera",         "category": "gulf_media",     "country": "Qatar",         "alignment": "gulf",         "tier": 2},
    "alarabiya.net":      {"name": "Al Arabiya",         "category": "gulf_media",     "country": "Saudi Arabia",  "alignment": "gulf",         "tier": 2},
    "arabnews.com":       {"name": "Arab News",          "category": "gulf_media",     "country": "Saudi Arabia",  "alignment": "gulf",         "tier": 2},
    "tass.com":           {"name": "TASS",               "category": "state_media",    "country": "Russia",        "alignment": "eastern",      "tier": 2},
    "rt.com":             {"name": "RT",                 "category": "state_media",    "country": "Russia",        "alignment": "eastern",      "tier": 3},
    "cgtn.com":           {"name": "CGTN",               "category": "state_media",    "country": "China",         "alignment": "eastern",      "tier": 2},
    "xinhuanet.com":      {"name": "Xinhua",             "category": "state_media",    "country": "China",         "alignment": "eastern",      "tier": 2},
    "globaltimes.cn":     {"name": "Global Times",       "category": "state_media",    "country": "China",         "alignment": "eastern",      "tier": 3},
    "presstv.ir":         {"name": "Press TV",           "category": "state_media",    "country": "Iran",          "alignment": "iran",         "tier": 3},
    "irna.ir":            {"name": "IRNA",               "category": "state_media",    "country": "Iran",          "alignment": "iran",         "tier": 2},
    "timesofisrael.com":  {"name": "Times of Israel",    "category": "regional_media", "country": "Israel",        "alignment": "israel",       "tier": 2},
    "haaretz.com":        {"name": "Haaretz",            "category": "regional_media", "country": "Israel",        "alignment": "israel",       "tier": 2},
    "jpost.com":          {"name": "Jerusalem Post",     "category": "regional_media", "country": "Israel",        "alignment": "israel",       "tier": 2},
    "dawn.com":           {"name": "Dawn",               "category": "regional_media", "country": "Pakistan",      "alignment": "south_asian",  "tier": 2},
    "geo.tv":             {"name": "Geo TV",             "category": "regional_media", "country": "Pakistan",      "alignment": "south_asian",  "tier": 2},
    "thehindu.com":       {"name": "The Hindu",          "category": "regional_media", "country": "India",         "alignment": "south_asian",  "tier": 2},
    "middleeasteye.net":  {"name": "Middle East Eye",    "category": "independent",    "country": "UK",            "alignment": "independent",  "tier": 2},
    "theintercept.com":   {"name": "The Intercept",      "category": "independent",    "country": "USA",           "alignment": "independent",  "tier": 2},
    "bellingcat.com":     {"name": "Bellingcat",         "category": "osint",          "country": "International", "alignment": "independent",  "tier": 1},
    "en.wikipedia.org":   {"name": "Wikipedia",          "category": "encyclopedia",   "country": "International", "alignment": "neutral",      "tier": 3},
}

PUBLISHER_NAME_MAP = {
    "al jazeera":       {"name": "Al Jazeera",      "category": "gulf_media",   "country": "Qatar",         "alignment": "gulf",        "tier": 2},
    "tass":             {"name": "TASS",             "category": "state_media",  "country": "Russia",        "alignment": "eastern",     "tier": 2},
    "cgtn":             {"name": "CGTN",             "category": "state_media",  "country": "China",         "alignment": "eastern",     "tier": 2},
    "xinhua":           {"name": "Xinhua",           "category": "state_media",  "country": "China",         "alignment": "eastern",     "tier": 2},
    "dawn pk":          {"name": "Dawn",             "category": "regional_media","country": "Pakistan",     "alignment": "south_asian", "tier": 2},
    "dawn":             {"name": "Dawn",             "category": "regional_media","country": "Pakistan",     "alignment": "south_asian", "tier": 2},
    "middle east eye":  {"name": "Middle East Eye",  "category": "independent",  "country": "UK",            "alignment": "independent", "tier": 2},
    "press tv":         {"name": "Press TV",         "category": "state_media",  "country": "Iran",          "alignment": "iran",        "tier": 3},
    "tehran times":     {"name": "Tehran Times",     "category": "state_media",  "country": "Iran",          "alignment": "iran",        "tier": 3},
    "wikipedia":        {"name": "Wikipedia",        "category": "encyclopedia", "country": "International", "alignment": "neutral",     "tier": 3},
    "wikinews":         {"name": "Wikinews",         "category": "encyclopedia", "country": "International", "alignment": "neutral",     "tier": 3},
    "reuters":          {"name": "Reuters",          "category": "wire_service", "country": "International", "alignment": "western",     "tier": 1},
    "ap news":          {"name": "AP News",          "category": "wire_service", "country": "International", "alignment": "western",     "tier": 1},
    "associated press": {"name": "AP News",          "category": "wire_service", "country": "International", "alignment": "western",     "tier": 1},
    "bbc":              {"name": "BBC",              "category": "western_msm",  "country": "UK",            "alignment": "western",     "tier": 1},
    "the guardian":     {"name": "The Guardian",     "category": "western_msm",  "country": "UK",            "alignment": "western",     "tier": 1},
    "new york times":   {"name": "New York Times",   "category": "western_msm",  "country": "USA",           "alignment": "western",     "tier": 1},
    "france 24":        {"name": "France 24",        "category": "western_msm",  "country": "France",        "alignment": "western",     "tier": 2},
    "deutsche welle":   {"name": "Deutsche Welle",   "category": "western_msm",  "country": "Germany",       "alignment": "western",     "tier": 2},
    "dw":               {"name": "Deutsche Welle",   "category": "western_msm",  "country": "Germany",       "alignment": "western",     "tier": 2},
    "al arabiya":       {"name": "Al Arabiya",       "category": "gulf_media",   "country": "Saudi Arabia",  "alignment": "gulf",        "tier": 2},
    "bellingcat":       {"name": "Bellingcat",       "category": "osint",        "country": "International", "alignment": "independent", "tier": 1},
}

ALIGNMENT_GROUP_LABELS = {
    "western":     "Western Media",
    "eastern":     "Russian & Chinese State Media",
    "gulf":        "Gulf & Arab Media",
    "iran":        "Iranian State Media",
    "israel":      "Israeli Media",
    "south_asian": "South Asian Media",
    "independent": "Independent & Investigative Media",
    "neutral":     "Reference Sources",
}

from urllib.parse import urlparse

def get_source_metadata(url: str, publisher: str = "") -> dict:
    """
    Given a URL, return source metadata from the registry.
    Falls back to inferred metadata if domain is not in the registry.
    """
    domain = urlparse(url).netloc
    
    # Strip common feed subdomains
    for prefix in ["www.", "feeds.", "rss.", "news."]:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
            
    if domain in SOURCE_REGISTRY:
        return SOURCE_REGISTRY[domain]
    for known_domain, meta in SOURCE_REGISTRY.items():
        if domain == known_domain or domain.endswith("." + known_domain):
            return meta

    # Infer from TLD or domain keywords
    inferred = {"name": domain, "category": "unknown", "country": "Unknown", "alignment": "unknown", "tier": 3}
    if any(x in domain for x in [".gov", ".mil"]):
        inferred["category"] = "official"
        inferred["alignment"] = "official"
        inferred["tier"] = 1
    elif domain.endswith(".ir"):
        inferred["alignment"] = "iran"
    elif domain.endswith(".il"):
        inferred["alignment"] = "israel"
    elif domain.endswith(".ru"):
        inferred["alignment"] = "eastern"
    elif domain.endswith(".cn"):
        inferred["alignment"] = "eastern"

    # Try publisher name fallback
    if publisher:
        pub_lower = publisher.strip().lower()
        if pub_lower in PUBLISHER_NAME_MAP:
            return PUBLISHER_NAME_MAP[pub_lower]
        pub_tokens = set(pub_lower.split())
        for known_name, meta in PUBLISHER_NAME_MAP.items():
            known_tokens = set(known_name.split())
            if pub_tokens == known_tokens:
                return meta

    return inferred
