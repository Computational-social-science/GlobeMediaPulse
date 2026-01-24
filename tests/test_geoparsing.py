import asyncio
import sys
import os
import nltk

import logging

# Configure logging to see ParserOperator warnings
logging.basicConfig(level=logging.INFO)

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.operators.parsing.parser_operator import ParserOperator

import random

async def test_geoparsing():
    # Ensure NLTK resources
    for r in ['punkt', 'averaged_perceptron_tagger', 'maxent_ne_chunker', 'words']:
        try:
            nltk.data.find(f'tokenizers/{r}' if r == 'punkt' else f'help/{r}' if r == 'tagsets' else f'chunkers/{r}' if r == 'maxent_ne_chunker' else f'corpora/{r}' if r == 'words' else f'taggers/{r}')
        except LookupError:
            print(f"Downloading {r}...")
            nltk.download(r, quiet=True)

    parser = ParserOperator()
    
    # Generate random suffix to bypass Redis cache
    run_id = random.randint(1000, 9999)
    print(f"Run ID: {run_id}")
    
    print("Running Geoparsing Tests...")
    
    # Test Case 1: Strong NER Signal
    # Note: Text needs to be > 100 chars to trigger NER as per ParserOperator logic
    text_france = "The event took place in Paris, France during the summer olympics. " * 3
    
    # Debug: Check extraction directly
    extracted = parser._extract_locations(text_france)
    print(f"Debug Extracted: {extracted}")
    
    import pycountry
    try:
        c = pycountry.countries.lookup("France")
        print(f"Debug pycountry: {c.alpha_3}")
    except Exception as e:
        print(f"Debug pycountry failed: {e}")

    resolved = await parser._resolve_country_from_text(text_france)
    print(f"Debug Resolved: {resolved}")
    
    article_empty = {}
    res_france = await parser.parse_article_metadata(article_empty, f"http://test.com/{run_id}/1", text_france)
    print(f"Test 1 (France): {res_france['country']} (Expected: FRA)")
    assert res_france['country'] == "FRA"

    # Test Case 2: NER Conflict with GDELT (NER wins)
    text_japan = "Tokyo authorities announced new measures today. " * 3
    article_us = {"sourcecountry": "US"}
    res_japan = await parser.parse_article_metadata(article_us, f"http://test.com/{run_id}/2", text_japan)
    print(f"Test 2 (Japan vs US): {res_japan['country']} (Expected: JPN)")
    assert res_japan['country'] == "JPN"

    # Test Case 3: No NER, GDELT Fallback
    text_generic = "The economy is growing steadily."
    article_us = {"sourcecountry": "US"}
    res_fallback = await parser.parse_article_metadata(article_us, f"http://test.com/{run_id}/3", text_generic)
    print(f"Test 3 (Fallback): {res_fallback['country']} (Expected: USA)")
    assert res_fallback['country'] == "USA"

    # Test Case 4: Ambiguous / No Signal -> UNK
    text_none = "Nothing specific here."
    article_none = {}
    res_unk = await parser.parse_article_metadata(article_none, f"http://test.com/{run_id}/4", text_none)
    print(f"Test 4 (UNK): {res_unk['country']} (Expected: UNK)")
    assert res_unk['country'] == "UNK"

    # Test Case 5: Nominatim Fallback (Requires Internet)
    # "Lyon" is not in city_map, but Nominatim should find it as France
    text_lyon = "The conference was held in Lyon." * 5
    # Force run without NER filtering first to test resolver logic if NER extracts "Lyon"
    # Actually, NER should extract Lyon.
    
    try:
        res_lyon = await parser.parse_article_metadata(article_empty, f"http://test.com/{run_id}/5", text_lyon)
        print(f"Test 5 (Lyon -> Nominatim): {res_lyon['country']} (Expected: FRA)")
        # Note: This might fail if API is down or rate limited, so we soft assert
        if res_lyon['country'] == "FRA":
            print("PASS: Nominatim resolved Lyon correctly.")
        else:
            print(f"WARN: Nominatim failed or returned {res_lyon['country']}")
    except Exception as e:
        print(f"WARN: Nominatim test error: {e}")

    print("All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_geoparsing())
