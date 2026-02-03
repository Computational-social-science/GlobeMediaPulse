import time
import functools
import logging
from typing import Callable, Type, Tuple, Union, Any

logger = logging.getLogger(__name__)

def retry_with_backoff(
    retries: int = 3,
    backoff_in_seconds: float = 1.0,
    max_backoff: float = 30.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = (Exception,),
    raise_on_failure: bool = True,
    fallback_value: Any = None
):
    """
    Decorator for robust retries with exponential backoff.
    
    Research Motivation:
        - Mitigates transient network failures (e.g. DNS, 5xx, Rate Limits).
        - Prevents thundering herd problem via progressive backoff.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            current_backoff = backoff_in_seconds
            
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    x += 1
                    if x > retries:
                        logger.error(f"Function {func.__name__} failed after {retries} retries. Last error: {e}")
                        if raise_on_failure:
                            raise e
                        return fallback_value
                    
                    # Log warning
                    logger.warning(f"Retry {x}/{retries} for {func.__name__} due to {type(e).__name__}: {e}. Waiting {current_backoff}s...")
                    
                    time.sleep(current_backoff)
                    
                    # Exponential Backoff
                    current_backoff = min(current_backoff * 2, max_backoff)
        return wrapper
    return decorator
