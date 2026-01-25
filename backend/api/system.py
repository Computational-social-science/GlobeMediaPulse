
from fastapi import APIRouter, HTTPException
from backend.operators.system.process_manager import process_manager
from backend.operators.system.guardian import system_guardian
from backend.core.logging_handlers import ws_log_handler

router = APIRouter()

@router.post("/crawler/start")
async def start_crawler():
    """Manually start the news crawler."""
    if process_manager.is_crawler_running():
        return {"status": "already_running", "message": "Crawler is already active."}
    
    process_manager.start_crawler()
    return {"status": "started", "message": "Crawler process initiated."}

@router.post("/crawler/stop")
async def stop_crawler():
    """Manually stop the news crawler."""
    if not process_manager.is_crawler_running():
        return {"status": "not_running", "message": "Crawler is not running."}
    
    process_manager.stop_crawler()
    return {"status": "stopped", "message": "Crawler process terminated."}

@router.post("/crawler/restart")
async def restart_crawler():
    """Manually restart the news crawler."""
    process_manager.restart_crawler()
    return {"status": "restarted", "message": "Crawler process restarted."}

@router.get("/logs/recent")
async def get_recent_logs():
    """Get the most recent buffered logs."""
    return list(ws_log_handler.log_buffer)

@router.get("/health/full")
async def health_full(autoheal: bool = False):
    """Full system health check."""
    return await system_guardian.check_health(autoheal=autoheal)

@router.post("/health/autoheal")
async def autoheal():
    """Trigger manual self-healing."""
    report = await system_guardian.auto_heal()
    status = await system_guardian.check_health(autoheal=False)
    status["self_heal"] = report
    return status
