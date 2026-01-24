import nltk
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet
from backend.spell_checker import SpellChecker
import os

def get_wordnet_pos(treebank_tag):
    if treebank_tag.startswith('J'):
        return wordnet.ADJ
    elif treebank_tag.startswith('V'):
        return wordnet.VERB
    elif treebank_tag.startswith('N'):
        return wordnet.NOUN
    elif treebank_tag.startswith('R'):
        return wordnet.ADV
    else:
        return wordnet.NOUN

def test_debug():
    # Ensure resources
    try:
        nltk.data.find('corpora/wordnet')
    except LookupError:
        nltk.download('wordnet')
        nltk.download('omw-1.4') 

    lemmatizer = WordNetLemmatizer()
    checker = SpellChecker(dictionary_path=os.path.join("data", "symspell_freq_dict.txt"))

    words_to_test = [
        ("protects", "VBZ"),
        ("Decorations", "NNS"),
        ("staffing", "NN"), # or VBG
        ("fides", "NNS"),
        ("bona", "JJ"), # bona fides
    ]

    print("\n--- Debugging Lemmatization & Check ---")
    for word, tag in words_to_test:
        wn_pos = get_wordnet_pos(tag)
        lemma = lemmatizer.lemmatize(word, pos=wn_pos)
        lower_lemma = lemmatizer.lemmatize(word.lower(), pos=wn_pos)
        
        in_dict_direct = checker.check_word(word)
        in_dict_lemma = checker.check_word(lemma)
        in_dict_lower_lemma = checker.check_word(lower_lemma)
        
        print(f"Word: {word} ({tag}) -> POS: {wn_pos}")
        print(f"  Direct Check: {in_dict_direct}")
        print(f"  Lemma: {lemma} -> Check: {in_dict_lemma}")
        print(f"  Lower Lemma: {lower_lemma} -> Check: {in_dict_lower_lemma}")
        print("-" * 30)

if __name__ == "__main__":
    test_debug()
