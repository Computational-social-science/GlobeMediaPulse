import os
import sys
import logging
from sqlalchemy import create_engine, text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """
    Database Migration Script: Adds 'citation_count' column to 'candidate_sources'.
    
    Scientific Motivation:
    To support the "Snowball Sampling" algorithm, we need to quantify the influence of potential 
    Tier-2 sources. The 'citation_count' metric tracks how many times a candidate domain 
    has been cited by Tier-0 sources, serving as a proxy for its authority and relevance.
    """
    url = settings.DATABASE_URL
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(url)
    
    with engine.connect() as conn:
        try:
            # Idempotent Migration: Add column only if it doesn't exist
            logger.info("Migrating Schema: Checking for 'citation_count' in 'candidate_sources'...")
            conn.execute(text("ALTER TABLE candidate_sources ADD COLUMN IF NOT EXISTS citation_count INTEGER DEFAULT 1"))
            conn.commit()
            logger.info("Migration Successful: 'citation_count' column ensured.")
        except Exception as e:
            logger.error(f"Migration Failed: {e}")

if __name__ == "__main__":
    migrate()
