"""
Camera Status Broadcaster Service

Provides real-time camera status updates using Server-Sent Events (SSE).
Broadcasts status changes to subscribed clients whenever worker heartbeats
or streaming status changes occur.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Set

from fastapi import Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


class CameraStatusBroadcaster:
    """Manages real-time broadcasting of camera status updates"""

    def __init__(self):
        self.connections: Dict[str, Set[asyncio.Queue]] = {}  # site_id -> set of queues
        self.last_status: Dict[int, Dict[str, Any]] = {}  # camera_id -> last status

    def add_client(self, site_id: str, queue: asyncio.Queue):
        """Add a client connection for a specific site"""
        if site_id not in self.connections:
            self.connections[site_id] = set()
        self.connections[site_id].add(queue)
        logger.info(
            f"Added SSE client for site {site_id}. Total clients: {len(self.connections[site_id])}"
        )

    def remove_client(self, site_id: str, queue: asyncio.Queue):
        """Remove a client connection"""
        if site_id in self.connections:
            self.connections[site_id].discard(queue)
            if not self.connections[site_id]:
                del self.connections[site_id]
            logger.info(f"Removed SSE client for site {site_id}")

    async def broadcast_camera_status_change(
        self, site_id: str, camera_id: int, status_data: Dict[str, Any]
    ):
        """Broadcast camera status change to all clients for a site"""
        if site_id not in self.connections or not self.connections[site_id]:
            return

        # Check if status actually changed
        camera_key = camera_id
        if (
            camera_key in self.last_status
            and self.last_status[camera_key] == status_data
        ):
            return  # No change, don't broadcast

        self.last_status[camera_key] = status_data

        message = {
            "type": "camera_status_update",
            "site_id": site_id,
            "camera_id": camera_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": status_data,
        }

        # Send to all connected clients for this site
        disconnected_queues = set()
        for queue in self.connections[site_id].copy():
            try:
                queue.put_nowait(message)
            except Exception as e:
                logger.warning(f"Failed to send message to SSE client: {e}")
                disconnected_queues.add(queue)

        # Clean up disconnected clients
        for queue in disconnected_queues:
            self.remove_client(site_id, queue)

    async def broadcast_site_status_update(
        self, site_id: str, site_status_data: Dict[str, Any]
    ):
        """Broadcast comprehensive site status update"""
        if site_id not in self.connections or not self.connections[site_id]:
            return

        message = {
            "type": "site_status_update",
            "site_id": site_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": site_status_data,
        }

        # Send to all connected clients for this site
        disconnected_queues = set()
        for queue in self.connections[site_id].copy():
            try:
                queue.put_nowait(message)
            except Exception as e:
                logger.warning(f"Failed to send message to SSE client: {e}")
                disconnected_queues.add(queue)

        # Clean up disconnected clients
        for queue in disconnected_queues:
            self.remove_client(site_id, queue)

    async def stream_site_status(
        self, site_id: str, request: Request
    ) -> StreamingResponse:
        """Create SSE stream for site camera status updates"""
        queue = asyncio.Queue()
        self.add_client(site_id, queue)

        async def event_stream():
            try:
                # Send initial connection confirmation
                yield f"data: {json.dumps({'type': 'connected', 'site_id': site_id})}\n\n"

                while True:
                    # Check if client disconnected
                    if await request.is_disconnected():
                        break

                    try:
                        # Wait for new message with timeout
                        message = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"data: {json.dumps(message)}\n\n"
                    except asyncio.TimeoutError:
                        # Send keepalive
                        yield f"data: {json.dumps({'type': 'keepalive', 'timestamp': datetime.utcnow().isoformat()})}\n\n"

            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"SSE stream error: {e}")
            finally:
                self.remove_client(site_id, queue)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET",
                "Access-Control-Allow-Headers": "Cache-Control",
            },
        )


# Global broadcaster instance
camera_status_broadcaster = CameraStatusBroadcaster()
