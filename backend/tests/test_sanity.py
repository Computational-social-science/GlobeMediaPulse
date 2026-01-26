
import pytest
from sqlalchemy import create_engine
from backend.core.config import settings

def test_sanity():
    """Basic sanity check to ensure testing environment is working."""
    assert True

def test_import_spacy():
    """Ensure Spacy can be imported without Pydantic errors."""
    import spacy
    nlp = spacy.blank("en")
    assert nlp is not None

def test_settings_load():
    """Ensure settings are loaded correctly."""
    assert settings.PROJECT_NAME == "GlobeMediaPulse"
