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
    
    Research Motivation:
        High-throughput crawling requires efficient database connection management.
        Creating a new connection for every request is computationally expensive (TCP handshake, authentication).
        This class implements a Singleton pattern to manage a `ThreadedConnectionPool`, ensuring
        O(1) access to active connections and minimizing overhead.
    
    Architectural Role:
        - Acts as the central gateway for all synchronous database interactions.
        - Integrates with a Circuit Breaker pattern to prevent cascading failures during database outages.
    """
    _instance = None
    _pool = None

    def __new__(cls):
        """
        Enforce Singleton pattern to ensure only one connection pool exists per process.
        """
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def initialize(self):
        """
        Initialize the global connection pool if not already initialized.
        
        Implementation Details:
            - Uses `psycopg2.pool.ThreadedConnectionPool` for thread-safe access in concurrent environments.
            - Implements a retry mechanism with exponential backoff (implied) to handle transient startup failures.
        """
        if self._pool:
            return

        if not psycopg2:
            logger.error("psycopg2 not installed. Database disabled.")
            return

        db_url = settings.DATABASE_URL
        # Log only the host/db part for security, masking credentials
        logger.info(f"Initializing Global DB Pool for {db_url.split('@')[-1] if db_url else 'None'}")

        max_retries = 3
        for i in range(max_retries):
            try:
                # minconn=1: Keep at least one connection open to reduce latency for the first request.
                # maxconn=50: Increased to 50 to support Scrapy concurrency and API requests.
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1, maxconn=50, dsn=db_url
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
        """
        Retrieve the active connection pool, initializing it lazily if necessary.
        
        Returns:
            psycopg2.pool.ThreadedConnectionPool: The active connection pool.
        """
        if not self._pool:
            self.initialize()
        return self._pool

    def close(self):
        """
        Gracefully close all connections in the pool.
        
        Usage:
            Should be called during application shutdown to release database resources.
        """
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("Global DB Pool closed.")

    @contextmanager
    def get_connection(self):
        """
        Context manager to acquire a connection from the pool.
        
        Research Motivation:
            - **Resource Management**: Ensures connections are always returned to the pool (putconn)
              even if exceptions occur, preventing connection leaks.
            - **Resilience**: Integrates with `postgres_breaker` (Circuit Breaker) to fail fast
              when the database is unhealthy, preserving system resources.
        
        Yields:
            psycopg2.extensions.connection: A database connection object, or None if unavailable.
        """
        # Circuit Breaker Check: Fail fast if the database is known to be down.
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
            # Record failure in circuit breaker to trip if error rate exceeds threshold.
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
