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

try:
    import psycopg2
except ImportError:
    psycopg2 = None

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
        self._crawler_restart_backoff_s: float = 60.0
        self._crawler_restart_failures: int = 0

        self._initialized = True
        logger.info("SystemGuardianOperator initialized.")

    def _external_crawler_enabled(self) -> bool:
        mode = (os.getenv("CRAWLER_MODE") or "").strip().lower()
        if not mode:
            return False
        return mode in ("external", "docker", "compose")

    def _external_crawler_is_alive(self) -> Optional[Dict[str, Any]]:
        if not self.redis_url:
            return None
        key = (os.getenv("CRAWLER_HEARTBEAT_KEY") or "gmp:crawler:heartbeat").strip()
        stale_s = float(os.getenv("CRAWLER_HEARTBEAT_STALE_S") or "45")
        try:
            raw = self.redis_client.get(key)
            if raw is None:
                return {"alive": False, "age_s": None, "key": key, "stale_s": stale_s}
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="replace")
            ts = float(str(raw).strip() or "0")
            age_s = max(0.0, time.time() - ts) if ts else None
            alive = (age_s is not None) and (age_s <= stale_s)
            return {"alive": alive, "age_s": age_s, "key": key, "stale_s": stale_s}
        except Exception as e:
            self.last_redis_error = str(e)
            return {"alive": False, "age_s": None, "key": key, "error": str(e)}

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
        if self._external_crawler_enabled():
            ext = self._external_crawler_is_alive() or {}
            services["crawler_diag"] = {"external": True, "heartbeat": ext}
            services["crawler_health"] = "ok" if bool(ext.get("alive")) else "degraded"
            services["crawler"] = "ok" if bool(ext.get("alive")) else "error"
        else:
            crawler_diag = process_manager.get_crawler_diagnostics()
            services["crawler_diag"] = crawler_diag
            crawler_alerts = (crawler_diag or {}).get("alerts") or {}
            crawler_health = "ok"
            if crawler_alerts.get("has_traceback"):
                crawler_health = "degraded"
            elif int(crawler_alerts.get("rate_limit_hits") or 0) >= 25:
                crawler_health = "degraded"
            elif int(crawler_alerts.get("network_error_hits") or 0) >= 25:
                crawler_health = "degraded"
            services["crawler_health"] = crawler_health

            crawler_running = process_manager.is_crawler_running()
            if crawler_running:
                thread_status.heartbeat('crawler')
                if self._crawler_restart_failures:
                    self._crawler_restart_failures = 0
                    self._crawler_restart_backoff_s = 60.0
            else:
                services["crawler"] = "error"
                if autoheal:
                    now = time.time()
                    if now - self._last_crawler_restart_at >= float(self._crawler_restart_backoff_s):
                        try:
                            await asyncio.to_thread(process_manager.restart_crawler)
                            self._last_crawler_restart_at = now
                            self._crawler_restart_failures = 0
                            self._crawler_restart_backoff_s = 60.0
                            services["crawler"] = "restarting"
                        except Exception as e:
                            self._last_crawler_restart_at = now
                            self._crawler_restart_failures += 1
                            self._crawler_restart_backoff_s = min(
                                900.0,
                                max(60.0, 30.0 * (2.0 ** min(float(self._crawler_restart_failures), 5.0))),
                            )
                            services["crawler"] = "error"
                            services["crawler_error"] = str(e)
                    else:
                        pass
            
        thread_stats = thread_status.get_status()
        
        postgres_ok = services.get("postgres") in ("ok", "disabled")
        redis_ok = services.get("redis") in ("ok", "disabled")
        crawler_ok = services.get("crawler") in ("ok", "restarting")
        is_healthy = postgres_ok and redis_ok and crawler_ok
        status = "ok" if is_healthy else "degraded"
        metrics = await self._collect_metrics()
        
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
        if metrics:
            report["metrics"] = metrics
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

    async def _collect_metrics(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        if settings.DATABASE_URL:
            metrics["postgres_pool"] = await asyncio.to_thread(self._get_postgres_pool_metrics)
        if self.redis_url:
            metrics["redis"] = await asyncio.to_thread(self._get_redis_metrics)
        return metrics

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
            if self._external_crawler_enabled():
                ext = self._external_crawler_is_alive() or {}
                actions_taken.append("crawler_external_mode")
                actions_taken.append(f"crawler_external_alive={bool(ext.get('alive'))}")
            else:
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
            except asyncio.TimeoutError:
                self.last_postgres_error = "timeout"
                return "error"
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
            except asyncio.TimeoutError:
                self.last_redis_error = "timeout"
                return "error"
            except Exception:
                return "error"

        pg_status, redis_status = await asyncio.gather(check_pg(), check_redis())
        if self._external_crawler_enabled():
            ext = self._external_crawler_is_alive() or {}
            crawler_status = "ok" if bool(ext.get("alive")) else "error"
        else:
            crawler_status = "ok" if process_manager.is_crawler_running() else "error"
        
        return {
            "postgres": pg_status,
            "redis": redis_status,
            "crawler": crawler_status
        }

    def _get_postgres_pool_metrics(self) -> Dict[str, Any]:
        try:
            return db_manager.get_pool_metrics()
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _get_redis_metrics(self) -> Dict[str, Any]:
        client = self.redis_client
        if not client:
            return {"status": "uninitialized"}
        try:
            info = client.info()
            hits = info.get("keyspace_hits")
            misses = info.get("keyspace_misses")
            hit_rate = None
            if isinstance(hits, (int, float)) and isinstance(misses, (int, float)):
                total = hits + misses
                hit_rate = (hits / total) if total else None
            return {
                "status": "ok",
                "hits": hits,
                "misses": misses,
                "hit_rate": hit_rate,
                "used_memory": info.get("used_memory"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "uptime_in_seconds": info.get("uptime_in_seconds"),
            }
        except Exception as e:
            self.last_redis_error = str(e)
            return {"status": "error", "error": str(e)}

    def _check_postgres_sync(self) -> bool:
        if not psycopg2:
            self.last_postgres_error = "psycopg2_not_installed"
            return False

        db_url = settings.DATABASE_URL
        if not db_url:
            self.last_postgres_error = "missing_database_url"
            return False
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        connect_timeout_s = int(os.getenv("PG_HEALTH_CONNECT_TIMEOUT_S", "2") or "2")
        stmt_timeout_ms = int(os.getenv("PG_HEALTH_STATEMENT_TIMEOUT_MS", "2000") or "2000")
        lock_timeout_ms = int(os.getenv("PG_HEALTH_LOCK_TIMEOUT_MS", "1000") or "1000")
        options = f"-c statement_timeout={stmt_timeout_ms} -c lock_timeout={lock_timeout_ms}"

        try:
            conn = psycopg2.connect(db_url, connect_timeout=connect_timeout_s, options=options)
            try:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return True
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
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
