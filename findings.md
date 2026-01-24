# Findings: Geoparsing Optimization

## Current State Analysis
- **ParserOperator (`backend/operators/parsing/parser_operator.py`)**:
    - Currently uses `FIPS_TO_ISO3` map for `sourcecountry`.
    - Fallback to TLD mapping.
    - No content analysis for location.
    - Issues: "Black-box" reliance on GDELT, high "UNK" rate, potential for sea-based coordinates.

## Requirements
- **Scientific Approach**: Use NER + Gazetteer.
- **Transparency**: Clear logic for country assignment.
- **Robustness**: Fallback chain (NER -> GDELT -> TLD).

## Strategy (Final Implemented Architecture)
1.  **NER**: **NLTK (MaxEnt NE Chunker)**
    *   *Decision*: Selected over `spacy` (incompatible with Python 3.14/Pydantic) and `GeospaCy` (failed installation/no package structure).
    *   *Role*: Extracts `GPE` (Geopolitical Entities) from article text.
2.  **Resolution Layer**:
    *   **Layer 1: Local Heuristics (Fastest)**: Instant lookup for major capital cities (Tokyo, Paris, etc.) -> Country Code.
    *   **Layer 2: PyCountry (Standard)**: Resolves standard country names.
    *   **Layer 3: Nominatim API (High Precision Fallback)**: Resolves difficult entities (e.g., "Lyon", "Manchester") using OpenStreetMap data.
        *   *Optimization*: Only queries "important" entities (capitalized, >3 chars).
        *   *Caching*: Redis caches successes for 7 days, failures for 1 hour.
3.  **Consensus Logic**:
    *   If NER+Resolution finds a country -> **Use it** (High Confidence).
    *   Else -> Fallback to GDELT `sourcecountry` (Medium Confidence).
    *   Else -> Fallback to TLD (Low Confidence).

## Dependencies
- `nltk` (NER)
- `pycountry` (ISO Codes)
- `geopy` (Nominatim API Client)
- `redis` (Caching)
