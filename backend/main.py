from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.tasks import router as tasks_router
from api.websocket import router as ws_router, start_broadcaster
from config import get_settings

from channels.telegram_bot import start_bot, stop_bot

settings = get_settings()

# ----------------
# Lifespan
# ----------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    start_broadcaster()
    await start_bot()
    yield
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