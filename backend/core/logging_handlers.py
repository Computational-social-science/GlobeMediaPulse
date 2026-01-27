
import logging
import asyncio
from typing import Deque
from collections import deque
from backend.core.shared_state import ws_manager

class WebSocketLogHandler(logging.Handler):
    """
    Custom logging handler that broadcasts log records to connected WebSocket clients.
    Also maintains a small buffer of recent logs for new connections.
    """
    def __init__(self, capacity: int = 100):
        super().__init__()
        self.log_buffer: Deque[dict] = deque(maxlen=capacity)

    def emit(self, record):
        try:
            log_entry = self.format(record)
            
            # Create structured log object
            log_data = {
                "timestamp": record.created,
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
                "formatted": log_entry
            }
            
            self.log_buffer.append(log_data)
            
            # Broadcast asynchronously
            # Since emit is synchronous, we need to schedule the broadcast
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(ws_manager.broadcast({
                            "type": "log",
                            "payload": log_data
                        }))
            except RuntimeError:
                # Loop might not be running yet or we are in a different thread
                pass
                
        except Exception:
            self.handleError(record)

# Global instance
ws_log_handler = WebSocketLogHandler()
