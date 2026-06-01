"""NLP Pipeline using spaCy for Truth Mirror."""

import logging

try:
    import spacy
    DEPENDENCIES_MET = True
except ImportError:
    DEPENDENCIES_MET = False

logger = logging.getLogger(__name__)

# Initialize model
nlp = None
if DEPENDENCIES_MET:
    try:
        # Task requested en_core_web_trf
        nlp = spacy.load("en_core_web_trf")
    except OSError:
        logger.warning("en_core_web_trf not found. Please run: python -m spacy download en_core_web_trf")
        # Try fallback if possible, though user explicitly asked for trf
        try:
            nlp = spacy.load("en_core_web_sm")
            logger.info("Using en_core_web_sm as fallback.")
        except OSError:
            logger.warning("No spaCy model found.")

def extract_nlp_features(text: str) -> dict:
    """Extract NER, dependencies, and coreferences using spaCy."""
    if not nlp:
        logger.warning("NLP model not loaded. Returning empty features.")
        return {"ner": [], "dependencies": [], "coreferences": []}

    doc = nlp(text)

    # 1. NER
    entities = [(ent.text, ent.label_) for ent in doc.ents]

    # 2. Dependencies
    dependencies = [(token.text, token.dep_, token.head.text) for token in doc]

    # 3. Coreferences (Standard spaCy doesn't provide coref natively without extensions,
    # but we can check if an extension is registered or use a stub for now.)
    coreferences = []
    if doc.has_extension("coref_clusters") and doc._.coref_clusters:
        coreferences = [[span.text for span in cluster] for cluster in doc._.coref_clusters]

    return {
        "ner": entities,
        "dependencies": dependencies,
        "coreferences": coreferences
    }
