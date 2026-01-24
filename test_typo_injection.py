import sys
import os
sys.path.append('.')
from backend.detect_errors import detect_errors_batch
from backend.spell_checker import SpellChecker
from backend.storage import DataStorage

def test_injection():
    # 1. Setup
    db = DataStorage()
    dict_path = os.path.join("data", "symspell_freq_dict.txt")
    spell_checker = SpellChecker(dictionary_path=dict_path)
    
    # 2. Create dummy article with known typo
    # "Teh" -> The (Common typo)
    # "goverment" -> government
    article = {
        "url": "http://test.com/typo-test",
        "title": "Test Article with Typos",
        "content": "Teh goverment announced a new policy today. It was vary good.",
        "date": "2024-01-01T00:00:00",
        "scraped_at": "2024-01-01T00:00:00",
        "word_count": 10
    }
    
    print("Injecting article:", article["content"])
    
    # 3. Run Detection
    results = detect_errors_batch([article], spell_checker)
    processed_article = results[0]
    
    errors = processed_article.get("errors", [])
    print(f"Found {len(errors)} errors.")
    for e in errors:
        print(f" - {e['word']} -> {e['candidates']}")
        
    # 4. Save to DB
    print("Saving to DB...")
    db.save_articles([processed_article])
    
    # 5. Verify DB
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM error_events WHERE url = %s", (article["url"],))
        count = cur.fetchone()[0]
        print(f"DB Error Count for this URL: {count}")
        
        if count > 0:
            print("SUCCESS: Error events stored correctly.")
        else:
            print("FAILURE: No error events found in DB.")

if __name__ == "__main__":
    test_injection()
