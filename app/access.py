from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import Settings
from app.limits import get_or_create_daily_usage
from app.preferences import get_or_create_user_settings


@dataclass(frozen=True)
class AccessStatus:
    tariff: str
    used_today: int
    daily_limit: int
    remaining_today: int | None
    reset_date: date
    is_unlimited: bool
    can_process: bool


def is_owner(user_id: int, username: str | None, settings: Settings) -> bool:
    if settings.owner_telegram_id is not None and user_id == settings.owner_telegram_id:
        return True
    return (username or "").lower() == "aaios"


def get_access_status(
    session: Session,
    user_id: int,
    username: str | None,
    settings: Settings,
) -> AccessStatus:
    usage = get_or_create_daily_usage(session, user_id)
    user_settings = get_or_create_user_settings(session, user_id)

    owner = is_owner(user_id, username, settings)
    env_unlimited = user_id in settings.unlimited_user_ids
    db_unlimited = bool(user_settings.is_unlimited)
    premium = bool(user_settings.is_premium)
    unlimited = owner or env_unlimited or db_unlimited or premium

    if owner or env_unlimited or db_unlimited:
        tariff = "Авторский безлимит 😎"
    elif premium:
        tariff = "Premium"
    else:
        tariff = "Free"

    remaining = None if unlimited else max(settings.daily_voice_limit - usage.voice_count, 0)
    return AccessStatus(
        tariff=tariff,
        used_today=usage.voice_count,
        daily_limit=settings.daily_voice_limit,
        remaining_today=remaining,
        reset_date=date.today() + timedelta(days=1),
        is_unlimited=unlimited,
        can_process=unlimited or (remaining is not None and remaining > 0),
    )


def add_unlimited_user(session: Session, telegram_user_id: int) -> None:
    user_settings = get_or_create_user_settings(session, telegram_user_id)
    user_settings.is_unlimited = True
