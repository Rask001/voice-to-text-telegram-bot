from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.analytics_service import track_event
from app.config import Settings
from app.formatters import format_details, format_share, format_tasks, format_voice_analysis
from app.handlers.constants import BUTTON_LOCKS
from app.handlers.utils import (
    join_message_ids,
    parse_note_action,
    send_html_chunks,
    send_text_chunks,
)
from app.models import UserSettings, VoiceNote
from app.tasks import parse_stored_tasks, split_stored_list
from app.voice_analysis import parse_voice_analysis_json


router = Router()


@router.callback_query(F.data.startswith("fresh_") | F.data.startswith("note:"))
async def fresh_note_callback(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or callback.data is None:
        return

    lock_key = f"{callback.from_user.id}:{callback.data}"
    if lock_key in BUTTON_LOCKS:
        await callback.answer("Уже показываю, секунду.")
        return

    BUTTON_LOCKS.add(lock_key)

    try:
        parsed = parse_note_action(callback.data)
        if parsed is None:
            await callback.answer("Неизвестное действие", show_alert=True)
            return
        action, note_id_text = parsed
        try:
            note_id = int(note_id_text)
        except ValueError:
            await callback.answer(
                "Не нашёл сохранённый результат. Попробуйте отправить голосовое ещё раз.",
                show_alert=True,
            )
            return

        if not isinstance(callback.message, Message):
            await callback.answer("Не удалось отправить ответ", show_alert=True)
            return

        with session_factory() as session:
            note = session.scalar(
                select(VoiceNote).where(
                    VoiceNote.id == note_id,
                    VoiceNote.telegram_user_id == callback.from_user.id,
                )
            )
            if note is None:
                await callback.answer(
                    "Не нашёл сохранённый результат. Попробуйте отправить голосовое ещё раз.",
                    show_alert=True,
                )
                return

            if action == "full_text":
                if not note.transcript:
                    await callback.answer(
                        "Не нашёл сохранённый результат. Попробуйте отправить голосовое ещё раз.",
                        show_alert=True,
                    )
                    return
                if note.full_text_message_ids:
                    await callback.answer("Этот блок уже был отправлен выше 👆")
                    return
                await callback.answer("Открываю...")
                sent_messages = await send_text_chunks(
                    callback.message,
                    note.transcript,
                    title="📄 Полный текст",
                )
                note.full_text_message_ids = join_message_ids(sent_messages)
                session.commit()
            elif action == "details":
                details_text = format_details(
                    note.summary,
                    parse_stored_tasks(note.action_items),
                    note.details,
                    split_stored_list(note.important_points),
                )
                if not note.summary and not note.details and not note.important_points:
                    await callback.answer(
                        "Не нашёл сохранённый результат. Попробуйте отправить голосовое ещё раз.",
                        show_alert=True,
                    )
                    return
                if note.details_message_ids:
                    await callback.answer("Этот блок уже был отправлен выше 👆")
                    return
                await callback.answer("Открываю...")
                sent_messages = await send_html_chunks(callback.message, details_text)
                note.details_message_ids = join_message_ids(sent_messages)
                session.commit()
            elif action == "tasks":
                if note.tasks_message_ids:
                    await callback.answer("Этот блок уже был отправлен выше 👆")
                    return
                await callback.answer("Открываю...")
                sent_messages = await send_html_chunks(
                    callback.message,
                    format_tasks(parse_stored_tasks(note.action_items)),
                )
                note.tasks_message_ids = join_message_ids(sent_messages)
                session.commit()
            elif action == "share":
                track_event(
                    session_factory,
                    "share_clicked",
                    callback.from_user,
                    {"transcription_id": note.id, "source": "fresh"},
                    settings=settings,
                )
                if note.share_message_ids:
                    await callback.answer("Блок для пересылки уже был отправлен выше 👆")
                    return
                await callback.answer("Открываю...")
                sent_messages = await send_html_chunks(
                    callback.message,
                    format_share(
                        note.summary,
                        parse_stored_tasks(note.action_items),
                        parse_voice_analysis_json(
                            note.voice_analysis_json,
                            note.duration_seconds,
                        ),
                    )
                )
                note.share_message_ids = join_message_ids(sent_messages)
                session.commit()
            elif action == "analysis":
                if note.analysis_message_ids:
                    await callback.answer("Этот блок уже был отправлен выше 👆")
                    return
                await callback.answer("Открываю...")
                user_settings = session.scalar(
                    select(UserSettings).where(UserSettings.telegram_user_id == callback.from_user.id)
                )
                total_saved_seconds = (
                    user_settings.total_saved_seconds if user_settings is not None else 0
                )
                sent_messages = await send_html_chunks(
                    callback.message,
                    format_voice_analysis(
                        parse_voice_analysis_json(
                            note.voice_analysis_json,
                            note.duration_seconds,
                        ),
                        total_saved_seconds or 0,
                    ),
                )
                note.analysis_message_ids = join_message_ids(sent_messages)
                session.commit()
            else:
                await callback.answer("Неизвестное действие", show_alert=True)
    finally:
        BUTTON_LOCKS.discard(lock_key)


@router.callback_query(F.data.startswith("history_"))
async def history_note_callback(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or callback.data is None:
        return

    parsed = parse_note_action(callback.data)
    if parsed is None:
        await callback.answer("Неизвестное действие", show_alert=True)
        return
    action, note_id_text = parsed
    try:
        note_id = int(note_id_text)
    except ValueError:
        await callback.answer("Запись не найдена. Возможно, она была удалена.", show_alert=True)
        return
    if action not in {"full_text", "tasks", "details", "share", "analysis"}:
        await callback.answer("Неизвестное действие", show_alert=True)
        return

    if not isinstance(callback.message, Message):
        await callback.answer("Не удалось отправить ответ", show_alert=True)
        return

    with session_factory() as session:
        note = session.get(VoiceNote, note_id)
        if note is None:
            await callback.answer("Запись не найдена. Возможно, она была удалена.", show_alert=True)
            return
        if note.telegram_user_id != callback.from_user.id:
            await callback.answer("Эта запись недоступна.", show_alert=True)
            return
        if action == "full_text" and not note.transcript:
            await callback.answer("Запись не найдена. Возможно, она была удалена.", show_alert=True)
            return

        await callback.answer("Открываю...")
        if action == "full_text":
            await send_text_chunks(
                callback.message,
                note.transcript,
                title="📄 Полный текст",
            )
        elif action == "tasks":
            await send_html_chunks(
                callback.message,
                format_tasks(parse_stored_tasks(note.action_items)),
            )
        elif action == "details":
            await send_html_chunks(
                callback.message,
                format_details(
                    note.summary,
                    parse_stored_tasks(note.action_items),
                    note.details,
                    split_stored_list(note.important_points),
                ),
            )
        elif action == "share":
            track_event(
                session_factory,
                "share_clicked",
                callback.from_user,
                {"transcription_id": note.id, "source": "history"},
                settings=settings,
            )
            await send_html_chunks(
                callback.message,
                format_share(
                    note.summary,
                    parse_stored_tasks(note.action_items),
                    parse_voice_analysis_json(
                        note.voice_analysis_json,
                        note.duration_seconds,
                    ),
                ),
            )
        elif action == "analysis":
            user_settings = session.scalar(
                select(UserSettings).where(UserSettings.telegram_user_id == callback.from_user.id)
            )
            await send_html_chunks(
                callback.message,
                format_voice_analysis(
                    parse_voice_analysis_json(
                        note.voice_analysis_json,
                        note.duration_seconds,
                    ),
                    (user_settings.total_saved_seconds if user_settings is not None else 0) or 0,
                ),
            )
