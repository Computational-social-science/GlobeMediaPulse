import json
import asyncio
import os
import time
import importlib
import hmac
import hashlib
import random
from contextlib import nullcontext
from functools import lru_cache
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
import sentry_sdk

from backend.operators.storage import storage_operator
from backend.core.config import settings
from backend.core.database import db_manager
from backend.core.models import MediaSource, UiPreference
from backend.operators.system.process_manager import process_manager
from backend.operators.system.guardian import system_guardian
from backend.core.logging_handlers import ws_log_handler

router = APIRouter()

_webhook_lock = asyncio.Lock()
_last_webhook_action_at: float = 0.0
_last_webhook_state: Dict[str, Any] = {}
_otel_tracer = None
_otel_trace_mod = None
_otel_resource_cls = None
_otel_tracer_provider_cls = None
_otel_span_processor_cls = None
_otel_exporter_cls = None

def _require_sync_token(x_sync_token: Optional[str]) -> None:
    expected = os.getenv("SYNC_TOKEN", "").strip()
    if not expected or not x_sync_token or x_sync_token.strip() != expected:
        raise HTTPException(status_code=403, detail="forbidden")

def _require_optional_sync_token(x_sync_token: Optional[str]) -> None:
    expected = os.getenv("SYNC_TOKEN", "").strip()
    if expected and (not x_sync_token or x_sync_token.strip() != expected):
        raise HTTPException(status_code=403, detail="forbidden")

def _github_signature_ok(secret: str, body: bytes, sig256: Optional[str], sig1: Optional[str]) -> bool:
    secret_bytes = (secret or "").encode("utf-8")
    if not secret_bytes:
        return False
    if sig256:
        s = sig256.strip()
        if s.startswith("sha256="):
            s = s[len("sha256="):]
        expected = hmac.new(secret_bytes, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, s)
    if sig1:
        s = sig1.strip()
        if s.startswith("sha1="):
            s = s[len("sha1="):]
        expected = hmac.new(secret_bytes, body, hashlib.sha1).hexdigest()
        return hmac.compare_digest(expected, s)
    return False

def _webhook_gray_percent() -> float:
    raw = (os.getenv("GITHUB_WEBHOOK_GRAY_PERCENT", "100") or "100").strip()
    try:
        percent = float(raw)
    except Exception:
        percent = 100.0
    return max(0.0, min(100.0, percent))

def _webhook_gray_allowed() -> tuple[bool, float]:
    percent = _webhook_gray_percent()
    if percent >= 100.0:
        return True, percent
    if percent <= 0.0:
        return False, percent
    return (random.random() * 100.0) < percent, percent

def _webhook_throttle_bypass() -> bool:
    raw = (os.getenv("GITHUB_WEBHOOK_THROTTLE_BYPASS", "") or "").strip().lower()
    return raw in ("1", "true", "yes", "y")

def _record_webhook_state(state: Dict[str, Any]) -> None:
    global _last_webhook_state
    _last_webhook_state = state

def _otel_enabled() -> bool:
    return bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or os.getenv("OTEL_TRACES_EXPORTER"))

def _load_otel_modules():
    global _otel_trace_mod
    global _otel_resource_cls
    global _otel_tracer_provider_cls
    global _otel_span_processor_cls
    global _otel_exporter_cls
    if _otel_trace_mod is not None:
        return _otel_trace_mod, _otel_resource_cls, _otel_tracer_provider_cls, _otel_span_processor_cls, _otel_exporter_cls
    try:
        _otel_trace_mod = importlib.import_module("opentelemetry.trace")
        resources_mod = importlib.import_module("opentelemetry.sdk.resources")
        sdk_trace_mod = importlib.import_module("opentelemetry.sdk.trace")
        export_mod = importlib.import_module("opentelemetry.sdk.trace.export")
        otlp_mod = importlib.import_module("opentelemetry.exporter.otlp.proto.http.trace_exporter")
        _otel_resource_cls = getattr(resources_mod, "Resource", None)
        _otel_tracer_provider_cls = getattr(sdk_trace_mod, "TracerProvider", None)
        _otel_span_processor_cls = getattr(export_mod, "BatchSpanProcessor", None)
        _otel_exporter_cls = getattr(otlp_mod, "OTLPSpanExporter", None)
    except Exception:
        _otel_trace_mod = None
        _otel_resource_cls = None
        _otel_tracer_provider_cls = None
        _otel_span_processor_cls = None
        _otel_exporter_cls = None
    return _otel_trace_mod, _otel_resource_cls, _otel_tracer_provider_cls, _otel_span_processor_cls, _otel_exporter_cls

