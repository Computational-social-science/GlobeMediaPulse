from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, func
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass

class FetchLog(Base):
    """
    Log entry for a data fetching operation.
    
    Attributes:
        id (int): Primary key.
        url (str): URL fetched.
        status (str): Status of the fetch (e.g., "success", "error").
        error_message (str): Error details if failed.
        fetcher (str): Name of the fetcher component.
        timestamp (datetime): Time of the fetch operation.
    """
    __tablename__ = "fetch_logs"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(Text)
    status = Column(Text)
    error_message = Column(Text)
    fetcher = Column(Text)
    timestamp = Column(DateTime, server_default=func.now())

class NewsArticle(Base):
    """
    Represents a raw news article fetched from GDELT or other sources.
    
    Attributes:
        id (int): Primary key.
        url (str): Unique URL of the article.
        title (str): Article title.
        country_code (str): Associated country code.
        country_name (str): Associated country name.
        content (str): Full text content of the article.
        published_at (datetime): Publication timestamp.
        scraped_at (datetime): Timestamp when scraped by our system.
        processed (bool): Whether the article has been processed by the pipeline.
        word_count (int): Word count of the article.
    """
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(Text, unique=True)
    title = Column(Text)
    country_code = Column(Text)
    country_name = Column(Text)
    content = Column(Text)
    published_at = Column(DateTime, index=True)
    scraped_at = Column(DateTime)
    processed = Column(Boolean, default=False)
    word_count = Column(Integer, default=0)
    country_source = Column(Text)
    
    # Media Source Classification Fields
    source_tier = Column(Text, index=True) # Tier-0, Tier-1, Tier-2
    source_domain = Column(Text, index=True)
    
    # URL Hashing Strategy (Added)
    url_hash = Column(String(64), index=True, nullable=True) # SHA-256 Hash

class UrlLibrary(Base):
    """
    Central repository for URL Fingerprints.
    Mapping: SHA-256 Hash -> Original URL.
    Used for efficient storage and deduplication.
    """
    __tablename__ = "url_library"
    
    hash = Column(String(64), primary_key=True, index=True)
    original_url = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class CandidateSource(Base):
    """
    Potential media sources discovered during crawling.
    Used for 'Tier-2' discovery and manual validation.
    """
    __tablename__ = "candidate_sources"
    
    domain = Column(Text, primary_key=True, index=True)
    found_on = Column(Text) # URL where this was found (Referer)
    found_at = Column(DateTime, server_default=func.now())
    status = Column(Text, default="pending") # pending, approved, rejected
    tier_suggestion = Column(Text, nullable=True)

class MediaSource(Base):
    """
    Authoritative list of global media sources.
    Includes metadata for tiering, visualization, and structural identification.
    """
    __tablename__ = "media_sources"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(Text, unique=True, index=True, nullable=False)
    name = Column(Text, nullable=False) # Official Name
    abbreviation = Column(Text, nullable=True)
    
    # Geographic & Cultural Metadata
    country_code = Column(Text, index=True) # ISO Alpha-3 preferred
    country_name = Column(Text)
    language = Column(Text) # ISO 639-1/2
    
    # Branding & UI
    logo_url = Column(Text, nullable=True)
    
    # Structural Fingerprinting
    # SimHash for homepage structure/layout (not content) to detect design changes
    structure_simhash = Column(Text, nullable=True) 
    
    # Classification
    tier = Column(Text, default="Tier-2", index=True) # Dynamic Tier: Tier-0, Tier-1, Tier-2
    type = Column(Text, nullable=True) # Newspaper, Broadcaster, Agency, Digital Native
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

