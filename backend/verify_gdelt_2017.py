
import asyncio
import httpx
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_gdelt_2017():
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": "sourcelang:eng",
        "mode": "artlist",
        "maxrecords": "10",
        "format": "json",
        "startdatetime": "20170101000000",
        "enddatetime": "20170102000000"
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            logger.info(f"Requesting GDELT: {base_url} with params {params}")
            resp = await client.get(base_url, params=params)
            logger.info(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("articles", [])
                logger.info(f"Found {len(articles)} articles.")
                for art in articles:
                    logger.info(f"- {art.get('title')} ({art.get('url')})")
            else:
                logger.error(f"Error: {resp.text}")
        except Exception as e:
            logger.error(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_gdelt_2017())
