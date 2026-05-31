from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.orm import Session, sessionmaker

from app.access import LIMIT_EXPIRED_MESSAGE
from app.access_service import check_user_access
from app.analytics_service import track_event
from app.config import Settings
from app.formatters import help_text
from app.handlers.constants import (
    MENU_HELP,
    MENU_HISTORY,
    MENU_NEW_VOICE,
    MENU_PROFILE,
    MENU_SETTINGS,
)
from app.handlers.history import _send_history
from app.handlers.keyboards import main_keyboard
from app.handlers.profile import build_profile_text
from app.handlers.settings import settings_command


router = Router()


@router.message(F.text.in_({MENU_NEW_VOICE, MENU_PROFILE, MENU_HISTORY, MENU_SETTINGS, MENU_HELP}))
async def reply_keyboard_handler(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.text == MENU_NEW_VOICE:
        if message.from_user is None:
            return

        with session_factory() as session:
            access_status = check_user_access(
                session,
                message.from_user.id,
                message.from_user.username,
                settings,
            )
            session.commit()

        if not access_status.can_process:
            track_event(
                session_factory,
                "paywall_shown",
                message.from_user,
                {
                    "reason": access_status.denial_reason or LIMIT_EXPIRED_MESSAGE,
                    "remaining_minutes": access_status.minutes_remaining_month,
                    "remaining_daily_messages": access_status.remaining_today,
                    "source": "new_voice_menu",
                },
                settings=settings,
                tariff_type=access_status.tariff_type,
            )
            await message.answer(
                LIMIT_EXPIRED_MESSAGE,
                reply_markup=main_keyboard(),
            )
            return

        await message.answer(
            "Отправь мне голосовое сообщение 🎙\n\n"
            "Я расшифрую его, сделаю краткое содержание и выделю задачи.",
            reply_markup=main_keyboard(),
        )
    elif message.text == MENU_PROFILE and message.from_user is not None:
        track_event(session_factory, "profile_opened", message.from_user, settings=settings)
        await message.answer(
            build_profile_text(
                message.from_user.id,
                message.from_user.full_name,
                message.from_user.username,
                settings,
                session_factory,
            ),
            reply_markup=main_keyboard(),
        )
    elif message.text == MENU_HISTORY and message.from_user is not None:
        track_event(session_factory, "history_opened", message.from_user, settings=settings)
        await _send_history(message, message.from_user.id, session_factory)
    elif message.text == MENU_SETTINGS:
        await settings_command(message, settings, session_factory)
    elif message.text == MENU_HELP:
        await message.answer(help_text(), reply_markup=main_keyboard())
