from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from config import get_settings
from integrations.email_client import imap_reader, smtp_sender

settings = get_settings()

router = APIRouter()


# ----------------
# Request schema
# ----------------
class SendMailBody(BaseModel):
    to: str
    subject: str
    body: str = ""


# ----------------
# Endpoints
# ----------------
@router.post("/send", status_code=status.HTTP_204_NO_CONTENT)
async def send_mail(payload: SendMailBody) -> None:
    try:
        await smtp_sender.send(
            to=payload.to,
            subject=payload.subject,
            body=payload.body,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Kon de mail niet versturen via SMTP: {exc}",
        )


@router.get("/inbox")
async def get_inbox(limit: int = 30) -> list[dict]:
    clamped = min(limit, 100)
    messages = await imap_reader.fetch_all(max_messages=clamped)
    return [m.as_dict() for m in messages]


@router.get("/address")
async def get_address() -> dict:
    return {"address": settings.bot_email}