def _get_tracer():
    global _otel_tracer
    if _otel_tracer is not None:
        return _otel_tracer
    trace_mod, Resource, TracerProvider, BatchSpanProcessor, OTLPSpanExporter = _load_otel_modules()
    if trace_mod is None or not _otel_enabled():
        return None
    provider = trace_mod.get_tracer_provider()
    if TracerProvider and isinstance(provider, TracerProvider):
        _otel_tracer = trace_mod.get_tracer("gmp.webhook")
        return _otel_tracer
    if TracerProvider and Resource and BatchSpanProcessor and OTLPSpanExporter:
        service_name = (os.getenv("OTEL_SERVICE_NAME") or "globemediapulse-backend").strip()
        resource = Resource.create({"service.name": service_name})
        tracer_provider = TracerProvider(resource=resource)
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        exporter = OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()
        tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        trace_mod.set_tracer_provider(tracer_provider)
        _otel_tracer = trace_mod.get_tracer("gmp.webhook")
        return _otel_tracer
    return None

def _span_context(tracer, name: str, attrs: Optional[Dict[str, Any]] = None):
    if not tracer:
        return nullcontext()
    trace_mod, _, _, _, _ = _load_otel_modules()
    if trace_mod is None:
        return nullcontext()
    span = tracer.start_span(name)
    if attrs:
        for key, value in attrs.items():
            if value is None:
                continue
            try:
                span.set_attribute(key, value)
            except Exception:
                continue
    return trace_mod.use_span(span, end_on_exit=True)

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

@router.get("/stats/seeds")
def get_seed_stats() -> Dict[str, Any]:
    from backend.scripts.expand_global_south_seeds import get_seed_metrics

    return get_seed_metrics()

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
    del query, max_records, start_date, end_date
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
    return storage_operator.get_growth_recent(days=days)

@router.get("/stats/src/series")
def get_src_series(
    days: int = Query(7, description="Number of days to analyze"),
    bucket: str = Query("hour", description="Bucket size: hour or day"),
) -> List[Dict[str, Any]]:
    return storage_operator.get_src_metrics_recent(days=days, bucket=bucket)

@router.get("/stats/src/alert")
def get_src_alert(window_minutes: int = Query(30, description="Alert window in minutes")) -> Dict[str, Any]:
    return storage_operator.get_src_alert(window_minutes=window_minutes)

@router.post("/system/seeds/expand")
def expand_seed_pool() -> Dict[str, Any]:
    from backend.scripts.expand_global_south_seeds import expand_global_south

    result = expand_global_south()
    return result if isinstance(result, dict) else {"status": "unknown"}

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
    mode = (os.getenv("CRAWLER_MODE") or "").strip().lower()
    if mode in ("external", "docker", "compose"):
        key = (os.getenv("CRAWLER_HEARTBEAT_KEY") or "gmp:crawler:heartbeat").strip()
        stale_s = float(os.getenv("CRAWLER_HEARTBEAT_STALE_S") or "45")
        try:
            import redis

            client = redis.from_url(settings.REDIS_URL)
            raw = client.get(key)
            if raw is None:
                return {"running": False, "pid": None, "uptime_s": None, "external": True, "heartbeat": None}
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="replace")
            ts = float(str(raw).strip() or "0")
            age_s = max(0.0, time.time() - ts) if ts else None
            alive = (age_s is not None) and (age_s <= stale_s)
            return {"running": bool(alive), "pid": None, "uptime_s": None, "external": True, "heartbeat": {"key": key, "age_s": age_s, "stale_s": stale_s}}
        except Exception as e:
            return {"running": False, "pid": None, "uptime_s": None, "external": True, "error": f"{type(e).__name__}: {e}"}
    running = process_manager.is_crawler_running()
    pid = process_manager.crawler_process.pid if running and process_manager.crawler_process else None
    started_at = getattr(process_manager, "crawler_start_time", 0) or 0
    uptime_s = (time.time() - float(started_at)) if running and started_at else None
    return {"running": running, "pid": pid, "uptime_s": uptime_s}

