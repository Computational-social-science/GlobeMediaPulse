import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
# Adjust path to include the parent directory of 'backend'
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.models import MediaSource
from backend.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data extracted from Wikipedia references and general knowledge
# Format: Name, Domain, Country, Tier, Type, Language
SEED_DATA = [
    # --- News Agencies (Tier-0) ---
    {"name": "Reuters", "domain": "reuters.com", "country_name": "United Kingdom", "country_code": "GBR", "tier": "Tier-0", "type": "Agency", "language": "en"},
    {"name": "Associated Press", "domain": "apnews.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Agency", "language": "en"},
    {"name": "Agence France-Presse", "domain": "afp.com", "country_name": "France", "country_code": "FRA", "tier": "Tier-0", "type": "Agency", "language": "fr"},
    {"name": "Bloomberg", "domain": "bloomberg.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Agency", "language": "en"},

    # --- World News Channels (Tier-0/Tier-1) ---
    {"name": "BBC News", "domain": "bbc.com", "country_name": "United Kingdom", "country_code": "GBR", "tier": "Tier-0", "type": "Broadcaster", "language": "en"},
    {"name": "CNN", "domain": "cnn.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Broadcaster", "language": "en"},
    {"name": "Al Jazeera", "domain": "aljazeera.com", "country_name": "Qatar", "country_code": "QAT", "tier": "Tier-0", "type": "Broadcaster", "language": "en"},
    {"name": "Deutsche Welle", "domain": "dw.com", "country_name": "Germany", "country_code": "DEU", "tier": "Tier-0", "type": "Broadcaster", "language": "en"},
    {"name": "France 24", "domain": "france24.com", "country_name": "France", "country_code": "FRA", "tier": "Tier-0", "type": "Broadcaster", "language": "en"},
    {"name": "NHK World", "domain": "nhk.or.jp", "country_name": "Japan", "country_code": "JPN", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "RT", "domain": "rt.com", "country_name": "Russia", "country_code": "RUS", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "CNA", "domain": "channelnewsasia.com", "country_name": "Singapore", "country_code": "SGP", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "Voice of America", "domain": "voanews.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    
    # --- Major Newspapers (Tier-0/Tier-1) ---
    {"name": "The New York Times", "domain": "nytimes.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Newspaper", "language": "en"},
    {"name": "The Wall Street Journal", "domain": "wsj.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Newspaper", "language": "en"},
    {"name": "The Washington Post", "domain": "washingtonpost.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Newspaper", "language": "en"},
    {"name": "The Guardian", "domain": "theguardian.com", "country_name": "United Kingdom", "country_code": "GBR", "tier": "Tier-0", "type": "Newspaper", "language": "en"},
    {"name": "Financial Times", "domain": "ft.com", "country_name": "United Kingdom", "country_code": "GBR", "tier": "Tier-0", "type": "Newspaper", "language": "en"},
    {"name": "Yomiuri Shimbun", "domain": "yomiuri.co.jp", "country_name": "Japan", "country_code": "JPN", "tier": "Tier-1", "type": "Newspaper", "language": "ja"},
    {"name": "Asahi Shimbun", "domain": "asahi.com", "country_name": "Japan", "country_code": "JPN", "tier": "Tier-1", "type": "Newspaper", "language": "ja"},
    {"name": "China Daily", "domain": "chinadaily.com.cn", "country_name": "China", "country_code": "CHN", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "Times of India", "domain": "timesofindia.indiatimes.com", "country_name": "India", "country_code": "IND", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "El País", "domain": "elpais.com", "country_name": "Spain", "country_code": "ESP", "tier": "Tier-1", "type": "Newspaper", "language": "es"},
    {"name": "Le Monde", "domain": "lemonde.fr", "country_name": "France", "country_code": "FRA", "tier": "Tier-1", "type": "Newspaper", "language": "fr"},
    {"name": "South China Morning Post", "domain": "scmp.com", "country_name": "Hong Kong", "country_code": "HKG", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
]

def seed_media_sources():
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        count = 0
        for data in SEED_DATA:
            # Check if exists
            exists = db.query(MediaSource).filter(MediaSource.domain == data["domain"]).first()
            if not exists:
                source = MediaSource(
                    name=data["name"],
                    domain=data["domain"],
                    country_name=data["country_name"],
                    country_code=data["country_code"],
                    tier=data["tier"],
                    type=data["type"],
                    language=data["language"]
                )
                db.add(source)
                count += 1
            else:
                # Optional: Update fields if needed
                pass
        
        db.commit()
        logger.info(f"Successfully seeded {count} new media sources.")
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_media_sources()
