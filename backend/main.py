import asyncio
import logging
import sys
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import time
from typing import Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import redis

# Add project root to path to allow absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import db_manager
from backend.api.endpoints import router as api_router
from backend.core.shared_state import ws_manager
from backend.pipelines.init_pipeline import init_pipeline

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
# db_manager is already a singleton imported from core.database

# Initialize Redis Client (Global)
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    redis_client = redis.from_url(REDIS_URL)
else:
    redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", 6379)))

SELF_HEAL_COOLDOWN_SECONDS = float(os.getenv("SELF_HEAL_COOLDOWN_SECONDS", "30"))
self_heal_lock = asyncio.Lock()
self_heal_last_run = 0.0

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Globe Media Pulse Backend...")
    
    # Run Initialization Pipeline
    init_pipeline.run()
    
    # Start Health Monitor
    asyncio.create_task(monitor_system_health())

    # Log all routes
    for route in app.routes:
        methods = getattr(route, "methods", None)
        logger.info(f"Route: {route.path} {methods}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Globe Media Pulse Backend...")
    db_manager.close()

async def monitor_system_health():
    """
    Background task: Periodically checks system health and triggers auto-heal if needed.
    """
    consecutive_failures = 0
    MAX_FAILURES = 3
    CHECK_INTERVAL = 30  # seconds

    logger.info("Starting System Health Monitor...")
    
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL)
            
            # Run health checks
            services = await _run_health_checks()
            is_healthy = services["postgres"] == "ok" and services["redis"] == "ok"
            
            if is_healthy:
                if consecutive_failures > 0:
                    logger.info(f"System recovered after {consecutive_failures} failures.")
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(f"Health check failed ({consecutive_failures}/{MAX_FAILURES}). Services: {services}")
                
                if consecutive_failures >= MAX_FAILURES:
                    logger.warning("Max failures reached. Triggering Auto-Heal...")
                    result = await _autoheal_internal()
                    logger.info(f"Auto-Heal Result: {result}")
                    
                    # Reset counter after auto-heal attempt
                    consecutive_failures = 0
                    
        except Exception as e:
            logger.error(f"Error in Health Monitor: {e}")
            await asyncio.sleep(5)  # Short sleep on error to avoid tight loops

app = FastAPI(lifespan=lifespan)

# CORS
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "https://computational-social-science.github.io"
]
if allowed_origins_env:
    origins.extend([origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"Including API Router with {len(api_router.routes)} routes")
app.include_router(api_router, prefix="/api")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    Connects clients to the shared WebSocket manager.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, maybe handle client messages
            # For now, just wait for disconnect
            data = await websocket.receive_text()
            # Optional: handle ping/pong or control messages
    except Exception:
        ws_manager.disconnect(websocket)

# Helper functions for health checks (Sync wrappers)
def _check_postgres_sync():
    """Perform a real connectivity check on Postgres."""
    try:
        # get_connection is a context manager that handles pool.getconn/putconn
        with db_manager.get_connection() as conn:
            if conn is None:
                return False
            # Lightweight query to ensure connection is valid
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
    except Exception as e:
        logger.error(f"Health Check Postgres Error: {e}")
        return False

def _check_redis_sync():
    """Perform a real connectivity check on Redis."""
    try:
        return redis_client.ping()
    except Exception as e:
        logger.error(f"Health Check Redis Error: {e}")
        return False

@app.get("/health/full")
async def health_full(autoheal: bool = False) -> Dict[str, Any]:
    """
    Detailed health check for internal services (Async + Parallel).
    """
    status = {"status": "ok", "services": {}, "self_heal": None}
    services = await _run_health_checks()
    status["services"] = services

    if services["postgres"] != "ok" or services["redis"] != "ok":
        status["status"] = "degraded"
        logger.warning(f"Health check degraded: {status}")

    if autoheal and status["status"] != "ok":
        status["self_heal"] = await _autoheal_internal()
        services = await _run_health_checks()
        status["services"] = services
        status["status"] = "ok" if services["postgres"] == "ok" and services["redis"] == "ok" else "degraded"

    return status

@app.post("/health/autoheal")
async def autoheal() -> Dict[str, Any]:
    result = await _autoheal_internal()
    services = await _run_health_checks()
    status = "ok" if services["postgres"] == "ok" and services["redis"] == "ok" else "degraded"
    return {"status": status, "services": services, "self_heal": result}

async def _run_health_checks() -> Dict[str, str]:
    TIMEOUT = 2.0

    async def safe_check(check_func, name):
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(check_func),
                timeout=TIMEOUT
            )
            return "ok" if result else "error"
        except asyncio.TimeoutError:
            logger.warning(f"Health check timed out for {name}")
            return "timeout"
        except Exception as e:
            logger.error(f"Health check failed for {name}: {e}")
            return "error"

    pg_task = safe_check(_check_postgres_sync, "postgres")
    redis_task = safe_check(_check_redis_sync, "redis")
    pg_status, redis_status = await asyncio.gather(pg_task, redis_task)
    return {"postgres": pg_status, "redis": redis_status}

async def _autoheal_internal() -> Dict[str, Any]:
    global redis_client, self_heal_last_run
    if self_heal_lock.locked():
        return {"state": "busy"}

    async with self_heal_lock:
        now = time.monotonic()
        cooldown_remaining = max(0.0, SELF_HEAL_COOLDOWN_SECONDS - (now - self_heal_last_run))
        if cooldown_remaining > 0:
            return {"state": "cooldown", "cooldown_seconds": round(cooldown_remaining, 2)}

        self_heal_last_run = now
        actions = {"postgres": "skipped", "redis": "skipped"}

        try:
            services = await _run_health_checks()

            if services["postgres"] != "ok":
                try:
                    db_manager.close()
                    db_manager.initialize()
                    actions["postgres"] = "reinitialized"
                except Exception as e:
                    actions["postgres"] = f"failed:{e}"

            if services["redis"] != "ok":
                try:
                    # Re-init redis client
                    global redis_client
                    REDIS_URL = os.getenv("REDIS_URL")
                    if REDIS_URL:
                        redis_client = redis.from_url(REDIS_URL)
                    else:
                        redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", 6379)))
                    
                    if redis_client.ping():
                        actions["redis"] = "reconnected"
                except Exception as e:
                    actions["redis"] = f"failed:{e}"

        finally:
            pass

        return {"state": "completed", "actions": actions}

@app.get("/")
def read_root() -> Dict[str, str]:
    """
    Root endpoint.
    
    Returns:
        dict: Basic system status.
    """
    return {
        "status": "online",
        "system": "Globe Media Pulse V1.0"
    }

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8002, reload=True)
