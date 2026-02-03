import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.operators.intelligence.geo_resolver import GeoResolver, TLDStrategy, WHOISStrategy

@pytest.fixture
def resolver():
    return GeoResolver()

def test_tld_resolution(resolver):
    # Standard ccTLDs
    assert resolver.resolve("http://www.bbc.co.uk")['country_code'] == 'GBR'
    assert resolver.resolve("https://lemonde.fr")['country_code'] == 'FRA'
    assert resolver.resolve("http://news.cn")['country_code'] == 'CHN'
    
    # Generic TLDs (should be UNK or resolved by other means if implemented)
    assert resolver.resolve("http://example.com")['country_code'] == 'UNK'

def test_overrides(resolver):
    # Verify overrides are working
    assert resolver.resolve("http://tech.io")['country_code'] == 'UNK' # .io is overridden to UNK
    assert resolver.resolve("http://startup.ai")['country_code'] == 'UNK' # .ai is overridden to UNK
    assert resolver.resolve("http://europa.eu")['country_code'] == 'EU'

def test_strategy_metadata(resolver):
    # Use a domain that is NOT in Heuristic overrides but IS in TLD map
    res = resolver.resolve("https://www.government.se")
    assert res['confidence'] > 0.8
    assert "TLD" in [log.split(':')[0] for log in res['logs']]
    assert res['duration_ms'] >= 0

def test_invalid_inputs(resolver):
    assert resolver.resolve("not_a_url")['country_code'] == 'UNK'
    assert resolver.resolve("")['country_code'] == 'UNK'

# Note: We skip WHOIS tests in CI usually because they hit network and are slow/flaky
# but here is a manual one if needed
@pytest.mark.skip(reason="Network dependent")
def test_whois_fallback(resolver):
    # A domain with .com but clear registration
    res = resolver.resolve("http://nytimes.com")
    # This might fail if WHOIS is blocked or returns privacy protection
    assert res['country_code'] in ['USA', 'UNK']
