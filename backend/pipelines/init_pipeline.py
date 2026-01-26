
import logging
import os
from backend.core.config import settings
from backend.operators.storage import storage_operator
from backend.core.shared_state import country_geo_map

logger = logging.getLogger(__name__)

class InitPipeline:
    """
    Initialization pipeline for environment bootstrap and shared-state hydration.

    Research motivation: ensure a consistent initialization map
    $m: \mathcal{C} \rightarrow \mathbb{R}^2$ from country codes to geo-centroids,
    which stabilizes downstream spatial joins.
    """
    def __init__(self):
        pass

    def run(self):
        """
        Execute initialization steps.

        Steps:
        1. Ensure data directories exist.
        2. Populate shared state for geographic lookup.
        """
        logger.info("Running Initialization Pipeline...")
        self._ensure_dirs()
        self._init_global_state()
        logger.info("Initialization complete.")

    def _ensure_dirs(self):
        """
        Create required data directories.

        Ensures $D_{\mathrm{data}}$ exists for downstream persistence.
        """
        os.makedirs(settings.DATA_DIR, exist_ok=True)

    def _init_global_state(self):
        """
        Populate global shared state for geo lookups.

        Builds a mapping for both ISO codes and uppercase names to
        reduce lookup variance $\mathbb{V}[\hat{g}(c)]$ under noisy inputs.
        """
        count = 0
        for c_name, data in storage_operator.countries_map.items():
            country_geo_map[data["code"]] = {"lat": data["lat"], "lng": data["lng"], "name": c_name}
            country_geo_map[c_name.upper()] = {"lat": data["lat"], "lng": data["lng"], "name": c_name}
            count += 1
        logger.info(f"Initialized Country Geo Map with {count} entries.")

init_pipeline = InitPipeline()
