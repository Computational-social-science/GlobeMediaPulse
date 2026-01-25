import sys
import os
import redis

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import settings

def check_queue():
    """
    Redis Queue Inspection Utility.
    
    Functionality:
    -   Connects to the Redis instance.
    -   Reports the current size of the 'news_urls_queue'.
    -   Previews the first 5 items in the queue.
    -   Optionally allows clearing the queue if it exceeds a threshold (manual intervention).
    """
    r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", 6379)))
    q_key = "news_urls_queue"
    
    size = r.llen(q_key)
    print(f"Current Queue Size: {size}")
    
    if size > 0:
        print("Head of Queue Preview (First 5):")
        items = r.lrange(q_key, 0, 4)
        for i in items:
            print(f" - {i}")
            
    # Interactive Management: Prevent queue overflow during development
    if size > 1000:
        print("Warning: Queue size exceeds 1000 items.")
        # Note: Auto-clear is disabled for safety; uncomment if needed for dev reset.
        # print("Clearing queue for fresh start...")
        # r.delete(q_key)
        # print("Queue cleared.")

if __name__ == "__main__":
    check_queue()