@router.get("/system/crawler/diagnostics")
def crawler_diagnostics() -> Dict[str, Any]:
    mode = (os.getenv("CRAWLER_MODE") or "").strip().lower()
    if mode in ("external", "docker", "compose"):
        status = crawler_status()
        return {"external": True, "status": status}
    return process_manager.get_crawler_diagnostics()

@router.get("/system/ui/sidebar-config")
def get_sidebar_config(db: Session = Depends(db_manager.get_db)) -> Dict[str, Any]:
    try:
        pref = db.query(UiPreference).filter(UiPreference.key == "sidebarConfig").first()
    except SQLAlchemyError:
        return {"config": None, "updatedAtMs": None}
    if not pref:
        return {"config": None, "updatedAtMs": None}
    updated = pref.updated_at.timestamp() * 1000 if getattr(pref, "updated_at", None) is not None else None
    return {"config": pref.value, "updatedAtMs": int(updated) if updated is not None else None}

@router.put("/system/ui/sidebar-config")
def put_sidebar_config(
    payload: Dict[str, Any],
    x_sync_token: Optional[str] = Header(default=None),
    db: Session = Depends(db_manager.get_db),
) -> Dict[str, Any]:
    _require_optional_sync_token(x_sync_token)
    config = payload.get("config")
    try:
        encoded = json.dumps(config)
    except Exception:
        raise HTTPException(status_code=400, detail="config must be JSON-serializable")
    if len(encoded.encode("utf-8")) > 200_000:
        raise HTTPException(status_code=413, detail="config too large")

    try:
        pref = db.query(UiPreference).filter(UiPreference.key == "sidebarConfig").first()
        if pref:
            pref.value = config
        else:
            pref = UiPreference(key="sidebarConfig", value=config)
            db.add(pref)
        db.commit()
        db.refresh(pref)
    except SQLAlchemyError:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=503, detail="db_unavailable")
    updated = pref.updated_at.timestamp() * 1000 if getattr(pref, "updated_at", None) is not None else None
    return {"ok": True, "updatedAtMs": int(updated) if updated is not None else None}

