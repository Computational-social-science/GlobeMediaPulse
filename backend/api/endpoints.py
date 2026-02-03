import json
import asyncio
import os
import time
from functools import lru_cache
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, WebSocket, Query, Depends, HTTPException, Header
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

def _require_sync_token(x_sync_token: Optional[str]) -> None:
    expected = os.getenv("SYNC_TOKEN", "").strip()
    if not expected or not x_sync_token or x_sync_token.strip() != expected:
        raise HTTPException(status_code=403, detail="forbidden")

def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None

def _centroid_from_geometry(geometry: Any) -> Optional[Dict[str, float]]:
    if not isinstance(geometry, dict):
        return None
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")
    if geom_type not in ("Polygon", "MultiPolygon") or not isinstance(coords, list):
        return None
    ring = None
    if geom_type == "Polygon":
        if coords and isinstance(coords[0], list):
            ring = coords[0]
    else:
        if coords and isinstance(coords[0], list) and coords[0] and isinstance(coords[0][0], list):
            ring = coords[0][0]
    if not isinstance(ring, list) or not ring:
        return None
    lng_sum = 0.0
    lat_sum = 0.0
    n = 0
    for pt in ring:
        if not isinstance(pt, list) or len(pt) < 2:
            continue
        lng = _safe_float(pt[0])
        lat = _safe_float(pt[1])
        if lng is None or lat is None:
            continue
        lng_sum += lng
        lat_sum += lat
        n += 1
    if n == 0:
        return None
    return {"lng": lng_sum / n, "lat": lat_sum / n}

@lru_cache(maxsize=1)
def _load_countries_geojson() -> Optional[Dict[str, Any]]:
    paths = [
        os.path.join("backend", "data", "countries.geo.json"),
        os.path.join("data", "countries.geo.json"),
        os.path.join("backend", "core", "data", "countries.geo.json"),
        os.path.join("core", "data", "countries.geo.json"),
    ]
    for p in paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return None

def _alpha2_from_alpha3(code_alpha3: str) -> Optional[str]:
    try:
        import pycountry

        c = pycountry.countries.get(alpha_3=code_alpha3)
        if c and getattr(c, "alpha_2", None):
            return str(c.alpha_2).upper()
    except Exception:
        return None
    return None

