from __future__ import annotations

from models import Task, TaskCreate, TaskUpdate
from services.task_service import  TaskNotFound, VersionConflict, task_service
from events import Channel

__all__ = [
    "CommandService",
    "command_service",
    "TaskNotFound",
    "VersionConflict",
]


class CommandService:
    # ----------------
    # Create
    # ----------------
    async def create_task(self, data: TaskCreate, source: Channel) -> Task:
        return await task_service.create_task(
            data=data,
            source=source,
        )

    # ----------------
    # Update
    # ----------------
    async def update_task(self, task_id: str, expected_version: int, update: TaskUpdate, source: Channel) -> Task:
        return await task_service.update_task(
            task_id=task_id,
            expected_version=expected_version,
            update=update,
            source=source,
        )

    # ----------------
    # Delete
    # ----------------
    async def delete_task(self, task_id: str, expected_version: int, source: Channel) -> None:
        await task_service.delete_task(
            task_id,
            expected_version,
            source=source,
        )


# Singleton
command_service = CommandService()