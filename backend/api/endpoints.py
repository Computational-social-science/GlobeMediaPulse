import json
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, WebSocket, Query
from backend.operators.storage import storage_operator
from backend.core.shared_state import news_queue, country_geo_map
from backend.core.config import settings
from backend.core.data import GEOJSON_PATH

router = APIRouter()

@router.get("/metadata/countries")
def get_countries() -> Dict[str, Any]:
    """
    Retrieve the mapping of country codes to country metadata.
    """
    return storage_operator.countries_map

@router.get("/metadata/geojson")
def get_geojson() -> Dict[str, Any]:
    """
    Retrieve the GeoJSON data for world countries.
    """
    if GEOJSON_PATH.exists():
        with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"error": "GeoJSON not found"}

@router.get("/map-data")
def get_map_data() -> Dict[str, Any]:
    """
    Get aggregated map statistics for visualization.
    """
    return storage_operator.get_stats()

@router.post("/debug/fetch-news")
async def trigger_news_fetch(
    query: str = Query("sourcelang:eng", description="GDELT query string"), 
    max_records: int = Query(50, description="Maximum records to fetch"),
    start_date: Optional[str] = Query(None, description="Start date filter"),
    end_date: Optional[str] = Query(None, description="End date filter")
) -> Dict[str, Any]:
    """
    Manually trigger the news fetching pipeline for debugging purposes.
    DEPRECATED: This endpoint is disabled as we move to Scrapy-based architecture.
    """
    return {"status": "deprecated", "message": "GDELT fetching is disabled. Use Scrapy scheduler."}

@router.get("/media/sources")
def get_media_sources() -> List[Dict[str, Any]]:
    """
    Retrieve all media sources from the database.
    """
    return storage_operator.get_all_media_sources()

@router.get("/stats/brain")
def get_brain_stats() -> Dict[str, Any]:
    """
    Get aggregated intelligence stats (Entities, Narrative Divergence).
    """
    return storage_operator.get_brain_stats()

@router.get("/health")
def health_check() -> Dict[str, str]:
    """
    Health check endpoint.
    """
    return {"status": "ok"}
