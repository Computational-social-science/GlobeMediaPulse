import os
import sys
import logging

# Add project root (parent of backend)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.database import db_manager
from backend.core.models import Base
from sqlalchemy import create_engine
from backend.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """
    Database Initialization Utility.
    
    Functionality:
    Creates all database tables defined in SQLAlchemy models (`Base.metadata`).
    This is typically run once during initial deployment or setup.
    """
    print(f"Initializing Database Schema at {settings.DATABASE_URL}...")
    try:
        url = settings.DATABASE_URL
        # Compatibility Patch for Fly.io (postgres:// -> postgresql://)
        if url and url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
            
        engine = create_engine(url)
        Base.metadata.create_all(bind=engine)
        print("Schema Initialization Successful: Tables created.")
    except Exception as e:
        print(f"Critical Initialization Failure: {e}")

if __name__ == "__main__":
    init_db()
