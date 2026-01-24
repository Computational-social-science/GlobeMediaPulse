
import asyncio
import os
import sys
import logging
from datetime import datetime

# Adjust path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.pipelines.data_pipeline import DataPipeline
from backend.core.database import db_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    print("--- Starting Verification Script ---")
    
    # 1. Initialize Pipeline
    pipeline = DataPipeline()
    
    # 2. Run Pipeline (Fetch small batch)
    print("\nRunning Pipeline (Fetch -> Detect -> Store)...")
    try:
        # Use a query that likely has results
        processed = await pipeline.run(query="sourcelang:eng", max_records=5)
        
        print(f"\nPipeline finished. Processed {len(processed)} articles.")
        
        if processed:
            print("\nSample Article Data:")
            a = processed[0]
            print(f"Title: {a.get('title')}")
            print(f"Country: {a.get('country')}")
            print(f"Date: {a.get('date')}")
            print(f"Word Count: {a.get('word_count')}")
            print(f"Errors Found: {len(a.get('errors', []))}")
            if a.get('errors'):
                print(f"First Error: {a['errors'][0]}")
    except Exception as e:
        print(f"Pipeline Error: {e}")
        import traceback
        traceback.print_exc()

    # 3. Check DB Pool
    print("\nChecking DB Pool Status...")
    pool = db_manager.get_pool()
    if pool:
        print("Global DB Pool is active.")
    else:
        print("Global DB Pool is NOT active.")

    # 4. Cleanup
    db_manager.close()
    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(main())
