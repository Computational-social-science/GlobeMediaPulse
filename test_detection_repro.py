
import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.operators.detection import detector_operator

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_detection():
    print("Testing detection...")
    
    # Test case 1: Obvious errors
    articles = [
        {
            "title": "Test Article",
            "content": "Thsi is a tset sentence with some erors. The quick brown fox jumps over the lazy dog.",
            "url": "http://test.com/1",
            "country": "US",
            "date": "2017-01-01T00:00:00Z"
        },
        {
            "title": "Real News Sample",
            "content": "The governmnet announced new polices regarding climate change. Presidnet Trump said he would veto the bill.",
            "url": "http://test.com/2",
            "country": "US",
            "date": "2017-01-01T00:00:00Z"
        }
    ]
    
    print(f"Detecting errors in {len(articles)} articles...")
    results = detector_operator.detect_batch(articles)
    
    for res in results:
        print(f"\nArticle: {res.get('title')}")
        errors = res.get('errors', [])
        print(f"Errors found: {len(errors)}")
        for err in errors:
            print(f"  - {err['word']} -> {err['suggestion']} (Context: {err['context']})")
            
        skipped = res.get('skipped', [])
        print(f"Skipped items: {len(skipped)}")
        # for skip in skipped[:5]:
        #    print(f"  - {skip['word']} ({skip['reason']})")

if __name__ == "__main__":
    test_detection()
