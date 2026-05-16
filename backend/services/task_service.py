from __future__ import annotations

from events import Channel, EventBus, EventType, TaskEvent, event_bus
from models import Task, TaskCreate, TaskUpdate, TaskStatus
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
    async def create_task(self, data: TaskCreate, source: Channel) -> Task:
        task = await self._store.add(data)
        await self._bus.publish(
            TaskEvent(
                type=EventType.TASK_CREATED,
                task=task,
                task_id=task.id,
                source=source,
            )
        )
        return task

    async def update_task(self, task_id: str, expected_version: int, update: TaskUpdate, source: Channel) -> Task:
        task = await self._store.update(task_id, expected_version, update)
        is_completed = task.status == TaskStatus.DONE
        await self._bus.publish(
            TaskEvent(
                type=EventType.TASK_COMPLETED if is_completed else EventType.TASK_UPDATED,
                task=task,
                task_id=task.id,
                source=source,
            )
        )
        return task
    
    async def delete_task(self, task_id: str, expected_version: int, source: Channel) -> None:
        await self._store.delete(task_id, expected_version)
        await self._bus.publish(
            TaskEvent(
                type=EventType.TASK_DELETED,
                task=None,
                task_id=task_id,
                source=source,
            )
        )


# ----------------
# Singleton
# ----------------
task_service = TaskService(store=store, bus=event_bus)