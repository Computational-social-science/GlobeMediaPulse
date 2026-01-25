import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket

# Global shared state
# Research Motivation:
# - news_queue: Implements a Producer-Consumer pattern. Crawlers push metadata here,
#   and the WebSocket manager consumes it to broadcast to frontend clients.
news_queue = asyncio.Queue()

# country_geo_map: In-memory cache for GeoJSON data to optimize map rendering latency.
country_geo_map: Dict[str, Any] = {}

class ConnectionManager:
    """
    Manages WebSocket connections for real-time data dissemination.
    
    Research Motivation:
        - Enables push-based updates to the frontend, eliminating the need for client-side polling.
        - Supports low-latency visualization of crawling events (e.g., "News Flash" map effects).
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
                # If sending fails, we assume the connection is dead.
                # In a more robust implementation, we might schedule it for removal.
                pass

ws_manager = ConnectionManager()
