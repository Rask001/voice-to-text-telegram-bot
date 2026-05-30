import asyncio
from datetime import date, datetime, timedelta
from html import escape
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from openai import OpenAIError, RateLimitError
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker, Session

from app.access import add_unlimited_user, get_access_status, is_owner
from app.config import Settings
from app.limits import increment_voice_usage
from app.models import VoiceNote
from app.openai_service import OpenAIInsufficientQuotaError, OpenAIService
from app.preferences import get_response_mode, normalize_response_mode, set_response_mode


router = Router()
logger = logging.getLogger(__name__)
TELEGRAM_TEXT_LIMIT = 3900
MODE_LABELS = {
    "short": "Краткий ответ",
    "full": "Полный ответ",
    "tasks": "Только задачи",
}
BUTTON_LOCKS: set[str] = set()
MENU_NEW_VOICE = "🎙 Новое голосовое"
MENU_PROFILE = "👤 Профиль"
MENU_HISTORY = "📚 История"
MENU_SETTINGS = "⚙️ Настройки"
MENU_HELP = "❓ Помощь"


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Привет! Я <b>Voice to Text</b> — бот, который превращает голосовые "
        "в нормальный текст.\n\n"
        "Что умею:\n"
        "🎙 Расшифровываю голосовые\n"
        "🧠 Делаю краткое содержание\n"
        "✅ Выделяю задачи\n"
        "📌 Нахожу важные пункты\n"
        "📄 Показываю полный текст отдельно\n\n"
        "Как пользоваться:\n"
        "1. Просто отправь мне голосовое.\n"
        "2. Я сам расшифрую его.\n"
        "3. Верну короткий результат.\n"
        "4. Полный текст можно открыть кнопкой.\n\n"
        "Бесплатно доступно: 3 голосовых сообщения в день.\n\n"
        "Отправь голосовое — и погнали.",
        reply_markup=_main_keyboard(),
    )


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
            await callback.message.answer(
                _format_profile(
                    callback.from_user.id,
                    callback.from_user.full_name,
                    callback.from_user.username,
                    settings,
                    session_factory,
                ),
                reply_markup=_main_keyboard(),
            )
    elif action == "help":
        await callback.answer("Открываю помощь...")
        if isinstance(callback.message, Message):
            await callback.message.answer(_help_text(), reply_markup=_main_keyboard())


