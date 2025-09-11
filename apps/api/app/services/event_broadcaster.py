"""
Generic Tenant Event Broadcaster (SSE)

Allows API to push async results to subscribed clients per-tenant.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Set

from fastapi import Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


class TenantEventBroadcaster:
    def __init__(self):
        # tenant_id -> set of queues
        self.connections: Dict[str, Set[asyncio.Queue]] = {}

    def add_client(self, tenant_id: str, queue: asyncio.Queue):
        if tenant_id not in self.connections:
            self.connections[tenant_id] = set()
        self.connections[tenant_id].add(queue)

    def remove_client(self, tenant_id: str, queue: asyncio.Queue):
        if tenant_id in self.connections:
            self.connections[tenant_id].discard(queue)
            if not self.connections[tenant_id]:
                del self.connections[tenant_id]

    async def broadcast(self, tenant_id: str, event: Dict[str, Any]):
        if tenant_id not in self.connections or not self.connections[tenant_id]:
            return
        message = {
            "type": event.get("type", "event"),
            "timestamp": datetime.utcnow().isoformat(),
            "data": event,
        }
        stale = set()
        for q in list(self.connections[tenant_id]):
            try:
                q.put_nowait(message)
            except Exception as e:
                logger.warning(f"Failed to enqueue SSE message: {e}")
                stale.add(q)
        for q in stale:
            self.remove_client(tenant_id, q)

    async def stream(self, tenant_id: str, request: Request) -> StreamingResponse:
        queue = asyncio.Queue()
        self.add_client(tenant_id, queue)

        async def event_stream():
            try:
                yield f"data: {json.dumps({'type': 'connected', 'tenant_id': tenant_id})}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"data: {json.dumps(item)}\n\n"
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'type': 'keepalive', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            finally:
                self.remove_client(tenant_id, queue)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            },
        )


tenant_event_broadcaster = TenantEventBroadcaster()
