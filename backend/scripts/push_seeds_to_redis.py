
import logging
import redis
import os
import sys
from sqlalchemy import create_engine, text
from backend.core.config import settings

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def push_seeds():
    # 1. Connect to Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    try:
        r = redis.from_url(redis_url)
        logger.info(f"Connected to Redis at {redis_url}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return

    # 2. Connect to DB
    db_url = settings.DATABASE_URL
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    try:
        engine = create_engine(db_url)
        logger.info(f"Connected to DB at {db_url}")
    except Exception as e:
        logger.error(f"Failed to connect to DB: {e}")
        return

    # 3. Fetch Seeds
    seeds = []
    with engine.connect() as conn:
        result = conn.execute(text("SELECT domain FROM media_sources"))
        for row in result:
            seeds.append(row[0])
    
    logger.info(f"Fetched {len(seeds)} seeds from DB.")

    # 4. Push to Redis
    key = "universal_news:start_urls"
    count = 0
    for domain in seeds:
        url = f"https://{domain}"
        # lpush adds to the list
        r.lpush(key, url)
        count += 1
        
    logger.info(f"Pushed {count} URLs to {key}")

if __name__ == "__main__":
    push_seeds()
