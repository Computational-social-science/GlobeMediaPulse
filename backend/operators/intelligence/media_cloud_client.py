import logging
import time
import mediacloud.api
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.core.config import settings
from backend.core.models import MediaSource
from backend.core.database import SessionLocal
from backend.utils.retry import retry_with_backoff

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

    @retry_with_backoff(retries=3, backoff_in_seconds=2.0, raise_on_failure=False, fallback_value=None)
    def get_national_collection_id(self, country_name: str) -> Optional[int]:
        """
        Search for a national collection ID by country name.
        Strategies:
        1. Check known hardcoded list.
        2. Search API for "CountryName - National".
        """
        if not self.directory_api:
            return None
            
        # 1. Check known list (Fast path)
        known_collections = {
            "United States": 34412234,
            "India": 34412118,
            "United Kingdom": 34412476,
            "France": 34412146,
            "Germany": 34412156,
            "Russia": 34412204,
            "China": 34412089,
            "Japan": 34412170,
            # Global South Expansion
            "Brazil": 34412257,
            "South Africa": 34412238,
            "Nigeria": 38376341,
            "Indonesia": 34412392,
            "Egypt": 34412471,
            "Argentina": 34412043,
            "Saudi Arabia": 34412050,
            "Turkey": 34412131,
            "Thailand": 34412328,
            "Mexico": 34412427
        }
        if country_name in known_collections:
            return known_collections[country_name]

        # 2. Dynamic Search
        # Removed try/except to allow retry_with_backoff to handle transient errors
        
        # Search for collections with "CountryName - National"
        # This is the standard naming convention in Media Cloud for national collections
        name_query = f"{country_name} - National"
        results = self.directory_api.collection_list(name=name_query, limit=5)
        for col in results.get('results', []):
            # Strict check to ensure we get the right one
            # e.g. "Kenya - National"
            col_name = col.get('name', '')
            if col_name.lower() == name_query.lower() or col_name.lower() == f"national - {country_name.lower()}":
                logger.info(f"Dynamically found collection for {country_name}: {col['id']} ({col_name})")
                return col['id']
                
        # Fallback: Try just country name but require "National" in label
        results = self.directory_api.collection_list(name=country_name, limit=20)
        for col in results.get('results', []):
            col_name = col.get('name', '')
            if "national" in col_name.lower() and country_name.lower() in col_name.lower():
                logger.info(f"Dynamically found collection for {country_name}: {col['id']} ({col_name})")
                return col['id']
                    
        return None

    @retry_with_backoff(retries=3, backoff_in_seconds=2.0, raise_on_failure=False, fallback_value=[])
    def fetch_sources_from_collection(self, collection_id: int, limit: int = 1000) -> List[Dict]:
        """
        Fetch media sources from a specific Media Cloud collection.
        """
        if not self.directory_api:
            return []
            
        sources = []
        offset = 0
        # Removed try/except for retry_with_backoff
        while True:
            response = self.directory_api.source_list(collection_id=collection_id, limit=limit, offset=offset)
            batch = response.get('results', [])
            sources.extend(batch)
            
            if response.get('next') is None or len(sources) >= limit:
                break
            offset += len(batch)
            
        logger.info(f"Fetched {len(sources)} sources from collection {collection_id}")
        return sources

    def sync_sources_to_db(self, sources: List[Dict], default_tier: int = 2, country_code: str = "UNK"):
        """
        Sync fetched sources to the local database.
        """
        db: Session = SessionLocal()
        count_new = 0
        count_updated = 0
        started_at = time.perf_counter()
        
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
                    # Update country code if we have a specific one and existing is UNK or None
                    if country_code != "UNK" and (existing.country_code == "UNK" or existing.country_code is None):
                        existing.country_code = country_code
                        db.add(existing)
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
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            try:
                from backend.operators.storage import storage_operator

                storage_operator.record_src_metric(
                    action="write",
                    status="ok",
                    latency_ms=elapsed_ms,
                    delta_count=int(count_new or 0),
                )
            except Exception:
                pass
            logger.info(f"Media Cloud Sync: {count_new} new, {count_updated} updated.")
            return count_new, count_updated
            
        except Exception as e:
            logger.error(f"Error syncing to DB: {e}")
            db.rollback()
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            try:
                from backend.operators.storage import storage_operator

                storage_operator.record_src_metric(
                    action="write",
                    status="error",
                    latency_ms=elapsed_ms,
                    error_message=str(e),
                )
            except Exception:
                pass
            return 0, 0
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
