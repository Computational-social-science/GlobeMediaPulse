import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path (Parent of 'backend')
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.models import MediaSource
from backend.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Curated Seed Data: "Ground Truth" for Media Tiering
# Sources: Wikipedia, Academic Media Indexes, General Knowledge
# Format: Name, Domain, Country, Tier, Type, Language
SEED_DATA = [
    # --- Tier-0: Global News Agencies (The "Source of Sources") ---
    {"name": "Reuters", "domain": "reuters.com", "country_name": "United Kingdom", "country_code": "GBR", "tier": "Tier-0", "type": "Agency", "language": "en"},
    {"name": "Associated Press", "domain": "apnews.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Agency", "language": "en"},
    {"name": "Agence France-Presse", "domain": "afp.com", "country_name": "France", "country_code": "FRA", "tier": "Tier-0", "type": "Agency", "language": "fr"},
    {"name": "Bloomberg", "domain": "bloomberg.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Agency", "language": "en"},

    # --- Tier-0/Tier-1: Global Broadcasters & Elite Media ---
    {"name": "BBC News", "domain": "bbc.com", "country_name": "United Kingdom", "country_code": "GBR", "tier": "Tier-0", "type": "Broadcaster", "language": "en"},
    {"name": "CNN", "domain": "cnn.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Broadcaster", "language": "en"},
    {"name": "Al Jazeera", "domain": "aljazeera.com", "country_name": "Qatar", "country_code": "QAT", "tier": "Tier-0", "type": "Broadcaster", "language": "en"},
    {"name": "Deutsche Welle", "domain": "dw.com", "country_name": "Germany", "country_code": "DEU", "tier": "Tier-0", "type": "Broadcaster", "language": "en"},
    {"name": "France 24", "domain": "france24.com", "country_name": "France", "country_code": "FRA", "tier": "Tier-0", "type": "Broadcaster", "language": "en"},
    {"name": "The New York Times", "domain": "nytimes.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Newspaper", "language": "en"},
    {"name": "The Wall Street Journal", "domain": "wsj.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Newspaper", "language": "en"},
    {"name": "The Washington Post", "domain": "washingtonpost.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Newspaper", "language": "en"},
    {"name": "The Guardian", "domain": "theguardian.com", "country_name": "United Kingdom", "country_code": "GBR", "tier": "Tier-0", "type": "Newspaper", "language": "en"},
    {"name": "Financial Times", "domain": "ft.com", "country_name": "United Kingdom", "country_code": "GBR", "tier": "Tier-0", "type": "Newspaper", "language": "en"},

    # --- Tier-1: National Hubs ---
    {"name": "NHK World", "domain": "nhk.or.jp", "country_name": "Japan", "country_code": "JPN", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "RT", "domain": "rt.com", "country_name": "Russia", "country_code": "RUS", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "CNA", "domain": "channelnewsasia.com", "country_name": "Singapore", "country_code": "SGP", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "Voice of America", "domain": "voanews.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "Yomiuri Shimbun", "domain": "yomiuri.co.jp", "country_name": "Japan", "country_code": "JPN", "tier": "Tier-1", "type": "Newspaper", "language": "ja"},
    {"name": "Asahi Shimbun", "domain": "asahi.com", "country_name": "Japan", "country_code": "JPN", "tier": "Tier-1", "type": "Newspaper", "language": "ja"},
    {"name": "China Daily", "domain": "chinadaily.com.cn", "country_name": "China", "country_code": "CHN", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "Times of India", "domain": "timesofindia.indiatimes.com", "country_name": "India", "country_code": "IND", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "El País", "domain": "elpais.com", "country_name": "Spain", "country_code": "ESP", "tier": "Tier-1", "type": "Newspaper", "language": "es"},
    {"name": "Le Monde", "domain": "lemonde.fr", "country_name": "France", "country_code": "FRA", "tier": "Tier-1", "type": "Newspaper", "language": "fr"},
    {"name": "South China Morning Post", "domain": "scmp.com", "country_name": "Hong Kong", "country_code": "HKG", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
]

def seed_media_sources():
    """
    Populates the Database with the initial 'Ground Truth' media seed library.
    
    Logic:
    1.  Establishes a DB connection using SQLAlchemy.
    2.  Iterates through the `SEED_DATA` constant.
    3.  Checks for existence to avoid duplicates (Idempotent operation).
    4.  Inserts new records if missing.
    """
    url = settings.DATABASE_URL
    # Patch for Fly.io/SQLAlchemy compatibility (postgres:// -> postgresql://)
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        count = 0
        for data in SEED_DATA:
            # Idempotency Check
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
                # Potential Future Logic: Update fields if schema changes
                pass
        
        db.commit()
        logger.info(f"Initialization Complete: Seeded {count} new media sources.")
    except Exception as e:
        logger.error(f"Seeding Failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_media_sources()
