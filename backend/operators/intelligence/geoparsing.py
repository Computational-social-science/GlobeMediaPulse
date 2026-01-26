import sys
import os
import logging
import json
import redis
import time
# Patch for geograpy3 compatibility with newer pylodstorage
try:
    import lodstorage.entity # type: ignore
except ImportError:
    try:
        # If lodstorage.entity is missing, try to alias it to lodentity.entity
        # This fixes the "ModuleNotFoundError: No module named 'lodstorage.entity'"
        import lodentity.entity # type: ignore
        import lodstorage # type: ignore
        lodstorage.entity = lodentity.entity
        sys.modules['lodstorage.entity'] = lodentity.entity
    except ImportError:
        pass

import geograpy
import whois
import nltk
import pycountry
import functools
from collections import Counter
from urllib.parse import urlparse
from typing import Optional, List, Dict, Tuple, Any
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
    Advanced Geoparsing Operator using Geograpy3, WHOIS, MediaCloud, and caching.
    Implements Conflict Resolution and Hierarchy Validation.
    """
    
    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis = redis.from_url(redis_url)
        self.country_map, self.country_coords = self._load_country_data()
        
    def _load_country_data(self) -> Tuple[Dict[str, str], Dict[str, Dict[str, float]]]:
        """
        Loads country data:
        1. Name -> ISO-3 Code mapping
        2. ISO-3 Code -> {lat, lng} mapping
        Primary Source: data/countries_data.json
        """
        mapping = {}
        coords = {}
        # Correct path to the root data directory
        json_path = os.path.join(settings.BASE_DIR, 'data', 'countries_data.json')
        
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    countries = []
                    if isinstance(data, dict) and "COUNTRIES" in data:
                        countries = data["COUNTRIES"]
                    elif isinstance(data, list):
                        countries = data
                        
                    for c in countries:
                        code = c.get('code') # ISO-3
                        name = c.get('name')
                        official_name = c.get('official_name')
                        lat = c.get('lat')
                        lng = c.get('lng')
                        
                        if code:
                            # Populate coords
                            if lat is not None and lng is not None:
                                coords[code] = {'lat': float(lat), 'lng': float(lng)}

                            # Populate name mapping
                            if name:
                                mapping[name.lower()] = code
                            if official_name:
                                mapping[official_name.lower()] = code
                                
                            # Add aliases or alternate names if available in the future
                            # Currently utilizing name and official_name
                            
                            # Also map alpha2 if unique
                            if c.get('code_alpha2'):
                                mapping[c.get('code_alpha2').lower()] = code
                            
                            # Map native names if available (for future expansion)
                            # e.g., "Deutschland" -> DEU
                            
            except Exception as e:
                logger.error(f"Failed to load countries_data.json: {e}")
        else:
            logger.warning(f"countries_data.json not found at {json_path}")
            
        return mapping, coords

    def get_coords(self, country_code: str) -> Optional[Dict[str, float]]:
        """Returns {lat, lng} for a given ISO-3 country code."""
        return self.country_coords.get(country_code)

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

    @functools.lru_cache(maxsize=1024)
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
        if not text or not text.strip():
            return None, []

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

    @functools.lru_cache(maxsize=1024)
    def validate_with_mediacloud(self, url: str) -> Optional[str]:
        """Queries Media Cloud for authoritative location verification."""
        try:
            from backend.operators.intelligence.media_cloud_client import MediaCloudIntegrator
            integrator = MediaCloudIntegrator()
            if not integrator.directory_api:
                return None
            return integrator.verify_source_location(url)
        except Exception as e:
            logger.warning(f"Media Cloud verification failed: {e}")
            return None

    def infer_from_tld(self, url: str) -> str:
        """
        Infers ISO-3 country code from URL TLD.
        """
        try:
            domain = urlparse(url).netloc
            parts = domain.split('.')
            if len(parts) < 2:
                return 'UNK'
            tld = parts[-1].lower()
            
            # Enhanced TLD Map
            tld_map = {
                # Asia
                'jp': 'JPN', 'cn': 'CHN', 'in': 'IND', 'kr': 'KOR', 'id': 'IDN', 
                'ph': 'PHL', 'vn': 'VNM', 'th': 'THA', 'my': 'MYS', 'sg': 'SGP',
                'pk': 'PAK', 'bd': 'BGD', 'lk': 'LKA', 'np': 'NPL', 'tw': 'TWN',
                'hk': 'HKG', 'sa': 'SAU', 'ae': 'ARE', 'ir': 'IRN', 'tr': 'TUR',
                'il': 'ISR', 'qa': 'QAT', 'kw': 'KWT', 'om': 'OMN', 'jo': 'JOR',
                
                # Europe
                'uk': 'GBR', 'de': 'DEU', 'fr': 'FRA', 'it': 'ITA', 'es': 'ESP',
                'nl': 'NLD', 'be': 'BEL', 'ch': 'CHE', 'at': 'AUT', 'se': 'SWE',
                'no': 'NOR', 'dk': 'DNK', 'fi': 'FIN', 'ie': 'IRL', 'pt': 'PRT',
                'pl': 'POL', 'cz': 'CZE', 'hu': 'HUN', 'ro': 'ROU', 'gr': 'GRC',
                'ua': 'UKR', 'ru': 'RUS', 'by': 'BLR', 'rs': 'SRB', 'hr': 'HRV',
                
                # Americas
                'ca': 'CAN', 'br': 'BRA', 'mx': 'MEX', 'ar': 'ARG', 'co': 'COL',
                'cl': 'CHL', 'pe': 'PER', 've': 'VEN', 'ec': 'ECU', 'uy': 'URY',
                
                # Africa
                'za': 'ZAF', 'eg': 'EGY', 'ng': 'NGA', 'ke': 'KEN', 'gh': 'GHA',
                'ma': 'MAR', 'dz': 'DZA', 'tn': 'TUN', 'et': 'ETH', 'tz': 'TZA',
                
                # Oceania
                'au': 'AUS', 'nz': 'NZL', 'fj': 'FJI', 'pg': 'PNG'
            }
            
            return tld_map.get(tld, 'UNK')
        except Exception as e:
            logger.error(f"TLD inference failed: {e}")
            return 'UNK'

    def resolve(self, url: str, text: str, tier: int = 2, existing_code: str = 'UNK') -> Tuple[str, str]:
        """
        Resolves country code using multi-source consensus.
        Returns (Country Code, Confidence Level)
        """
        domain = urlparse(url).netloc
        
        # Publish "Start" Event
        self._publish_event("geoparsing_start", {"domain": domain, "tier": tier})
        
        # 1. Check Cache
        cached = self.get_cached_location(domain)
        if cached:
            self._publish_event("geoparsing_complete", {"domain": domain, "result": cached, "method": "cache"})
            return cached, 'high'

        candidates = []
        logs = []
        
        # 2. Existing (TLD/Override)
        # If UNK, try to infer from TLD locally to be robust
        if existing_code == 'UNK':
            existing_code = self.infer_from_tld(url)

        if existing_code and existing_code != 'UNK':
            candidates.append(existing_code) # Weight: 1
            msg = f"TLD/Override Match: {existing_code}"
            logs.append(msg)
            self._publish_event("geoparsing_step", {"domain": domain, "step": "TLD", "message": msg})

        # 3. WHOIS
        self._publish_event("geoparsing_step", {"domain": domain, "step": "WHOIS", "message": "Querying WHOIS database..."})
        whois_country = self.extract_from_whois(domain)
        if whois_country:
            # WHOIS usually returns ISO-2, need ISO-3 if possible. 
            import pycountry
            try:
                c = pycountry.countries.get(alpha_2=whois_country)
                if c:
                    candidates.append(c.alpha_3)
                    msg = f"WHOIS Match: {c.alpha_3}"
                    logs.append(msg)
                    self._publish_event("geoparsing_step", {"domain": domain, "step": "WHOIS", "message": msg})
            except:
                pass

        # 4. Media Cloud Verification (Authoritative)
        mc_country = self.validate_with_mediacloud(url)
        if mc_country:
             candidates.append(mc_country)
             candidates.append(mc_country) # Double weight for authority
             msg = f"MediaCloud Authority Match: {mc_country} (x2)"
             logs.append(msg)
             self._publish_event("geoparsing_step", {"domain": domain, "step": "MediaCloud", "message": msg})

        # 5. Text Extraction (Geograpy3)
        geo_name, all_geo_countries = self.extract_from_text(text[:5000]) # Limit text size
        if geo_name:
            code = None
            # Try internal mapping
            if geo_name.lower() in self.country_map:
                code = self.country_map[geo_name.lower()]
            
            # Fallback: Try Pycountry direct lookup if mapping failed
            if not code:
                try:
                    import pycountry
                    c = pycountry.countries.lookup(geo_name)
                    if c:
                        code = c.alpha_3
                except:
                    pass

            if code:
                candidates.append(code)
                msg = f"Geograpy3 Text Analysis: {code}"
                logs.append(msg)
                self._publish_event("geoparsing_step", {"domain": domain, "step": "NLP", "message": msg})
            else:
                 self._publish_event("geoparsing_step", {"domain": domain, "step": "NLP", "message": f"Found '{geo_name}' but could not map to ISO-3"})

        # 6. Conflict Resolution (Majority Consensus)
        if not candidates:
            logger.warning(f"Geoparsing FAILED for {domain}. Candidates empty. Logs: {logs}")
            self._publish_event("geoparsing_failed", {"domain": domain})
            return 'UNK', 'unknown'
            
        counts = Counter(candidates)
        most_common = counts.most_common(1)
        
        winner, count = most_common[0]
        
        # Confidence Logic
        confidence = 'low'
        if count > 1 or mc_country == winner:
            confidence = 'high'
        elif len(candidates) == 1:
            confidence = 'medium'
            
        # Cache result if valid
        if winner != 'UNK':
            self.cache_location(domain, winner, tier)
        
        # Publish "Complete" Event with details
        self._publish_event("geoparsing_complete", {
            "domain": domain, 
            "result": winner, 
            "confidence": confidence,
            "details": "; ".join(logs)
        })
            
        return winner, confidence

    def _publish_event(self, event_type: str, data: Dict[str, Any]):
        """Publishes real-time events to Redis for frontend visualization."""
        try:
            payload = {
                "type": "log", 
                "sub_type": event_type,
                "timestamp": time.time(),
                "data": data
            }
            # Use 'news_pulse' channel so existing listener picks it up
            self.redis.publish("news_pulse", json.dumps(payload))
        except Exception as e:
            logger.debug(f"Redis publish failed: {e}")