@router.post("/github/webhook")
async def github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(default=None, alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(default=None, alias="X-Hub-Signature-256"),
    x_hub_signature: Optional[str] = Header(default=None, alias="X-Hub-Signature"),
    x_github_delivery: Optional[str] = Header(default=None, alias="X-GitHub-Delivery"),
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    received_at = time.time()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="webhook_secret_missing")

    body = await request.body()
    if not _github_signature_ok(secret=secret, body=body, sig256=x_hub_signature_256, sig1=x_hub_signature):
        raise HTTPException(status_code=401, detail="invalid_signature")

    payload: Dict[str, Any] = {}
    if body:
        try:
            parsed = json.loads(body.decode("utf-8"))
            if isinstance(parsed, dict):
                payload = parsed
        except Exception:
            payload = {}

    event = (x_github_event or "").strip().lower() or "unknown"
    trace_id = x_github_delivery or f"local-{int(received_at * 1000)}-{random.randint(1000, 9999)}"
    tracer = _get_tracer()
    span_durations: Dict[str, float] = {}
    span_starts: Dict[str, float] = {}

    def _span_start(name: str) -> None:
        span_starts[name] = time.perf_counter()

    def _span_finish(name: str) -> None:
        started = span_starts.get(name)
        if started is None:
            return
        span_durations[name] = (time.perf_counter() - started) * 1000

    def finalize(status: str, **extra: Any) -> Dict[str, Any]:
        span_ranking = sorted(
            [{"span": k, "duration_ms": int(v)} for k, v in span_durations.items()],
            key=lambda item: item["duration_ms"],
            reverse=True,
        )
        payload = {
            "status": status,
            "event": event,
            "trace_id": trace_id,
            "span_ranking": span_ranking,
            **extra,
        }
        state = {
            "received_at": received_at,
            "event": event,
            "trace_id": trace_id,
            "delivery": x_github_delivery,
            "span_ranking": span_ranking,
            **extra,
        }
        _record_webhook_state(state)
        return payload

    with _span_context(
        tracer,
        "github_webhook",
        {"github.event": event, "github.delivery": x_github_delivery, "github.trace_id": trace_id},
    ):
        with sentry_sdk.start_transaction(op="webhook", name="github_webhook") as txn:
            txn.set_tag("github.event", event)
            if x_github_delivery:
                txn.set_tag("github.delivery", x_github_delivery)
            txn.set_tag("github.trace_id", trace_id)
            _span_start("event_check")
            with _span_context(tracer, "webhook.event_check", {"github.event": event}):
                if event == "ping":
                    _span_finish("event_check")
                    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                    return finalize("ok", decision="ping", elapsed_ms=elapsed_ms)

                if event != "push":
                    _span_finish("event_check")
                    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                    return finalize("ignored", decision="ignored", reason="event_not_push", elapsed_ms=elapsed_ms)
            _span_finish("event_check")

            _span_start("branch_check")
            ref = payload.get("ref")
            branch = str(ref).split("/")[-1] if ref else ""
            allowed_branches = [b.strip() for b in (os.getenv("GITHUB_WEBHOOK_BRANCHES", "main,master") or "").split(",") if b.strip()]
            with _span_context(tracer, "webhook.branch_check", {"github.branch": branch}):
                if allowed_branches and branch and branch not in allowed_branches:
                    _span_finish("branch_check")
                    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                    return finalize(
                        "ignored",
                        decision="ignored",
                        reason="branch_not_allowed",
                        branch=branch,
                        allowed_branches=allowed_branches,
                        elapsed_ms=elapsed_ms,
                    )
            _span_finish("branch_check")

            _span_start("gray_check")
            gray_allowed, gray_percent = _webhook_gray_allowed()
            with _span_context(tracer, "webhook.gray_check", {"github.gray_percent": gray_percent}):
                if not gray_allowed:
                    txn.set_tag("github.gray", "skip")
                    _span_finish("gray_check")
                    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                    return finalize(
                        "ignored",
                        decision="ignored",
                        reason="gray_skip",
                        branch=branch,
                        gray_percent=gray_percent,
                        elapsed_ms=elapsed_ms,
                    )
            _span_finish("gray_check")

            _span_start("throttle_check")
            action = (os.getenv("GITHUB_WEBHOOK_ACTION", "restart_crawler") or "restart_crawler").strip().lower()
            min_interval_s = float(os.getenv("GITHUB_WEBHOOK_MIN_INTERVAL_S", "30") or "30")
            throttle_bypass = _webhook_throttle_bypass()
            now = time.time()
            with _span_context(
                tracer,
                "webhook.throttle_check",
                {"github.throttle_bypass": throttle_bypass, "github.min_interval_s": min_interval_s},
            ):
                async with _webhook_lock:
                    global _last_webhook_action_at
                    since_last_s = now - _last_webhook_action_at if _last_webhook_action_at else None
                    if not throttle_bypass and _last_webhook_action_at and (now - _last_webhook_action_at) < min_interval_s:
                        txn.set_tag("github.throttle", "hit")
                        _span_finish("throttle_check")
                        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                        return finalize(
                            "ignored",
                            decision="ignored",
                            reason="throttled",
                            branch=branch,
                            min_interval_s=min_interval_s,
                            since_last_s=since_last_s,
                            elapsed_ms=elapsed_ms,
                        )
                    _last_webhook_action_at = now
            _span_finish("throttle_check")

            txn.set_tag("github.branch", branch)
            txn.set_tag("github.action", action)
            txn.set_tag("github.gray_percent", gray_percent)
            if throttle_bypass:
                txn.set_tag("github.throttle", "bypass")

            _span_start("action")
            with _span_context(tracer, f"webhook.action.{action}", {"github.action": action}):
                if action == "none":
                    _span_finish("action")
                    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                    return finalize(
                        "accepted",
                        decision="accepted",
                        branch=branch,
                        action="none",
                        gray_percent=gray_percent,
                        throttle_bypass=throttle_bypass,
                        elapsed_ms=elapsed_ms,
                    )
                if action == "autoheal":
                    asyncio.create_task(system_guardian.auto_heal())
                    _span_finish("action")
                    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                    return finalize(
                        "accepted",
                        decision="accepted",
                        branch=branch,
                        action="autoheal",
                        gray_percent=gray_percent,
                        throttle_bypass=throttle_bypass,
                        elapsed_ms=elapsed_ms,
                    )

                asyncio.create_task(asyncio.to_thread(process_manager.restart_crawler))
                _span_finish("action")
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                return finalize(
                    "accepted",
                    decision="accepted",
                    branch=branch,
                    action="restart_crawler",
                    gray_percent=gray_percent,
                    throttle_bypass=throttle_bypass,
                    elapsed_ms=elapsed_ms,
                )

