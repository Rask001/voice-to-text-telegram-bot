from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reminder
from app.reminder_parser import DEFAULT_REMINDER_TIMEZONE, now_in_timezone


REMINDER_STATUS_PENDING = "pending"
REMINDER_STATUS_SENDING = "sending"
REMINDER_STATUS_SENT = "sent"
REMINDER_STATUS_COMPLETED = "completed"
REMINDER_STATUS_CANCELLED = "cancelled"
REMINDER_STATUS_FAILED = "failed"

ACTIVE_REMINDER_STATUSES = {
    REMINDER_STATUS_PENDING,
    REMINDER_STATUS_SENDING,
}


def create_reminder(
    session: Session,
    telegram_id: int,
    task_text: str,
    remind_at: datetime,
    timezone: str = DEFAULT_REMINDER_TIMEZONE,
    transcription_id: int | None = None,
    source_text: str | None = None,
) -> Reminder:
    reminder = Reminder(
        telegram_id=telegram_id,
        transcription_id=transcription_id,
        task_text=task_text.strip(),
        source_text=source_text,
        remind_at=remind_at,
        timezone=timezone,
        status=REMINDER_STATUS_PENDING,
    )
    session.add(reminder)
    session.flush()
    return reminder


def get_user_reminders(
    session: Session,
    telegram_id: int,
    statuses: set[str] | None = None,
    limit: int = 10,
) -> list[Reminder]:
    selected_statuses = statuses or ACTIVE_REMINDER_STATUSES
    return list(
        session.scalars(
            select(Reminder)
            .where(
                Reminder.telegram_id == telegram_id,
                Reminder.status.in_(selected_statuses),
            )
            .order_by(Reminder.remind_at.asc(), Reminder.id.asc())
            .limit(limit)
        )
    )


def get_reminder_by_id(
    session: Session,
    reminder_id: int,
    telegram_id: int | None = None,
) -> Reminder | None:
    query = select(Reminder).where(Reminder.id == reminder_id)
    if telegram_id is not None:
        query = query.where(Reminder.telegram_id == telegram_id)
    return session.scalar(query)


def cancel_reminder(session: Session, reminder: Reminder, now: datetime | None = None) -> Reminder:
    current = now or datetime.now()
    reminder.status = REMINDER_STATUS_CANCELLED
    reminder.cancelled_at = current
    reminder.updated_at = current
    session.flush()
    return reminder


def complete_reminder(session: Session, reminder: Reminder, now: datetime | None = None) -> Reminder:
    current = now or datetime.now()
    reminder.status = REMINDER_STATUS_COMPLETED
    reminder.completed_at = current
    reminder.updated_at = current
    session.flush()
    return reminder


def snooze_reminder(
    session: Session,
    reminder: Reminder,
    remind_at: datetime | None = None,
    delta: timedelta | None = None,
    now: datetime | None = None,
) -> Reminder:
    current = now or datetime.now()
    reminder.remind_at = remind_at or current + (delta or timedelta(hours=1))
    reminder.status = REMINDER_STATUS_PENDING
    reminder.sent_at = None
    reminder.updated_at = current
    session.flush()
    return reminder


def get_due_reminders(
    session: Session,
    now: datetime | None = None,
    limit: int = 20,
) -> list[Reminder]:
    current = now or now_in_timezone(DEFAULT_REMINDER_TIMEZONE)
    return list(
        session.scalars(
            select(Reminder)
            .where(
                Reminder.status == REMINDER_STATUS_PENDING,
                Reminder.remind_at <= current,
            )
            .order_by(Reminder.remind_at.asc(), Reminder.id.asc())
            .limit(limit)
        )
    )


def mark_reminder_sending(
    session: Session,
    reminder: Reminder,
    now: datetime | None = None,
) -> Reminder:
    current = now or datetime.now()
    reminder.status = REMINDER_STATUS_SENDING
    reminder.updated_at = current
    session.flush()
    return reminder


def mark_reminder_sent(
    session: Session,
    reminder: Reminder,
    now: datetime | None = None,
) -> Reminder:
    current = now or datetime.now()
    reminder.status = REMINDER_STATUS_SENT
    reminder.sent_at = current
    reminder.updated_at = current
    session.flush()
    return reminder


def mark_reminder_failed(
    session: Session,
    reminder: Reminder,
    now: datetime | None = None,
) -> Reminder:
    current = now or datetime.now()
    reminder.status = REMINDER_STATUS_FAILED
    reminder.updated_at = current
    session.flush()
    return reminder
