import json
import os

DATA_PATH = r"D:\2026-AI4S\GlobeMediaPulse\data\countries_data.json"

NEW_ENTRIES = [
    {
        "code": "ASC",
        "code_alpha2": "AC",
        "name": "Ascension Island",
        "official_name": "Ascension Island",
        "lat": -7.9467,
        "lng": -14.3559,
        "region": "Africa",
        "subregion": "Saint Helena, Ascension and Tristan da Cunha"
    },
    {
        "code": "CPT",
        "code_alpha2": "CP",
        "name": "Clipperton Island",
        "official_name": "Clipperton Island",
        "lat": 10.2833,
        "lng": -109.2167,
        "region": "Americas",
        "subregion": "North America"
    },
    {
        "code": "TAA",
        "code_alpha2": "TA",
        "name": "Tristan da Cunha",
        "official_name": "Tristan da Cunha",
        "lat": -37.1052,
        "lng": -12.2777,
        "region": "Africa",
        "subregion": "Saint Helena, Ascension and Tristan da Cunha"
    },
    {
        "code": "DGA",
        "code_alpha2": "DG",
        "name": "Diego Garcia",
        "official_name": "Diego Garcia",
        "lat": -7.3195,
        "lng": 72.4228,
        "region": "Asia",
        "subregion": "South-Eastern Asia"
    },
    {
        "code": "EA",
        "code_alpha2": "EA",
        "name": "Ceuta & Melilla",
        "official_name": "Ceuta & Melilla",
        "lat": 35.8894,
        "lng": -5.3213,
        "region": "Africa",
        "subregion": "Northern Africa"
    },
    {
        "code": "IC",
        "code_alpha2": "IC",
        "name": "Canary Islands",
        "official_name": "Canary Islands",
        "lat": 28.2916,
        "lng": -16.6291,
        "region": "Africa",
        "subregion": "Northern Africa"
    },
    {
        "code": "UN",
        "code_alpha2": "UN",
        "name": "United Nations",
        "official_name": "United Nations",
        "lat": 40.7489,
        "lng": -73.9680,
        "region": "Americas",
        "subregion": "International"
    },
    {
        "code": "EU",
        "code_alpha2": "EU",
        "name": "European Union",
        "official_name": "European Union",
        "lat": 50.8503,
        "lng": 4.3517,
        "region": "Europe",
        "subregion": "Western Europe"
    }
]

def update_countries():
    if not os.path.exists(DATA_PATH):
        print(f"Error: {DATA_PATH} not found.")
        return

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    countries = data.get("COUNTRIES", [])
    existing_codes = {c.get("code") for c in countries}
    
    added_count = 0
    for entry in NEW_ENTRIES:
        if entry["code"] not in existing_codes:
            countries.append(entry)
            added_count += 1
            print(f"Added: {entry['name']} ({entry['code']})")
        else:
            print(f"Skipped: {entry['name']} ({entry['code']}) already exists")
            
    # Sort by name
    countries.sort(key=lambda x: x.get("name", ""))
    
    data["COUNTRIES"] = countries
    
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    print(f"Successfully updated countries data. Total count: {len(countries)}")
    
    # Validation
    if len(countries) == 258:
        print("✅ Validation PASSED: Count is 258.")
    else:
        print(f"⚠️ Validation WARNING: Count is {len(countries)}, expected 258.")

if __name__ == "__main__":
    update_countries()
