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

    # ========================================================================
    # Multi-KB specific broadcast methods
    # ========================================================================

    async def broadcast_multi_kb_progress(
        self,
        job_id: str,
        overall: dict,
        kb_update: dict,
    ):
        """
        Broadcast multi-KB progress update.

        Args:
            job_id: The job ID
            overall: Overall job metrics
            kb_update: Updated KB status
        """
        from datetime import datetime
        await self.broadcast_to_job(job_id, {
            "type": "multi_kb_progress",
            "job_id": job_id,
            "timestamp": datetime.now().isoformat(),
            "overall": overall,
            "kb_update": kb_update,
        })

    async def broadcast_kb_completed(
        self,
        job_id: str,
        kb_id: str,
        kb_name: str,
        stats: dict,
    ):
        """
        Broadcast that a Knowledge Base crawl has completed.

        Args:
            job_id: The job ID
            kb_id: The KB ID
            kb_name: The KB name
            stats: KB statistics
        """
        await self.broadcast_to_job(job_id, {
            "type": "kb_completed",
            "job_id": job_id,
            "kb_id": kb_id,
            "kb_name": kb_name,
            "stats": stats,
        })

    async def broadcast_kb_failed(
        self,
        job_id: str,
        kb_id: str,
        kb_name: str,
        error: str,
        partial_stats: dict = None,
    ):
        """
        Broadcast that a Knowledge Base crawl has failed.

        Args:
            job_id: The job ID
            kb_id: The KB ID
            kb_name: The KB name
            error: Error message
            partial_stats: Partial statistics if available
        """
        await self.broadcast_to_job(job_id, {
            "type": "kb_failed",
            "job_id": job_id,
            "kb_id": kb_id,
            "kb_name": kb_name,
            "error": error,
            "partial_stats": partial_stats or {},
        })

    async def broadcast_page_complete(
        self,
        job_id: str,
        kb_id: str,
        kb_name: str,
        url: str,
        status: str,
        depth: int,
    ):
        """
        Broadcast individual page completion.

        Args:
            job_id: The job ID
            kb_id: The KB ID
            kb_name: The KB name
            url: Page URL
            status: Page status
            depth: Page depth
        """
        await self.broadcast_to_job(job_id, {
            "type": "page_complete",
            "job_id": job_id,
            "kb_id": kb_id,
            "kb_name": kb_name,
            "url": url,
            "status": status,
            "depth": depth,
        })


# Global connection manager instance
connection_manager = ConnectionManager()
