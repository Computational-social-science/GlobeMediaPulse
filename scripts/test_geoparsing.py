
import sys
import os
import logging
from urllib.parse import urlparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.operators.intelligence.geoparsing import GeoParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestGeoParser")

def test_geoparsing():
    print("Initializing GeoParser...")
    # Use default Redis URL from environment or localhost
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    geo_parser = GeoParser(redis_url)

    test_cases = [
        {
            "url": "https://www.bbc.com/news/world-europe-12345",
            "text": "London is the capital of the United Kingdom. The Prime Minister announced new policies today.",
            "existing_code": "GBR", # Simulate Classifier/TLD match
            "expected": "GBR"
        },
        {
            "url": "https://www.unknown-source.com/article",
            "text": "Tokyo is a busy city in Japan. The yen has strengthened.",
            "existing_code": "UNK",
            "expected": "JPN" # Text extraction should find Japan
        },
        {
            "url": "https://www.conflict-example.com",
            "text": "Paris is beautiful this time of year.",
            "existing_code": "USA", # Simulate wrong classifier
            "expected": "USA" # Majority consensus might be tricky here. 
                              # Existing=USA, Text=FRA. WHOIS=? 
                              # If WHOIS fails, it's a tie. 
                              # If tie, currently my logic picks one (most common).
        }
    ]

    print("\nRunning Tests...")
    
    # Debug Geograpy3 directly
    print("\n--- Debugging Geograpy3 Direct Call ---")
    try:
        import geograpy
        import traceback
        text = "Tokyo is a busy city in Japan."
        print(f"Text: {text}")
        places = geograpy.get_geoPlace_context(text=text)
        print(f"Countries found: {places.countries}")
    except Exception:
        traceback.print_exc()
    print("---------------------------------------")

    for case in test_cases:
        print(f"\nTesting: {case['url']}")
        country, confidence = geo_parser.resolve(
            url=case['url'],
            text=case['text'],
            tier=2,
            existing_code=case['existing_code']
        )
        print(f"Result: {country} (Confidence: {confidence})")
        
        # Check against expectation (loose check as WHOIS might interfere in real run)
        if case['expected'] == country:
            print("✅ Match Expected")
        else:
            print(f"⚠️ Mismatch (Expected {case['expected']}) - Check logic/WHOIS")

    # Test Caching
    print("\nTesting Cache...")
    url = "https://www.bbc.com/news/test-cache"
    domain = urlparse(url).netloc
    
    # 1. Force cache set (simulated via resolve)
    geo_parser.resolve(url, "United Kingdom", tier=0, existing_code="GBR")
    
    # 2. Check direct cache
    cached = geo_parser.get_cached_location(domain)
    print(f"Cache for {domain}: {cached}")
    if cached == "GBR":
        print("✅ Cache Hit")
    else:
        print("❌ Cache Miss")

if __name__ == "__main__":
    test_geoparsing()
