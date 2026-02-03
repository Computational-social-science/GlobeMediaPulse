import abc
import logging
import time
import socket
from typing import Optional, Dict, Any, Tuple, List
from urllib.parse import urlparse
import tldextract
import pycountry
import whois
from backend.core.config import settings

logger = logging.getLogger(__name__)

class GeoResolutionStrategy(abc.ABC):
    """
    Abstract Base Class for Geoparsing Strategies.
    Each strategy implements a specific method to resolve a URL to a country code.
    """
    name: str = "base"
    weight: float = 1.0

    @abc.abstractmethod
    def resolve(self, domain: str, meta: Dict[str, Any]) -> Optional[str]:
        """
        Resolve domain to ISO-3 country code.
        Returns None if not applicable or failed.
        """
        pass

class TLDStrategy(GeoResolutionStrategy):
    """
    Strategy 1: Public Suffix List (PSL) & TLD Strict Mapping.
    Uses tldextract for robust parsing and maps ccTLDs to ISO-3 codes.
    """
    name = "TLD"
    weight = 0.9 # High confidence for explicit ccTLDs

    def __init__(self):
        # Initialize TLD map (could be loaded from external config in future)
        self.tld_map = self._build_tld_map()

    def _build_tld_map(self) -> Dict[str, str]:
        # Basic mapping from pycountry, plus overrides
        mapping = {}
        for country in pycountry.countries:
            if hasattr(country, 'alpha_2'):
                mapping[country.alpha_2.lower()] = country.alpha_3
        
        # Manual Overrides for non-standard or generic-use ccTLDs
        # These are often used as generic TLDs (e.g., .io, .ai, .tv, .co)
        # We might want to EXCLUDE them from automatic mapping if they are treated as generic
        overrides = {
            'uk': 'GBR', # .uk -> GBR
            'su': 'RUS', # Soviet Union -> Russia
            'eu': 'EU',  # European Union
            'tv': 'UNK', # Tuvalu (often generic) - Let's be conservative
            'io': 'UNK', # BIOT (tech)
            'ai': 'UNK', # Anguilla (tech)
            'co': 'UNK', # Colombia (often generic "Company")
            'me': 'UNK', # Montenegro (personal)
            'fm': 'UNK', # Micronesia (radio)
        }
        mapping.update(overrides)
        return mapping

    def resolve(self, domain: str, meta: Dict[str, Any]) -> Optional[str]:
        extracted = tldextract.extract(domain)
        suffix = extracted.suffix.lower()
        
        # Handle composite TLDs like co.uk
        parts = suffix.split('.')
        tld = parts[-1] if parts else ""
        
        if tld in self.tld_map:
            code = self.tld_map[tld]
            return code
        return None

class IPGeolocationStrategy(GeoResolutionStrategy):
    """
    Strategy 2: DNS Resolution + IP Geolocation.
    Resolves domain to IP and looks up country.
    Fast and provides a good signal for server location (though CDN can mask this).
    """
    name = "IP"
    weight = 0.4 # Lower confidence due to CDNs/Cloud hosting

    def resolve(self, domain: str, meta: Dict[str, Any]) -> Optional[str]:
        try:
            # Resolve IP
            ip_address = socket.gethostbyname(domain)
            # Placeholder for MaxMind GeoLite2
            # if geoip_reader:
            #     response = geoip_reader.country(ip_address)
            #     return response.country.iso_code
            return None 
        except Exception:
            return None

class WHOISStrategy(GeoResolutionStrategy):
    """
    Strategy 3: WHOIS Lookup.
    Slow, but authoritative for registrar data.
    """
    name = "WHOIS"
    weight = 0.6

    def resolve(self, domain: str, meta: Dict[str, Any]) -> Optional[str]:
        try:
            w = whois.whois(domain)
            c = w.country
            if isinstance(c, list):
                c = c[0]
            if c:
                # Map 2-letter to 3-letter
                c_obj = pycountry.countries.get(alpha_2=c.upper())
                if c_obj:
                    return c_obj.alpha_3
        except Exception:
            pass
        return None

class HeuristicStrategy(GeoResolutionStrategy):
    """
    Strategy 4: Domain Name Heuristics.
    Looks for known media patterns and major outlets.
    High precision manual overrides for top-tier domains.
    """
    name = "Heuristic"
    weight = 0.95 # Very high confidence for manual overrides

    def __init__(self):
        self.overrides = {
            'nytimes': 'USA', 'wsj': 'USA', 'washingtonpost': 'USA', 'cnn': 'USA', 'foxnews': 'USA', 'usatoday': 'USA', 'nbcnews': 'USA', 'cnbc': 'USA', 'bloomberg': 'USA', 'apnews': 'USA', 'npr': 'USA',
            'bbc': 'GBR', 'reuters': 'GBR', 'theguardian': 'GBR', 'independent': 'GBR', 'dailymail': 'GBR', 'telegraph': 'GBR', 'skynews': 'GBR',
            'aljazeera': 'QAT',
            'rt': 'RUS', 'sputniknews': 'RUS', 'tass': 'RUS', 'moscowtimes': 'RUS',
            'xinhua': 'CHN', 'chinadaily': 'CHN', 'scmp': 'HKG', 'globaltimes': 'CHN',
            'dw': 'DEU', 'france24': 'FRA', 'euronews': 'FRA',
            'kyodonews': 'JPN', 'japantimes': 'JPN', 'asahi': 'JPN',
            'yonhap': 'KOR', 'koreaherald': 'KOR',
            'thehindu': 'IND', 'timesofindia': 'IND', 'hindustantimes': 'IND',
            'straitstimes': 'SGP', 'bangkokpost': 'THA', 'jakartapost': 'IDN',
            'smh': 'AUS', 'abc': 'AUS',
            'globeandmail': 'CAN', 'cbc': 'CAN',
            'folha': 'BRA', 'clarin': 'ARG'
        }

    def resolve(self, domain: str, meta: Dict[str, Any]) -> Optional[str]:
        domain_lower = domain.lower()
        parts = domain_lower.replace('-', '.').split('.') # Handle hyphens too? maybe not.
        # Simple split by dot
        parts = domain_lower.split('.')
        
        for key, code in self.overrides.items():
            # Strict match: key must be one of the domain parts
            # e.g. "bbc" in "bbc.co.uk", "nytimes" in "nytimes.com"
            if key in parts:
                return code
        return None

