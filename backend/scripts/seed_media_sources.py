import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import settings
from backend.core.models import MediaSource, MediaTier

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initial Seed Data (Tier-0: Agencies, Tier-1: Major Broadcasters/Papers)
SEED_DATA = [
    # --- Original Seeds ---
    {"name": "Reuters", "domain": "reuters.com", "country_name": "United Kingdom", "country_code": "GBR", "tier": "Tier-0", "type": "Agency", "language": "en"},
    {"name": "Associated Press", "domain": "apnews.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-0", "type": "Agency", "language": "en"},
    {"name": "Agence France-Presse", "domain": "afp.com", "country_name": "France", "country_code": "FRA", "tier": "Tier-0", "type": "Agency", "language": "fr"},
    {"name": "BBC News", "domain": "bbc.com", "country_name": "United Kingdom", "country_code": "GBR", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "CNN", "domain": "cnn.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "Al Jazeera", "domain": "aljazeera.com", "country_name": "Qatar", "country_code": "QAT", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "New York Times", "domain": "nytimes.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "The Guardian", "domain": "theguardian.com", "country_name": "United Kingdom", "country_code": "GBR", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "Washington Post", "domain": "washingtonpost.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "Le Monde", "domain": "lemonde.fr", "country_name": "France", "country_code": "FRA", "tier": "Tier-1", "type": "Newspaper", "language": "fr"},
    {"name": "Der Spiegel", "domain": "spiegel.de", "country_name": "Germany", "country_code": "DEU", "tier": "Tier-1", "type": "Newspaper", "language": "de"},
    {"name": "El Pais", "domain": "elpais.com", "country_name": "Spain", "country_code": "ESP", "tier": "Tier-1", "type": "Newspaper", "language": "es"},
    {"name": "China Daily", "domain": "chinadaily.com.cn", "country_name": "China", "country_code": "CHN", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "Russia Today", "domain": "rt.com", "country_name": "Russia", "country_code": "RUS", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "Times of India", "domain": "timesofindia.indiatimes.com", "country_name": "India", "country_code": "IND", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "The Australian", "domain": "theaustralian.com.au", "country_name": "Australia", "country_code": "AUS", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "Globe and Mail", "domain": "theglobeandmail.com", "country_name": "Canada", "country_code": "CAN", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "Asahi Shimbun", "domain": "asahi.com", "country_name": "Japan", "country_code": "JPN", "tier": "Tier-1", "type": "Newspaper", "language": "ja"},
    {"name": "Straits Times", "domain": "straitstimes.com", "country_name": "Singapore", "country_code": "SGP", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "South China Morning Post", "domain": "scmp.com", "country_name": "Hong Kong", "country_code": "HKG", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "O Globo", "domain": "oglobo.globo.com", "country_name": "Brazil", "country_code": "BRA", "tier": "Tier-1", "type": "Newspaper", "language": "pt"},
    {"name": "La Nacion", "domain": "lanacion.com.ar", "country_name": "Argentina", "country_code": "ARG", "tier": "Tier-1", "type": "Newspaper", "language": "es"},
    {"name": "Ahram Online", "domain": "english.ahram.org.eg", "country_name": "Egypt", "country_code": "EGY", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "Daily Nation", "domain": "nation.africa", "country_name": "Kenya", "country_code": "KEN", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "Jakarta Post", "domain": "thejakartapost.com", "country_name": "Indonesia", "country_code": "IDN", "tier": "Tier-1", "type": "Newspaper", "language": "en"},

    # --- Expanded Seeds (Wiki Import 2026-01-26) ---
    # News Agencies
    {"name": "Xinhua", "domain": "xinhuanet.com", "country_name": "China", "country_code": "CHN", "tier": "Tier-0", "type": "Agency", "language": "en"},
    {"name": "EFE", "domain": "efe.com", "country_name": "Spain", "country_code": "ESP", "tier": "Tier-0", "type": "Agency", "language": "es"},
    {"name": "DPA", "domain": "dpa.com", "country_name": "Germany", "country_code": "DEU", "tier": "Tier-0", "type": "Agency", "language": "de"},
    {"name": "ANSA", "domain": "ansa.it", "country_name": "Italy", "country_code": "ITA", "tier": "Tier-0", "type": "Agency", "language": "it"},
    {"name": "Kyodo News", "domain": "kyodonews.net", "country_name": "Japan", "country_code": "JPN", "tier": "Tier-0", "type": "Agency", "language": "en"},
    {"name": "Yonhap", "domain": "yna.co.kr", "country_name": "South Korea", "country_code": "KOR", "tier": "Tier-0", "type": "Agency", "language": "en"},
    {"name": "TASS", "domain": "tass.com", "country_name": "Russia", "country_code": "RUS", "tier": "Tier-0", "type": "Agency", "language": "en"},

    # Global Broadcasters & Channels
    {"name": "Sky News", "domain": "news.sky.com", "country_name": "United Kingdom", "country_code": "GBR", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "ABC News Australia", "domain": "abc.net.au", "country_name": "Australia", "country_code": "AUS", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "CBC", "domain": "cbc.ca", "country_name": "Canada", "country_code": "CAN", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "Euronews", "domain": "euronews.com", "country_name": "European Union", "country_code": "EU", "tier": "Tier-1", "type": "Broadcaster", "language": "en"},
    {"name": "TeleSUR", "domain": "telesurtv.net", "country_name": "Venezuela", "country_code": "VEN", "tier": "Tier-1", "type": "Broadcaster", "language": "es"},

    # High Circulation Newspapers
    {"name": "The Yomiuri Shimbun", "domain": "yomiuri.co.jp", "country_name": "Japan", "country_code": "JPN", "tier": "Tier-1", "type": "Newspaper", "language": "ja"},
    {"name": "The Asahi Shimbun", "domain": "asahi.com", "country_name": "Japan", "country_code": "JPN", "tier": "Tier-1", "type": "Newspaper", "language": "ja"},
    {"name": "USA Today", "domain": "usatoday.com", "country_name": "United States", "country_code": "USA", "tier": "Tier-1", "type": "Newspaper", "language": "en"},
    {"name": "Dainik Bhaskar", "domain": "bhaskar.com", "country_name": "India", "country_code": "IND", "tier": "Tier-1", "type": "Newspaper", "language": "hi"},
    {"name": "Dainik Jagran", "domain": "jagran.com", "country_name": "India", "country_code": "IND", "tier": "Tier-1", "type": "Newspaper", "language": "hi"},
    {"name": "The Mainichi", "domain": "mainichi.jp", "country_name": "Japan", "country_code": "JPN", "tier": "Tier-1", "type": "Newspaper", "language": "ja"},
    {"name": "Cankao Xiaoxi", "domain": "cankaoxiaoxi.com", "country_name": "China", "country_code": "CHN", "tier": "Tier-1", "type": "Newspaper", "language": "zh"},
    {"name": "Amar Ujala", "domain": "amarujala.com", "country_name": "India", "country_code": "IND", "tier": "Tier-1", "type": "Newspaper", "language": "hi"},
    {"name": "The Nikkei", "domain": "nikkei.com", "country_name": "Japan", "country_code": "JPN", "tier": "Tier-1", "type": "Newspaper", "language": "ja"},
    {"name": "People's Daily", "domain": "people.cn", "country_name": "China", "country_code": "CHN", "tier": "Tier-1", "type": "Newspaper", "language": "zh"},
    {"name": "Hindustan", "domain": "livehindustan.com", "country_name": "India", "country_code": "IND", "tier": "Tier-1", "type": "Newspaper", "language": "hi"},
    {"name": "Malayala Manorama", "domain": "manoramaonline.com", "country_name": "India", "country_code": "IND", "tier": "Tier-1", "type": "Newspaper", "language": "ml"},
    {"name": "Bild", "domain": "bild.de", "country_name": "Germany", "country_code": "DEU", "tier": "Tier-1", "type": "Newspaper", "language": "de"},
    {"name": "Guangzhou Daily", "domain": "gzdaily.dayoo.com", "country_name": "China", "country_code": "CHN", "tier": "Tier-1", "type": "Newspaper", "language": "zh"},
    {"name": "Nanfang City News", "domain": "nandu.com", "country_name": "China", "country_code": "CHN", "tier": "Tier-1", "type": "Newspaper", "language": "zh"},
    {"name": "Rajasthan Patrika", "domain": "patrika.com", "country_name": "India", "country_code": "IND", "tier": "Tier-1", "type": "Newspaper", "language": "hi"},
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