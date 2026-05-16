from __future__ import annotations

from dataclasses import dataclass
from email import message_from_bytes
from email.header import decode_header as _decode_header
from email.message import EmailMessage

import aioimaplib
import aiosmtplib

from config import get_settings

settings = get_settings()


# ----------------
# Data types
# ----------------
@dataclass(frozen=True)
class IncomingMail:
    uid: str
    from_address: str
    subject: str
    is_reply: bool = False


@dataclass(frozen=True)
class MailMessage:
    uid: str
    from_address: str
    subject: str
    body: str
    date: str

    def as_dict(self) -> dict:
        return {
            "uid": self.uid,
            "from_address": self.from_address,
            "subject": self.subject,
            "body": self.body,
            "date": self.date,
        }


# ----------------
# IMAP reader
# ----------------
class ImapReader:

    async def fetch_unseen(self) -> list[IncomingMail]:
        client = aioimaplib.IMAP4(
            host=settings.imap_host,
            port=settings.imap_port,
        )
        await client.wait_hello_from_server()

        try:
            await client.login(settings.email_address, settings.email_password)
            await client.select("INBOX")

            typ, data = await client.search("UNSEEN")
            if typ != "OK":
                return []

            uid_bytes = data[0]
            if not uid_bytes or uid_bytes.strip() == b"":
                return []

            uids = uid_bytes.decode().split()

            mails: list[IncomingMail] = []
            for uid in uids:
                mail = await self._fetch_one(client, uid)
                if mail is not None:
                    mails.append(mail)

            return mails

        except Exception:
            return []

        finally:
            try:
                await client.logout()
            except Exception:
                pass

    async def _fetch_one(self, client: aioimaplib.IMAP4, uid: str) -> IncomingMail | None:
        try:
            typ, data = await client.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            if typ != "OK" or len(data) < 2:
                return None

            await client.store(uid, "+FLAGS", "(\\Seen)")

            raw_headers: bytes = data[1]
            msg = message_from_bytes(raw_headers)

            from_address = _decode_mime(msg.get("From", ""))
            subject = _decode_mime(msg.get("Subject", ""))
            is_reply = msg.get("X-TaskBoard-Reply", "").lower() == "true"

            return IncomingMail(
                uid=uid,
                from_address=from_address,
                subject=subject,
                is_reply=is_reply,
            )

        except Exception:
            return None


    async def fetch_all(self, max_messages: int = 30) -> list[MailMessage]:
        client = aioimaplib.IMAP4(
            host=settings.imap_host,
            port=settings.imap_port,
        )
        await client.wait_hello_from_server()

        try:
            await client.login(settings.email_address, settings.email_password)
            await client.select("INBOX")

            typ, data = await client.search("ALL")
            if typ != "OK":
                return []

            uid_bytes = data[0]
            if not uid_bytes or uid_bytes.strip() == b"":
                return []

            all_uids = uid_bytes.decode().split()

            # Neem de laatste `max_messages` (nieuwste) en draai de volgorde om
            # zodat de nieuwste berichten bovenaan staan.
            recent_uids = list(reversed(all_uids[-max_messages:]))

            messages: list[MailMessage] = []
            for uid in recent_uids:
                msg = await self._fetch_full(client, uid)
                if msg is not None:
                    messages.append(msg)

            return messages

        except Exception:
            return []

        finally:
            try:
                await client.logout()
            except Exception:
                pass

    async def _fetch_full(self, client: aioimaplib.IMAP4, uid: str) -> MailMessage | None:
        try:
            typ, data = await client.fetch(uid, "(BODY.PEEK[])")
            if typ != "OK" or len(data) < 2:
                return None

            raw: bytes = data[1]
            msg = message_from_bytes(raw)

            from_address = _decode_mime(msg.get("From", ""))
            subject     = _decode_mime(msg.get("Subject", ""))
            date        = msg.get("Date", "")

            body = _extract_text(msg)

            return MailMessage(
                uid=uid,
                from_address=from_address,
                subject=subject,
                body=body,
                date=date,
            )

        except Exception:
            return None


# ----------------
# SMTP sender
# ----------------
class SmtpSender:
    async def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = settings.email_address
        msg["To"] = to
        msg["Subject"] = subject
        msg["X-TaskBoard-Reply"] = "true"
        msg.set_content(body)

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            # Geen TLS: GreenMail op poort 3025 is plain SMTP
        )


# ----------------
# Hulpfuncties
# ----------------
def _decode_mime(value: str) -> str:
    parts = _decode_header(value)
    result: list[str] = []
    for raw, encoding in parts:
        if isinstance(raw, bytes):
            result.append(raw.decode(encoding or "utf-8", errors="replace"))
        else:
            result.append(raw)
    return "".join(result).strip()


def _extract_text(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace").strip()
        return ""

    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace").strip()
    return ""


# ----------------
# Singletons
# ----------------
imap_reader = ImapReader()
smtp_sender = SmtpSender()