import sys
import os
import json
import logging
import redis
import time

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.operators.intelligence.media_cloud_client import MediaCloudIntegrator
from backend.core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    print("=== Global Media Cloud Seed Injection ===")
    
    # Initialize Clients
    mc = MediaCloudIntegrator()
    # Check API Key
    if not mc.directory_api:
        logger.error("Media Cloud API Key is missing! Cannot proceed with MediaCloud-first seeding.")
        logger.error("Please set MEDIA_CLOUD_API_KEY in backend/core/config.py or .env")
        # Proceeding with empty key will cause errors downstream
        # But we can try to rely on the crawler part if we skip the MC fetch
        # For now, let's exit to force user attention as this is a critical requirement
        sys.exit(1)

    r_client = redis.from_url(settings.REDIS_URL)

    # 1. Load Countries
    logger.info("Loading countries_data.json...")
    json_path = os.path.join(settings.BASE_DIR, 'data', 'countries_data.json')
    if not os.path.exists(json_path):
        logger.error(f"Countries data not found at {json_path}")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Handle if it's a dict with "COUNTRIES" key or just a list
        if isinstance(data, dict) and "COUNTRIES" in data:
            countries = data["COUNTRIES"]
        elif isinstance(data, list):
            countries = data
        else:
            logger.error("Invalid format in countries_data.json")
            return
        
    total_countries = len(countries)
    logger.info(f"Loaded {total_countries} target countries.")
    
    # Counters
    total_sources_added = 0
    total_sources_updated = 0
    
    for idx, country in enumerate(countries):
        name = country.get('name')
        code = country.get('code') # ISO-3
        
        logger.info(f"[{idx+1}/{total_countries}] Processing {name} ({code})...")
        
        # 1. Find Collection
        # Use the updated smart search in MediaCloudIntegrator
        collection_id = mc.get_national_collection_id(name)
        
        if not collection_id:
            logger.warning(f"  No collection found for {name}. Skipping.")
            continue
            
        # 2. Fetch Sources
        # Limit set to 2000 to get a good breadth (user mentioned 60k total, 200*200 = 40k, so 2000 is safer)
        # But many collections are smaller.
        sources = mc.fetch_sources_from_collection(collection_id, limit=2000)
        
        if not sources:
            logger.info(f"  No sources returned for collection {collection_id}.")
            continue
            
        logger.info(f"  Fetched {len(sources)} sources.")
        
        # 3. Sync to DB
        # Tier-1 for National Collections
        added, updated = mc.sync_sources_to_db(sources, default_tier=1, country_code=code)
        total_sources_added += added
        total_sources_updated += updated
        
        # 4. Push to Redis for Immediate Crawling (Snowballing)
        # We push the homepage URLs
        pushed_count = 0
        for src in sources:
            url = src.get('url') or src.get('homepage')
            if url:
                # Basic validation
                if not url.startswith('http'):
                    url = 'http://' + url
                
                # Push to Redis list
                r_client.lpush("universal_news:start_urls", url)
                pushed_count += 1
                
        logger.info(f"  Pushed {pushed_count} URLs to Crawler Queue.")
        
        # Rate Limiting (Politeness)
        time.sleep(1) 
        
    print("\n=== Summary ===")
    print(f"Total New Sources: {total_sources_added}")
    print(f"Total Updated Sources: {total_sources_updated}")
    print("Seed Injection Complete. Crawler queue populated.")

if __name__ == "__main__":
    main()
