from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from models import Task

# ----------------
# Event types
# ----------------
class EventType(str, Enum):
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_DELETED = "task_deleted"


class Channel(str, Enum):
    WEB = "web"
    TELEGRAM = "telegram"
    EMAIL = "email"


@dataclass(frozen=True)
class TaskEvent:
    type: EventType
    task: Optional[Task]    # None for TASK_DELETED
    task_id: str
    source: Channel

    def as_dict(self) -> dict:
        return {
            "type": self.type.value,
            "task": self.task.as_dict() if self.task is not None else None,
            "task_id": self.task_id,
            "source": self.source.value,
        }


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[TaskEvent]] = []

    # ----------------
    # Subscription
    # ----------------
    def subscribe(self) -> asyncio.Queue[TaskEvent]:
        q: asyncio.Queue[TaskEvent] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[TaskEvent]) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    # ----------------
    # Publishing
    # ----------------
    async def publish(self, event: TaskEvent) -> None:
        """Broadcast an event to all current subscribers."""
        for q in self._subscribers:
            await q.put(event)


# ----------------
# Singleton
# ----------------
event_bus = EventBus()