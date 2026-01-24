
import wn
import sys

try:
    # Try to load the project we know exists from previous turns
    # It was loaded as oewn:2025+ or oewn:2025
    # We'll just try to find it again logic from generate_vocabulary.py briefly
    projects = wn.projects()
    target = None
    for p in projects:
        if p['id'] == 'oewn' and p.get('version') == '2025+':
            target = "oewn:2025+"
            break
    if not target:
        target = "oewn:2025" # Fallback
    
    print(f"Loading {target}")
    ewn = wn.Wordnet(target)
    words = list(ewn.words())
    if words:
        w = words[0]
        print(f"First word: {w}")
        print(f"Dir(w): {dir(w)}")
        print(f"w.lemma(): {w.lemma()}")
        try:
            print(f"w.pos: {w.pos}")
        except:
            print("w.pos does not exist")
        
        # Check if we can find 'run'
        runs = list(ewn.words(lemma="run"))
        print(f"Words for 'run': {len(runs)}")
        for r in runs:
            print(f" - {r.lemma()} ({getattr(r, 'pos', 'N/A')}) ID: {r.id}")

except Exception as e:
    print(e)
