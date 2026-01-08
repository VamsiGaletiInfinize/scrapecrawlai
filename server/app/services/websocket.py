"""
WebSocket connection manager for real-time updates.

Manages WebSocket connections and broadcasts job status updates
to connected clients.
"""

import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket

from ..utils.logger import get_api_logger

logger = get_api_logger()


class ConnectionManager:
    """
    Manages WebSocket connections for real-time job updates.

    Features:
    - Track connections per job_id
    - Broadcast updates to all subscribers of a job
    - Handle connection/disconnection gracefully
    """

    def __init__(self):
        # Map job_id -> set of WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = {}
        # Map WebSocket -> job_id for cleanup
        self._websocket_to_job: Dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, job_id: str):
        """
        Accept a WebSocket connection and subscribe to job updates.

        Args:
            websocket: The WebSocket connection
            job_id: The job ID to subscribe to
        """
        await websocket.accept()

        async with self._lock:
            if job_id not in self._connections:
                self._connections[job_id] = set()
            self._connections[job_id].add(websocket)
            self._websocket_to_job[websocket] = job_id

        logger.info(f"[WS] Client connected to job {job_id}")

    async def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove
        """
        async with self._lock:
            job_id = self._websocket_to_job.pop(websocket, None)
            if job_id and job_id in self._connections:
                self._connections[job_id].discard(websocket)
                if not self._connections[job_id]:
                    del self._connections[job_id]

        logger.info(f"[WS] Client disconnected from job {job_id}")

    async def broadcast_to_job(self, job_id: str, data: dict):
        """
        Broadcast a message to all clients subscribed to a job.

        Args:
            job_id: The job ID to broadcast to
            data: The data to send
        """
        async with self._lock:
            connections = self._connections.get(job_id, set()).copy()

        if not connections:
            return

        message = json.dumps(data)
        disconnected = []

        for websocket in connections:
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.debug(f"[WS] Failed to send to client: {e}")
                disconnected.append(websocket)

        # Clean up disconnected clients
        for websocket in disconnected:
            await self.disconnect(websocket)

    async def broadcast_status_update(self, job_id: str, status: dict):
        """
        Broadcast a job status update.

        Args:
            job_id: The job ID
            status: The status data
        """
        await self.broadcast_to_job(job_id, {
            "type": "status_update",
            "job_id": job_id,
            "data": status
        })

    async def broadcast_job_completed(self, job_id: str, status: dict):
        """
        Broadcast that a job has completed.

        Args:
            job_id: The job ID
            status: The final status data
        """
        await self.broadcast_to_job(job_id, {
            "type": "job_completed",
            "job_id": job_id,
            "data": status
        })

    async def broadcast_job_failed(self, job_id: str, error: str):
        """
        Broadcast that a job has failed.

        Args:
            job_id: The job ID
            error: The error message
        """
        await self.broadcast_to_job(job_id, {
            "type": "job_failed",
            "job_id": job_id,
            "error": error
        })

    def get_subscriber_count(self, job_id: str) -> int:
        """Get the number of subscribers for a job."""
        return len(self._connections.get(job_id, set()))


# Global connection manager instance
connection_manager = ConnectionManager()
