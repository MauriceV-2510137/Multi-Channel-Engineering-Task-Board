from __future__ import annotations

from events import EventBus, EventType, TaskEvent, event_bus
from models import Task, TaskCreate, TaskClear, TaskFields
from store import TaskNotFound, TaskStore, VersionConflict, store

__all__ = [
    "TaskService",
    "task_service",
    "TaskNotFound",
    "VersionConflict",
]


class TaskService:
    def __init__(self, store: TaskStore, bus: EventBus) -> None:
        self._store = store
        self._bus   = bus

    # ----------------
    # Queries
    # ----------------
    async def get_all(self) -> list[Task]:
        return await self._store.get_all()

    async def get(self, task_id: str) -> Task:
        return await self._store.get(task_id)

    # ----------------
    # Commands
    # ----------------
    async def create_task(self, data: TaskCreate) -> Task:
        task = await self._store.add(data)
        await self._bus.publish(TaskEvent(type=EventType.TASK_CREATED, task=task, task_id=task.id))
        return task

    async def update_task(self, task_id: str, expected_version: int, fields: TaskFields, clear: TaskClear = TaskClear()) -> Task:
        task = await self._store.update(task_id, expected_version, fields, clear)
        await self._bus.publish(TaskEvent(type=EventType.TASK_UPDATED, task=task, task_id=task.id))
        return task

    async def complete_task(self, task_id: str, expected_version: int) -> Task:
        task = await self._store.mark_done(task_id, expected_version)
        await self._bus.publish(TaskEvent(type=EventType.TASK_COMPLETED, task=task, task_id=task.id))
        return task

    async def delete_task(self, task_id: str, expected_version: int) -> None:
        await self._store.delete(task_id, expected_version)
        await self._bus.publish(TaskEvent(type=EventType.TASK_DELETED, task=None, task_id=task_id))


# ----------------
# Singleton
# ----------------
task_service = TaskService(store=store, bus=event_bus)