
import os
import time
import logging
from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2 import pool
except ImportError:
    psycopg2 = None

from backend.core.config import settings
from backend.utils.circuit_breaker import postgres_breaker

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Singleton Database Manager for PostgreSQL connection pooling.
    Handles initialization, connection acquisition, and graceful shutdown.
    """
    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def initialize(self):
        """
        Initialize the global connection pool if not already initialized.
        Uses ThreadedConnectionPool for thread safety.
        Retries connection up to 3 times on failure.
        """
        if self._pool:
            return

        if not psycopg2:
            logger.error("psycopg2 not installed. Database disabled.")
            return

        db_url = settings.DATABASE_URL
        logger.info(f"Initializing Global DB Pool for {db_url.split('@')[-1] if db_url else 'None'}")

        max_retries = 3
        for i in range(max_retries):
            try:
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1, maxconn=20, dsn=db_url
                )
                logger.info("Global PostgreSQL Connection Pool initialized successfully.")
                break
            except Exception as e:
                if i < max_retries - 1:
                    logger.warning(f"DB Connection failed ({e}), retrying in 1s...")
                    time.sleep(1)
                else:
                    logger.critical(f"CRITICAL: Could not connect to DB: {e}")
    
    def get_pool(self):
        """Returns the active connection pool, initializing it if necessary."""
        if not self._pool:
            self.initialize()
        return self._pool

    def close(self):
        """Closes all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("Global DB Pool closed.")

    @contextmanager
    def get_connection(self):
        """
        Context manager to acquire a connection from the pool.
        Integrates with Circuit Breaker to fail fast during outages.
        
        Yields:
            psycopg2.extensions.connection: A database connection object, or None if unavailable.
        """
        # Circuit Breaker Check
        if not postgres_breaker.allow_request():
            yield None
            return

        pool = self.get_pool()
        conn = None
        if not pool:
            yield None
            return

        try:
            conn = pool.getconn()
        except Exception as e:
            postgres_breaker.record_failure()
            logger.error(f"Error getting connection from pool: {e}")
            yield None
            return

        try:
            yield conn
            postgres_breaker.record_success()
        except Exception as e:
            postgres_breaker.record_failure()
            raise e
        finally:
            if conn:
                pool.putconn(conn)

# Global Instance
db_manager = DatabaseManager()
