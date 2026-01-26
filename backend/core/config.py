
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
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5433/globemediapulse")
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Path Configuration
    # Resolve project root directory dynamically
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR: str = os.path.join(BASE_DIR, "backend", "data")
    
    # Feature Flags
    ENABLE_REAL_DATA: bool = True
    
    # Media Cloud Integration
    MEDIA_CLOUD_API_KEY: str = os.getenv("MEDIA_CLOUD_API_KEY", "")
    
    model_config = SettingsConfigDict(case_sensitive=True)

settings = Settings()
