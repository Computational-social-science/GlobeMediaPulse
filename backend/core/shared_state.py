
import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket

# Global shared state
news_queue = asyncio.Queue()
country_geo_map: Dict[str, Any] = {}

class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.
    """
    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """
        Accept a new WebSocket connection and add it to the active list.

        Args:
            websocket (WebSocket): The WebSocket connection instance.
        """
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection from the active list.

        Args:
            websocket (WebSocket): The WebSocket connection to remove.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """
        Broadcast a JSON message to all active WebSocket connections.

        Args:
            message (dict): The message to broadcast.
        """
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # If sending fails, assume disconnected and remove? 
                # Or let disconnect handle it. 
                # Ideally we should handle cleanup.
                pass

ws_manager = ConnectionManager()
