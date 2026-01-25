import os
import sys
import logging
import psycopg2
from urllib.parse import urlparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """
    Migration V2: Add Fingerprinting Columns to Media Sources.
    """
    db_url = settings.DATABASE_URL
    if not db_url:
        logger.error("DATABASE_URL not set")
        return

    # Patch for Fly.io/SQLAlchemy compatibility if needed (though we use raw psycopg2 here which is fine with postgres://)
    # But settings.DATABASE_URL might be postgresql:// already.
    
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='media_sources' AND column_name='logo_hash';
        """)
        if cursor.fetchone():
            logger.info("Column 'logo_hash' already exists. Skipping.")
        else:
            logger.info("Adding column 'logo_hash'...")
            cursor.execute("ALTER TABLE media_sources ADD COLUMN logo_hash TEXT;")
            cursor.execute("CREATE INDEX ix_media_sources_logo_hash ON media_sources (logo_hash);")

        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='media_sources' AND column_name='copyright_text';
        """)
        if cursor.fetchone():
            logger.info("Column 'copyright_text' already exists. Skipping.")
        else:
            logger.info("Adding column 'copyright_text'...")
            cursor.execute("ALTER TABLE media_sources ADD COLUMN copyright_text TEXT;")

        conn.commit()
        logger.info("Migration V2 completed successfully.")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate()
