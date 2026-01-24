import time
import logging
from functools import wraps
from enum import Enum
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Enumeration of Circuit Breaker states."""
    CLOSED = "CLOSED"     # Normal operation
    OPEN = "OPEN"         # Failing, blocking requests
    HALF_OPEN = "HALF_OPEN" # Probing

class CircuitBreaker:
    """
    Implements the Circuit Breaker pattern to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation. Requests are allowed.
    - OPEN: Failure threshold reached. Requests are blocked.
    - HALF_OPEN: Recovery timeout passed. One probe request is allowed.
    """
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 30):
        """
        Initialize the Circuit Breaker.

        Args:
            name (str): Name of the service/resource (e.g., 'redis', 'postgres').
            failure_threshold (int): Number of failures before opening the circuit. Defaults to 5.
            recovery_timeout (int): Seconds to wait before probing (Half-Open). Defaults to 30.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
    
    def allow_request(self) -> bool:
        """
        Check if a request is allowed based on the current state.

        Returns:
            bool: True if the request is allowed, False if the circuit is OPEN.
        """
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            now = time.time()
            if now - self.last_failure_time > self.recovery_timeout:
                logger.info(f"CircuitBreaker '{self.name}': Recovery timeout passed. Entering HALF_OPEN.")
                self.state = CircuitState.HALF_OPEN
                return True # Allow one probe request
            return False # Still open
            
        if self.state == CircuitState.HALF_OPEN:
            # We only allow one request at a time in half-open generally, 
            # but for simplicity here we assume the caller will handle the result.
            # Real implementations might use a lock or counter.
            return True 
            
        return True

    def record_success(self):
        """
        Record a successful request.
        Resets failure count and closes the circuit if it was HALF_OPEN.
        """
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"CircuitBreaker '{self.name}': Probe successful. Closing circuit.")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success if we want "consecutive" failures
            self.failure_count = 0

    def record_failure(self):
        """
        Record a failed request.
        Increments failure count and opens the circuit if threshold is reached.
        """
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"CircuitBreaker '{self.name}': Probe failed. Re-opening circuit.")
            self.state = CircuitState.OPEN
        
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.warning(f"CircuitBreaker '{self.name}': Threshold reached ({self.failure_count}). Opening circuit.")
                self.state = CircuitState.OPEN

class CircuitBreakerOpenException(Exception):
    """Exception raised when a request is blocked by an open circuit breaker."""
    pass

def circuit_breaker(cb: CircuitBreaker) -> Callable:
    """
    Decorator to wrap functions with circuit breaker logic.
    
    Args:
        cb (CircuitBreaker): The circuit breaker instance to use.
        
    Returns:
        Callable: The decorated function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if not cb.allow_request():
                # logger.warning(f"CircuitBreaker '{cb.name}' is OPEN. Blocking call to {func.__name__}.")
                # Raise specific exception or return None?
                # Raising exception is safer for control flow
                raise CircuitBreakerOpenException(f"Circuit {cb.name} is OPEN")
            
            try:
                result = func(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as e:
                # If it's a known "safe" error (like value error), maybe don't trip?
                # But for now assume all exceptions are failures of the resource
                cb.record_failure()
                raise e
        return wrapper
    return decorator

# Global instances (Singletons)
redis_breaker = CircuitBreaker("redis", failure_threshold=5, recovery_timeout=30)
postgres_breaker = CircuitBreaker("postgres", failure_threshold=5, recovery_timeout=30)
