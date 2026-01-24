import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any

GEOJSON_URL = "https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json"
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "data"
CACHE_PATH = CACHE_DIR / "countries.geo.json"


def load_geojson() -> Optional[Dict[str, Any]]:
    """
    Load the world countries GeoJSON data.
    
    Tries to load from a local cache first. If the cache does not exist,
    it downloads the data from the remote URL and saves it to the cache.

    Returns:
        Optional[Dict[str, Any]]: The GeoJSON data dictionary, or None if loading fails.
    """
    if CACHE_PATH.exists():
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        response = requests.get(GEOJSON_URL, timeout=15)
        response.raise_for_status()
        geojson = response.json()
    except Exception:
        return None
    
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    return geojson


def get_authoritative_name_map() -> Dict[str, str]:
    """
    Create a mapping from country codes to authoritative country names.

    Uses the loaded GeoJSON data to build the map.

    Returns:
        Dict[str, str]: A dictionary mapping country codes (e.g., "USA") to names (e.g., "United States of America").
    """
    geojson = load_geojson()
    if not geojson:
        return {}
    name_map = {}
    for feature in geojson.get("features", []):
        code = feature.get("id")
        name = feature.get("properties", {}).get("name")
        if code and name:
            name_map[code] = name
    return name_map
