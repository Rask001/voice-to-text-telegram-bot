from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.orm import Session, sessionmaker

from app.analytics_service import track_event
from app.access_service import check_user_access
from app.config import Settings
from app.formatters import format_my_id, format_profile
from app.handlers.keyboards import main_keyboard


router = Router()


@router.message(Command("profile"))
async def profile(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return

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


@router.message(Command("my_id"))
async def my_id(message: Message) -> None:
    if message.from_user is None:
        return

    await message.answer(format_my_id(message.from_user.id), reply_markup=main_keyboard())


def build_profile_text(
    user_id: int,
    full_name: str,
    username: str | None,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> str:
    with session_factory() as session:
        access_status = check_user_access(session, user_id, username, settings)
        session.commit()

    return format_profile(full_name, username, access_status)
