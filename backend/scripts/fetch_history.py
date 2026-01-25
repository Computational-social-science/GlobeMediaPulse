import asyncio
import os
import sys
import logging
from datetime import datetime, timedelta
import argparse
from tqdm.asyncio import tqdm

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.producer import GDELTProducer

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fetch_history.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def fetch_history(start_date, end_date, interval_hours=1):
    """
    Historical Data Backfill Utility.
    
    Functionality:
    Iteratively fetches historical news URLs from the GDELT 2.0 API within a specified date range 
    and pushes them to the Redis Queue for asynchronous processing.
    
    Args:
        start_date (datetime): The starting timestamp for backfilling.
        end_date (datetime): The ending timestamp.
        interval_hours (int): The size of each time chunk to fetch (prevents API timeouts).
    """
    producer = GDELTProducer()
    current_start = start_date
    total_pushed = 0
    
    # Calculate total intervals for progress tracking
    total_seconds = (end_date - start_date).total_seconds()
    step_seconds = interval_hours * 3600
    if total_seconds <= 0:
        total_intervals = 1
    else:
        total_intervals = int(total_seconds / step_seconds)
    
    pbar = tqdm(total=total_intervals, desc="Backfilling GDELT History", unit="interval")
    
    while current_start < end_date:
        chunk_end = current_start + timedelta(hours=interval_hours)
        if chunk_end > end_date:
            chunk_end = end_date
             
        try:
            # Fetch from GDELT and Push to Redis
            count = await producer.fetch_urls_for_interval(current_start, chunk_end)
            total_pushed += count
            
            pbar.set_postfix(pushed=total_pushed, last_batch=count)
            
        except Exception as e:
            logger.error(f"Backfill Error in interval {current_start}-{chunk_end}: {e}")
        
        current_start = chunk_end
        pbar.update(1)
        
        # Rate Limiting: Polite pause to respect GDELT API fair usage
        await asyncio.sleep(0.5)
    
    pbar.close()
    print(f"\nBackfill Operation Complete. Total URLs Pushed to Queue: {total_pushed}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GDELT Historical Data Backfill Utility")
    parser.add_argument("--start", type=str, required=True, help="Start Date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, required=True, help="End Date (YYYY-MM-DD)")
    parser.add_argument("--hours", type=int, default=1, help="Chunk size in hours (default: 1)")
    
    args = parser.parse_args()
    
    try:
        s_date = datetime.strptime(args.start, "%Y-%m-%d")
        e_date = datetime.strptime(args.end, "%Y-%m-%d")
        
        asyncio.run(fetch_history(s_date, e_date, args.hours))
    except ValueError:
        print("Error: Invalid date format. Please use YYYY-MM-DD.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBackfill operation interrupted by user.")