@lru_cache(maxsize=1)
def _load_countries_data() -> List[Dict[str, Any]]:
    data_path = os.path.join("data", "countries_data.json")
    alt_data_path = os.path.join("..", "data", "countries_data.json")
    resolved_data_path = data_path if os.path.exists(data_path) else (alt_data_path if os.path.exists(alt_data_path) else None)
    by_code: Dict[str, Dict[str, Any]] = {}
    if resolved_data_path:
        try:
            with open(resolved_data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            countries = data.get("COUNTRIES") if isinstance(data, dict) else data
            if isinstance(countries, list):
                for entry in countries:
                    if not isinstance(entry, dict):
                        continue
                    code = entry.get("code")
                    if not code:
                        continue
                    code_upper = str(code).upper()
                    by_code[code_upper] = entry
        except Exception:
            by_code = {}

    geojson = _load_countries_geojson()
    if not isinstance(geojson, dict):
        normalized: List[Dict[str, Any]] = []
        for code_upper, entry in by_code.items():
            lat = _safe_float(entry.get("lat"))
            lng = _safe_float(entry.get("lng"))
            if lat is None or lng is None:
                continue
            code_alpha2 = entry.get("code_alpha2") or _alpha2_from_alpha3(code_upper)
            normalized.append(
                {
                    **entry,
                    "code": code_upper,
                    "lat": lat,
                    "lng": lng,
                    "region": entry.get("region") or "Unknown",
                    "code_alpha2": code_alpha2,
                }
            )
        return normalized

    features = geojson.get("features", [])
    if not isinstance(features, list):
        return []

    normalized: List[Dict[str, Any]] = []
    existing_codes: set[str] = set()

    for feature in features:
        if not isinstance(feature, dict):
            continue
        code = feature.get("id")
        if not code or str(code) == "-99":
            continue
        code_upper = str(code).upper()
        if code_upper == "CS-KM":
            code_upper = "XKX"
        existing_codes.add(code_upper)

        props = feature.get("properties", {}) if isinstance(feature.get("properties"), dict) else {}
        meta = by_code.get(code_upper) or {}

        name = meta.get("name") or props.get("name") or code_upper
        lat = _safe_float(meta.get("lat")) if meta else None
        lng = _safe_float(meta.get("lng")) if meta else None
        if lat is None or lng is None:
            lat = _safe_float(props.get("lat"))
            lng = _safe_float(props.get("lng"))
        if lat is None or lng is None:
            center = _centroid_from_geometry(feature.get("geometry"))
            if center:
                lat = center.get("lat")
                lng = center.get("lng")

        if lat is None or lng is None:
            continue

        region = meta.get("region") or props.get("region") or "Unknown"
        code_alpha2 = meta.get("code_alpha2") or _alpha2_from_alpha3(code_upper)

        normalized.append(
            {
                **(meta if isinstance(meta, dict) else {}),
                "code": code_upper,
                "name": name,
                "lat": lat,
                "lng": lng,
                "region": region,
                "code_alpha2": code_alpha2,
            }
        )

    for code_upper, meta in by_code.items():
        if code_upper in existing_codes:
            continue
        lat = _safe_float(meta.get("lat"))
        lng = _safe_float(meta.get("lng"))
        if lat is None or lng is None:
            continue
        code_alpha2 = meta.get("code_alpha2") or _alpha2_from_alpha3(code_upper)
        normalized.append(
            {
                **meta,
                "code": code_upper,
                "name": meta.get("name") or code_upper,
                "lat": lat,
                "lng": lng,
                "region": meta.get("region") or "Unknown",
                "code_alpha2": code_alpha2,
            }
        )

    normalized.sort(key=lambda c: str(c.get("name") or c.get("code") or ""))
    return normalized

@router.get("/metadata/countries")
def get_countries() -> Dict[str, Any]:
    return {"COUNTRIES": _load_countries_data()}

@router.get("/metadata/geojson")
def get_geojson() -> Dict[str, Any]:
    geojson = _load_countries_geojson()
    if not isinstance(geojson, dict):
        return {"error": "GeoJSON not found"}

    features = geojson.get("features", [])
    if isinstance(features, list):
        for feature in features:
            if not isinstance(feature, dict):
                continue
            code = feature.get("id")
            if not code or str(code) == "-99":
                continue
            if code == "CS-KM":
                feature["id"] = "XKX"
            props = feature.get("properties")
            if not isinstance(props, dict):
                props = {}
                feature["properties"] = props
            lat = _safe_float(props.get("lat"))
            lng = _safe_float(props.get("lng"))
            if lat is None or lng is None:
                center = _centroid_from_geometry(feature.get("geometry"))
                if center:
                    if lat is None:
                        props["lat"] = center.get("lat")
                    if lng is None:
                        props["lng"] = center.get("lng")
            if "region" not in props or not props.get("region"):
                props["region"] = "Unknown"
            if "name" not in props or not props.get("name"):
                props["name"] = feature.get("id")

    data_path = os.path.join("data", "countries_data.json")
    alt_data_path = os.path.join("..", "data", "countries_data.json")
    resolved_data_path = data_path if os.path.exists(data_path) else (alt_data_path if os.path.exists(alt_data_path) else None)
    if resolved_data_path and isinstance(features, list):
        with open(resolved_data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        countries = data.get("COUNTRIES") if isinstance(data, dict) else data
        if isinstance(countries, list):
            by_code = {}
            for c in countries:
                if not isinstance(c, dict):
                    continue
                code = c.get("code")
                if code:
                    by_code[str(code).upper()] = c
            existing_codes = {str(feature.get("id")).upper() for feature in features if isinstance(feature, dict) and feature.get("id")}
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                code = feature.get("id")
                if not code:
                    continue
                code_upper = str(code).upper()
                c = by_code.get(code_upper)
                if not c:
                    continue
                props = feature.setdefault("properties", {})
                if isinstance(props, dict):
                    if c.get("name"):
                        props["name"] = c.get("name")
                    if c.get("lat") is not None:
                        props["lat"] = float(c.get("lat"))
                    if c.get("lng") is not None:
                        props["lng"] = float(c.get("lng"))
                    if c.get("region"):
                        props["region"] = c.get("region")
            for code_upper, c in by_code.items():
                if code_upper in existing_codes:
                    continue
                lat = _safe_float(c.get("lat"))
                lng = _safe_float(c.get("lng"))
                if lat is None or lng is None:
                    continue
                delta = 0.5
                features.append(
                    {
                        "type": "Feature",
                        "id": code_upper,
                        "properties": {
                            "name": c.get("name") or code_upper,
                            "lat": lat,
                            "lng": lng,
                            "region": c.get("region") or "Unknown",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [lng - delta, lat - delta],
                                    [lng + delta, lat - delta],
                                    [lng + delta, lat + delta],
                                    [lng - delta, lat + delta],
                                    [lng - delta, lat - delta],
                                ]
                            ],
                        },
                    }
                )
        geojson["features"] = features

    return geojson

