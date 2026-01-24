
import logging
import os
from backend.core.config import settings
from backend.operators.storage import storage_operator
from backend.core.shared_state import country_geo_map

logger = logging.getLogger(__name__)

class InitPipeline:
    """
    Initialization Pipeline responsible for setting up the application environment.
    Handles directory creation and global state initialization.
    """
    def __init__(self):
        pass

    def run(self):
        """
        Execute the initialization steps.
        
        Steps:
        1. Create necessary data directories.
        2. Initialize global shared state (e.g., Country Geo Map).
        """
        logger.info("Running Initialization Pipeline...")
        
        # 1. Directory Setup
        self._ensure_dirs()
        
        # 2. Global State Setup
        self._init_global_state()
        
        logger.info("Initialization complete.")

    def _ensure_dirs(self):
        """Create necessary data directories if they don't exist."""
        os.makedirs(settings.DATA_DIR, exist_ok=True)

    def _init_global_state(self):
        """Populate global shared state (country_geo_map) from storage."""
        # Populate country_geo_map from storage
        count = 0
        for c_name, data in storage_operator.countries_map.items():
            country_geo_map[data["code"]] = {"lat": data["lat"], "lng": data["lng"], "name": c_name}
            # Also map uppercase name
            country_geo_map[c_name.upper()] = {"lat": data["lat"], "lng": data["lng"], "name": c_name}
            count += 1
        logger.info(f"Initialized Country Geo Map with {count} entries.")

init_pipeline = InitPipeline()
