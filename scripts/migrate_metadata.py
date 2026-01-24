import json
import re
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
FRONTEND_DATA_PATH = BASE_DIR / 'frontend/src/lib/data.js'
GEOJSON_PATH = BASE_DIR / 'backend/data/countries.geo.json'

def migrate():
    print(f"Reading frontend data from {FRONTEND_DATA_PATH}...")
    with open(FRONTEND_DATA_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract COUNTRIES array using regex
    match = re.search(r'COUNTRIES:\s*(\[\s*\{.*?\}\s*\])', content, re.DOTALL)
    if not match:
        print("Could not find COUNTRIES array in frontend/src/lib/data.js")
        return

    countries_json_str = match.group(1)
    # Fix JS object keys to be valid JSON (quote them)
    # This is a simple regex fix for keys like code: "AFG" -> "code": "AFG"
    countries_json_str = re.sub(r'(\w+):', r'"\1":', countries_json_str)
    
    try:
        countries_data = json.loads(countries_json_str)
        print(f"Parsed {len(countries_data)} countries from frontend data.")
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        return

    # Create a map for quick lookup
    # Using 'code' as key (which matches 'id' in GeoJSON)
    metadata_map = {c['code']: c for c in countries_data}

    print(f"Reading GeoJSON from {GEOJSON_PATH}...")
    with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
        geo_data = json.load(f)

    updated_count = 0
    for feature in geo_data['features']:
        iso_code = feature.get('id')
        if iso_code in metadata_map:
            meta = metadata_map[iso_code]
            # Update properties with lat, lng, region
            feature['properties']['lat'] = meta.get('lat')
            feature['properties']['lng'] = meta.get('lng')
            feature['properties']['region'] = meta.get('region')
            updated_count += 1
        else:
            print(f"Warning: No metadata found for {iso_code}")

    print(f"Updated {updated_count} features.")

    print(f"Saving updated GeoJSON to {GEOJSON_PATH}...")
    with open(GEOJSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(geo_data, f, indent=2, ensure_ascii=False)

    print("Migration complete.")

import os
import sys

# Add parent directory to path so we can import backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.data import DATA

def migrate():
    # ... logic ...
    pass

if __name__ == "__main__":
    migrate()
