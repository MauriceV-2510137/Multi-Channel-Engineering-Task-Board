from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from models import TaskCreate, TaskClear, TaskFields, TaskStatus

# ----------------
# Request schemas
# ----------------
class CreateTaskBody(BaseModel):
    title: str
    location: Optional[str] = None
    deadline: Optional[datetime] = None

    def to_domain(self) -> TaskCreate:
        return TaskCreate(
            title=self.title,
            location=self.location,
            deadline=self.deadline,
        )


class UpdateTaskBody(BaseModel):
    expected_version: int
    title: Optional[str] = None
    status: Optional[TaskStatus] = None
    location: Optional[str] = None
    deadline: Optional[datetime] = None

    def to_domain(self) -> tuple[TaskFields, TaskClear]:
        sent = self.model_fields_set
        fields = TaskFields(
            title=self.title,
            status=self.status,
            location=self.location,
            deadline=self.deadline,
        )
        clear = TaskClear(
            location="location" in sent and self.location is None,
            deadline="deadline" in sent and self.deadline is None,
        )
        return fields, clear


class VersionBody(BaseModel):
    """Herbruikbaar voor /complete (POST body)."""
    expected_version: int