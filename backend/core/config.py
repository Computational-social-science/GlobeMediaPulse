import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application Configuration using Pydantic BaseSettings.
    Reads environment variables automatically.
    """
    PROJECT_NAME: str = "GlobeMediaPulse"
    API_V1_STR: str = "/api"
    
    # Database Configuration
    # Default to local Postgres instance if not set
    _raw_database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5433/globemediapulse",
    )
    DATABASE_URL: str = (
        _raw_database_url.replace("postgres://", "postgresql://", 1)
        if _raw_database_url.startswith("postgres://")
        else _raw_database_url
    )
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6380")
    
    # Path Configuration
    # Resolve project root directory dynamically
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR: str = os.path.join(BASE_DIR, "backend", "data")
    
    # Feature Flags
    ENABLE_REAL_DATA: bool = True
    
    # Media Cloud Integration
    MEDIA_CLOUD_API_KEY: str = os.getenv("MEDIA_CLOUD_API_KEY", "")

    SEED_QUEUE_KEY: str = os.getenv("SEED_QUEUE_KEY", "universal_news:start_urls")
    SEED_SOURCE_TIERS: str = os.getenv("SEED_SOURCE_TIERS", "Tier-0,Tier-1")
    SEED_QUEUE_MIN: int = int(os.getenv("SEED_QUEUE_MIN", "50"))
    SEED_QUEUE_TARGET: int = int(os.getenv("SEED_QUEUE_TARGET", "200"))
    SEED_URL_SCHEME: str = os.getenv("SEED_URL_SCHEME", "https")

    CANDIDATE_PROMOTION_THRESHOLD: int = int(os.getenv("CANDIDATE_PROMOTION_THRESHOLD", "5"))
    CANDIDATE_CITATION_TIERS: str = os.getenv("CANDIDATE_CITATION_TIERS", "Tier-0,Tier-1")

    SOT_ROLE: str = os.getenv("SOT_ROLE", "cache")
    SOT_REMOTE_API_URL: str = os.getenv("SOT_REMOTE_API_URL", os.getenv("REMOTE_API_URL", ""))

    SIMHASH_SIMILARITY_THRESHOLD: int = int(os.getenv("SIMHASH_SIMILARITY_THRESHOLD", "3"))
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