class GeoResolver:
    """
    Hierarchical Probabilistic Resolver for Domain Geolocation.
    """
    def __init__(self):
        self.strategies: List[GeoResolutionStrategy] = [
            HeuristicStrategy(), # Check knowns first (Fastest & Most Accurate)
            TLDStrategy(),       # Then TLD
            WHOISStrategy(),     # Then WHOIS (Slow)
            IPGeolocationStrategy(), # Finally IP
        ]
        self.logger = logging.getLogger("GeoResolver")
        self.country_coords = self._load_country_coords()

    def _load_country_coords(self) -> Dict[str, Dict[str, float]]:
        """Loads country coordinates from data/countries_data.json"""
        import json
        import os
        coords = {}
        try:
            # Try standard paths
            paths = [
                os.path.join(settings.BASE_DIR, "data", "countries_data.json"),
                os.path.join(settings.BASE_DIR, "..", "data", "countries_data.json"),
                os.path.join("data", "countries_data.json")
            ]
            json_path = next((p for p in paths if os.path.exists(p)), None)
            
            if json_path:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                countries = data.get("COUNTRIES", []) if isinstance(data, dict) else data
                for c in countries:
                    if isinstance(c, dict):
                        code = c.get("code")
                        lat = c.get("lat")
                        lng = c.get("lng")
                        if code and lat is not None and lng is not None:
                            coords[code] = {"lat": float(lat), "lng": float(lng)}
        except Exception as e:
            self.logger.error(f"Failed to load country coords: {e}")
        return coords

    def get_coords(self, country_code: str) -> Optional[Dict[str, float]]:
        """Returns {lat, lng} for a given ISO-3 country code."""
        return self.country_coords.get(country_code)

    def resolve(self, url: str) -> Dict[str, Any]:
        """
        Resolve a URL to a country code with metadata.
        """
        start_time = time.time()
        
        # 1. Normalize Domain
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path # Handle cases without scheme
            if not domain:
                return self._error_result("Invalid URL")
            
            # Strip port if present
            if ':' in domain:
                domain = domain.split(':')[0]
        except Exception as e:
            return self._error_result(f"Parse Error: {e}")

        # 2. Run Strategies (Fail-Fast)
        candidates = []
        logs = []
        
        for strategy in self.strategies:
            try:
                s_start = time.time()
                result = strategy.resolve(domain, {})
                duration = (time.time() - s_start) * 1000
                
                if result:
                    candidates.append({
                        "code": result,
                        "strategy": strategy.name,
                        "weight": strategy.weight,
                        "duration_ms": duration
                    })
                    logs.append(f"{strategy.name}: {result} ({duration:.1f}ms)")
                    
                    # SHORT-CIRCUIT: If we have a high-confidence match, stop.
                    # Heuristic (0.95) and TLD (0.9) are sufficient.
                    if strategy.weight >= 0.9:
                        break
                else:
                    logs.append(f"{strategy.name}: None ({duration:.1f}ms)")
            except Exception as e:
                self.logger.error(f"Strategy {strategy.name} failed: {e}")

        # 3. Decision Logic (Weighted Vote)
        best_code = "UNK"
        confidence = 0.0
        details = {}
        
        if candidates:
            # Sum weights by country
            scores = {}
            for c in candidates:
                scores[c['code']] = scores.get(c['code'], 0) + c['weight']
            
            # Find max score
            best_code = max(scores, key=scores.get)
            total_score = scores[best_code]
            
            # Normalize confidence (0.0 - 1.0)
            # Heuristic: TLD (0.9) alone is ~0.9. WHOIS (0.6) alone is 0.6. Both = 1.5 -> 1.0
            confidence = min(total_score, 1.0)
            details["candidates"] = candidates

        duration_total = (time.time() - start_time) * 1000
        
        return {
            "country_code": best_code,
            "confidence": confidence,
            "duration_ms": duration_total,
            "domain": domain,
            "logs": logs,
            "details": details
        }

    def _error_result(self, msg: str) -> Dict[str, Any]:
        return {
            "country_code": "UNK",
            "confidence": 0.0,
            "error": msg,
            "duration_ms": 0.0
        }
