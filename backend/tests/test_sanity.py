import os
import sys

import pytest
from sqlalchemy import create_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import settings

def test_sanity():
    """Basic sanity check to ensure testing environment is working."""
    assert True

def test_import_spacy():
    """Ensure Spacy can be imported without Pydantic errors."""
    if sys.version_info >= (3, 14):
        pytest.skip("Spacy/Pydantic v1 is incompatible with Python 3.14+")
    import spacy
    nlp = spacy.blank("en")
    assert nlp is not None

def test_settings_load():
    """Ensure settings are loaded correctly."""
    assert settings.PROJECT_NAME == "GlobeMediaPulse"

def test_database_url_normalization():
    raw = os.getenv("DATABASE_URL")
    if raw and raw.startswith("postgres://"):
        assert settings.DATABASE_URL.startswith("postgresql://")

def test_countries_data_has_key_territories():
    import json

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_json_path = os.path.join(project_root, "data", "countries_data.json")
    geojson_paths = [
        os.path.join(project_root, "backend", "data", "countries.geo.json"),
        os.path.join(project_root, "backend", "core", "data", "countries.geo.json"),
    ]

    codes = set()
    if os.path.exists(data_json_path):
        with open(data_json_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        countries = payload.get("COUNTRIES", [])
        codes = {c.get("code") for c in countries if isinstance(c, dict)}
    else:
        geojson_path = next((p for p in geojson_paths if os.path.exists(p)), None)
        assert geojson_path is not None
        with open(geojson_path, "r", encoding="utf-8") as f:
            geojson = json.load(f)
        codes = {feature.get("id") for feature in geojson.get("features", []) if isinstance(feature, dict)}

    assert {"BMU", "GRL", "GUM"}.issubset(codes)
