import json
from pathlib import Path
from typing import Dict, Any, List

# Paths
BASE_DIR = Path(__file__).parent
GEOJSON_PATH = BASE_DIR.parent / 'data' / 'countries.geo.json'
CONSTANTS_PATH = BASE_DIR.parent / 'data' / 'constants.json'

def load_data() -> Dict[str, Any]:
    """
    Load static data required for the application.

    This includes:
    1. Country metadata from GeoJSON (code, name, lat, lng, region).
    2. Application constants from a JSON file.

    Returns:
        Dict[str, Any]: A dictionary containing loaded data keys (e.g., "COUNTRIES").
    """
    data = {}
    
    # Load GeoJSON and extract Countries
    countries: List[Dict[str, Any]] = []
    if GEOJSON_PATH.exists():
        with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
            geo_data = json.load(f)
        
        for feature in geo_data.get('features', []):
            props = feature.get('properties', {})
            # Ensure we have the required fields
            country = {
                "code": feature.get('id'),
                "name": props.get('name'),
                "lat": props.get('lat', 0.0),
                "lng": props.get('lng', 0.0),
                "region": props.get('region', 'Unknown')
            }
            countries.append(country)
            
    data["COUNTRIES"] = countries

    # Load Constants
    if CONSTANTS_PATH.exists():
        with open(CONSTANTS_PATH, 'r', encoding='utf-8') as f:
            constants = json.load(f)
            data.update(constants)
            
    return data

# Expose DATA dictionary
DATA = load_data()
