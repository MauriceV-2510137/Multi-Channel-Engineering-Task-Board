from __future__ import annotations

import asyncio

from models import Task, TaskCreate, TaskClear, TaskFields, TaskStatus

# ----------------
# Custom exceptions
# ----------------
class TaskNotFound(Exception):
    """Raised when a task ID does not exist in the store."""

class VersionConflict(Exception):
    """
    Raised when the caller's expected version does not match the stored version.
    """
    def __init__(self, current_version: int) -> None:
        self.current_version = current_version
        super().__init__(
            f"Version conflict: store is at version {current_version}."
        )


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    # ----------------
    # Read
    # ----------------
    async def get_all(self) -> list[Task]:
        async with self._lock:
            return list(self._tasks.values())

    async def get(self, task_id: str) -> Task:
        async with self._lock:
            return self._get_or_raise(task_id)

    # ----------------
    # Write
    # ----------------
    async def add(self, data: TaskCreate) -> Task:
        task = Task.create(data)
        async with self._lock:
            self._tasks[task.id] = task
        return task

    async def update(self, task_id: str, expected_version: int, fields: TaskFields, clear: TaskClear = TaskClear(),) -> Task:
        async with self._lock:
            current = self._get_or_raise(task_id)
            self._check_version(current, expected_version)
            updated = current.with_updates(fields, clear)
            self._tasks[task_id] = updated
            return updated

    async def delete(self, task_id: str, expected_version: int) -> None:
        async with self._lock:
            current = self._get_or_raise(task_id)
            self._check_version(current, expected_version)
            del self._tasks[task_id]

    async def mark_done(self, task_id: str, expected_version: int) -> Task:
        return await self.update(
            task_id=task_id,
            expected_version=expected_version,
            fields=TaskFields(status=TaskStatus.DONE),
        )

    # ----------------
    # Private helpers
    # ----------------
    def _get_or_raise(self, task_id: str) -> Task:
        task = self._tasks.get(task_id)
        if task is None:
            raise TaskNotFound(f"Task '{task_id}' not found.")
        return task

    @staticmethod
    def _check_version(task: Task, expected: int) -> None:
        if task.version != expected:
            raise VersionConflict(current_version=task.version)


# ----------------
# Singleton
# ----------------
store = TaskStore()