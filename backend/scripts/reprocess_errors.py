import os
import sys
import logging
import asyncio
from tqdm import tqdm

# Ensure project root is in path
sys.path.append(os.getcwd())

from backend.operators.storage import storage_operator
from backend.operators.detection import detector_operator

logging.basicConfig(level=logging.INFO, filename='reprocess.log')
logger = logging.getLogger(__name__)

def reprocess_2017():
    """
    Legacy Data Reprocessing Script (2017 Dataset).
    
    Functionality:
    Performs a retrospective analysis on archived articles from 2017.
    1.  Fetches articles from the DB within the target date range.
    2.  Re-runs the `DetectorOperator` (Anomaly/Event Detection).
    3.  Updates the database with new detection results.
    
    Note: This script is maintained for historical data audits.
    """
    print("Initiating Reprocessing Pipeline for 2017 Dataset...")
    
    # 1. Data Retrieval
    print("Fetching article batch from Database...")
    articles = []
    
    try:
        with storage_operator.get_connection() as conn:
            if not conn:
                logger.error("Database connection unavailable.")
                return
            cursor = conn.cursor()
            cursor.execute("""
                SELECT url, title, content, country_code, country_name, published_at, scraped_at 
                FROM news_articles 
                WHERE published_at >= '2017-01-01' AND published_at < '2018-01-01'
            """)
            rows = cursor.fetchall()
            for row in rows:
                articles.append({
                    "url": row[0],
                    "title": row[1],
                    "content": row[2],
                    "country_code": row[3],
                    "country_name": row[4],
                    "published_at": row[5],
                    "scraped_at": row[6]
                })
    except Exception as e:
        logger.error(f"Data Retrieval Failed: {e}")
        print(f"Data Retrieval Failed: {e}")
        return

    print(f"Retrieved {len(articles)} articles.")

    # 2. Re-Analysis (Detection)
    print("Executing Detection Operator...")
    
    batch_size = 100
    processed_articles = []
    
    with tqdm(total=len(articles), desc="Processing Articles") as pbar:
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i+batch_size]
            results = detector_operator.detect_batch(batch)
            processed_articles.extend(results)
            pbar.update(len(batch))
    
    # Statistics
    total_errors = sum(len(a.get('errors', [])) for a in processed_articles)
    print(f"Analysis Complete. Identified {total_errors} events in {len(processed_articles)} articles.")
    
    # 3. Persistence
    print("Persisting results to Database...")
    storage_operator.save_articles(processed_articles)
    print("Reprocessing Pipeline Completed Successfully.")

if __name__ == "__main__":
    reprocess_2017()
