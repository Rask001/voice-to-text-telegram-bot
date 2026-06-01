import logging
import shutil
import subprocess
import tempfile
from datetime import date
from html import escape
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup, Message

from app.formatters import TELEGRAM_TEXT_LIMIT, fallback_title


logger = logging.getLogger(__name__)


async def download_voice(bot: Bot, file_id: str) -> Path:
    file = await bot.get_file(file_id)
    suffix = Path(file.file_path or "voice.ogg").suffix or ".ogg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = Path(tmp.name)
    tmp.close()

    await bot.download_file(file.file_path, destination=tmp_path)
    return tmp_path


def convert_to_mp3(source_path: Path) -> Path:
    ffmpeg_path = find_ffmpeg()
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


def find_ffmpeg() -> str:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    homebrew_ffmpeg = Path("/opt/homebrew/bin/ffmpeg")
    if homebrew_ffmpeg.exists():
        return str(homebrew_ffmpeg)
    intel_homebrew_ffmpeg = Path("/usr/local/bin/ffmpeg")
    if intel_homebrew_ffmpeg.exists():
        return str(intel_homebrew_ffmpeg)

    raise RuntimeError("ffmpeg is not installed or not available in PATH")


async def safe_edit(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    try:
        return await message.edit_text(text, reply_markup=reply_markup)
    except TelegramAPIError:
        logger.exception("Failed to edit status message, sending a new one")
        return await message.answer(text, reply_markup=reply_markup)


def clean_title(title: str, note_date: date) -> str:
    cleaned = " ".join(title.replace("\n", " ").split()).strip("\"'“”«». ")
    if not cleaned:
        return fallback_title(note_date)

    words = cleaned.split()
    if len(words) > 5:
        cleaned = " ".join(words[:5])
    return cleaned or fallback_title(note_date)


def parse_note_action(callback_data: str) -> tuple[str, str] | None:
    if callback_data.startswith("note:"):
        parts = callback_data.split(":", 2)
        if len(parts) != 3:
            return None
        action = "full_text" if parts[1] == "transcript" else parts[1]
        return action, parts[2]

    if ":" not in callback_data:
        return None
    action_part, note_id_text = callback_data.split(":", 1)
    if "_" not in action_part:
        return None
    _, action = action_part.split("_", 1)
    return action, note_id_text


async def send_html_chunks(
    message: Message,
    html_text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> list[Message]:
    chunks = split_html_for_telegram(html_text)
    sent_messages = []
    for index, chunk in enumerate(chunks):
        sent_messages.append(
            await message.answer(
                chunk,
                reply_markup=reply_markup if index == 0 else None,
            )
        )
    return sent_messages


async def send_text_chunks(
    message: Message,
    text: str,
    title: str | None = None,
) -> list[Message]:
    chunks = split_for_telegram(text, reserved_chars=120 if title else 0)
    sent_messages = []
    for index, chunk in enumerate(chunks):
        if title:
            prefix = f"<b>{escape(title)}</b>"
            if len(chunks) > 1:
                prefix += f" {index + 1}/{len(chunks)}"
            chunk = prefix + "\n\n" + chunk
        sent_messages.append(await message.answer(chunk))
    return sent_messages


def join_message_ids(messages: list[Message]) -> str:
    return ",".join(str(message.message_id) for message in messages)


def split_html_for_telegram(text: str) -> list[str]:
    if len(text) <= TELEGRAM_TEXT_LIMIT:
        return [text]

    chunks = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(line) > TELEGRAM_TEXT_LIMIT:
            if current:
                chunks.append(current.rstrip())
                current = ""
            for start in range(0, len(line), TELEGRAM_TEXT_LIMIT):
                chunks.append(line[start : start + TELEGRAM_TEXT_LIMIT].rstrip())
            continue

        if len(current) + len(line) > TELEGRAM_TEXT_LIMIT:
            chunks.append(current.rstrip())
            current = line
        else:
            current += line

    if current:
        chunks.append(current.rstrip())
    return chunks or [""]


def split_for_telegram(text: str, reserved_chars: int = 0) -> list[str]:
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