@router.message(Command("health"))
async def health(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    checks = [
        ("bot", True, "polling is running"),
        ("database", *_check_database(session_factory)),
        ("ffmpeg", *_check_ffmpeg()),
        ("openai_api_key", bool(settings.openai_api_key), "configured"),
    ]

    lines = ["<b>Health</b>"]
    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        lines.append(f"{status} {name}: {escape(detail)}")

    await message.answer("\n".join(lines))


@router.message(Command("settings"))
async def settings_command(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return

    with session_factory() as session:
        mode = get_response_mode(
            session,
            message.from_user.id,
            settings.default_response_mode,
        )

    await message.answer(
        _format_settings(mode),
        reply_markup=_settings_keyboard(mode),
    )


@router.message(Command("profile"))
async def profile(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return

    await message.answer(
        _format_profile(
            message.from_user.id,
            message.from_user.full_name,
            message.from_user.username,
            settings,
            session_factory,
        ),
        reply_markup=_main_keyboard(),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(_help_text(), reply_markup=_main_keyboard())


@router.message(Command("history"))
async def history_command(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    await _send_history(message, message.from_user.id, session_factory)


@router.message(Command("admin_add_unlimited"))
async def admin_add_unlimited(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return

    if not is_owner(message.from_user.id, message.from_user.username, settings):
        await message.answer("Команда доступна только владельцу.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /admin_add_unlimited <telegram_id>")
        return

    telegram_user_id = int(parts[1])
    with session_factory() as session:
        add_unlimited_user(session, telegram_user_id)
        session.commit()

    await message.answer(f"Пользователь {telegram_user_id} добавлен в авторский безлимит.")


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
            _format_settings(selected_mode),
            reply_markup=_settings_keyboard(selected_mode),
        )
    await callback.answer("Настройки сохранены")


@router.message(F.voice)
async def handle_voice(
    message: Message,
    bot: Bot,
    settings: Settings,
    session_factory: sessionmaker[Session],
    openai_service: OpenAIService,
) -> None:
    if message.from_user is None or message.voice is None:
        return

    user_id = message.from_user.id
    status = await message.answer("🎧 Голосовое получил. Проверяю лимиты...")

    if message.voice.duration > settings.max_voice_seconds:
        await _safe_edit(
            status,
            f"Голосовое слишком длинное. Сейчас лимит: {settings.max_voice_seconds // 60} мин."
        )
        return

    with session_factory() as session:
        access_status = get_access_status(
            session,
            user_id,
            message.from_user.username,
            settings,
        )
        if not access_status.can_process:
            await _safe_edit(
                status,
                "Бесплатный лимит закончился. Завтра снова будут бесплатные "
                "расшифровки. Скоро добавим оплату."
            )
            return
        session.commit()

    raw_audio_path: Path | None = None
    mp3_audio_path: Path | None = None

    try:
        status = await _safe_edit(status, "📥 Скачиваю аудио...")
        raw_audio_path = await _download_voice(bot, message.voice.file_id)
        mp3_audio_path = await asyncio.to_thread(_convert_to_mp3, raw_audio_path)
        status = await _safe_edit(status, "🎙 Расшифровываю речь...")

        transcript = await asyncio.to_thread(openai_service.transcribe, mp3_audio_path)
        if not transcript:
            await _safe_edit(status, "Не получилось получить текст из голосового.")
            return

        status = await _safe_edit(status, "🧠 Делаю краткое содержание и задачи...")
        analysis = await asyncio.to_thread(openai_service.analyze, transcript)

        with session_factory() as session:
            increment_voice_usage(session, user_id)
            response_mode = get_response_mode(
                session,
                user_id,
                settings.default_response_mode,
            )
            note = VoiceNote(
                telegram_user_id=user_id,
                telegram_file_id=message.voice.file_id,
                title=_clean_title(str(analysis.get("title", "")), note_date=date.today()),
                duration_seconds=message.voice.duration,
                transcript=transcript,
                summary=str(analysis["summary"]),
                action_items="\n".join(analysis["action_items"]),
                details=str(analysis.get("details", "")),
                important_points="\n".join(analysis["important_points"]),
            )
            session.add(note)
            session.flush()
            note_id = note.id
            session.commit()

        status = await _safe_edit(status, "✅ Готово, сейчас появится.")
        result_message = await message.answer(
            _format_response(response_mode, transcript, analysis),
            reply_markup=_note_keyboard(note_id),
        )
        with session_factory() as session:
            note = session.get(VoiceNote, note_id)
            if note is not None:
                note.result_message_id = result_message.message_id
                session.commit()
        if response_mode == "full":
            sent_messages = await _send_text_chunks(
                result_message,
                transcript,
                title="📄 Полный текст",
            )
            with session_factory() as session:
                note = session.get(VoiceNote, note_id)
                if note is not None:
                    note.full_text_message_ids = _join_message_ids(sent_messages)
                    session.commit()

    except OpenAIInsufficientQuotaError:
        await _safe_edit(
            status,
            "Сейчас обработка временно недоступна: закончилась API-квота. "
            "Попробуйте позже."
        )
        logger.exception("OpenAI insufficient quota")
    except RateLimitError:
        await _safe_edit(
            status,
            "OpenAI временно ограничил запросы. Попробуйте ещё раз чуть позже."
        )
        logger.exception("OpenAI rate limit after retries")
    except OpenAIError:
        await _safe_edit(
            status,
            "OpenAI не смог обработать запрос. Проверь API key, модель и логи приложения."
        )
        logger.exception("OpenAI API error")
    except RuntimeError as exc:
        await _safe_edit(status, str(exc))
        logger.exception("Runtime error while processing voice")
    except Exception:
        await _safe_edit(status, "Не удалось обработать голосовое. Проверь логи приложения.")
        logger.exception("Voice processing failed")
    finally:
        for path in (raw_audio_path, mp3_audio_path):
            if path and path.exists():
                path.unlink(missing_ok=True)


@router.callback_query(F.data.startswith("note:"))
async def note_callback(
    callback: CallbackQuery,
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
        _, action, note_id_text = callback.data.split(":", 2)
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

            if action == "transcript":
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
                sent_messages = await _send_text_chunks(
                    callback.message,
                    note.transcript,
                    title="📄 Полный текст",
                )
                note.full_text_message_ids = _join_message_ids(sent_messages)
                session.commit()
            elif action == "details":
                details_text = _format_details(
                    note.summary,
                    _split_stored_list(note.action_items),
                    note.details,
                    _split_stored_list(note.important_points),
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
                sent = await callback.message.answer(_trim_html(details_text))
                note.details_message_ids = str(sent.message_id)
                session.commit()
            elif action == "tasks":
                action_items = _split_stored_list(note.action_items)
                if note.tasks_message_ids:
                    await callback.answer("Этот блок уже был отправлен выше 👆")
                    return
                await callback.answer("Открываю...")
                sent = await callback.message.answer(_format_tasks(action_items))
                note.tasks_message_ids = str(sent.message_id)
                session.commit()
            elif action == "share":
                if note.share_message_ids:
                    await callback.answer("Блок для пересылки уже был отправлен выше 👆")
                    return
                await callback.answer("Открываю...")
                sent = await callback.message.answer(
                    _format_share(
                        note.summary,
                        _split_stored_list(note.action_items),
                    )
                )
                note.share_message_ids = str(sent.message_id)
                session.commit()
            else:
                await callback.answer("Неизвестное действие", show_alert=True)
    finally:
        BUTTON_LOCKS.discard(lock_key)


@router.callback_query(F.data.startswith("history:"))
async def history_callback(
    callback: CallbackQuery,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or callback.data is None:
        return

    await callback.answer("Открываю...")
    try:
        note_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Не нашёл сохранённый результат. Попробуйте отправить голосовое ещё раз.", show_alert=True)
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

        text = _format_history_item(note)
        keyboard = _note_keyboard(note.id)

    if isinstance(callback.message, Message):
        await callback.message.answer(text, reply_markup=keyboard)


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
            access_status = get_access_status(
                session,
                message.from_user.id,
                message.from_user.username,
                settings,
            )
            session.commit()

        if not access_status.can_process:
            await message.answer(
                "❌ Ваш лимит закончился.\n\n"
                "Чтобы продолжить пользоваться ботом, оформите подписку.\n\n"
                "Скоро здесь появится оплата через Telegram Stars ⭐",
                reply_markup=_main_keyboard(),
            )
            return

        await message.answer(
            "Отправь мне голосовое сообщение 🎙\n\n"
            "Я расшифрую его, сделаю краткое содержание и выделю задачи.",
            reply_markup=_main_keyboard(),
        )
    elif message.text == MENU_PROFILE and message.from_user is not None:
        await message.answer(
            _format_profile(
                message.from_user.id,
                message.from_user.full_name,
                message.from_user.username,
                settings,
                session_factory,
            ),
            reply_markup=_main_keyboard(),
        )
    elif message.text == MENU_HISTORY and message.from_user is not None:
        await _send_history(message, message.from_user.id, session_factory)
    elif message.text == MENU_SETTINGS:
        await settings_command(message, settings, session_factory)
    elif message.text == MENU_HELP:
        await message.answer(_help_text(), reply_markup=_main_keyboard())


@router.message(F.text)
async def text_fallback(message: Message) -> None:
    await message.answer(
        "Я пока работаю с голосовыми сообщениями 🎙\n\n"
        "Отправь voice message — я расшифрую его, сделаю краткое содержание "
        "и выделю задачи.",
        reply_markup=_main_keyboard(),
    )


@router.message(F.photo | F.document | F.video | F.video_note | F.audio)
async def unsupported_media(message: Message) -> None:
    await message.answer(
        "Пока я работаю только с обычными голосовыми сообщениями 🎙\n\n"
        "Фото, файлы, кружки и аудиофайлы добавим позже.",
        reply_markup=_main_keyboard(),
    )


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(
        "Пока я работаю только с обычными голосовыми сообщениями 🎙\n\n"
        "Отправь voice message — я расшифрую его, сделаю краткое содержание "
        "и выделю задачи.",
        reply_markup=_main_keyboard(),
    )


async def _download_voice(bot: Bot, file_id: str) -> Path:
    file = await bot.get_file(file_id)
    suffix = Path(file.file_path or "voice.ogg").suffix or ".ogg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = Path(tmp.name)
    tmp.close()

    await bot.download_file(file.file_path, destination=tmp_path)
    return tmp_path


def _convert_to_mp3(source_path: Path) -> Path:
    ffmpeg_path = _find_ffmpeg()
    target_path = source_path.with_suffix(".mp3")
    subprocess.run(
        [
            ffmpeg_path,
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-b:a",
            "64k",
            str(target_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return target_path


def _find_ffmpeg() -> str:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    homebrew_ffmpeg = Path("/opt/homebrew/bin/ffmpeg")
    if homebrew_ffmpeg.exists():
        return str(homebrew_ffmpeg)

    raise RuntimeError("ffmpeg is not installed or not available in PATH")


async def _safe_edit(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    try:
        return await message.edit_text(text, reply_markup=reply_markup)
    except TelegramAPIError:
        logger.exception("Failed to edit status message, sending a new one")
        return await message.answer(text, reply_markup=reply_markup)


def _check_database(session_factory: sessionmaker[Session]) -> tuple[bool, str]:
    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        return True, "available"
    except Exception as exc:
        logger.exception("Database health check failed")
        return False, repr(exc)


def _check_ffmpeg() -> tuple[bool, str]:
    try:
        return True, _find_ffmpeg()
    except RuntimeError as exc:
        return False, str(exc)


def _format_response(
    mode: str,
    transcript: str,
    analysis: dict[str, list[str] | str],
) -> str:
    normalized_mode = normalize_response_mode(mode)
    action_items = _analysis_list(analysis["action_items"])
    important_points = _analysis_list(analysis["important_points"])
    summary = str(analysis["summary"])
    details = str(analysis.get("details", ""))

    if normalized_mode == "tasks":
        return _format_tasks(action_items)

    if normalized_mode == "full":
        return _trim_html(_format_details(summary, action_items, details, important_points))

    return _trim_html(_format_short(summary, action_items))


def _format_short(summary: str, action_items: list[str]) -> str:
    return "\n\n".join(
        [
            "🧠 <b>Кратко:</b>\n" + escape(_trim_plain(summary, limit=450)),
            _format_tasks(action_items),
        ]
    )


def _format_details(
    summary: str,
    action_items: list[str],
    details: str,
    important_points: list[str],
) -> str:
    details_block = escape(_trim_plain(details, limit=1000)) if details else _format_list(important_points)
    return "\n\n".join(
        [
            "🧠 <b>Кратко:</b>\n" + escape(_trim_plain(summary, limit=700)),
            _format_tasks(action_items),
            "💡 <b>Подробнее:</b>\n" + details_block,
        ]
    )


def _format_tasks(action_items: list[str]) -> str:
    return "✅ <b>Задачи:</b>\n" + _format_numbered_list(action_items)


def _format_share(summary: str, action_items: list[str]) -> str:
    parts = [
        "📝 <b>Расшифровка голосового</b>",
        "",
        "🧠 <b>Кратко:</b>",
        escape(_trim_plain(summary, limit=700)) or "Нет краткого содержания.",
    ]
    if action_items:
        parts.extend(["", _format_tasks(action_items)])
    parts.extend(["", "🎙Создано через: @voitext_bot"])
    return _trim_html("\n".join(parts))


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
            "Истории пока нет. Отправь первое голосовое — и я сохраню результат здесь.",
            reply_markup=_main_keyboard(),
        )
        return

    await message.answer(
        _format_history(notes),
        reply_markup=_history_keyboard(notes),
    )


def _format_history(notes: list[VoiceNote]) -> str:
    lines = ["📚 <b>История</b>"]
    for index, note in enumerate(notes, start=1):
        lines.extend(
            [
                "",
                f"{index}. <b>{escape(_note_title(note))}</b> — {_format_note_date(note.created_at)}",
                "   " + escape(_trim_plain(note.summary or "Без краткого содержания.", limit=140)),
            ]
        )
    return "\n".join(lines)


def _history_keyboard(notes: list[VoiceNote]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"{index}️⃣", callback_data=f"history:{note.id}")
        for index, note in enumerate(notes, start=1)
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def _format_history_item(note: VoiceNote) -> str:
    action_items = _split_stored_list(note.action_items)
    return "\n\n".join(
        [
            f"📌 <b>{escape(_note_title(note))}</b>",
            f"Дата: <b>{_format_note_date(note.created_at)}</b>",
            "🧠 <b>Кратко:</b>\n" + escape(_trim_plain(note.summary or "", limit=700)),
            _format_tasks(action_items),
        ]
    )


def _note_title(note: VoiceNote) -> str:
    if note.title:
        return note.title
    return _fallback_title(note.created_at.date() if note.created_at else date.today())


def _main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_NEW_VOICE)],
            [KeyboardButton(text=MENU_PROFILE), KeyboardButton(text=MENU_HISTORY)],
            [KeyboardButton(text=MENU_SETTINGS), KeyboardButton(text=MENU_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def _format_legacy_result(transcript: str, analysis: dict[str, list[str] | str]) -> str:
    action_items = analysis["action_items"]
    important_points = analysis["important_points"]

    parts = [
        "<b>Краткое содержание</b>",
        escape(_trim_plain(str(analysis["summary"]), limit=1000)) or "Нет содержания.",
        "",
        "<b>Задачи</b>",
        _format_list(action_items),
        "",
        "<b>Важные пункты</b>",
        _format_list(important_points),
        "",
        "<b>Расшифровка</b>",
        _trim(transcript, limit=1500),
    ]
    rendered = "\n".join(parts)
    if len(rendered) <= TELEGRAM_TEXT_LIMIT:
        return rendered

    return rendered[: TELEGRAM_TEXT_LIMIT - 10].rstrip() + "\n..."


def _note_keyboard(note_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📄 Полный текст",
                    callback_data=f"note:transcript:{note_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧠 Подробнее",
                    callback_data=f"note:details:{note_id}",
                ),
                InlineKeyboardButton(
                    text="✅ Только задачи",
                    callback_data=f"note:tasks:{note_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📤 Поделиться",
                    callback_data=f"note:share:{note_id}",
                )
            ],
        ]
    )


def _settings_keyboard(selected_mode: str) -> InlineKeyboardMarkup:
    keyboard = []
    for mode, label in MODE_LABELS.items():
        prefix = "• " if mode == selected_mode else ""
        keyboard.append(
            [InlineKeyboardButton(text=prefix + label, callback_data=f"settings:{mode}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _format_settings(mode: str) -> str:
    return (
        "<b>Настройки ответа</b>\n\n"
        f"Текущий режим: <b>{escape(MODE_LABELS[normalize_response_mode(mode)])}</b>\n\n"
        "Выберите формат ответа после голосового:"
    )


def _format_profile(
    user_id: int,
    full_name: str,
    username: str | None,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> str:
    with session_factory() as session:
        access_status = get_access_status(session, user_id, username, settings)
        session.commit()

    remaining = "∞" if access_status.remaining_today is None else str(access_status.remaining_today)
    total_limit = "∞" if access_status.is_unlimited else str(access_status.daily_limit)
    username_text = f"@{username}" if username else "не указан"
    reset_text = f"{access_status.reset_date.isoformat()} 00:00"
    return (
        "👤 <b>Профиль</b>\n\n"
        f"Имя: <b>{escape(full_name)}</b>\n"
        f"Username: <b>{escape(username_text)}</b>\n\n"
        f"Тариф:\n<b>{escape(access_status.tariff)}</b>\n\n"
        f"Использовано сегодня:\n<b>{access_status.used_today}</b>\n\n"
        f"Осталось сегодня:\n<b>{remaining}</b>\n\n"
        f"Дневной лимит:\n<b>{total_limit}</b>\n\n"
        f"Сброс лимита:\n<b>{reset_text}</b>"
    )


def _help_text() -> str:
    return (
        "❓ <b>Помощь</b>\n\n"
        "Я работаю только с обычными voice messages 🎙\n"
        "Текст, фото, файлы, кружки и аудиофайлы пока не обрабатываю.\n\n"
        "История обработок: /history или кнопка 📚 История.\n"
        "Профиль и лимиты: /profile или кнопка 👤 Профиль.\n"
        "📤 Поделиться создаёт отдельный блок, который удобно переслать вручную."
    )


def _format_list(items: list[str] | str) -> str:
    if not isinstance(items, list) or not items:
        return "Нет."
    visible_items = items[:5]
    rendered = "\n".join(
        f"- {escape(_trim_plain(item, limit=250))}" for item in visible_items
    )
    if len(items) > len(visible_items):
        rendered += f"\n...ещё {len(items) - len(visible_items)}"
    return rendered


def _format_numbered_list(items: list[str]) -> str:
    if not items:
        return "Нет задач."
    visible_items = items[:5]
    rendered = "\n".join(
        f"{index}. {escape(_trim_plain(item, limit=220))}"
        for index, item in enumerate(visible_items, start=1)
    )
    if len(items) > len(visible_items):
        rendered += f"\n...ещё {len(items) - len(visible_items)}"
    return rendered


def _analysis_list(value: list[str] | str) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if item]
    return _split_stored_list(value)


def _split_stored_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [line.strip() for line in value.splitlines() if line.strip()]


def _clean_title(title: str, note_date: date) -> str:
    cleaned = " ".join(title.replace("\n", " ").split()).strip("\"'“”«». ")
    if not cleaned:
        return _fallback_title(note_date)

    words = cleaned.split()
    if len(words) > 5:
        cleaned = " ".join(words[:5])
    return cleaned or _fallback_title(note_date)


def _fallback_title(note_date: date) -> str:
    return f"Голосовое от {note_date.strftime('%d.%m')}"


def _format_note_date(value: datetime | None) -> str:
    if value is None:
        return ""
    today = date.today()
    note_date = value.date()
    if note_date == today:
        return "сегодня"
    if note_date == today - timedelta(days=1):
        return "вчера"
    return note_date.strftime("%d.%m.%Y")


async def _send_text_chunks(
    message: Message,
    text: str,
    title: str | None = None,
) -> list[Message]:
    chunks = _split_for_telegram(text, reserved_chars=120 if title else 0)
    sent_messages = []
    for index, chunk in enumerate(chunks):
        if title:
            prefix = f"<b>{escape(title)}</b>"
            if len(chunks) > 1:
                prefix += f" {index + 1}/{len(chunks)}"
            chunk = prefix + "\n\n" + chunk
        sent_messages.append(await message.answer(chunk))
    return sent_messages


def _join_message_ids(messages: list[Message]) -> str:
    return ",".join(str(message.message_id) for message in messages)


def _split_for_telegram(text: str, reserved_chars: int = 0) -> list[str]:
    limit = TELEGRAM_TEXT_LIMIT - reserved_chars
    escaped_text = escape(text)
    if len(escaped_text) <= limit:
        return [escaped_text]

    chunks = []
    current = ""
    for line in escaped_text.splitlines(keepends=True):
        if len(line) > limit:
            if current:
                chunks.append(current.rstrip())
                current = ""
            for start in range(0, len(line), limit):
                chunks.append(line[start : start + limit].rstrip())
            continue

        if len(current) + len(line) > limit:
            chunks.append(current.rstrip())
            current = line
        else:
            current += line

    if current:
        chunks.append(current.rstrip())
    return chunks


def _trim_html(text: str) -> str:
    if len(text) <= TELEGRAM_TEXT_LIMIT:
        return text
    return text[: TELEGRAM_TEXT_LIMIT - 10].rstrip() + "\n..."


def _trim(text: str, limit: int) -> str:
    return escape(_trim_plain(text, limit=limit))


def _trim_plain(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n..."
