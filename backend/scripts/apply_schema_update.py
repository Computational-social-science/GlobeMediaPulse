import os
import sys
import psycopg2
from urllib.parse import urlparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import settings

def apply_updates():
    print(f"Connecting to {settings.DATABASE_URL}...")
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 1. Add columns to error_events
        print("Checking 'error_events' table schema...")
        columns_to_add = [
            ("simhash", "TEXT"),
            ("media", "TEXT"),
            ("coordinates", "TEXT")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                print(f"Attempting to add column '{col_name}'...")
                cursor.execute(f"ALTER TABLE error_events ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                print(f"Column '{col_name}' added or already exists.")
            except Exception as e:
                print(f"Error adding column '{col_name}': {e}")
        
        # 2. Add index for simhash
        try:
            print("Adding index for 'simhash'...")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_error_events_simhash ON error_events (simhash)")
            print("Index added.")
        except Exception as e:
            print(f"Error adding index: {e}")

        # 3. Create url_library table (New)
        print("Checking 'url_library' table...")
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS url_library (
                    hash VARCHAR(64) PRIMARY KEY,
                    original_url TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            print("Table 'url_library' created or already exists.")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_url_library_hash ON url_library (hash)")
            print("Index on url_library(hash) ensured.")
        except Exception as e:
            print(f"Error creating url_library: {e}")

        # 4. Add url_hash to news_articles (New)
        print("Checking 'news_articles' table for 'url_hash'...")
        try:
            cursor.execute("ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS url_hash VARCHAR(64)")
            print("Column 'url_hash' added or already exists.")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_news_articles_url_hash ON news_articles (url_hash)")
            print("Index on news_articles(url_hash) ensured.")
        except Exception as e:
            print(f"Error adding url_hash to news_articles: {e}")

        conn.close()
        print("Schema update complete.")
        
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    apply_updates()
