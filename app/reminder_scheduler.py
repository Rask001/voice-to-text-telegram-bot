import asyncio
import logging
from contextlib import suppress
from datetime import datetime
from html import escape

from aiogram import Bot
from sqlalchemy.orm import Session, sessionmaker

from app.analytics_service import track_event
from app.config import Settings
from app.handlers.keyboards import reminder_action_keyboard
from app.models import Reminder
from app.reminder_parser import DEFAULT_REMINDER_TIMEZONE, now_in_timezone
from app.reminder_service import (
    get_due_reminders,
    mark_reminder_failed,
    mark_reminder_sending,
    mark_reminder_sent,
)


logger = logging.getLogger(__name__)


async def run_reminder_scheduler(
    bot: Bot,
    session_factory: sessionmaker[Session],
    settings: Settings,
    interval_seconds: int = 30,
) -> None:
    while True:
        try:
            await process_due_reminders_once(bot, session_factory, settings)
        except Exception:
            logger.exception("Reminder scheduler iteration failed")
        await asyncio.sleep(interval_seconds)


async def process_due_reminders_once(
    bot: Bot,
    session_factory: sessionmaker[Session],
    settings: Settings | None = None,
    now: datetime | None = None,
) -> int:
    timezone = settings.default_timezone if settings is not None else DEFAULT_REMINDER_TIMEZONE
    current = now or now_in_timezone(timezone)
    sent_count = 0
    with session_factory() as session:
        reminders = get_due_reminders(session, current)

    for reminder_snapshot in reminders:
        reminder_id = reminder_snapshot.id
        with session_factory() as session:
            reminder = session.get(Reminder, reminder_id)
            if reminder is None or reminder.status != "pending":
                continue
            mark_reminder_sending(session, reminder, current)
            session.commit()

        try:
            await bot.send_message(
                reminder_snapshot.telegram_id,
                _format_reminder_message(reminder_snapshot.task_text),
                reply_markup=reminder_action_keyboard(reminder_id),
            )
        except Exception:
            logger.exception("Failed to send reminder %s", reminder_id)
            with suppress(Exception), session_factory() as session:
                reminder = session.get(Reminder, reminder_id)
                if reminder is not None:
                    mark_reminder_failed(session, reminder)
                    session.commit()
            continue

        with session_factory() as session:
            reminder = session.get(Reminder, reminder_id)
            if reminder is not None:
                mark_reminder_sent(session, reminder)
                session.commit()
        if settings is not None:
            track_event(
                session_factory,
                "reminder_sent",
                reminder_snapshot.telegram_id,
                {"reminder_id": reminder_id},
                settings=settings,
            )
        sent_count += 1

    return sent_count


def _format_reminder_message(task_text: str) -> str:
    return f"🔔 <b>Напоминание</b>\n\n{escape(task_text)}"
