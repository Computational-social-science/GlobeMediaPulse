import os
import sys
import psycopg2
from urllib.parse import urlparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import settings

def apply_updates():
    """
    Comprehensive Database Schema Migration Utility.
    
    Responsibilities:
    1.  **Error Tracking**: Adds context fields (simhash, media, coordinates) to `error_events`.
    2.  **Performance Indexing**: Creates indices for fast lookups on SimHash.
    3.  **Deduplication Infrastructure**: Creates the `url_library` table for global URL fingerprinting.
    4.  **Metadata Enhancement**: Adds `url_hash` to `news_articles` for optimized joins and lookups.
    """
    print(f"Connecting to Database at {settings.DATABASE_URL}...")
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 1. Schema Evolution: Error Events
        print("Migrating 'error_events' schema...")
        columns_to_add = [
            ("simhash", "TEXT"),
            ("media", "TEXT"),
            ("coordinates", "TEXT")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                print(f"Adding column '{col_name}'...")
                cursor.execute(f"ALTER TABLE error_events ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                print(f"Column '{col_name}' ensured.")
            except Exception as e:
                print(f"Warning: Failed to add column '{col_name}': {e}")
        
        # 2. Performance Optimization: SimHash Index
        try:
            print("Creating index for 'simhash'...")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_error_events_simhash ON error_events (simhash)")
            print("Index created.")
        except Exception as e:
            print(f"Warning: Failed to create index: {e}")

        # 3. Infrastructure: URL Fingerprint Library
        print("Migrating 'url_library' schema...")
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS url_library (
                    hash VARCHAR(64) PRIMARY KEY,
                    original_url TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            print("Table 'url_library' ensured.")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_url_library_hash ON url_library (hash)")
            print("Index on url_library(hash) ensured.")
        except Exception as e:
            print(f"Error creating url_library: {e}")

        # 4. Schema Evolution: Article Metadata
        print("Migrating 'news_articles' schema...")
        try:
            cursor.execute("ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS url_hash VARCHAR(64)")
            print("Column 'url_hash' ensured.")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_news_articles_url_hash ON news_articles (url_hash)")
            print("Index on news_articles(url_hash) ensured.")
        except Exception as e:
            print(f"Error adding url_hash to news_articles: {e}")

        # 5. Schema Evolution: Candidate Sources
        print("Migrating 'candidate_sources' schema...")
        try:
            cursor.execute("""
                ALTER TABLE candidate_sources
                ADD COLUMN IF NOT EXISTS citation_count INTEGER DEFAULT 0;
            """)
            print("Schema update applied successfully.")
        except Exception as e:
            print(f"Error migrating candidate_sources: {e}")

        conn.close()
        print("Schema Migration Complete.")
        
    except Exception as e:
        print(f"Critical Migration Failure: {e}")

if __name__ == "__main__":
    apply_updates()
