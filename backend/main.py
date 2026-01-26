import asyncio
import logging
import json
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import redis.asyncio as redis

from backend.core.database import db_manager
from backend.api.endpoints import router as api_router
from backend.core.shared_state import ws_manager
from backend.pipelines.init_pipeline import init_pipeline
from backend.scripts.cleanup_resources import cleanup_temp_resources
from backend.core.monitoring import thread_status
from backend.operators.system.guardian import system_guardian
from backend.operators.system.process_manager import process_manager
from backend.core.logging_handlers import ws_log_handler

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Add WebSocket Log Handler
logging.getLogger().addHandler(ws_log_handler)

# Global instances
# db_manager is already a singleton imported from core.database

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the FastAPI application.

    The lifecycle enforces global orchestration with explicit supervision
    $\mathcal{G}=\{\text{init},\text{monitor},\text{heal}\}$ to minimize
    cascading failures $P_f$ under concurrent workloads.
    """
    # Startup Phase
    logger.info("Starting Globe Media Pulse Backend System...")
    
    # Execute Initialization Pipeline
    init_pipeline.run()
    
    # Launch System Guardian (Background Daemon)
    asyncio.create_task(system_guardian.start_daemon())
    
    # Launch Periodic Cleanup Task (Background Daemon)
    asyncio.create_task(periodic_cleanup_task())

    # Launch Redis Event Listener (Data Flow Bridge)
    asyncio.create_task(redis_event_listener())
    
    # Start Crawler Process (Managed by ProcessManager)
    process_manager.start_crawler()

    # Audit Routes
    for route in app.routes:
        methods = getattr(route, "methods", None)
        logger.info(f"Registered Route: {route.path} {methods}")
    
    yield
    
    # Shutdown Phase
    logger.info("Shutting down Globe Media Pulse Backend System...")
    process_manager.stop_crawler()
    db_manager.close()

async def periodic_cleanup_task():
    """
    Background Daemon: Periodic Resource Cleanup.
    Runs every 2 hours (7200 seconds).

    Cleanup cadence follows $\Delta t=7200$ s to cap resource drift
    and keep disk usage under the threshold $\Omega$.
    """
    CLEANUP_INTERVAL = 7200 # 2 hours
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
    """
    Background Task: Listens to Redis 'news_pulse' channel and broadcasts to WebSockets.

    This task is the data-flow bridge $B:\text{Redis}\rightarrow\text{WebSocket}$
    that preserves event order to reduce temporal skew $\delta t$.
    """
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
                            # Smart Routing based on payload 'type'
                            if isinstance(payload, dict) and payload.get("type") == "log":
                                await ws_manager.broadcast({
                                    "type": "log_entry",
                                    "payload": payload
                                })
                            else:
                                # Default to news_event
                                await ws_manager.broadcast({
                                    "type": "news_event",
                                    "payload": payload
                                })
                        except json.JSONDecodeError:
                            # If not JSON, send as raw text payload
                            await ws_manager.broadcast({
                                "type": "news_event",
                                "payload": data_str
                            })
                    except Exception as e:
                        logger.error(f"Error broadcasting redis event: {e}")
                
                await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Redis Event Listener Failed: {e}")

app = FastAPI(title="Globe Media Pulse API", lifespan=lifespan)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket ingress for streaming updates with bounded reconnect delay
    $\Delta t=5\text{s}$ configured client-side.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        ws_manager.disconnect(websocket)

@app.get("/health/full")
async def health_full(autoheal: bool = False) -> Dict[str, Any]:
    """
    Global health endpoint with optional autoheal action $a\in\{0,1\}$.
    """
    return await system_guardian.check_health(autoheal=autoheal)

@app.post("/health/autoheal")
async def autoheal() -> Dict[str, Any]:
    """
    Trigger autohealing to restore system stability and reduce $P_f$.
    """
    report = await system_guardian.auto_heal()
    status = await system_guardian.check_health(autoheal=False)
    status["self_heal"] = report
    return status

@app.get("/")
def read_root() -> Dict[str, str]:
    """
    Root endpoint for fast liveness probes $t \rightarrow 0$.
    """
    return {
        "status": "online",
        "system": "Globe Media Pulse V1.0"
    }

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8002, reload=True)
