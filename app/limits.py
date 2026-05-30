from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyUsage


def get_or_create_daily_usage(session: Session, telegram_user_id: int) -> DailyUsage:
    today = date.today()
    usage = session.scalar(
        select(DailyUsage).where(
            DailyUsage.telegram_user_id == telegram_user_id,
            DailyUsage.usage_date == today,
        )
    )

    if usage is None:
        usage = DailyUsage(
            telegram_user_id=telegram_user_id,
            usage_date=today,
            voice_count=0,
        )
        session.add(usage)
        session.flush()

    return usage


def can_process_voice(session: Session, telegram_user_id: int, daily_limit: int) -> bool:
    usage = get_or_create_daily_usage(session, telegram_user_id)
    return usage.voice_count < daily_limit


def increment_voice_usage(session: Session, telegram_user_id: int) -> None:
    usage = get_or_create_daily_usage(session, telegram_user_id)
    usage.voice_count += 1

