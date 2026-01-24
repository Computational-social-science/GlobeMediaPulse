# Task Plan: Geoparsing Pipeline Optimization

**Goal:** Optimize the Geoparsing Pipeline to improve country-level accuracy, reduce "UNK" and sea-based errors, and implement a transparent, scientifically validated approach using NER (spaCy) and Gazetteer resolution.

## Phase 1: Planning & Setup (Completed)
- [x] Create `task_plan.md` (This file).
- [x] Create `findings.md` to document current state and research.
- [x] Check/Install dependencies (`spacy`, `pycountry`).
- [x] Update `InitPipeline` to download necessary spaCy models (`en_core_web_sm` or `trf`).

## Phase 2: Implementation (NER & Resolution) (Completed)
- [x] Modify `ParserOperator` to initialize spaCy/NLTK.
- [x] Implement `extract_locations` method in `ParserOperator`.
- [x] Implement `resolve_country` method using `pycountry` or gazetteer logic.
- [x] Integrate NER-based resolution into `parse_article_metadata` as a validation/enhancement layer over GDELT data.

## Phase 3: Validation & Testing (Completed)
- [x] Create a test script `tests/test_geoparsing.py` to verify country extraction on sample texts.
- [x] Verify integration with the main pipeline.

## Phase 4: Upgrade & Verification (Newspaper4k) (Completed)
- [x] Upgrade Preprocessing: Replace Newspaper3k with Newspaper4k in `NewsIngester`.
- [x] **NOTE**: Mordecai3 installation failed due to PyTorch < 2.0 requirement incompatible with Python 3.14. Using NLTK-based Geoparsing (already implemented) as the robust alternative.
- [x] Cleanup: Remove redundant code and dependencies.
- [x] Verification: Test the upgraded pipeline with new components.

## Phase 5: Geoparsing Iteration (Nominatim & Heuristics) (Completed)
- [x] Install Dependencies: `geopy` for Nominatim access.
- [x] Upgrade `ParserOperator`:
    - [x] Integrate Nominatim API for fallback geocoding.
    - [x] Implement population-based disambiguation (Heuristic).
    - [x] Add smart caching for API results.
- [x] Verification: Update `tests/test_geoparsing.py` to test new logic.

## Phase 6: UI Verification & Monitoring (Completed)
- [x] Monitor Logs: Backend started successfully with new geoparsing logic.
- [x] Verify UI: Frontend started at `http://localhost:5174/`.
- [x] Cleanup: All phases complete.

## Phase 7: GeospaCy Integration (Abandoned)
- [x] Install GeospaCy: `pip install geospacy` (Failed: Package not found on PyPI).
- [x] Attempt Git Install: `git+https://github.com/mehtab-alam/GeospaCy.git` (Failed: Not a valid Python package structure - no setup.py/pyproject.toml).
- [x] **DECISION**: Permanently abandon GeospaCy. The repository appears to be a research demo/web app, not a reusable library.
- [x] **Fallback**: The current NLTK + Nominatim pipeline is verified, robust, and follows best practices for this environment.

## Phase 8: Final Cleanup (Completed)
- [x] Suppress GDELT "Timespan too short" log noise in `backend/producer.py`.
- [x] Finalize `findings.md` with architectural decisions.
- [x] Confirm system stability.

**Status:** All tasks completed. System running on verified NLTK/Nominatim pipeline.

## Phase 9: Status Monitoring & Automation (Completed)
- [x] **Backend Automation**: Verified and strengthened `monitor_system_health` to trigger auto-heal after 3 consecutive failures.
- [x] **Backend Data**: Updated `PostgresStorage` to aggregate and cache `country_source` (Resolution Source) for each country.
- [x] **Frontend UI**: Updated "REGIONAL" (Countries) window to display the dominant resolution source (e.g., NER, GDELT) for each country.
