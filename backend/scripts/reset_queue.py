import redis
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def reset_redis():
    """
    Redis State Reset Utility.
    
    Functionality:
    Clears all application-specific keys from Redis, effectively resetting the 
    crawling state. This includes:
    -   Duplication Filters (`universal_news:dupefilter`)
    -   Request Queues (`universal_news:requests`)
    -   URL Queues (`news_urls_queue`)
    -   Bloom Filters (`seen_urls_bloom`)
    
    Use Case:
    Run this script when you need to restart the crawling process from scratch 
    or clear out stale data after a failed run.
    """
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        print(f"Connecting to Redis via REDIS_URL")
        r = redis.from_url(redis_url)
    else:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        print(f"Connecting to Redis at {redis_host}:{redis_port}")
        r = redis.Redis(host=redis_host, port=redis_port, db=0)
    
    # Target Keys for Cleanup
    keys = [
        "universal_news:dupefilter", 
        "universal_news:requests",
        "news_urls_queue", 
        "seen_urls_bloom", 
        "failed_urls_retry"
    ]
    
    print("Initiating Redis State Reset...")
    for key in keys:
        if r.exists(key):
            r.delete(key)
            print(f" - Deleted Key: {key}")
        else:
            print(f" - Key Not Found (Skipped): {key}")
    
    print("Redis Reset Complete.")

if __name__ == "__main__":
    reset_redis()
