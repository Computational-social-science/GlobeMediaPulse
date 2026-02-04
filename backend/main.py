import asyncio
import logging
import json
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import redis.asyncio as redis
import os
import sentry_sdk

from backend.core.database import db_manager
from backend.api.endpoints import router as api_router
from backend.core.shared_state import ws_manager
from backend.pipelines.init_pipeline import init_pipeline
from backend.scripts.cleanup_resources import cleanup_temp_resources
from backend.core.monitoring import thread_status
from backend.operators.system.guardian import system_guardian
from backend.operators.system.process_manager import process_manager
from backend.core.logging_handlers import ws_log_handler

# Initialize Sentry for Backend Monitoring
# Research Motivation: Real-time error tracking and performance monitoring in production.
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=1.0, # Capture 100% of transactions for debugging
        profiles_sample_rate=1.0,
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger().addHandler(ws_log_handler)

def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None

def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    try:
        s = str(value).strip()
        return s if s else None
    except Exception:
        return None

def _normalize_ws_event(payload: Any) -> tuple[str, Dict[str, Any]] | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        title = _to_str(payload)
        if not title:
            return None
        return ("news", {"type": "news", "title": title, "country_code": "UNK", "source_domain": "unknown"})

    event_type = _to_str(payload.get("type")) or "news"
    if event_type not in ("news", "discovery", "log"):
        event_type = "news"

    if event_type == "log":
        normalized = {k: v for k, v in payload.items() if k != "type"}
        ts = _to_float(normalized.get("timestamp"))
        if ts is None:
            ts = _to_float(payload.get("timestamp"))
        if ts is not None:
            normalized["timestamp"] = ts
        return ("log", normalized)

    country_code = _to_str(payload.get("country_code")) or _to_str(payload.get("country")) or _to_str(payload.get("countryCode")) or "UNK"
    country_code = country_code.upper()
    tier = _to_str(payload.get("tier")) or ("Candidate" if event_type == "discovery" else "Tier-2")
    language = _to_str(payload.get("language")) or "en"
    source_domain = _to_str(payload.get("source_domain")) or _to_str(payload.get("domain"))
    if source_domain:
        source_domain = source_domain.lower()
    title = _to_str(payload.get("title")) or _to_str(payload.get("headline")) or "Untitled"
    url = _to_str(payload.get("url"))
    lat = _to_float(payload.get("lat"))
    lng = _to_float(payload.get("lng"))
    ts = _to_float(payload.get("timestamp"))

    normalized = {
        "type": event_type,
        "title": title,
        "url": url,
        "source_domain": source_domain or "unknown",
        "source_name": _to_str(payload.get("source_name")),
        "tier": tier,
        "language": language,
        "country_code": country_code,
        "confidence": _to_str(payload.get("confidence")),
        "lat": lat,
        "lng": lng,
        "timestamp": ts,
        "logo_url": _to_str(payload.get("logo_url")),
    }
    return (event_type, normalized)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Globe Media Pulse Backend System...")
    
    init_pipeline.run()
    
    asyncio.create_task(system_guardian.start_daemon())
    
    asyncio.create_task(periodic_cleanup_task())

    asyncio.create_task(redis_event_listener())
    
    auto_start_crawler = os.getenv("AUTO_START_CRAWLER", "1").strip().lower() not in ("0", "false", "no", "off")
    crawler_region = os.getenv("CRAWLER_REGION", "").strip().lower()
    fly_region = os.getenv("FLY_REGION", "").strip().lower()
    if crawler_region and fly_region and fly_region != crawler_region:
        auto_start_crawler = False
    if auto_start_crawler:
        process_manager.start_crawler()

    for route in app.routes:
        methods = getattr(route, "methods", None)
        logger.info(f"Registered Route: {route.path} {methods}")
    
    yield
    
    # Shutdown Phase
    logger.info("Shutting down Globe Media Pulse Backend System...")
    process_manager.stop_crawler()
    db_manager.close()

async def periodic_cleanup_task():
    CLEANUP_INTERVAL = 7200
    logger.info("Periodic Resource Cleanup Daemon Started.")
    thread_status.heartbeat('cleanup')
    
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL)
            logger.info("Executing scheduled resource cleanup...")
            await asyncio.to_thread(cleanup_temp_resources)
            thread_status.heartbeat('cleanup')
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            await asyncio.sleep(60)

async def redis_event_listener():
    from backend.core.config import settings
    redis_url = settings.REDIS_URL
    
    try:
        r = redis.from_url(redis_url)
            
        async with r.pubsub() as pubsub:
            await pubsub.subscribe("news_pulse")
            logger.info("Redis Event Listener Subscribed to 'news_pulse'")
            
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    try:
                        data_str = message["data"].decode("utf-8")
                        try:
                            payload = json.loads(data_str)
                            normalized = _normalize_ws_event(payload)
                            if normalized:
                                out_type, out_payload = normalized
                                await ws_manager.broadcast({"type": out_type, "payload": out_payload})
                        except json.JSONDecodeError:
                            normalized = _normalize_ws_event(data_str)
                            if normalized:
                                out_type, out_payload = normalized
                                await ws_manager.broadcast({"type": out_type, "payload": out_payload})
                    except Exception as e:
                        logger.error(f"Error broadcasting redis event: {e}")
                
                await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Redis Event Listener Failed: {e}")

app = FastAPI(title="Globe Media Pulse API", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "services": {
            "postgres": "unknown" if db_manager._pool is None else "connected",
            "redis": "connected"
        }
    }

# CORS Configuration
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()] or [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:4173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:4173",
]
allow_credentials = "*" not in allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        ws_manager.disconnect(websocket)

@app.get("/health/full")
async def health_full(autoheal: bool = False) -> Dict[str, Any]:
    return await system_guardian.check_health(autoheal=autoheal)

@app.post("/health/autoheal")
async def autoheal() -> Dict[str, Any]:
    report = await system_guardian.auto_heal()
    status = await system_guardian.check_health(autoheal=False)
    status["self_heal"] = report
    return status

@app.get("/")
def read_root() -> Dict[str, str]:
    return {
        "status": "online",
        "system": "Globe Media Pulse V1.0"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000") or "8000")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
