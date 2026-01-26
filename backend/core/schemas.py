from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

class MediaTier(str, Enum):
    """
    Classification of media sources based on influence and geographic scope.
    
    Research Motivation:
        - **Tier-0 (Global Mainstream)**: High-impact, globally cited sources (e.g., Reuters, AP). 
          Used as "seed nodes" for snowball sampling.
        - **Tier-1 (National Mainstream)**: Major national outlets with significant domestic influence.
        - **Tier-2 (Local/Regional)**: Hyper-local or niche sources. 
          Target for discovery via citation analysis from Tier-0/1.
    """
    TIER_0 = "Tier-0"  # Global Mainstream
    TIER_1 = "Tier-1"  # National Mainstream
    TIER_2 = "Tier-2"  # Local/Regional
    UNKNOWN = "Unknown"

class MediaSource(BaseModel):
    """
    Data model representing a verified media source.
    """
    name: str
    domain: str
    tier: MediaTier
    country: Optional[str] = None
    language: Optional[str] = None
    tags: List[str] = []

class MediaLibrary(BaseModel):
    """
    Collection of verified media sources.
    Used for bulk initialization and configuration.
    """
    sources: List[MediaSource]
