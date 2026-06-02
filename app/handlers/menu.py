from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.orm import Session, sessionmaker

from app.access import LIMIT_EXPIRED_MESSAGE
from app.access_service import check_user_access
from app.analytics_service import track_event
from app.config import Settings
from app.formatters import help_text
from app.handlers.constants import (
    MENU_BACK,
    MENU_HELP,
    MENU_HISTORY,
    MENU_NEW_VOICE,
    MENU_NEW_VOICE_LEGACY,
    MENU_PROFILE,
    MENU_REMINDER_CREATE,
    MENU_REMINDER_CURRENT,
    MENU_REMINDERS,
    MENU_REMINDERS_LEGACY,
    MENU_REMINDERS_SHORT_LEGACY,
    MENU_SETTINGS,
)
from app.handlers.history import _send_history
from app.handlers.keyboards import main_keyboard, profile_payment_keyboard, reminders_menu_keyboard
from app.handlers.profile import build_profile_text
from app.handlers.reminders import send_user_reminders, start_reminder_creation
from app.handlers.settings import settings_command


router = Router()


@router.message(
    F.text.in_(
        {
            MENU_NEW_VOICE,
            MENU_NEW_VOICE_LEGACY,
            MENU_PROFILE,
            MENU_HISTORY,
            MENU_REMINDERS,
            MENU_REMINDERS_LEGACY,
            MENU_REMINDERS_SHORT_LEGACY,
            MENU_REMINDER_CREATE,
            MENU_REMINDER_CURRENT,
            MENU_BACK,
            MENU_SETTINGS,
            MENU_HELP,
        }
    )
)
async def reply_keyboard_handler(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.text in {MENU_NEW_VOICE, MENU_NEW_VOICE_LEGACY}:
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
                    "reason": access_status.denial_code or "limit_exceeded",
                    "remaining_minutes": access_status.minutes_remaining_month,
                    "remaining_daily_messages": access_status.remaining_today,
                    "source": "new_voice_menu",
                },
                settings=settings,
                tariff_type=access_status.tariff_type,
            )
            await message.answer(
                LIMIT_EXPIRED_MESSAGE,
                reply_markup=profile_payment_keyboard(),
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
            reply_markup=profile_payment_keyboard(),
        )
    elif message.text == MENU_HISTORY and message.from_user is not None:
        track_event(session_factory, "history_opened", message.from_user, settings=settings)
        await _send_history(message, message.from_user.id, session_factory)
    elif (
        message.text in {MENU_REMINDERS, MENU_REMINDERS_LEGACY, MENU_REMINDERS_SHORT_LEGACY}
        and message.from_user is not None
    ):
        track_event(
            session_factory,
            "reminders_opened",
            message.from_user,
            {"source": "reply_keyboard_menu"},
            settings=settings,
        )
        await message.answer(
            "🔔 Раздел напоминаний.\n\nВыберите действие:",
            reply_markup=reminders_menu_keyboard(),
        )
    elif message.text == MENU_REMINDER_CREATE:
        await start_reminder_creation(message, state)
    elif message.text == MENU_REMINDER_CURRENT and message.from_user is not None:
        track_event(
            session_factory,
            "reminders_opened",
            message.from_user,
            {"source": "reply_keyboard_current"},
            settings=settings,
        )
        await send_user_reminders(
            message,
            message.from_user.id,
            session_factory,
            empty_reply_markup=reminders_menu_keyboard(),
        )
    elif message.text == MENU_BACK:
        await message.answer("Вернулся в главное меню.", reply_markup=main_keyboard())
    elif message.text == MENU_SETTINGS:
        await settings_command(message, settings, session_factory)
    elif message.text == MENU_HELP:
        await message.answer(help_text(), reply_markup=main_keyboard())
