import os
import re
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Settings(BaseSettings):
    """
    Application Configuration using Pydantic BaseSettings.
    Reads environment variables automatically.
    """
    PROJECT_NAME: str = "GlobeMediaPulse"
    API_V1_STR: str = "/api"
    
    # Database Configuration
    # Default to local Postgres instance if not set
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "globemediapulse"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433
    DATABASE_URL: str | None = None

    @model_validator(mode="after")
    def _build_database_url(self) -> "Settings":
        if not self.DATABASE_URL or not re.search(r"://[^:]+:[^@]+@", self.DATABASE_URL):
            self.DATABASE_URL = (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_database_url(cls, value: str | None) -> str | None:
        if value and value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql://", 1)
        return value
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Path Configuration
    # Resolve project root directory dynamically
    BASE_DIR: str = PROJECT_ROOT
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
    
    model_config = SettingsConfigDict(env_file=os.path.join(PROJECT_ROOT, ".env"), case_sensitive=True, extra="ignore")

settings = Settings()
