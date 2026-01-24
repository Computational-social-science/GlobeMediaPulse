import json
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
GEOJSON_PATH = BASE_DIR / 'backend/data/countries.geo.json'
CONSTANTS_PATH = BASE_DIR / 'backend/data/constants.json'
OUTPUT_PATH = BASE_DIR / 'frontend/src/lib/data.js'

def build_frontend_data():
    print("Building frontend data...")
    
    data = {}
    
    # 1. Process Countries from GeoJSON
    countries = []
    if GEOJSON_PATH.exists():
        with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
            geo_data = json.load(f)
        
        for feature in geo_data.get('features', []):
            props = feature.get('properties', {})
            countries.append({
                "code": feature.get('id'),
                "name": props.get('name'),
                "lat": props.get('lat', 0.0),
                "lng": props.get('lng', 0.0),
                "region": props.get('region', 'Unknown')
            })
        print(f"Loaded {len(countries)} countries from GeoJSON.")
    else:
        print("Warning: GeoJSON file not found.")
        
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
    js_content += f"// Source: backend/data/countries.geo.json, backend/data/constants.json\n\n"
    js_content += f"export const DATA = {json.dumps(data, indent=4)};\n"
    
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(js_content)
        
    print(f"Successfully wrote data to {OUTPUT_PATH}")

if __name__ == "__main__":
    build_frontend_data()
