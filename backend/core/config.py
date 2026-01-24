
import os
from pydantic_settings import BaseSettings

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
    
    # Path Configuration
    # Resolve project root directory dynamically
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR: str = os.path.join(BASE_DIR, "backend", "data")
    
    # Feature Flags
    ENABLE_REAL_DATA: bool = True
    
    class Config:
        case_sensitive = True

settings = Settings()
