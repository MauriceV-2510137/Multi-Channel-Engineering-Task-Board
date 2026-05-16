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


# ----------------
# IMAP reader
# ----------------
class ImapReader:
    async def fetch_unseen(self) -> list[IncomingMail]:
        """Geeft alle UNSEEN mails in de INBOX terug en markeert ze als SEEN."""
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

            # data[0] is een bytes-string van spatie-gescheiden sequence numbers
            # bv. b"1 2 5" of b"" als er niets is
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
        """Fetch headers van één mail en markeer als gelezen."""
        try:
            # Alleen de FROM en SUBJECT headers ophalen. efficienter dan RFC822
            typ, data = await client.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            if typ != "OK" or len(data) < 2:
                return None

            # Markeer als gelezen
            await client.store(uid, "+FLAGS", "(\\Seen)")

            # data[1] bevat de raw header bytes
            raw_headers: bytes = data[1]
            msg = message_from_bytes(raw_headers)

            from_address = _decode_mime(msg.get("From", ""))
            subject = _decode_mime(msg.get("Subject", ""))

            return IncomingMail(uid=uid, from_address=from_address, subject=subject)

        except Exception:
            return None


# ----------------
# SMTP sender
# ----------------
class SmtpSender:
    async def send(self, to: str, subject: str, body: str) -> None:
        """Stuurt een plain-text mail naar `to`."""
        msg = EmailMessage()
        msg["From"] = settings.email_address
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                # Geen TLS: GreenMail op poort 3025 is plain SMTP
            )
        except Exception:
            pass


# ----------------
# Hulpfunctie: MIME header decoderen
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


# ----------------
# Singletons
# ----------------
imap_reader = ImapReader()
smtp_sender = SmtpSender()