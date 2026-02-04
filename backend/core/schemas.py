from enum import Enum
from typing import Optional, Dict
from pydantic import BaseModel

class MediaTier(str, Enum):
    TIER_0 = "Tier-0"
    TIER_1 = "Tier-1"
    TIER_2 = "Tier-2"
    UNKNOWN = "UNKNOWN"

class MediaSource(BaseModel):
    domain: str
    name: Optional[str] = None
    short_name: Optional[str] = None
    abbr: Optional[str] = None
    tier: MediaTier = MediaTier.UNKNOWN
    country: str = "UNK"
    country_name: Optional[str] = None
    type: Optional[str] = None
    language: Optional[str] = None
    logo_url: Optional[str] = None
    structure_simhash: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserBase(BaseModel):
    email: str
    is_active: bool = True
    is_superuser: bool = False

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    preferences: Dict = {}

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    password: Optional[str] = None
    preferences: Optional[Dict] = None
