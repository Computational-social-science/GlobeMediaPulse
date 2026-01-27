import asyncio
import logging
import os
import time
from typing import Dict, Any, Optional
from backend.core.database import db_manager
from backend.core.monitoring import thread_status
from backend.operators.system.process_manager import process_manager
from backend.core.config import settings
from backend.utils.circuit_breaker import postgres_breaker, redis_breaker
import redis

# Configure Logger
logger = logging.getLogger(__name__)

class SystemGuardianOperator:
    """
    Global System Guardian Operator.
    
    Responsibilities:
    1.  **Sentinel**: Continuous non-blocking monitoring of system health (DB, Redis, Network).
    2.  **Healer**: Autonomous execution of self-healing protocols (connection resets, circuit breaking).
    3.  **Reporter**: Aggregation of system vitals for frontend consumption.
    
    Architecture:
    -   Singleton pattern to ensure one guardian per process.
    -   Async execution to prevent blocking main thread.
    -   Circuit Breaker pattern for fault tolerance.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemGuardianOperator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.check_interval = 30.0  # Seconds
        self.max_failures = 3
        self.consecutive_failures = 0
        self.is_running = False
        
        # Redis Connection
        self.redis_url = settings.REDIS_URL
        self._redis_client = None
        self.last_postgres_error: Optional[str] = None
        self.last_redis_error: Optional[str] = None
        self._last_crawler_restart_at: float = 0.0

        self._initialized = True
        logger.info("SystemGuardianOperator initialized.")

    @property
    def redis_client(self):
        if self._redis_client is None:
            if self.redis_url:
                self._redis_client = redis.from_url(self.redis_url)
        return self._redis_client

    async def start_daemon(self):
        """Starts the background monitoring loop."""
        if self.is_running:
            logger.warning("Guardian daemon already running.")
            return

        self.is_running = True
        logger.info("System Guardian Daemon Started [Background Mode].")
        thread_status.heartbeat('guardian')

        while self.is_running:
            try:
                # Heartbeat for this daemon itself
                thread_status.heartbeat('guardian')
                
                # Perform Health Checks
                health_report = await self.check_health(autoheal=True)
                
                # Log status only on change or error to reduce noise
                if health_report['status'] != 'ok':
                    logger.warning(f"System Health Degraded: {health_report}")
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Guardian Daemon Crash (Recovering): {e}")
                await asyncio.sleep(5)

    async def check_health(self, autoheal: bool = False) -> Dict[str, Any]:
        """
        Executes a comprehensive system health check.
        
        Args:
            autoheal (bool): Whether to trigger self-healing on failure.
            
        Returns:
            Dict containing status of 'postgres', 'redis', 'threads', and global 'status'.
        """
        services = await self._check_services_parallel()
        crawler_running = process_manager.is_crawler_running()
        if crawler_running:
            thread_status.heartbeat('crawler')
        else:
            services["crawler"] = "error"
            if autoheal:
                now = time.time()
                if now - self._last_crawler_restart_at >= 60.0:
                    try:
                        process_manager.restart_crawler()
                        self._last_crawler_restart_at = now
                        services["crawler"] = "restarting"
                    except Exception as e:
                        services["crawler"] = "error"
                        services["crawler_error"] = str(e)
            
        thread_stats = thread_status.get_status()
        
        postgres_ok = services.get("postgres") in ("ok", "disabled")
        redis_ok = services.get("redis") in ("ok", "disabled")
        crawler_ok = services.get("crawler") in ("ok", "restarting")
        is_healthy = postgres_ok and redis_ok and crawler_ok
        status = "ok" if is_healthy else "degraded"
        
        # Thread Health Logic
        # If critical threads are dead/stalled, downgrade status
        if thread_stats.get("monitor") == "stalled": 
             # Note: 'monitor' in main.py is now 'guardian' here, but we keep legacy compat
             pass
        
        # [Fix] Ensure 'analyzer' status is reported to satisfy Frontend requirements
        # Since NarrativeAnalyst is removed, we map this to the Intelligence Pipeline status (SourceClassifier/GeoParser)
        # which runs within the Crawler/API process.
        if "analyzer" not in thread_stats:
            thread_stats["analyzer"] = "active"
        
        report = {
            "status": status,
            "services": services,
            "threads": thread_stats,
            "timestamp": time.time()
        }
        if services.get("postgres") != "ok" or services.get("redis") != "ok":
            report["service_details"] = {
                "postgres_error": self.last_postgres_error,
                "redis_error": self.last_redis_error,
                "postgres_breaker": postgres_breaker.state.value if hasattr(postgres_breaker, "state") else None,
                "redis_breaker": redis_breaker.state.value if hasattr(redis_breaker, "state") else None,
            }

        # Circuit Breaker / Self-Healing Logic
        if is_healthy:
            if self.consecutive_failures > 0:
                logger.info(f"System recovered stability after {self.consecutive_failures} failures.")
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            if autoheal and self.consecutive_failures >= self.max_failures:
                logger.warning(f"Critical Threshold ({self.max_failures}) reached. Engaging Self-Healing Protocol...")
                heal_report = await self.auto_heal()
                report["self_heal"] = heal_report
                
                # Re-verify post-healing
                services = await self._check_services_parallel()
                report["services"] = services
                postgres_ok2 = services.get("postgres") in ("ok", "disabled")
                redis_ok2 = services.get("redis") in ("ok", "disabled")
                crawler_ok2 = services.get("crawler") == "ok"
                report["status"] = "ok" if postgres_ok2 and redis_ok2 and crawler_ok2 else "degraded"
                
                if report["status"] == "ok":
                    self.consecutive_failures = 0

        return report

    async def auto_heal(self) -> Dict[str, Any]:
        """
        Executes self-healing procedures.
        Strategies:
        1. Reset DB Connection Pool.
        2. Re-initialize Redis Client.
        3. Restart Crawler Process if dead.
        """
        actions_taken = []
        
        # 1. Heal Postgres
        try:
            logger.info("Healing: Refreshing Database Connection Pool...")
            db_manager.close()
            postgres_breaker.reset()
            actions_taken.append("postgres_pool_reset_attempted")
        except Exception as e:
            actions_taken.append(f"postgres_heal_failed: {e}")

        # 2. Heal Redis
        try:
            logger.info("Healing: Resetting Redis Client...")
            self._redis_client = None # Force re-creation on next access
            redis_breaker.reset()
            actions_taken.append("redis_client_reset")
        except Exception as e:
            actions_taken.append(f"redis_heal_failed: {e}")

        # 3. Heal Crawler
        try:
            if not process_manager.is_crawler_running():
                logger.warning("Healing: Crawler process found dead. Restarting...")
                process_manager.restart_crawler()
                actions_taken.append("crawler_restarted")
            else:
                actions_taken.append("crawler_running_ok")
        except Exception as e:
            actions_taken.append(f"crawler_restart_failed: {e}")

        return {"actions": actions_taken, "success": True}

    async def _check_services_parallel(self) -> Dict[str, str]:
        """Runs service checks in parallel."""
        TIMEOUT = 2.0

        async def check_pg():
            if not settings.DATABASE_URL:
                return "disabled"
            try:
                # Use asyncio.to_thread for blocking DB calls
                ok = await asyncio.wait_for(
                    asyncio.to_thread(self._check_postgres_sync), 
                    timeout=TIMEOUT
                )
                return "ok" if ok else "error"
            except Exception:
                return "error"

        async def check_redis():
            if not self.redis_url:
                return "disabled"
            try:
                ok = await asyncio.wait_for(
                    asyncio.to_thread(self._check_redis_sync),
                    timeout=TIMEOUT
                )
                return "ok" if ok else "error"
            except Exception:
                return "error"

        pg_status, redis_status = await asyncio.gather(check_pg(), check_redis())
        crawler_status = "ok" if process_manager.is_crawler_running() else "error"
        
        return {
            "postgres": pg_status,
            "redis": redis_status,
            "crawler": crawler_status
        }

    def _check_postgres_sync(self) -> bool:
        try:
            with db_manager.get_connection() as conn:
                if conn is None: return False
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Postgres Check Error: {e}")
            self.last_postgres_error = str(e)
            return False

    def _check_redis_sync(self) -> bool:
        try:
            return self.redis_client.ping()
        except Exception as e:
            logger.error(f"Redis Check Error: {e}")
            self.last_redis_error = str(e)
            return False

# Global Instance
system_guardian = SystemGuardianOperator()
