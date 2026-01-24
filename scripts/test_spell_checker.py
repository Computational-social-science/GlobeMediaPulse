import sys
import os
import asyncio

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from detect_errors import analyze_article_nlp
from spell_checker import SpellChecker

def test_spell_checker():
    print("Initializing SpellChecker...")
    checker = SpellChecker()
    
    test_sentences = [
        "President Zelenskyy met with Biden in Kyiv today.", # Names/Places
        "The COVID-19 pandemic caused global supply chain issues.", # Acronyms/Mixed case
        "NATO announced new measures for security.", # Acronyms
        "The iPhone 15 was released by Apple.", # CamelCase/Brands
        "This is a teest of the speling cheker.", # Real errors
        "The GDP of the USA increased by 2%.", # Acronyms
        "He posted on LinkedIn about the AI revolution.", # CamelCase/Tech
        "The algorithm uses PyTorch and TensorFlow." # Tech names
    ]

    print("\nRunning tests...")
    
    # Initialize globals for analyze_article_nlp
    # We can pass a dummy path or create a temp file if we want to test whitelist, 
    # but here we focus on code logic.
    from detect_errors import init_worker, analyze_article_nlp # type: ignore
    
    # Create a dummy whitelist file
    with open("temp_whitelist.txt", "w") as f:
        f.write("whitelist_test_word\n")
    
    init_worker("temp_whitelist.txt")
    
    for sentence in test_sentences:
        print(f"\nContext: {sentence}")
        
        # Mock Article needs 'content' key as per analyze_article_nlp implementation
        article = {"content": sentence, "title": "Test", "url": "http://test.com"}
        
        # 1. Extract Candidates (NLP Phase)
        result = analyze_article_nlp(article)
        
        if not result or not result.get("candidates"):
            print("  Result: No candidates for checking (Filtered by NLP/Heuristics)")
            continue
            
        candidates = result.get("candidates", [])
        print(f"  Candidates extracted: {len(candidates)}")
        
        found_errors = []
        for cand in candidates:
            word = cand["word"]
            variants = cand["variants"]
            
            # 2. Check Candidates (Spell Check Phase)
            is_valid = False
            for v in variants:
                if checker.check_word(v):
                    is_valid = True
                    break
            
            if not is_valid:
                # It's an error!
                suggestions = checker.suggest(word)
                top_sugg = suggestions[0][0] if suggestions else "None"
                found_errors.append(f"'{word}' -> '{top_sugg}'")
        
        if not found_errors:
            print("  Result: All candidates valid (Correct)")
        else:
            print(f"  Result: Found {len(found_errors)} errors:")
            for err in found_errors:
                print(f"    - {err}")

    # Cleanup
    if os.path.exists("temp_whitelist.txt"):
        os.remove("temp_whitelist.txt")

if __name__ == "__main__":
    test_spell_checker()
