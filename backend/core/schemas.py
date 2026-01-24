from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

class MediaTier(str, Enum):
    TIER_0 = "Tier-0"  # Global Mainstream
    TIER_1 = "Tier-1"  # National Mainstream
    TIER_2 = "Tier-2"  # Local/Regional
    UNKNOWN = "Unknown"

class MediaSource(BaseModel):
    name: str
    domain: str
    tier: MediaTier
    country: str
    language: str
    tags: List[str] = []

class MediaLibrary(BaseModel):
    sources: List[MediaSource]
