from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

class TaskStatus(str, Enum):
    TODO = "todo"
    DONE = "done"


# ----------------
# Value objects (structs)
# ----------------
@dataclass(frozen=True)
class TaskCreate:
    """Data required to create a brand-new task."""
    title: str
    location: Optional[str] = None
    deadline: Optional[datetime] = None

@dataclass(frozen=True)
class TaskUpdate:
    title: Optional[str] = None
    status: Optional[TaskStatus] = None
    location: Optional[str] = None
    deadline: Optional[datetime] = None

    clear_location: bool = False
    clear_deadline: bool = False

@dataclass(frozen=True)
class Task:
    id: str
    title: str
    status: TaskStatus
    version: int

    location: Optional[str] = None
    deadline: Optional[datetime] = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ----------------
    # Factory
    # ----------------
    @staticmethod
    def create(data: TaskCreate) -> "Task":
        """Create a brand-new task at version 1."""
        now = datetime.now(timezone.utc)
        return Task(
            id=str(uuid.uuid4()),
            title=data.title,
            status=TaskStatus.TODO,
            version=1,
            location=data.location,
            deadline=data.deadline,
            created_at=now,
            updated_at=now,
        )

    # ----------------
    # Mutation helpers
    # ----------------
    def with_updates(self, update: TaskUpdate) -> "Task":
        return replace(
            self,
            title=update.title if update.title is not None else self.title,
            status=update.status if update.status is not None else self.status,
            location=(
                None if update.clear_location
                else update.location if update.location is not None
                else self.location
            ),
            deadline=(
                None if update.clear_deadline
                else update.deadline if update.deadline is not None
                else self.deadline
            ),
            version=self.version + 1,
            updated_at=datetime.now(timezone.utc),
        )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "version": self.version,
            "location": self.location,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }