"""WebSocket connection manager for real-time progress updates."""
import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for job progress updates.

    All methods run on the single event loop thread, so the connection dict
    needs no lock.
    """

    def __init__(self):
        # job_id -> list of WebSocket connections
        self.active_connections: dict[str, list[WebSocket]] = {}
        self._notifications: set[asyncio.Task] = set()

    def notify(self, job_id: str, message: dict[str, Any]) -> None:
        """Notifications must never delay cancellation or emergency light OFF."""
        task = asyncio.create_task(self.broadcast(job_id, message))
        self._notifications.add(task)
        task.add_done_callback(self._notifications.discard)

    async def connect(self, websocket: WebSocket, job_id: str):
        """Accept a new WebSocket connection for a job."""
        await websocket.accept()
        self.active_connections.setdefault(job_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str):
        """Remove a WebSocket connection."""
        connections = self.active_connections.get(job_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self.active_connections.pop(job_id, None)

    async def broadcast(self, job_id: str, message: dict[str, Any]):
        """Broadcast a message to all connections subscribed to a job."""
        for connection in list(self.active_connections.get(job_id, [])):
            # 浏览器断开或卡住不能拖慢任务状态推进：发送失败或超时就移除该连接
            try:
                await asyncio.wait_for(connection.send_json(message), timeout=1)
            except Exception as exc:
                logger.warning("Dropping WebSocket for job %s: %s", job_id, exc)
                self.disconnect(connection, job_id)


# Global connection manager instance
manager = ConnectionManager()
