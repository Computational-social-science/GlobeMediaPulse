import json
import logging
import os
import ast
import re
from typing import Dict, Optional, List
from pathlib import Path
from urllib.parse import urlparse

from backend.core.schemas import MediaSource, MediaTier
from backend.core.config import settings
from backend.operators.storage import storage_operator

logger = logging.getLogger(__name__)

class SourceClassifier:
    """
    Core Intelligence Operator for Media Source Classification and Stratification.
    
    Scientific Functionality:
    This class implements the "Tiered Media Layering Strategy" (Tier-0/1/2) fundamental to the 
    system's information propagation modeling. It classifies news sources based on their 
    global influence, reliability, and geographic scope.
    
    Algorithmic Logic:
    1.  **Seed-Based Initialization**: Loads a curated "Ground Truth" seed library from the 
        persistent store (Database) with a fail-safe fallback to a local JSON configuration.
        This ensures the system bootstraps with a verified set of high-authority nodes (Tier-0/1).
    2.  **Hierarchical Matching**: Implements a cascading matching algorithm:
        -   **Exact Domain Match**: O(1) lookup for known primary domains.
        -   **Subdomain Heuristic**: Identifies regional variants (e.g., `edition.cnn.com` -> `cnn.com`) 
            to correctly attribute them to the parent entity.
    3.  **Tier Definition**:
        -   **Tier-0 (Global Super-Nodes)**: Transnational wire services (Reuters, AP, AFP) and 
            global elite media (NYT, BBC).
        -   **Tier-1 (National Hubs)**: Dominant national broadcasters and newspapers (Le Monde, 
            Asahi Shimbun, CCTV).
        -   **Tier-2 (Regional/Local Nodes)**: Long-tail local media and specialized outlets.
            (Discovery of these nodes is driven by the "Snowball Sampling" algorithm).
            
    Attributes:
        sources (Dict[str, MediaSource]): In-memory hash map for fast classification lookups.
    """
    
    def __init__(self, seed_file: str = None):
        """
        Initializes the SourceClassifier.
        
        Args:
            seed_file (str, optional): Path to the JSON seed file. Defaults to `backend/resources/media_seeds.json`
                                       via `settings.BASE_DIR` for robust relative path resolution.
        """
        if seed_file is None:
            # Enforce Relative Path Rule: Construct path dynamically based on project root
            seed_file = os.path.join(settings.BASE_DIR, "backend", "resources", "media_seeds.json")
            
        self.seed_file = Path(seed_file)
        self.sources: Dict[str, MediaSource] = {}
        self._load_seeds()

    def _load_seeds(self):
        """
        Loads the media seed library into memory, prioritizing the Database as the source of truth.
        
        Loading Strategy (Resilience Pattern):
        1.  **Primary Source (DB)**: Attempts to fetch the latest curated list from the `media_sources` table.
            This allows for dynamic updates to the seed library without redeployment.
        2.  **Fallback Source (File)**: If the DB is unreachable or empty (bootstrap phase), falls back 
            to the static `media_seeds.json` file.
            
        Data Normalization:
        -   Ensures `country` fields are correctly mapped from `country_code` if missing.
        -   Instantiates `MediaSource` Pydantic models for strict type validation.
        """
        # 1. Try Loading from Database (Primary)
        try:
            db_sources = storage_operator.get_all_media_sources()
            if db_sources:
                for src_data in db_sources:
                    try:
                        # Normalize Country Field: Map 'country_code' to 'country' if needed
                        if 'country_code' in src_data and 'country' not in src_data:
                             src_data['country'] = src_data['country_code']
                        
                        source = MediaSource(**src_data)
                        self.sources[source.domain.lower()] = source
                    except Exception as e:
                        logger.warning(f"Skipping invalid DB source {src_data.get('domain')}: {e}")
                
                logger.info(f"Successfully loaded {len(self.sources)} media seeds from Database.")
                return
        except Exception as e:
            logger.warning(f"Failed to load seeds from DB ({e}). Falling back to static file.")

        loaded = self._load_seeds_from_json_file()
        if loaded >= settings.SEED_QUEUE_MIN:
            return

        loaded2 = self._load_seeds_from_seed_script()
        if loaded2:
            logger.info(f"Loaded {loaded2} media seeds from seed_media_sources.py fallback.")
            return

        logger.warning("No media seeds loaded. Classification capabilities will be limited.")

    def _load_seeds_from_json_file(self) -> int:
        if not self.seed_file.exists():
            return 0

        try:
            with open(self.seed_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded = 0
            for src_data in data.get("sources", []):
                try:
                    source = MediaSource(**src_data)
                    # Index by lower-case domain for case-insensitive O(1) lookup
                    self.sources[source.domain.lower()] = source
                    loaded += 1
                except Exception as e:
                    logger.error(f"Failed to parse source entry: {src_data}, error: {e}")
            
            if loaded:
                logger.info(f"Loaded {loaded} media seeds from JSON file {self.seed_file}")
            return loaded
            
        except Exception as e:
            logger.error(f"Failed to load media seeds from file: {e}")
            return 0

    def _load_seeds_from_seed_script(self) -> int:
        seed_py = Path(settings.BASE_DIR) / "backend" / "scripts" / "seed_media_sources.py"
        if not seed_py.exists():
            return 0
        try:
            text = seed_py.read_text(encoding="utf-8")
            m = re.search(
                r"SEED_DATA\s*=\s*(\[.*?\n\])\s*\n\s*def seed_media_sources",
                text,
                re.S,
            )
            if not m:
                return 0
            raw = ast.literal_eval(m.group(1))
            if not isinstance(raw, list):
                return 0
            loaded = 0
            seen: set[str] = set()
            for src in raw:
                if not isinstance(src, dict):
                    continue
                domain = src.get("domain")
                name = src.get("name")
                if not domain or not name:
                    continue
                domain = str(domain).lower().strip()
                if not domain or domain in seen:
                    continue
                seen.add(domain)
                payload = {
                    "domain": domain,
                    "name": str(name),
                    "tier": src.get("tier") or MediaTier.UNKNOWN.value,
                    "country": src.get("country_code") or src.get("country") or "UNK",
                    "country_name": src.get("country_name"),
                    "type": src.get("type"),
                    "language": src.get("language"),
                }
                try:
                    source = MediaSource(**payload)
                    self.sources[source.domain.lower()] = source
                    loaded += 1
                except Exception as e:
                    logger.error(f"Failed to parse seed script source {domain}: {e}")
            return loaded
        except Exception as e:
            logger.error(f"Failed to load media seeds from seed script: {e}")
            return 0

    def classify(self, url: str) -> Dict[str, Optional[str]]:
        """
        Classifies a given URL into a Media Tier and identifies its source domain.
        
        Methodology:
        1.  **URL Parsing**: Extracts the netloc (domain) from the URL.
        2.  **Exact Matching**: Checks against the in-memory `sources` index.
        3.  **Subdomain Aggregation**: Applies heuristic matching to map subdomains (e.g., `news.google.com`) 
            to their parent canonical domain in the seed library.
            
        Args:
            url (str): The URL of the article or source to classify.
            
        Returns:
            Dict[str, Optional[str]]: A dictionary containing:
                - 'tier': The classification tier (Tier-0, Tier-1, Tier-2, or Unknown).
                - 'source_domain': The canonical domain of the identified source.
                - 'country': The ISO country code of the source.
        """
        if not url:
            return {"tier": MediaTier.UNKNOWN.value, "source_domain": None}

        # Robust Domain Extraction
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception:
            return {"tier": MediaTier.UNKNOWN.value, "source_domain": None}

        # 1. Exact Match Strategy
        if domain in self.sources:
            return {
                "tier": self.sources[domain].tier.value, 
                "source_domain": domain,
                "country": self.sources[domain].country
            }

        # 2. Subdomain Heuristic Strategy
        # Handles cases like 'edition.cnn.com' mapping to 'cnn.com'
        for seed_domain, source in self.sources.items():
            if domain.endswith("." + seed_domain) or domain == seed_domain:
                return {
                    "tier": source.tier.value,
                    "source_domain": seed_domain,
                    "country": source.country
                }

        # 3. Default / Unknown
        # Currently defaults to UNKNOWN. Future iterations will integrate the "Snowball Sampling"
        # discovery mechanism here to dynamically identify and propose new Tier-2 candidates.
        return {"tier": MediaTier.UNKNOWN.value, "source_domain": domain}

# Global Singleton Instance
source_classifier = SourceClassifier()
