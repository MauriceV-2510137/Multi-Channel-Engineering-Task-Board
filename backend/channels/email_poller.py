from __future__ import annotations

import asyncio
from email.utils import parseaddr

from config import get_settings
from events import Channel
from integrations.email_client import IncomingMail, imap_reader, smtp_sender
from models import TaskCreate, TaskStatus, TaskUpdate
from services.command_service import TaskNotFound, VersionConflict, command_service
from services.task_service import task_service

settings = get_settings()

# ----------------
# Command handlers
# ----------------
async def _handle_mail(mail: IncomingMail) -> None:
    _, reply_to = parseaddr(mail.from_address)
    if not reply_to:
        reply_to = mail.from_address

    # if reply_to.lower() == settings.email_address.lower():
    #     return

    parts = mail.subject.strip().split(maxsplit=1)
    if not parts:
        await _reply(
            reply_to,
            "Onbekend commando",
            "Onderwerp is leeg.\n\n"
            "Beschikbare commando's:\n"
            "  ADD <titel>   — taak aanmaken\n"
            "  DONE <id>     — taak afronden\n"
            "  DELETE <id>   — taak verwijderen\n"
            "  LIST          — alle taken tonen",
        )
        return

    command = parts[0].upper()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if command == "ADD":
        await _cmd_add(reply_to, arg)
    elif command == "DONE":
        await _cmd_done(reply_to, arg)
    elif command == "DELETE":
        await _cmd_delete(reply_to, arg)
    elif command == "LIST":
        await _cmd_list(reply_to)
    else:
        await _reply(
            reply_to,
            f"Onbekend commando: {command}",
            "Beschikbare commando's:\n"
            "  ADD <titel>   — taak aanmaken\n"
            "  DONE <id>     — taak afronden\n"
            "  DELETE <id>   — taak verwijderen\n"
            "  LIST          — alle taken tonen",
        )


async def _cmd_add(reply_to: str, title: str) -> None:
    if not title:
        await _reply(reply_to, "Fout: geen titel opgegeven", "Gebruik: ADD <titel>")
        return

    task = await command_service.create_task(
        data=TaskCreate(title=title),
        source=Channel.EMAIL,
    )
    await _reply(
        reply_to,
        f"Taak aangemaakt: {task.title}",
        f"ID:     {task.id[:8]}\n"
        f"Titel:  {task.title}\n"
        f"Status: te doen",
    )


async def _cmd_done(reply_to: str, partial_id: str) -> None:
    if not partial_id:
        await _reply(reply_to, "Fout: geen ID opgegeven", "Gebruik: DONE <id>")
        return

    tasks = await task_service.get_all()
    matches = [t for t in tasks if t.id.startswith(partial_id.lower())]

    if not matches:
        await _reply(reply_to, f"Niet gevonden: {partial_id}", "Geen taak met dat ID gevonden.")
        return

    if len(matches) > 1:
        lines = "\n".join(f"  {t.id[:8]} — {t.title}" for t in matches)
        await _reply(reply_to, "Meerdere matches gevonden", f"Wees specifieker:\n{lines}")
        return

    task = matches[0]

    if task.status == TaskStatus.DONE:
        await _reply(
            reply_to,
            f"Al afgerond: {task.title}",
            "Deze taak was al als voltooid gemarkeerd.",
        )
        return

    try:
        updated = await command_service.update_task(
            task_id=task.id,
            expected_version=task.version,
            update=TaskUpdate(status=TaskStatus.DONE),
            source=Channel.EMAIL,
        )
        await _reply(
            reply_to,
            f"Afgerond: {updated.title}",
            f"ID:     {updated.id[:8]}\n"
            f"Titel:  {updated.title}\n"
            f"Status: afgerond",
        )
    except VersionConflict:
        await _reply(
            reply_to,
            "Versieconflict",
            "De taak werd tegelijkertijd aangepast via een ander kanaal.\n"
            "Stuur het commando opnieuw om het opnieuw te proberen.",
        )
    except TaskNotFound:
        await _reply(reply_to, "Niet gevonden", "Taak bestaat niet meer.")


async def _cmd_delete(reply_to: str, partial_id: str) -> None:
    if not partial_id:
        await _reply(reply_to, "Fout: geen ID opgegeven", "Gebruik: DELETE <id>")
        return

    tasks = await task_service.get_all()
    matches = [t for t in tasks if t.id.startswith(partial_id.lower())]

    if not matches:
        await _reply(reply_to, f"Niet gevonden: {partial_id}", "Geen taak met dat ID gevonden.")
        return

    if len(matches) > 1:
        lines = "\n".join(f"  {t.id[:8]} — {t.title}" for t in matches)
        await _reply(reply_to, "Meerdere matches gevonden", f"Wees specifieker:\n{lines}")
        return

    task = matches[0]
    try:
        await command_service.delete_task(
            task_id=task.id,
            expected_version=task.version,
            source=Channel.EMAIL,
        )
        await _reply(
            reply_to,
            f"Verwijderd: {task.title}",
            f"Taak {task.id[:8]} is permanent verwijderd.",
        )
    except VersionConflict:
        await _reply(
            reply_to,
            "Versieconflict",
            "De taak werd tegelijkertijd aangepast via een ander kanaal.\n"
            "Stuur het commando opnieuw om het opnieuw te proberen.",
        )
    except TaskNotFound:
        await _reply(reply_to, "Niet gevonden", "Taak bestaat niet meer.")


async def _cmd_list(reply_to: str) -> None:
    tasks = await task_service.get_all()
    if not tasks:
        await _reply(reply_to, "Takenlijst", "Geen taken gevonden.")
        return

    todo = [t for t in tasks if t.status == TaskStatus.TODO]
    done = [t for t in tasks if t.status == TaskStatus.DONE]

    lines: list[str] = []
    if todo:
        lines.append("Te doen:")
        lines.extend(f"  {t.id[:8]} — {t.title}" for t in todo)
    if done:
        if lines:
            lines.append("")
        lines.append("Afgerond:")
        lines.extend(f"  {t.id[:8]} — {t.title}" for t in done)

    await _reply(reply_to, f"Takenlijst ({len(tasks)} taken)", "\n".join(lines))


# ----------------
# Reply helper
# ----------------
async def _reply(to: str, subject: str, body: str) -> None:
    try:
        await smtp_sender.send(to=to, subject=subject, body=body)
    except Exception:
        pass


# ----------------
# Poll loop
# ----------------
async def _poll_loop() -> None:
    while True:
        try:
            mails = await imap_reader.fetch_unseen()
            for mail in mails:
                await _handle_mail(mail)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

        await asyncio.sleep(settings.email_poll_interval)


# ----------------
# Lifecycle
# ----------------
def start_poller() -> asyncio.Task:
    return asyncio.create_task(_poll_loop())