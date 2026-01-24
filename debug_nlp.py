import sys
import os
import nltk
sys.path.append('.')
from backend.detect_errors import analyze_article_nlp, init_worker
from backend.spell_checker import SpellChecker

def debug_nlp():
    # 1. Setup
    whitelist_path = os.path.join("data", "whitelist.txt")
    dict_path = os.path.join("data", "symspell_freq_dict.txt")
    
    print("--- Initializing Worker ---")
    init_worker(whitelist_path)
    
    print("--- Initializing SpellChecker ---")
    spell_checker = SpellChecker(dictionary_path=dict_path)
    
    article = {
        "url": "http://test.com/typo-test",
        "title": "Test Article with Typos",
        "content": "Teh goverment announced a new policy today. It was vary good.",
        "date": "2024-01-01T00:00:00",
        "scraped_at": "2024-01-01T00:00:00",
        "word_count": 10
    }
    
    print(f"\n--- Analyzing Article: '{article['content']}' ---")
    
    # Debug: Print raw tokens/tags
    sentences = nltk.sent_tokenize(article['content'])
    print(f"DEBUG: Found {len(sentences)} sentences.")
    for sent in sentences:
        tokens = nltk.word_tokenize(sent)
        tagged = nltk.pos_tag(tokens)
        print(f"DEBUG SENTENCE: {sent}")
        print(f"DEBUG TAGS: {tagged}")
        chunked = nltk.ne_chunk(tagged)
        print(f"DEBUG CHUNKED: {chunked}")

    # 2. Run NLP Analysis
    res = analyze_article_nlp(article)
    
    if not res:
        print("NLP Analysis returned None")
        return

    candidates = res.get("candidates", [])
    skipped = res.get("skipped", [])
    
    print(f"\nCandidates found: {len(candidates)}")
    for c in candidates:
        word = c['word']
        is_valid = spell_checker.check_word(word)
        print(f" - Word: '{word}', Tag: {c['tag']}, Lemma: {c['lemma']}, Valid in Dict: {is_valid}")
        
    print(f"\nSkipped items: {len(skipped)}")
    for s in skipped:
        print(f" - Word: '{s['word']}', Reason: {s['reason']}, Tag: {s['tag']}")

    # 3. Direct Dictionary Check
    print("\n--- Direct Dictionary Check ---")
    words_to_check = ["Teh", "teh", "goverment", "vary"]
    for w in words_to_check:
        print(f"'{w}': {spell_checker.check_word(w)}")

if __name__ == "__main__":
    debug_nlp()
