import pytest
import re
import base64
from unittest.mock import MagicMock

# 1. C2 SPARQL Injection Fix Test
from truth_mirror.kg_verifier import build_sparql_query

def test_c2_sparql_injection_escaping():
    entity_name = 'Test "Entity" \\ with injection'
    property_id = 'P36'
    query = build_sparql_query(entity_name, property_id)
    assert 'mwapi:search "Test \\"Entity\\" \\\\ with injection";' in query
    assert 'wdt:P36' in query

def test_c2_sparql_property_id_validation():
    with pytest.raises(ValueError, match="Invalid property_id"):
        build_sparql_query('France', 'P36; DROP TABLE')

    with pytest.raises(ValueError, match="Invalid property_id"):
        build_sparql_query('France', 'INVALID_P')

    # Valid property_id should succeed
    query = build_sparql_query('France', 'P1082')
    assert 'wdt:P1082' in query


# 2. C5 XXE Vulnerability Fix Test
import defusedxml.ElementTree as DefusedET
import truth_mirror.retrieval_news as r_news
import truth_mirror.retrieval_nonwestern as r_nonwestern
import truth_mirror.retrieval as r_retrieval

def test_c5_defusedxml_imports():
    assert r_news.ET is DefusedET
    assert r_nonwestern.ET is DefusedET
    assert r_retrieval.ET is DefusedET


# 3. C7 Auth Bypass Fix Test
from app import TruthMirrorHandler, AUTH_PASSWORD

def test_c7_auth_bypass_rejection():
    handler = MagicMock(spec=TruthMirrorHandler)
    handler.headers = {}
    
    # Execute _check_auth with mock headers (no Authorization header)
    result = TruthMirrorHandler._check_auth(handler)
    assert result is False
    handler.send_response.assert_called_with(401)
    handler.send_header.assert_any_call("WWW-Authenticate", 'Basic realm="Truth Mirror"')

def test_c7_auth_valid_credentials(monkeypatch):
    monkeypatch.setattr("app.AUTH_PASSWORD", "secret123")
    handler = MagicMock(spec=TruthMirrorHandler)
    valid_cred = base64.b64encode(b"admin:secret123").decode("utf-8")
    handler.headers = {"Authorization": f"Basic {valid_cred}"}
    
    result = TruthMirrorHandler._check_auth(handler)
    assert result is True


# 4. C9 Prompt Injection Sanitization Test
from truth_mirror.source_analyzer import _build_single_prompt
from truth_mirror.models import EvidenceItem

def test_c9_prompt_injection_sanitization():
    article = EvidenceItem(
        source_title="Title with ``` injection",
        source_type="journalism",
        publisher="TestNews",
        date="2026-07-24",
        url_or_id="https://test.com/news",
        excerpt="Excerpt with ``` and harmful instructions"
    )
    claim = "Claim with ``` and injection instructions"
    
    prompt = _build_single_prompt(article, claim)
    
    # Check that triple backticks are escaped
    assert "```" not in prompt
    assert "` ` `" in prompt
    
    # Check untrusted content wrappers
    assert "<untrusted_content>Claim with ` ` ` and injection instructions</untrusted_content>" in prompt
    assert "<untrusted_content>Title with ` ` ` injection</untrusted_content>" in prompt
    assert "<untrusted_content>Excerpt with ` ` ` and harmful instructions</untrusted_content>" in prompt
