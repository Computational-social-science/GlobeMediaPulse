import wn
import json
import os
import sys

def generate_vocabulary():
    print("Step 1: Downloading Open English Wordnet 2025+...")
    try:
        wn.download("oewn:2025-plus")
    except Exception as e:
        print(f"Standard download failed: {e}")
        print("Attempting direct download from URL...")
        try:
            # Try likely URLs for the Plus version
            urls_to_try = [
                "https://en-word.net/static/english-wordnet-2025-plus.xml.gz",
                "https://en-word.net/static/english-wordnet-plus-2025.xml.gz",
                "https://en-word.net/static/oewn-2025-plus.xml.gz"
            ]
            
            downloaded = False
            for url in urls_to_try:
                try:
                    print(f"Trying {url}...")
                    wn.download(url)
                    downloaded = True
                    break
                except Exception as e_url:
                    print(f"Failed to download from {url}: {e_url}")
            
            if not downloaded:
                # Fallback to standard 2025 if Plus fails, but user requested Plus
                print("Could not download Plus version. Falling back to standard 2025 (Core)...")
                wn.download("https://en-word.net/static/english-wordnet-2025.xml.gz")
                
        except Exception as e2:
             print(f"All download attempts failed: {e2}")
             return

    print("Step 2: Loading Wordnet...")
    
    # Debug: List all projects clearly
    projects = list(wn.projects())
    print(f"Total projects found: {len(projects)}")
    for p in projects:
        if 'oewn' in p.get('id', ''):
            print(f" - ID: {p.get('id')}, Version: {p.get('version')}, Label: {p.get('label')}")

    # Try to load 2025+ explicitly first
    oewn = None
    try:
        print("Attempting to load 'oewn:2025+'...")
        oewn = wn.Wordnet("oewn:2025+")
        print("Successfully loaded 'oewn:2025+'")
        output_version = "oewn:2025+"
    except Exception as e:
        print(f"Failed to load 'oewn:2025+': {e}")
        try:
            print("Attempting to load 'oewn:2025'...")
            oewn = wn.Wordnet("oewn:2025")
            print("Successfully loaded 'oewn:2025'")
            output_version = "oewn:2025"
        except Exception as e2:
             print(f"Failed to load 'oewn:2025': {e2}")
             # Fallback to just 'oewn' (latest)
             try:
                 print("Attempting to load 'oewn' (latest)...")
                 oewn = wn.Wordnet("oewn")
                 output_version = f"oewn:{oewn.version}"
                 print(f"Successfully loaded '{output_version}'")
             except Exception as e3:
                 print(f"Fatal error: Could not load any OEWN project: {e3}")
                 return

    print("Step 3: Extracting vocabulary with POS...")
    vocabulary_list = []
    words = list(oewn.words())
    print(f"Found {len(words)} word entries.")
    
    for w in words:
        # Extract lemma and POS. 
        # w.pos is typically 'n', 'v', 'a', 'r', 's'
        entry = {
            "id": w.id,
            "lemma": w.lemma(),
            "pos": w.pos
        }
        vocabulary_list.append(entry)
        
    # Sort by lemma then pos
    vocabulary_list.sort(key=lambda x: (x['lemma'], x['pos']))
    
    print(f"Total entries: {len(vocabulary_list)}")
    
    # Output structure
    output_data = {
        "meta": {
            "source": "Open English Wordnet",
            "version": output_version,
            "url": "https://github.com/globalwordnet/english-wordnet",
            "total_words": len(vocabulary_list),
            "note": "Includes part-of-speech (POS) information to match official word counts."
        },
        "words": vocabulary_list
    }
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    output_file = os.path.join("data", "english-wordnet-2025-plus.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"Success! Vocabulary saved to {output_file}")

if __name__ == "__main__":
    generate_vocabulary()
