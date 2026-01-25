
import time
from typing import Dict
from threading import Lock

class ThreadStatusManager:
    """
    Thread-safe singleton to track the heartbeat/status of background threads and daemons.
    Used to expose internal system health to the frontend.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ThreadStatusManager, cls).__new__(cls)
                    cls._instance.heartbeats: Dict[str, float] = {}
        return cls._instance

    def heartbeat(self, service_name: str):
        """Update the heartbeat timestamp for a specific service/thread."""
        with self._lock:
            self.heartbeats[service_name] = time.time()

    def get_status(self) -> Dict[str, str]:
        """
        Check liveness of all registered services.
        Returns a dict of {service: 'running'|'stalled'|'stopped'}
        """
        now = time.time()
        status = {}
        with self._lock:
            for service, last_beat in self.heartbeats.items():
                # Thresholds for different services could be configurable
                # Cleanup runs every 2h, so its threshold is large.
                # Monitor runs every 30s.
                
                threshold = 60 # Default 1 min
                if service == 'cleanup':
                    threshold = 7300 # 2h + buffer
                elif service == 'monitor':
                    threshold = 120 # 4x interval
                
                if now - last_beat < threshold:
                    status[service] = 'running'
                else:
                    status[service] = 'stalled'
        return status

thread_status = ThreadStatusManager()
