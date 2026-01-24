
import json
import csv
import os
import sys
import wn
from wordfreq import zipf_frequency, word_frequency

def convert_to_csv():
    # Input/Output paths
    json_file = os.path.join("data", "english-wordnet-2025-plus.json")
    csv_file = os.path.join("data", "oewn_vocab_with_freq.csv")
    
    if not os.path.exists(json_file):
        print(f"Error: {json_file} not found. Please run generate_vocabulary.py first.")
        return

    print("Step 1: Reading JSON vocabulary...")
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        words = data.get("words", [])
    
    print(f"Loaded {len(words)} entries.")

    print("Step 2: Processing and enriching with word frequency...")
    
    enriched_data = []
    
    # Counter for progress
    count = 0
    total = len(words)
    
    for entry in words:
        lemma = entry['lemma']
        pos = entry['pos']
        # WN ID is useful for linking back
        wn_id = entry['id']
        
        # Get frequencies using wordfreq
        # zipf_frequency: log-scale (0-9)
        # word_frequency: decimal (0-1)
        freq_zipf = zipf_frequency(lemma, 'en', wordlist='large')
        freq_decimal = word_frequency(lemma, 'en', wordlist='large')
        
        enriched_data.append({
            "lemma": lemma,
            "pos": pos,
            "frequency_zipf": freq_zipf,
            "frequency_decimal": freq_decimal,
            "wn_id": wn_id
        })
        
        count += 1
        if count % 10000 == 0:
            print(f"Processed {count}/{total}...")

    print("Step 3: Writing to CSV...")
    # Sort by frequency (descending) then lemma
    enriched_data.sort(key=lambda x: (-x['frequency_zipf'], x['lemma']))
    
    fieldnames = ["lemma", "pos", "frequency_zipf", "frequency_decimal", "wn_id"]
    
    with open(csv_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched_data)
        
    print(f"Success! CSV saved to {csv_file}")
    print(f"Total rows: {len(enriched_data)}")

if __name__ == "__main__":
    convert_to_csv()
