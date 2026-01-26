
import asyncio
import sys
import os
from sqlalchemy import create_engine, inspect, text

# Add project root to path
sys.path.append(os.getcwd())

from backend.core.config import settings

def verify_indexes():
    """
    Verifies that B-Tree indexes exist for media_sources.domain and media_sources.country_code.
    """
    print(f"Connecting to database: {settings.DATABASE_URL.split('@')[-1]}") # Hide credentials
    
    try:
        engine = create_engine(settings.DATABASE_URL)
        inspector = inspect(engine)
        
        indexes = inspector.get_indexes('media_sources')
        
        domain_index = False
        country_index = False
        
        print("Existing Indexes on 'media_sources':")
        for idx in indexes:
            print(f"- {idx['name']}: {idx['column_names']}")
            if 'domain' in idx['column_names']:
                domain_index = True
            if 'country_code' in idx['column_names']:
                country_index = True
                
        if domain_index and country_index:
            print("\nSUCCESS: Required B-Tree indexes found.")
        else:
            print("\nWARNING: Missing indexes.")
            if not domain_index:
                print("- Missing index on 'domain'")
            if not country_index:
                print("- Missing index on 'country_code'")
                
            # Attempt to create if missing
            with engine.connect() as conn:
                if not domain_index:
                    print("Creating index on 'domain'...")
                    conn.execute(text("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_media_sources_domain ON media_sources (domain)"))
                if not country_index:
                    print("Creating index on 'country_code'...")
                    conn.execute(text("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_media_sources_country_code ON media_sources (country_code)"))
                conn.commit()
                print("Indexes created.")
                
    except Exception as e:
        print(f"Error checking indexes: {e}")

if __name__ == "__main__":
    verify_indexes()
