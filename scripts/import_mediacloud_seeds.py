import sys
import os
import logging

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.operators.intelligence.media_cloud_client import MediaCloudIntegrator
from backend.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("=== Media Cloud Seed Importer ===")
    
    api_key = settings.MEDIA_CLOUD_API_KEY
    if not api_key:
        print("Media Cloud API Key not found in environment.")
        api_key = input("Please enter your Media Cloud API Key (or press Enter to skip): ").strip()
        
    if not api_key:
        print("No API Key provided. Exiting.")
        return

    integrator = MediaCloudIntegrator(api_key)
    
    # List of target countries to seed
    targets = [
        {"name": "United States", "code": "USA", "tier": 1},
        {"name": "United Kingdom", "code": "GBR", "tier": 1},
        {"name": "China", "code": "CHN", "tier": 1},
        {"name": "India", "code": "IND", "tier": 2},
    ]
    
    for target in targets:
        country_name = target["name"]
        print(f"\nProcessing {country_name}...")
        
        collection_id = integrator.get_national_collection_id(country_name)
        if not collection_id:
            print(f"  Collection ID not found for {country_name}. Skipping.")
            continue
            
        print(f"  Fetching sources from Collection {collection_id}...")
        sources = integrator.fetch_sources_from_collection(collection_id, limit=50) # Limit for demo
        
        if sources:
            print(f"  Syncing {len(sources)} sources to DB...")
            integrator.sync_sources_to_db(sources, default_tier=target["tier"], country_code=target["code"])
            print("  Done.")
        else:
            print("  No sources found.")

if __name__ == "__main__":
    main()
