from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session, sessionmaker

from app.analytics_service import track_event
from app.config import Settings
from app.formatters import format_settings
from app.handlers.constants import MODE_LABELS
from app.handlers.keyboards import settings_keyboard
from app.preferences import get_response_mode, set_response_mode


router = Router()


@router.message(Command("settings"))
async def settings_command(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return

    track_event(session_factory, "settings_opened", message.from_user, settings=settings)
    with session_factory() as session:
        mode = get_response_mode(
            session,
            message.from_user.id,
            settings.default_response_mode,
        )

    await message.answer(
        format_settings(mode, MODE_LABELS),
        reply_markup=settings_keyboard(mode),
    )


@router.callback_query(F.data.startswith("settings:"))
async def settings_callback(
    callback: CallbackQuery,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or callback.data is None:
        return

    mode = callback.data.split(":", 1)[1]
    with session_factory() as session:
        selected_mode = set_response_mode(session, callback.from_user.id, mode)
        session.commit()

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            format_settings(selected_mode, MODE_LABELS),
            reply_markup=settings_keyboard(selected_mode),
        )
    await callback.answer("Настройки сохранены")
