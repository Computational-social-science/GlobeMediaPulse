
import os
import sys
import logging
import mediacloud.api
import traceback
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Load env vars from .env file in root
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

from backend.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_collections(api_key, country_names):
    if not api_key:
        logger.error("No API Key provided")
        return

    directory_api = mediacloud.api.DirectoryApi(api_key)
    
    results = {}
    
    for country in country_names:
        logger.info(f"Searching for collections related to: {country}")
        try:
            # Note: The search capability depends on the API version.
            # Using name_search if available, or simple iteration if list is small (it's not).
            # The v4 API client usually has search_collections or similar.
            # Let's try name_search which is common in MC API clients.
            # If not, we might fail here, but it's a discovery script.
            
            # Try to find collections with "CountryName" and "National" in the name
            query = f"{country} - National"
            
            # Assuming search method exists. If not, we'll need to check the library docs or source.
            # Based on standard usage: directory_api.collection_list(name=...)
            response = directory_api.collection_list(name=country, limit=20)
            
            collections = response.get('results', [])
            
            if collections:
                print(f"DEBUG: Found {len(collections)} items")
            
            found = []
            for col in collections:
                # Heuristic: Prefer collections that explicitly mention "National" or look official
                # Handle if col is an object or dict
                col_name = col.get('name', '') if isinstance(col, dict) else getattr(col, 'name', str(col))
                
                if "National" in col_name or col_name == country:
                    found.append(col)
            
            if not found and collections:
                found = collections[:3] # Take top 3 if no "National" match
                
            if found:
                results[country] = found
                for f in found:
                    f_id = f.get('id') if isinstance(f, dict) else getattr(f, 'id', 'UNK')
                    f_name = f.get('name') if isinstance(f, dict) else getattr(f, 'name', str(f))
                    msg = f"  Found: {f_id} - {f_name}"
                    logger.info(msg)
                    print(msg) # Ensure stdout
            else:
                msg = f"  No collections found for {country}"
                logger.warning(msg)
                print(msg)
        except Exception as e:
            msg = f"  Error searching for {country}: {e}"
            logger.error(msg)
            print(msg)
            traceback.print_exc()

    return results

if __name__ == "__main__":
    api_key = os.getenv("MEDIA_CLOUD_API_KEY") or settings.MEDIA_CLOUD_API_KEY
    if not api_key:
        print("Please set MEDIA_CLOUD_API_KEY in .env")
        sys.exit(1)
        
    target_countries = [
        "Brazil", "South Africa", "Nigeria", "Indonesia", "Egypt", 
        "Argentina", "Saudi Arabia", "Turkey", "Thailand", "Mexico"
    ]
    
    search_collections(api_key, target_countries)
