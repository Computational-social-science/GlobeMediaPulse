
import redis
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def reset_redis():
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    r = redis.Redis(host=redis_host, port=redis_port, db=0)
    
    keys = ["news_urls_queue", "seen_urls_bloom", "failed_urls_retry"]
    
    for key in keys:
        if r.exists(key):
            r.delete(key)
            print(f"Deleted key: {key}")
        else:
            print(f"Key not found: {key}")

if __name__ == "__main__":
    reset_redis()
