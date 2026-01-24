import asyncio
import os
import sys
import logging
from datetime import datetime, timedelta
import argparse
import time
import subprocess

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("backfill.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

async def run_producer_consumer_backfill(start_year, end_year, producer_only=False):
    """
    Orchestrates Producer and Consumer processes for backfill.
    """
    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
    producer_script = os.path.join(backend_dir, "producer.py")
    consumer_script = os.path.join(backend_dir, "consumer.py")
    
    # 1. Start Consumer(s)
    consumers = []
    if not producer_only:
        # Start 2 consumers for parallelism
        logger.info("Starting Consumers...")
        for i in range(2):
            c = subprocess.Popen([sys.executable, consumer_script])
            consumers.append(c)
        
    try:
        current_date = datetime(start_year, 1, 1)
        end_date = datetime(end_year, 12, 31)
        if end_date > datetime.now():
            end_date = datetime.now()

        # 2. Run Producer Month by Month
        while current_date < end_date:
            chunk_start = current_date
            if chunk_start.month == 12:
                chunk_end = datetime(chunk_start.year + 1, 1, 1)
            else:
                chunk_end = datetime(chunk_start.year, chunk_start.month + 1, 1)
            
            if chunk_end > end_date:
                chunk_end = end_date + timedelta(days=1)
                
            last_day = chunk_end - timedelta(days=1)
            
            s_str = chunk_start.strftime("%Y-%m-%d")
            e_str = last_day.strftime("%Y-%m-%d")
            
            logger.info(f"=== Producer Task: {s_str} to {e_str} ===")
            
            # Run Producer synchronously (wait for it to finish pushing URLs for this month)
            # Or run it alongside? For backfill, filling the queue too fast might overflow Redis memory if not careful.
            # But URLs are small. 1M URLs is ~500MB. 
            # Safe to run producer for a month, then wait? 
            # Or just run producer for the whole period if we trust Redis?
            # Let's run producer month-by-month to be safe.
            
            proc = await asyncio.create_subprocess_exec(
                sys.executable, producer_script, "--start", s_str, "--end", e_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                logger.info(f"Producer finished for {s_str}-{e_str}")
            else:
                logger.error(f"Producer failed for {s_str}-{e_str}: {stderr.decode()}")
            
            current_date = chunk_end
            
            # Check consumers are still alive
            if not producer_only:
                for i, c in enumerate(consumers):
                    if c.poll() is not None:
                        logger.warning(f"Consumer {i} died. Restarting...")
                        consumers[i] = subprocess.Popen([sys.executable, "-m", "backend.consumer"])

        logger.info("All Producer tasks finished. Waiting for queue to empty is hard without monitoring.")
        if not producer_only:
            logger.info("Keeping consumers alive for 5 more minutes then exiting.")
            await asyncio.sleep(300)
        
    finally:
        if not producer_only:
            logger.info("Stopping Consumers...")
            for c in consumers:
                c.terminate()
                c.wait()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Producer-Consumer Backfill Manager")
    parser.add_argument("--start_year", type=int, default=2017, help="Start year")
    parser.add_argument("--end_year", type=int, default=2025, help="End year")
    parser.add_argument("--producer_only", action="store_true", help="Run only producer (use external consumers)")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_producer_consumer_backfill(args.start_year, args.end_year, args.producer_only))
    except KeyboardInterrupt:
        pass
