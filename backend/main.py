from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.tasks import router as tasks_router
from api.websocket import router as ws_router, start_broadcaster
from config import get_settings

from channels.telegram_bot import start_bot, stop_bot
from channels.email_poller import start_poller

settings = get_settings()


# ----------------
# Lifespan
# ----------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    broadcaster_task = start_broadcaster()
    poller_task = start_poller()
    await start_bot()

    try:
        yield
    finally:
        broadcaster_task.cancel()
        poller_task.cancel()

        for task in (broadcaster_task, poller_task):
            try:
                await task
            except Exception:
                pass

        await stop_bot()


# ----------------
# App
# ----------------
app = FastAPI(title="Task Board API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------
# Routers
# ----------------
app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
app.include_router(ws_router, prefix="/ws", tags=["websocket"])


@app.get("/")
async def health() -> dict:
    return {"status": "ok"}