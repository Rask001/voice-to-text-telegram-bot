from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session, sessionmaker

from app.admin_service import get_start_text
from app.analytics_service import track_event
from app.config import Settings
from app.formatters import help_text
from app.handlers.keyboards import main_keyboard
from app.handlers.profile import build_profile_text


router = Router()


@router.message(CommandStart())
async def start(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is not None:
        track_event(session_factory, "user_started", message.from_user, settings=settings)

    with session_factory() as session:
        start_text = get_start_text(session)

    await message.answer(start_text, reply_markup=main_keyboard())


@router.callback_query(F.data.startswith("start:"))
async def start_callback(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    action = callback.data.split(":", 1)[1] if callback.data else ""
    if action == "voice":
        await callback.answer("Отправь обычное голосовое сообщение 🎙", show_alert=True)
    elif action == "profile":
        await callback.answer("Открываю профиль...")
        if isinstance(callback.message, Message):
            track_event(session_factory, "profile_opened", callback.from_user, settings=settings)
            await callback.message.answer(
                build_profile_text(
                    callback.from_user.id,
                    callback.from_user.full_name,
                    callback.from_user.username,
                    settings,
                    session_factory,
                ),
                reply_markup=main_keyboard(),
            )
    elif action == "help":
        await callback.answer("Открываю помощь...")
        if isinstance(callback.message, Message):
            await callback.message.answer(help_text(), reply_markup=main_keyboard())
