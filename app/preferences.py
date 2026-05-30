from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserSettings


RESPONSE_MODES = {"short", "full", "tasks"}


def normalize_response_mode(mode: str) -> str:
    mode = mode.strip().lower()
    return mode if mode in RESPONSE_MODES else "short"


def get_response_mode(session: Session, telegram_user_id: int, default_mode: str) -> str:
    settings = session.scalar(
        select(UserSettings).where(UserSettings.telegram_user_id == telegram_user_id)
    )
    if settings is None:
        return normalize_response_mode(default_mode)
    return normalize_response_mode(settings.response_mode)


def set_response_mode(session: Session, telegram_user_id: int, mode: str) -> str:
    normalized = normalize_response_mode(mode)
    settings = session.scalar(
        select(UserSettings).where(UserSettings.telegram_user_id == telegram_user_id)
    )
    if settings is None:
        settings = UserSettings(
            telegram_user_id=telegram_user_id,
            response_mode=normalized,
        )
        session.add(settings)
    else:
        settings.response_mode = normalized
    return normalized


def get_or_create_user_settings(session: Session, telegram_user_id: int) -> UserSettings:
    settings = session.scalar(
        select(UserSettings).where(UserSettings.telegram_user_id == telegram_user_id)
    )
    if settings is None:
        settings = UserSettings(telegram_user_id=telegram_user_id)
        session.add(settings)
        session.flush()
    return settings
