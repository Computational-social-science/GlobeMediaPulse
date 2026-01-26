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
