
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
    print("Starting reprocessing of 2017 articles...")
    
    # 1. Fetch articles from DB
    print("Fetching articles from DB...")
    articles = []
    
    try:
        with storage_operator.get_connection() as conn:
            if not conn:
                logger.error("No DB connection.")
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
        logger.error(f"DB Error: {e}")
        print(f"DB Error: {e}")
        return

    print(f"Fetched {len(articles)} articles.")

    # 2. Run detection
    print("Running detection...")
    
    # Batch process in chunks to show progress
    batch_size = 100
    processed_articles = []
    
    with tqdm(total=len(articles), desc="Detecting Errors") as pbar:
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i+batch_size]
            results = detector_operator.detect_batch(batch)
            processed_articles.extend(results)
            pbar.update(len(batch))
    
    # Count stats
    total_errors = sum(len(a.get('errors', [])) for a in processed_articles)
    print(f"Detection complete. Found {total_errors} errors in {len(processed_articles)} articles.")
    
    # 3. Save results
    print("Saving results to DB...")
    storage_operator.save_articles(processed_articles)
    print("Done.")

if __name__ == "__main__":
    reprocess_2017()
