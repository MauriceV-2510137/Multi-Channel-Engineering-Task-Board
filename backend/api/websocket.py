from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from events import EventBus, TaskEvent, event_bus

router = APIRouter()

# ----------------
# Connection manager
# ----------------
class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        try:
            self._connections.remove(ws)
        except ValueError:
            pass

    async def broadcast(self, data: dict) -> None:
        payload = json.dumps(data)
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()

# ----------------
# Background broadcaster
# ----------------
async def _broadcast_events(bus: EventBus) -> None:
    """Long-running coroutine: drains the event queue and broadcasts to WS clients."""
    q = bus.subscribe()
    try:
        while True:
            event: TaskEvent = await q.get()
            await manager.broadcast(event.as_dict())
    finally:
        bus.unsubscribe(q)


# ----------------
# Startup hook
# ----------------
def start_broadcaster() -> asyncio.Task:
    return asyncio.create_task(_broadcast_events(event_bus))

# ----------------
# Endpoint
# ----------------
@router.websocket("/tasks")
async def ws_tasks(ws: WebSocket) -> None:
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)