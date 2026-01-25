import os
import sys
import logging
import psycopg2

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """
    Migration V3: Add Brain Analysis Columns to News Articles.
    """
    db_url = settings.DATABASE_URL
    if not db_url:
        logger.error("DATABASE_URL not set")
        return

    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Columns to add
        new_columns = [
            ("entities", "JSONB"),
            ("sentiment_score", "FLOAT"),
            ("safety_label", "TEXT"),
            ("safety_score", "FLOAT")
        ]

        for col_name, col_type in new_columns:
            cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='news_articles' AND column_name='{col_name}';
            """)
            if cursor.fetchone():
                logger.info(f"Column '{col_name}' already exists. Skipping.")
            else:
                logger.info(f"Adding column '{col_name}'...")
                cursor.execute(f"ALTER TABLE news_articles ADD COLUMN {col_name} {col_type};")

        conn.commit()
        logger.info("Migration V3 (Brain) completed successfully.")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate()
