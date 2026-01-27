import json
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
COUNTRIES_DATA_PATH = BASE_DIR / 'data/countries_data.json'
CONSTANTS_PATH = BASE_DIR / 'backend/data/constants.json'
OUTPUT_PATH = BASE_DIR / 'frontend/src/lib/data.js'

def build_frontend_data():
    print("Building frontend data...")
    
    data = {}
    
    # 1. Process Countries from countries_data.json
    countries = []
    if COUNTRIES_DATA_PATH.exists():
        with open(COUNTRIES_DATA_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        items = raw.get("COUNTRIES") if isinstance(raw, dict) else raw
        if isinstance(items, list):
            for entry in items:
                if not isinstance(entry, dict):
                    continue
                code = entry.get("code")
                name = entry.get("name")
                lat = entry.get("lat")
                lng = entry.get("lng")
                if not code or not name or lat is None or lng is None:
                    continue
                code_alpha2 = entry.get("code_alpha2")
                countries.append({
                    "code": str(code).upper(),
                    "code_alpha2": str(code_alpha2).upper() if code_alpha2 else None,
                    "name": name,
                    "lat": float(lat),
                    "lng": float(lng),
                    "region": entry.get("region") or "Unknown"
                })
        print(f"Loaded {len(countries)} countries from countries_data.json.")
    else:
        print("Warning: data/countries_data.json not found.")
        
    data["COUNTRIES"] = countries

    # 2. Process Constants
    if CONSTANTS_PATH.exists():
        with open(CONSTANTS_PATH, 'r', encoding='utf-8') as f:
            constants = json.load(f)
            data.update(constants)
        print(f"Loaded constants: {list(constants.keys())}")
    else:
        print("Warning: Constants file not found.")

    # 3. Write to JS file
    js_content = f"// This file is generated at build time. DO NOT EDIT MANUALLY.\n"
    js_content += f"// Source: data/countries_data.json, backend/data/constants.json\n\n"
    js_content += f"export const DATA = {json.dumps(data, indent=4)};\n"
    
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(js_content)
        
    print(f"Successfully wrote data to {OUTPUT_PATH}")

if __name__ == "__main__":
    build_frontend_data()
