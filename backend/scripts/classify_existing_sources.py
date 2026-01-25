import sys
import os
import json
import logging
from urllib.parse import urlparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.operators.storage.postgres_storage import PostgresStorageOperator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def classify_existing_sources():
    op = PostgresStorageOperator()
    
    # 1. Load GeoJSON for Name Matching
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    geo_path = os.path.join(base_dir, 'data', 'countries.geo.json')
    
    geo_map = {} # name/alias -> code
    if os.path.exists(geo_path):
        try:
            with open(geo_path, 'r', encoding='utf-8') as f:
                geo_data = json.load(f)
                for feature in geo_data.get('features', []):
                    code = feature.get('id')
                    props = feature.get('properties', {})
                    name = props.get('name')
                    
                    if name:
                        geo_map[name.lower()] = code
                    
                    # Add aliases
                    for alias in props.get('aliases', []):
                        geo_map[alias.lower()] = code
                    
                    # Add name_zh
                    if props.get('name_zh'):
                        geo_map[props.get('name_zh')] = code # Though domain matching against Chinese chars is unlikely
                        
            logger.info(f"Loaded {len(geo_map)} geographic name mappings.")
        except Exception as e:
            logger.error(f"Failed to load GeoJSON: {e}")
    
    # 2. Define TLD Map (Enhanced)
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
        'za': 'ZAF', 'ng': 'NGA', 'eg': 'EGY', 'ke': 'KEN', 'gh': 'GHA',
        'ma': 'MAR', 'dz': 'DZA', 'tn': 'TUN', 'et': 'ETH', 'tz': 'TZA',
        
        # Oceania
        'au': 'AUS', 'nz': 'NZL', 'fj': 'FJI'
    }

    try:
        with op.get_connection() as conn:
            with conn.cursor() as cursor:
                # 3. Get all UNK sources
                cursor.execute("SELECT domain FROM media_sources WHERE country_code = 'UNK' OR country_code IS NULL")
                sources = cursor.fetchall()
                logger.info(f"Found {len(sources)} sources with Unknown country.")
                
                updated_count = 0
                for (domain,) in sources:
                    inferred_code = 'UNK'
                    
                    # A. Check TLD
                    parts = domain.split('.')
                    if len(parts) >= 2:
                        tld = parts[-1].lower()
                        if tld in tld_map:
                            inferred_code = tld_map[tld]
                    
                    # B. Check Name/Alias Map if still UNK
                    if inferred_code == 'UNK':
                        domain_lower = domain.lower()
                        # Simple inclusion check (can be improved)
                        # We iterate through keys and see if they appear in the domain
                        # Optimization: Filter keys by length to avoid short matches like 'us' in 'virus'
                        for name, code in geo_map.items():
                            if len(name) > 3 and name in domain_lower:
                                inferred_code = code
                                break
                    
                    # C. Update if found
                    if inferred_code != 'UNK':
                        # Get Country Name if possible (from geojson or just Code)
                        country_name = inferred_code # Default
                        # Try to find name from geo_map (reverse lookup is hard, but we can rely on code)
                        # Actually we don't have a code->name map easily here without reloading geojson differently
                        # But update_media_source_country can handle name=None if we want, or we pass code
                        
                        op.update_media_source_country(domain, inferred_code, country_name=None)
                        logger.info(f"Updated {domain} -> {inferred_code}")
                        updated_count += 1
                        
                conn.commit()
                logger.info(f"Successfully classified {updated_count} sources.")

    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    classify_existing_sources()
