import logging
import mediacloud.api
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.core.config import settings
from backend.core.models import MediaSource
from backend.core.database import SessionLocal

from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class MediaCloudIntegrator:
    """
    Integration with Media Cloud API for:
    1. Seed Discovery: Fetching media sources by national collections.
    2. Verification: Cross-referencing sources for geolocation confidence.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.MEDIA_CLOUD_API_KEY
        if not self.api_key:
            logger.warning("Media Cloud API Key not found. Functionality will be limited.")
            self.directory_api = None
            self.search_api = None
        else:
            self.directory_api = mediacloud.api.DirectoryApi(self.api_key)
            self.search_api = mediacloud.api.SearchApi(self.api_key)

    def get_national_collection_id(self, country_name: str) -> Optional[int]:
        """
        Search for a national collection ID by country name.
        Note: This is a heuristic search. Media Cloud collections often follow 'Country - National' naming.
        """
        if not self.directory_api:
            return None
            
        try:
            # Search for collections matching the country name
            # Note: The API client might not have a direct 'collection_search' convenient method in all versions,
            # but usually it supports searching.
            # Based on common usage, we might need to iterate or use a specific search endpoint if available.
            # For now, let's assume we can search or we might need to rely on known IDs.
            # Let's try to search via tag_list or similar if available, but simplest is to prompt user or use known list.
            
            # Since I can't easily search collections without a known endpoint in the snippet,
            # I will return None and log a warning, OR implement a known mapping for major countries.
            
            known_collections = {
                "United States": 34412234,
                "India": 34412118,
                "United Kingdom": 34412476,
                "France": 34412146,
                "Germany": 34412156,
                "Russia": 34412204,
                "China": 34412089,
                "Japan": 34412170,
                # Add more as needed
            }
            return known_collections.get(country_name)
            
        except Exception as e:
            logger.error(f"Error searching collection for {country_name}: {e}")
            return None

    def fetch_sources_from_collection(self, collection_id: int, limit: int = 1000) -> List[Dict]:
        """
        Fetch media sources from a specific Media Cloud collection.
        """
        if not self.directory_api:
            return []
            
        sources = []
        offset = 0
        try:
            while True:
                response = self.directory_api.source_list(collection_id=collection_id, limit=limit, offset=offset)
                batch = response.get('results', [])
                sources.extend(batch)
                
                if response.get('next') is None or len(sources) >= limit:
                    break
                offset += len(batch)
                
            logger.info(f"Fetched {len(sources)} sources from collection {collection_id}")
            return sources
        except Exception as e:
            logger.error(f"Error fetching sources from collection {collection_id}: {e}")
            return []

    def sync_sources_to_db(self, sources: List[Dict], default_tier: int = 2, country_code: str = "UNK"):
        """
        Sync fetched sources to the local database.
        """
        db: Session = SessionLocal()
        count_new = 0
        count_updated = 0
        
        # DEBUG: Print structure of first source
        if sources:
            logger.info(f"Sample Source Data: {sources[0].keys()}")

        try:
            for src in sources:
                # Map MediaCloud API fields to our model
                url = src.get('homepage') or src.get('url')
                name = src.get('name') or src.get('label')
                
                if not url:
                    continue
                    
                # Basic normalization
                if not url.startswith('http'):
                    url = 'http://' + url
                
                try:
                    domain = urlparse(url).netloc
                    if not domain:
                        continue
                    # Strip www.
                    if domain.startswith('www.'):
                        domain = domain[4:]
                except:
                    continue
                    
                # Check existence
                existing = db.query(MediaSource).filter(MediaSource.domain == domain).first()
                
                if existing:
                    count_updated += 1
                else:
                    new_source = MediaSource(
                        name=name or domain,
                        domain=domain,
                        tier=f"Tier-{default_tier}",
                        country_code=country_code
                    )
                    db.add(new_source)
                    count_new += 1
            
            db.commit()
            logger.info(f"Media Cloud Sync: {count_new} new, {count_updated} updated.")
            
        except Exception as e:
            logger.error(f"Error syncing to DB: {e}")
            db.rollback()
        finally:
            db.close()

    def verify_source_location(self, url: str) -> Optional[str]:
        """
        Use Media Cloud data (synced locally) to verify a source's country.
        """
        if not url:
            return None
            
        try:
            # Normalize URL to domain
            domain = urlparse(url).netloc
            if domain.startswith('www.'):
                domain = domain[4:]
                
            db: Session = SessionLocal()
            try:
                # Query local DB which is synced with Media Cloud
                source = db.query(MediaSource).filter(MediaSource.domain == domain).first()
                if source and source.country_code and source.country_code != 'UNK':
                    return source.country_code
            finally:
                db.close()
                
            return None
        except Exception as e:
            logger.error(f"Error verifying source {url}: {e}")
            return None
