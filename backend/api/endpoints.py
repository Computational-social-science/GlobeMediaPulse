import json
import asyncio
import os
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, WebSocket, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.operators.storage import storage_operator
from backend.core.shared_state import news_queue, country_geo_map
from backend.core.config import settings
from backend.core.database import db_manager
from backend.core.models import MediaSource
from backend.operators.system.process_manager import process_manager
from backend.operators.system.guardian import system_guardian
from backend.core.logging_handlers import ws_log_handler

router = APIRouter()

@router.get("/metadata/countries")
def get_countries() -> Dict[str, Any]:
    """
    Retrieve the mapping of country codes to country metadata.

    Research motivation: enforce a stable code-to-attribute map to minimize
    downstream uncertainty in spatial joins and reduce error propagation
    $\epsilon=\|g(\hat{c})-g(c)\|$ when country codes are noisy.
    """
    return storage_operator.countries_map

@router.get("/metadata/geojson")
def get_geojson() -> Dict[str, Any]:
    """
    Retrieve the GeoJSON data for world countries.

    Scientific role: provides boundary geometry $G=\{g_i\}_{i=1}^n$ used by
    spatial kernels and visualization operators.
    """
    geojson_path = os.path.join("backend", "data", "countries.geo.json")
    if os.path.exists(geojson_path):
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson = json.load(f)
        data_path = os.path.join("data", "countries_data.json")
        if os.path.exists(data_path):
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            countries = data.get("COUNTRIES") if isinstance(data, dict) else data
            if isinstance(countries, list):
                by_code = {}
                for c in countries:
                    code = c.get("code")
                    if code:
                        by_code[code] = c
                features = geojson.get("features", [])
                existing_codes = {feature.get("id") for feature in features if feature.get("id")}
                for feature in features:
                    code = feature.get("id")
                    if code and code in by_code:
                        c = by_code[code]
                        props = feature.setdefault("properties", {})
                        if c.get("name"):
                            props["name"] = c.get("name")
                        if c.get("lat") is not None:
                            props["lat"] = float(c.get("lat"))
                        if c.get("lng") is not None:
                            props["lng"] = float(c.get("lng"))
                        if c.get("region"):
                            props["region"] = c.get("region")
                for code, c in by_code.items():
                    if code in existing_codes:
                        continue
                    lat = c.get("lat")
                    lng = c.get("lng")
                    if lat is None or lng is None:
                        continue
                    delta = 0.5
                    lat = float(lat)
                    lng = float(lng)
                    feature = {
                        "type": "Feature",
                        "id": code,
                        "properties": {
                            "name": c.get("name") or code,
                            "lat": lat,
                            "lng": lng,
                            "region": c.get("region") or "Unknown"
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [lng - delta, lat - delta],
                                [lng + delta, lat - delta],
                                [lng + delta, lat + delta],
                                [lng - delta, lat + delta],
                                [lng - delta, lat - delta]
                            ]]
                        }
                    }
                    features.append(feature)
                geojson["features"] = features
        return geojson
    return {"error": "GeoJSON not found"}

@router.get("/map-data")
def get_map_data() -> Dict[str, Any]:
    """
    Get aggregated map statistics for visualization.

    Aggregation follows $\hat{s}=\sum_{i=1}^{N} \phi(x_i)$ where $\phi(\cdot)$
    is a storage operator summarizing global source statistics.
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

    Research motivation: preserve reproducibility during controlled tests,
    while constraining compute to $R \leq 50$ records per call.
    """
    return {"status": "deprecated", "message": "GDELT fetching is disabled. Use Scrapy scheduler."}

@router.get("/media/sources")
def get_media_sources() -> List[Dict[str, Any]]:
    """
    Retrieve all media sources from the database.

    This endpoint exposes the canonical source set $S=\{s_i\}_{i=1}^N$
    for UI browsing and data audits.
    """
    return storage_operator.get_all_media_sources()

@router.get("/stats/brain")
def get_brain_stats() -> Dict[str, Any]:
    """
    Get aggregated intelligence stats (Entities, Narrative Divergence).

    The divergence metric follows $\Delta=\mu_{T0}-\mu_{T2}$ where
    $\mu_{Tk}$ denotes aggregated narrative signals for tier $k$ sources.
    """
    return storage_operator.get_brain_stats()

@router.get("/stats/heatmap", response_model=List[Dict[str, Any]])
def get_heatmap_data(db: Session = Depends(db_manager.get_db)) -> List[Dict[str, Any]]:
    """
    Return aggregated media source density per country for heatmap rendering.

    We estimate density as counts $\rho(c)=\sum_{i=1}^{N}\mathbb{1}[c_i=c]$
    and normalize in the client to avoid server-side coupling to UI scale.
    """
    results = db.query(
        MediaSource.country_code,
        func.count(MediaSource.id)
    ).filter(
        MediaSource.country_code != None,
        MediaSource.country_code != 'UNK'
    ).group_by(MediaSource.country_code).all()
    return [{"code": r[0], "count": r[1]} for r in results if r[0]]

@router.post("/system/crawler/start")
async def start_crawler() -> Dict[str, str]:
    """
    Start the news crawler process with single-command control $u\in\{\text{start}\}$.

    Research motivation: deterministic control reduces ingestion latency variance
    $\sigma^2(\tau)$ under bursty workloads.
    """
    if process_manager.is_crawler_running():
        return {"status": "already_running", "message": "Crawler is already active."}
    process_manager.start_crawler()
    return {"status": "started", "message": "Crawler process initiated."}

@router.post("/system/crawler/stop")
async def stop_crawler() -> Dict[str, str]:
    """
    Stop the crawler to prevent resource contention $C=\sum r_i$.
    """
    if not process_manager.is_crawler_running():
        return {"status": "not_running", "message": "Crawler is not running."}
    process_manager.stop_crawler()
    return {"status": "stopped", "message": "Crawler process terminated."}

@router.post("/system/crawler/restart")
async def restart_crawler() -> Dict[str, str]:
    """
    Restart the crawler to recover from transient failures $p_f(t)$.
    """
    process_manager.restart_crawler()
    return {"status": "restarted", "message": "Crawler process restarted."}

@router.get("/system/logs/recent")
async def get_recent_logs() -> List[Dict[str, Any]]:
    """
    Return buffered logs for UI inspection and human-in-the-loop diagnosis.
    """
    return list(ws_log_handler.log_buffer)

@router.get("/system/health/full")
async def health_full(autoheal: bool = False) -> Dict[str, Any]:
    """
    Full system health check with optional self-healing action $a\in\{0,1\}$.
    """
    return await system_guardian.check_health(autoheal=autoheal)

@router.post("/system/health/autoheal")
async def autoheal() -> Dict[str, Any]:
    """
    Trigger self-healing to mitigate cascading failures and stabilize $R(t)$.
    """
    report = await system_guardian.auto_heal()
    status = await system_guardian.check_health(autoheal=False)
    status["self_heal"] = report
    return status

@router.get("/health")
def health_check() -> Dict[str, str]:
    """
    Health check endpoint for rapid liveness validation.
    """
    return {"status": "ok"}
