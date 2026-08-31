"""WebSocket connection manager for real-time progress updates."""
import asyncio
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for job progress updates."""

    def __init__(self):
        # job_id -> list of WebSocket connections
        self.active_connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, job_id: str):
        """Accept a new WebSocket connection for a job."""
        await websocket.accept()
        async with self._lock:
            if job_id not in self.active_connections:
                self.active_connections[job_id] = []
            self.active_connections[job_id].append(websocket)
        logger.info(f"WebSocket connected for job {job_id}, total: {len(self.active_connections[job_id])}")

    async def disconnect(self, websocket: WebSocket, job_id: str):
        """Remove a WebSocket connection."""
        async with self._lock:
            if job_id in self.active_connections:
                try:
                    self.active_connections[job_id].remove(websocket)
                    if not self.active_connections[job_id]:
                        del self.active_connections[job_id]
                    logger.info(f"WebSocket disconnected from job {job_id}")
                except ValueError:
                    pass

    async def broadcast(self, job_id: str, message: dict[str, Any]):
        """Broadcast a message to all connections subscribed to a job."""
        async with self._lock:
            if job_id not in self.active_connections:
                return

            connections = self.active_connections[job_id].copy()

        # Send outside the lock to avoid blocking other operations
        disconnected = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(connection)
            except RuntimeError as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"Unexpected error sending WebSocket message: {e}")
                disconnected.append(connection)

        # Clean up disconnected sockets
        if disconnected:
            async with self._lock:
                if job_id in self.active_connections:
                    for conn in disconnected:
                        try:
                            self.active_connections[job_id].remove(conn)
                        except ValueError:
                            pass
                    if not self.active_connections[job_id]:
                        del self.active_connections[job_id]


# Global connection manager instance
manager = ConnectionManager()