@router.get("/system/webhook/status")
def webhook_status() -> Dict[str, Any]:
    allowed_branches = [b.strip() for b in (os.getenv("GITHUB_WEBHOOK_BRANCHES", "main,master") or "").split(",") if b.strip()]
    return {
        "config": {
            "action": (os.getenv("GITHUB_WEBHOOK_ACTION", "restart_crawler") or "restart_crawler").strip().lower(),
            "min_interval_s": float(os.getenv("GITHUB_WEBHOOK_MIN_INTERVAL_S", "30") or "30"),
            "gray_percent": _webhook_gray_percent(),
            "throttle_bypass": _webhook_throttle_bypass(),
            "allowed_branches": allowed_branches,
        },
        "last": _last_webhook_state,
        "last_action_at": _last_webhook_action_at,
    }

@router.get("/system/sync/counts")
def sync_counts(x_sync_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_sync_token(x_sync_token)
    return {"counts": storage_operator.get_sync_counts()}

@router.get("/system/export/media-sources")
def export_media_sources(
    tiers: str = Query(default=""),
    limit: int = Query(default=0, ge=0),
    x_sync_token: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    _require_sync_token(x_sync_token)
    sources = storage_operator.get_all_media_sources()
    tier_set = {t.strip() for t in (tiers or "").split(",") if t.strip()}
    if tier_set:
        sources = [s for s in sources if isinstance(s, dict) and (s.get("tier") in tier_set)]
    if limit:
        sources = sources[: int(limit)]
    return sources

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

@router.get("/system/export/candidate-sources")
def export_candidate_sources(
    limit: int = Query(default=0, ge=0),
    x_sync_token: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    _require_sync_token(x_sync_token)
    out = storage_operator.get_all_candidate_sources(limit=int(limit) if limit else None)
    return out

@router.get("/system/logs/recent")
async def get_recent_logs() -> List[Dict[str, Any]]:
    """
    Return buffered logs for UI inspection and human-in-the-loop diagnosis.
    """
    return list(ws_log_handler.log_buffer)

@router.get("/system/workflows/list")
def workflows_list() -> Dict[str, Any]:
    from backend.workflows.flows import list_workflows

    return {"workflows": list_workflows()}

@router.get("/system/workflows/snapshot")
def workflows_snapshot(
    from_iso: Optional[str] = Query(default=None),
    to_iso: Optional[str] = Query(default=None),
    statuses: str = Query(default=""),
    search: str = Query(default=""),
) -> Dict[str, Any]:
    from backend.workflows.flows import get_workflow_snapshot

    status_list = [s.strip() for s in (statuses or "").split(",") if s.strip()]
    return get_workflow_snapshot(from_iso=from_iso, to_iso=to_iso, statuses=status_list or None, search=search or None)

@router.post("/system/workflows/run")
def workflows_run(payload: Dict[str, Any], x_sync_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_sync_token(x_sync_token)
    from backend.workflows.flows import run_workflow

    name = str(payload.get("name") or "").strip()
    params = payload.get("params")
    if params is not None and not isinstance(params, dict):
        raise HTTPException(status_code=400, detail="params must be an object")
    result = run_workflow(name, params=params if isinstance(params, dict) else None)
    return {"ok": True, "result": result}

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
