from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.handlers.utils import find_ffmpeg, logger


router = Router()


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
        return True, find_ffmpeg()
    except RuntimeError as exc:
        return False, str(exc)
