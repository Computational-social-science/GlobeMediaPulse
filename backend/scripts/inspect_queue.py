
import sys
import os
import redis

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import settings

def check_queue():
    r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", 6379)))
    q_key = "news_urls_queue"
    
    size = r.llen(q_key)
    print(f"Queue Size: {size}")
    
    if size > 0:
        print("First 5 items:")
        items = r.lrange(q_key, 0, 4)
        for i in items:
            print(i)
            
    # Optional: Clear queue if user wants "Live" and queue is clogged with history
    if size > 1000:
        print("Queue is large. Clearing for fresh start...")
        r.delete(q_key)
        print("Queue cleared.")

if __name__ == "__main__":
    check_queue()
