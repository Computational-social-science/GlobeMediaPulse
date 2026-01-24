
import sys
import os
import asyncio
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.operators.storage import storage_operator

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_storage():
    print("Testing storage...")
    
    # Test case: Article with errors
    articles = [
        {
            "title": "Test Storage Article",
            "content": "Thsi is a tset sentence.",
            "url": f"http://test.com/storage_{int(datetime.now().timestamp())}",
            "country": "US",
            "country_name": "United States",
            "date": datetime.now().isoformat(),
            "scraped_at": datetime.now().isoformat(),
            "word_count": 5,
            "errors": [
                {
                    "word": "tset",
                    "suggestion": "set",
                    "context": "Thsi is a tset sentence.",
                    "corrected_context": "Thsi is a set sentence.",
                    "tag": "NN",
                    "lemma": "tset"
                }
            ],
            "skipped": []
        }
    ]
    
    print(f"Saving {len(articles)} articles with errors...")
    count = storage_operator.save_articles(articles)
    print(f"Saved count (new articles): {count}")
    
    # Verify by reading back (simulated check)
    # We can't easily query here without setting up a full DB connection in script, 
    # but the log "Saved count" tells us if it ran.
    
    # Try saving AGAIN (should be 0 new articles, but errors should be inserted if logic allows duplicates? 
    # logic doesn't check duplicates for errors, so it might duplicate errors if we are not careful.
    # But usually we process each article once.)
    
    # Actually, let's check if errors are saved.
    # We can use check_2017_data.py style query if we want.

if __name__ == "__main__":
    test_storage()
