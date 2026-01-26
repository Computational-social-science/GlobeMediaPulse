
import os
import sys
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Load env vars from .env file in root
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

from backend.operators.intelligence.media_cloud_client import MediaCloudIntegrator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def expand_global_south():
    logger.info("Starting Global South Seed Expansion...")
    
    mc = MediaCloudIntegrator()
    if not mc.api_key:
        logger.error("Media Cloud API Key missing!")
        return

    # List of countries to expand
    countries = [
        "Brazil", "South Africa", "Nigeria", "Indonesia", "Egypt",
        "Argentina", "Saudi Arabia", "Turkey", "Thailand", "Mexico"
    ]
    
    total_new = 0
    
    for country in countries:
        logger.info(f"Processing {country}...")
        
        # 1. Get Collection ID
        col_id = mc.get_national_collection_id(country)
        if not col_id:
            logger.warning(f"  No collection ID found for {country}")
            continue
            
        # 2. Fetch Sources
        sources = mc.fetch_sources_from_collection(col_id, limit=50) # Limit to 50 top sources per country
        logger.info(f"  Fetched {len(sources)} sources from collection {col_id}")
        
        if not sources:
            logger.warning(f"  No sources found for {country}")
            continue
            
        # Debug: Print first source to check structure
        if sources:
            logger.info(f"  Sample source: {sources[0]}")
            
        # 3. Sync to DB
        # Note: We use default_tier=2 for these new sources
        
        # Simple mapping for now or let GeoParser handle it.
        # Let's map it for better data quality.
        country_map = {
            "Brazil": "BR", "South Africa": "ZA", "Nigeria": "NG", 
            "Indonesia": "ID", "Egypt": "EG", "Argentina": "AR",
            "Saudi Arabia": "SA", "Turkey": "TR", "Thailand": "TH", "Mexico": "MX"
        }
        code = country_map.get(country, "UNK")
        
        # Call sync with correct code
        new_count, updated_count = mc.sync_sources_to_db(sources, default_tier=2, country_code=code)
        
        logger.info(f"  {country} ({code}): Added {new_count}, Updated {updated_count}")
        total_new += new_count

    logger.info(f"Global South Expansion Complete. Total new sources: {total_new}")

if __name__ == "__main__":
    expand_global_south()
