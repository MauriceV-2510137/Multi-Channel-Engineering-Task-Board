from __future__ import annotations
import asyncio

from fastapi import APIRouter, HTTPException, Query, status

from integrations.weather import get_weather
from api.schemas import CreateTaskBody, UpdateTaskBody, VersionBody
from services.task_service import TaskNotFound, VersionConflict, task_service

router = APIRouter()


# ----------------
# Helpers
# ----------------
def _not_found(task_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Task '{task_id}' not found.",
    )


def _conflict(exc: VersionConflict) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Version conflict: store is at version {exc.current_version}.",
    )

async def _task_dict_with_weather(task) -> dict:
    d = task.as_dict()
    if task.location:
        d["weather"] = await get_weather(task.location)
    return d

# ----------------
# Endpoints
# ----------------
@router.get("/")
async def list_tasks() -> list[dict]:
    tasks = await task_service.get_all()
    return list(await asyncio.gather(*[_task_dict_with_weather(t) for t in tasks]))


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_task(body: CreateTaskBody) -> dict:
    task = await task_service.create_task(body.to_domain())
    return await _task_dict_with_weather(task)


@router.get("/{task_id}")
async def get_task(task_id: str) -> dict:
    try:
        task = await task_service.get(task_id)
    except TaskNotFound:
        raise _not_found(task_id)
    return await _task_dict_with_weather(task)


@router.patch("/{task_id}")
async def update_task(task_id: str, body: UpdateTaskBody) -> dict:
    fields, clear = body.to_domain()
    try:
        task = await task_service.update_task(
            task_id=task_id,
            expected_version=body.expected_version,
            fields=fields,
            clear=clear,
        )
    except TaskNotFound:
        raise _not_found(task_id)
    except VersionConflict as exc:
        raise _conflict(exc)
    return await _task_dict_with_weather(task)


@router.post("/{task_id}/complete")
async def complete_task(task_id: str, body: VersionBody) -> dict:
    try:
        task = await task_service.complete_task(task_id, body.expected_version)
    except TaskNotFound:
        raise _not_found(task_id)
    except VersionConflict as exc:
        raise _conflict(exc)
    return await _task_dict_with_weather(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: str, expected_version: int = Query(..., description="Huidige versie van de taak")) -> None:
    try:
        await task_service.delete_task(task_id, expected_version)
    except TaskNotFound:
        raise _not_found(task_id)
    except VersionConflict as exc:
        raise _conflict(exc)