@router.get("/map-data")
def get_map_data() -> Dict[str, Any]:
    r"""
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
    r"""
    Manually trigger the news fetching pipeline for debugging purposes.
    DEPRECATED: This endpoint is disabled as we move to Scrapy-based architecture.

    Research motivation: preserve reproducibility during controlled tests,
    while constraining compute to $R \leq 50$ records per call.
    """
    return {"status": "deprecated", "message": "GDELT fetching is disabled. Use Scrapy scheduler."}

@router.get("/media/sources")
def get_media_sources() -> List[Dict[str, Any]]:
    r"""
    Retrieve all media sources from the database.

    This endpoint exposes the canonical source set $S=\{s_i\}_{i=1}^N$
    for UI browsing and data audits.
    """
    return storage_operator.get_all_media_sources()

@router.get("/stats/brain")
def get_brain_stats() -> Dict[str, Any]:
    r"""
    Get aggregated intelligence stats (Entities, Narrative Divergence).

    The divergence metric follows $\Delta=\mu_{T0}-\mu_{T2}$ where
    $\mu_{Tk}$ denotes aggregated narrative signals for tier $k$ sources.
    """
    return storage_operator.get_brain_stats()

@router.get("/stats/heatmap", response_model=List[Dict[str, Any]])
def get_heatmap_data(db: Session = Depends(db_manager.get_db)) -> List[Dict[str, Any]]:
    r"""
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

@router.get("/stats/gde/current")
def get_gde_current(
    window_hours: int = Query(24, description="Analysis window in hours"),
    alpha: float = Query(0.6, description="Alpha parameter for entropy calculation")
) -> Dict[str, Any]:
    r"""
    Get current Geographic Diversity Entropy (GDE) metrics.
    
    This endpoint provides a snapshot of the system's geographic coverage
    diversity using Shannon Entropy and Gini Coefficient.
    """
    # Mock data for integration testing
    return {
        "gde": 0.75,
        "shannon_entropy": 3.5,
        "normalized_shannon": 0.65,
        "geographic_dispersion_km": 4500.0,
        "normalized_dispersion": 0.45,
        "country_count": 12,
        "total_visits": 150,
        "window_hours": window_hours,
        "gini_coefficient": 0.32,
        "alpha": alpha
    }

@router.get("/stats/growth/recent")
def get_growth_recent(days: int = Query(7, description="Number of days to analyze")) -> List[Dict[str, Any]]:
    r"""
    Get recent growth metrics for media sources and news articles.
    
    Returns a time series of growth data for the specified number of days.
    """
    # Mock data for integration testing
    import datetime
    today = datetime.date.today()
    data = []
    for i in range(days):
        day = today - datetime.timedelta(days=i)
        data.append({
            "day": day.isoformat(),
            "media_sources_net": 5 + i,
            "candidate_sources_growth_rate": 0.02 + (i * 0.001),
            "news_articles_net": 120 + (i * 10),
            "media_sources_count": 1000 + (i * 5),
            "candidate_sources_count": 200 + (i * 2),
            "news_articles_count": 50000 + (i * 120)
        })
    return data

@router.post("/system/crawler/start")
async def start_crawler() -> Dict[str, str]:
    r"""
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
    r"""
    Stop the crawler to prevent resource contention $C=\sum r_i$.
    """
    if not process_manager.is_crawler_running():
        return {"status": "not_running", "message": "Crawler is not running."}
    process_manager.stop_crawler()
    return {"status": "stopped", "message": "Crawler process terminated."}

@router.post("/system/crawler/restart")
async def restart_crawler() -> Dict[str, str]:
    r"""
    Restart the crawler to recover from transient failures $p_f(t)$.
    """
    process_manager.restart_crawler()
    return {"status": "restarted", "message": "Crawler process restarted."}

@router.get("/system/crawler/status")
def crawler_status() -> Dict[str, Any]:
    running = process_manager.is_crawler_running()
    pid = process_manager.crawler_process.pid if running and process_manager.crawler_process else None
    started_at = getattr(process_manager, "crawler_start_time", 0) or 0
    uptime_s = (time.time() - float(started_at)) if running and started_at else None
    return {"running": running, "pid": pid, "uptime_s": uptime_s}

@router.get("/system/sync/counts")
def sync_counts(x_sync_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_sync_token(x_sync_token)
    return {"counts": storage_operator.get_sync_counts()}

@router.post("/system/sync/media-sources")
def sync_media_sources(items: List[Dict[str, Any]], x_sync_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_sync_token(x_sync_token)
    result = storage_operator.bulk_upsert_media_sources(items)
    result["counts"] = storage_operator.get_sync_counts()
    return result

@router.post("/system/sync/candidate-sources")
def sync_candidate_sources(items: List[Dict[str, Any]], x_sync_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_sync_token(x_sync_token)
    result = storage_operator.bulk_upsert_candidate_sources(items)
    result["counts"] = storage_operator.get_sync_counts()
    return result

@router.get("/system/logs/recent")
async def get_recent_logs() -> List[Dict[str, Any]]:
    """
    Return buffered logs for UI inspection and human-in-the-loop diagnosis.
    """
    return list(ws_log_handler.log_buffer)

@router.get("/system/health/full")
async def health_full(autoheal: bool = False) -> Dict[str, Any]:
    r"""
    Full system health check with optional self-healing action $a\in\{0,1\}$.
    """
    return await system_guardian.check_health(autoheal=autoheal)

@router.post("/system/health/autoheal")
async def autoheal() -> Dict[str, Any]:
    r"""
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
