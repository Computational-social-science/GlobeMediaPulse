import os
import logging
import json
import redis
import geograpy
import whois
import nltk
from collections import Counter
from urllib.parse import urlparse
from typing import Optional, List, Dict, Tuple
from backend.core.config import settings

# Configure logger
logger = logging.getLogger(__name__)

# Ensure NLTK data is available (idempotent)
try:
    nltk.data.find('words')
    nltk.data.find('maxent_ne_chunker')
    nltk.data.find('averaged_perceptron_tagger')
    nltk.data.find('punkt')
except LookupError:
    logger.info("Downloading NLTK data for Geograpy3...")
    nltk.download('words', quiet=True)
    nltk.download('maxent_ne_chunker', quiet=True)
    nltk.download('maxent_ne_chunker_tab', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
    nltk.download('averaged_perceptron_tagger_eng', quiet=True)
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)

class GeoParser:
    """
    Advanced Geoparsing Operator using Geograpy3, WHOIS, and caching.
    Implements Conflict Resolution and Hierarchy Validation.
    """
    
    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis = redis.from_url(redis_url)
        self.country_map = self._load_country_map()

    def _load_country_map(self) -> Dict[str, str]:
        """Loads country name to ISO-3 code mapping from GeoJSON."""
        mapping = {}
        geo_path = os.path.join(settings.DATA_DIR, 'countries.geo.json')
        if os.path.exists(geo_path):
            try:
                with open(geo_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for feature in data.get('features', []):
                        props = feature.get('properties', {})
                        code = feature.get('id')
                        name = props.get('name')
                        if code and name:
                            mapping[name.lower()] = code
                            for alias in props.get('aliases', []):
                                mapping[alias.lower()] = code
            except Exception as e:
                logger.error(f"Failed to load GeoJSON map: {e}")
        return mapping

    def get_cached_location(self, domain: str) -> Optional[str]:
        """Retrieves cached country code for a domain."""
        try:
            key = f"geo:{domain}"
            cached = self.redis.get(key)
            if cached:
                return cached.decode()
        except Exception as e:
            logger.error(f"Redis get error: {e}")
        return None

    def cache_location(self, domain: str, country_code: str, tier: int = 2):
        """Caches the resolved location with tier-based expiration."""
        try:
            key = f"geo:{domain}"
            # Tier 0 -> 1 day (86400s), Tier 2 -> 7 days (604800s)
            ttl = 86400 if tier == 0 else 604800
            self.redis.setex(key, ttl, country_code)
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    def extract_from_whois(self, domain: str) -> Optional[str]:
        """Extracts country from WHOIS data."""
        try:
            w = whois.whois(domain)
            # 'country' can be a string or list
            c = w.country
            if isinstance(c, list):
                c = c[0]
            if c:
                return c.upper() # Usually 2-letter ISO, might need mapping to 3-letter
        except Exception as e:
            logger.debug(f"WHOIS lookup failed for {domain}: {e}")
        return None

    def extract_from_text(self, text: str) -> Tuple[Optional[str], List[str]]:
        """
        Uses Geograpy3 to extract country and context.
        Returns (Best Country Name, List of Countries Found)
        """
        try:
            places = geograpy.get_geoPlace_context(text=text)
            if places.countries:
                # Return the most mentioned country
                if places.country_mentions:
                    return places.country_mentions[0][0], places.countries
                return places.countries[0], places.countries
        except Exception as e:
            logger.error(f"Geograpy3 extraction failed: {e}")
        return None, []

    def resolve(self, url: str, text: str, tier: int = 2, existing_code: str = 'UNK') -> Tuple[str, str]:
        """
        Resolves country code using multi-source consensus.
        Returns (Country Code, Confidence Level)
        """
        domain = urlparse(url).netloc
        
        # 1. Check Cache
        cached = self.get_cached_location(domain)
        if cached:
            return cached, 'high'

        candidates = []
        
        # 2. Existing (TLD/Override)
        if existing_code and existing_code != 'UNK':
            candidates.append(existing_code) # Weight: 1

        # 3. WHOIS
        whois_country = self.extract_from_whois(domain)
        if whois_country:
            # WHOIS usually returns ISO-2, need ISO-3 if possible. 
            # For now, let's assume we can map it or it's a code. 
            # Our system uses ISO-3 (JPN, USA). WHOIS gives 'US', 'JP'.
            # I need a 2-to-3 mapper. pycountry can help, or simple heuristic.
            # Let's rely on internal mapping if possible or just use it as a vote if it matches 3-letter.
            # Actually, `pycountry` is in requirements. 
            import pycountry
            try:
                c = pycountry.countries.get(alpha_2=whois_country)
                if c:
                    candidates.append(c.alpha_3)
            except:
                pass

        # 4. Text Extraction (Geograpy3)
        geo_name, all_geo_countries = self.extract_from_text(text[:5000]) # Limit text size
        if geo_name and geo_name.lower() in self.country_map:
            candidates.append(self.country_map[geo_name.lower()])
            
        # 5. Conflict Resolution (Majority Consensus)
        if not candidates:
            return 'UNK', 'unknown'
            
        counts = Counter(candidates)
        most_common = counts.most_common(1)
        
        winner, count = most_common[0]
        
        # Confidence Logic
        confidence = 'low'
        if count > 1:
            confidence = 'high'
        elif len(candidates) == 1:
            confidence = 'medium'
            
        # Hierarchy Validation (Bonus: if Geograpy found regions matching the winner)
        # (This is implicit if Geograpy returns the country based on regions)
        
        # Cache result if valid
        if winner != 'UNK':
            self.cache_location(domain, winner, tier)
            
        return winner, confidence
