import json
import logging
import os
from typing import Dict, Optional, List
from pathlib import Path

from backend.core.schemas import MediaSource, MediaTier
from backend.core.config import settings
from backend.operators.storage import storage_operator

logger = logging.getLogger(__name__)

class SourceClassifier:
    """
    Classifies news sources into tiers (Tier-0, Tier-1, Tier-2) based on a seed library.
    Implements the "Tier-0 -> Tier-1 -> Tier-2" traceable diffusion graph strategy.
    """
    
    def __init__(self, seed_file: str = None):
        if seed_file is None:
            # Use absolute path based on settings.BASE_DIR
            seed_file = os.path.join(settings.BASE_DIR, "backend", "resources", "media_seeds.json")
            
        self.seed_file = Path(seed_file)
        self.sources: Dict[str, MediaSource] = {}
        self._load_seeds()

    def _load_seeds(self):
        """Loads the media seed library from DB (primary) or JSON (fallback)."""
        # 1. Try Loading from Database
        try:
            db_sources = storage_operator.get_all_media_sources()
            if db_sources:
                for src_data in db_sources:
                    try:
                        # Map DB fields to Schema if necessary (schema matches mostly)
                        # DB has 'tier' as string "Tier-0", schema expects MediaTier enum
                        # src_data['tier'] is likely string, MediaSource handles it if valid
                        source = MediaSource(**src_data)
                        self.sources[source.domain.lower()] = source
                    except Exception as e:
                        logger.warning(f"Skipping invalid DB source {src_data.get('domain')}: {e}")
                
                logger.info(f"Loaded {len(self.sources)} media seeds from Database.")
                return
        except Exception as e:
            logger.warning(f"Failed to load seeds from DB ({e}). Falling back to file.")

        # 2. Fallback to JSON File
        if not self.seed_file.exists():
            logger.warning(f"Media seed file not found at {self.seed_file}. Classification will be limited.")
            return

        try:
            with open(self.seed_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            for src_data in data.get("sources", []):
                try:
                    source = MediaSource(**src_data)
                    # Index by domain for fast lookup
                    self.sources[source.domain.lower()] = source
                except Exception as e:
                    logger.error(f"Failed to parse source entry: {src_data}, error: {e}")
            
            logger.info(f"Loaded {len(self.sources)} media seeds from JSON file {self.seed_file}")
            
        except Exception as e:
            logger.error(f"Failed to load media seeds from file: {e}")

    def classify(self, url: str) -> Dict[str, str]:
        """
        Classifies a URL based on the seed library.
        Returns a dictionary with 'tier' and 'source_domain'.
        """
        if not url:
            return {"tier": MediaTier.UNKNOWN.value, "source_domain": None}

        # Simple domain extraction (can be improved with tldextract)
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception:
            return {"tier": MediaTier.UNKNOWN.value, "source_domain": None}

        # 1. Exact Match
        if domain in self.sources:
            return {
                "tier": self.sources[domain].tier.value, 
                "source_domain": domain,
                "country": self.sources[domain].country
            }

        # 2. Subdomain Match (e.g. edition.cnn.com -> cnn.com)
        # This is a basic heuristic.
        for seed_domain, source in self.sources.items():
            if domain.endswith("." + seed_domain) or domain == seed_domain:
                return {
                    "tier": source.tier.value,
                    "source_domain": seed_domain,
                    "country": source.country
                }

        # Default to Unknown if not in seed library
        # In the future, Tier-2 logic can be added here (e.g. unknown but localized domains)
        return {"tier": MediaTier.UNKNOWN.value, "source_domain": domain}

# Global instance
source_classifier = SourceClassifier()
