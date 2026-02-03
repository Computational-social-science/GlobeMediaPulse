import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def test_countries_count_is_258():
    """
    Verify that the global country/region count is exactly 258.
    This is a hard requirement for system consistency.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_path = os.path.join(project_root, "data", "countries_data.json")
    
    assert os.path.exists(data_path), "countries_data.json not found"
    
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    countries = data.get("COUNTRIES", [])
    assert len(countries) == 258, f"Expected 258 countries, found {len(countries)}"

def test_new_territories_present():
    """
    Verify that the 8 new territories are present in the dataset.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_path = os.path.join(project_root, "data", "countries_data.json")
    
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    countries = data.get("COUNTRIES", [])
    codes = {c.get("code") for c in countries}
    
    new_codes = {"ASC", "CPT", "TAA", "DGA", "EA", "IC", "UN", "EU"}
    missing = new_codes - codes
    assert not missing, f"Missing new territories: {missing}"

def test_linkage_attributes():
    """
    Verify that new entries have required attributes for linkage (lat, lng, region).
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_path = os.path.join(project_root, "data", "countries_data.json")
    
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    countries = data.get("COUNTRIES", [])
    country_map = {c.get("code"): c for c in countries}
    
    for code in ["ASC", "CPT", "TAA", "DGA", "EA", "IC", "UN", "EU"]:
        entry = country_map.get(code)
        assert entry is not None
        assert entry.get("lat") is not None
        assert entry.get("lng") is not None
        assert entry.get("region") is not None
