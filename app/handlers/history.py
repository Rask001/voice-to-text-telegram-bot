from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.analytics_service import track_event
from app.config import Settings
from app.formatters import format_history, format_history_item
from app.handlers.keyboards import history_keyboard, main_keyboard, note_keyboard
from app.handlers.utils import send_html_chunks
from app.models import VoiceNote


router = Router()


@router.message(Command("history"))
async def history_command(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    track_event(session_factory, "history_opened", message.from_user, settings=settings)
    await _send_history(message, message.from_user.id, session_factory)


@router.callback_query(F.data.startswith("history:"))
async def history_callback(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or callback.data is None:
        return

    try:
        note_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Запись не найдена. Возможно, она была удалена.", show_alert=True)
        return

    with session_factory() as session:
        note = session.get(VoiceNote, note_id)
        if note is None:
            await callback.answer("Запись не найдена. Возможно, она была удалена.", show_alert=True)
            return
        if note.telegram_user_id != callback.from_user.id:
            await callback.answer("Эта запись недоступна.", show_alert=True)
            return

        text = format_history_item(note)
        keyboard = note_keyboard(note.id, source="history")

    if not isinstance(callback.message, Message):
        await callback.answer("Не удалось отправить ответ", show_alert=True)
        return

    track_event(
        session_factory,
        "history_item_opened",
        callback.from_user,
        {"transcription_id": note_id},
        settings=settings,
    )
    await callback.answer("Открываю...")
    await send_html_chunks(callback.message, text, reply_markup=keyboard)


async def _send_history(
    message: Message,
    user_id: int,
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        notes = list(
            session.scalars(
                select(VoiceNote)
                .where(VoiceNote.telegram_user_id == user_id)
                .order_by(VoiceNote.created_at.desc())
                .limit(5)
            )
        )

    if not notes:
        await message.answer(
            "История пока пуста. Отправьте первое голосовое сообщение.",
            reply_markup=main_keyboard(),
        )
        return

    await message.answer(
        format_history(notes),
        reply_markup=history_keyboard(notes),
    )
