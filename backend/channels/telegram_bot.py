from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import get_settings
from models import TaskCreate, TaskFields, TaskStatus
from services.task_service import TaskNotFound, VersionConflict, task_service

settings = get_settings()


# ----------------
# Helpers
# ----------------
def _task_line(task) -> str:
    """Één regel per taak voor in een lijst."""
    status_icon = "✅" if task.status == TaskStatus.DONE else "🔲"
    location = f" 📍 {task.location}" if task.location else ""
    return f"{status_icon} [{task.id[:8]}] {task.title}{location}"


# ----------------
# Command handlers
# ----------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Task Board bot\n\n"
        "/list — alle taken tonen\n"
        "/add <titel> — taak aanmaken\n"
        "/done <id> — taak als afgerond markeren\n"
        "/delete <id> — taak verwijderen"
    )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tasks = await task_service.get_all()
    if not tasks:
        await update.message.reply_text("📭 Geen taken gevonden.")
        return

    todo = [t for t in tasks if t.status == TaskStatus.TODO]
    done = [t for t in tasks if t.status == TaskStatus.DONE]

    lines = []
    if todo:
        lines.append("*Te doen*")
        lines.extend(_task_line(t) for t in todo)
    if done:
        if lines:
            lines.append("")
        lines.append("*Afgerond*")
        lines.extend(_task_line(t) for t in done)

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    title = " ".join(context.args)
    if not title:
        await update.message.reply_text("❌ Gebruik: /add <titel>")
        return

    task = await task_service.create_task(TaskCreate(title=title))
    await update.message.reply_text(
        f"✅ Taak aangemaakt!\n`{task.id[:8]}` — {task.title}",
        parse_mode="Markdown",
    )


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("❌ Gebruik: /done <id>")
        return

    partial_id = context.args[0].lower()

    # Zoek taak op basis van volledige of verkorte ID
    tasks = await task_service.get_all()
    matches = [t for t in tasks if t.id.startswith(partial_id)]

    if not matches:
        await update.message.reply_text(f"❌ Geen taak gevonden met ID `{partial_id}`", parse_mode="Markdown")
        return
    if len(matches) > 1:
        lines = ["⚠️ Meerdere taken gevonden, wees specifieker:"]
        lines.extend(_task_line(t) for t in matches)
        await update.message.reply_text("\n".join(lines))
        return

    task = matches[0]
    if task.status == TaskStatus.DONE:
        await update.message.reply_text(f"ℹ️ Taak `{task.id[:8]}` is al afgerond.", parse_mode="Markdown")
        return

    try:
        updated = await task_service.complete_task(task.id, task.version)
        await update.message.reply_text(
            f"✅ Afgerond: {updated.title}",
            parse_mode="Markdown",
        )
    except VersionConflict:
        await update.message.reply_text("⚡ Versieconflict — probeer opnieuw.")


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("❌ Gebruik: /delete <id>")
        return

    partial_id = context.args[0].lower()

    tasks = await task_service.get_all()
    matches = [t for t in tasks if t.id.startswith(partial_id)]

    if not matches:
        await update.message.reply_text(f"❌ Geen taak gevonden met ID `{partial_id}`", parse_mode="Markdown")
        return
    if len(matches) > 1:
        lines = ["⚠️ Meerdere taken gevonden, wees specifieker:"]
        lines.extend(_task_line(t) for t in matches)
        await update.message.reply_text("\n".join(lines))
        return

    task = matches[0]
    try:
        await task_service.delete_task(task.id, task.version)
        await update.message.reply_text(f"🗑️ Verwijderd: {task.title}")
    except VersionConflict:
        await update.message.reply_text("⚡ Versieconflict — probeer opnieuw.")


# ----------------
# Bot lifecycle
# ----------------
_bot_app: Application | None = None


async def start_bot() -> None:
    global _bot_app

    token = settings.telegram_bot_token
    if not token:
        return

    _bot_app = (
        Application.builder()
        .token(token)
        .build()
    )

    _bot_app.add_handler(CommandHandler("start", cmd_start))
    _bot_app.add_handler(CommandHandler("list", cmd_list))
    _bot_app.add_handler(CommandHandler("add", cmd_add))
    _bot_app.add_handler(CommandHandler("done", cmd_done))
    _bot_app.add_handler(CommandHandler("delete", cmd_delete))

    await _bot_app.initialize()
    await _bot_app.start()
    await _bot_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)


async def stop_bot() -> None:
    if _bot_app:
        await _bot_app.updater.stop()
        await _bot_app.stop()
        await _bot_app.shutdown()