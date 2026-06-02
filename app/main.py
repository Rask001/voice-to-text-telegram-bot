import asyncio
import logging
from contextlib import suppress
from urllib.parse import urlsplit, urlunsplit

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from app.config import get_settings
from app.db import create_session_factory
from app.handlers import router
from app.ai_clients.deepseek_client import DeepSeekClient
from app.ai_clients.openai_client import OpenAITranscriptionClient
from app.reminder_scheduler import run_reminder_scheduler
from app.runtime_state import mark_reminder_scheduler_started
from app.text_analysis_service import TextAnalysisService
from app.transcription_service import TranscriptionService


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    settings = get_settings()
    _log_startup_settings(settings)
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp["settings"] = settings
    session_factory = create_session_factory(settings)
    dp["session_factory"] = session_factory
    dp["transcription_service"] = TranscriptionService(
        OpenAITranscriptionClient(settings)
    )
    dp["text_analysis_service"] = TextAnalysisService(DeepSeekClient(settings))

    dp.include_router(router)
    mark_reminder_scheduler_started()
    reminder_task = asyncio.create_task(
        run_reminder_scheduler(bot, session_factory, settings)
    )
    try:
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()
        with suppress(asyncio.CancelledError):
            await reminder_task


def _log_startup_settings(settings) -> None:
    token_suffix = settings.telegram_bot_token[-4:] if settings.telegram_bot_token else "none"
    if settings.app_env == "local":
        logging.info("Running in LOCAL TEST mode")
    elif settings.app_env == "production":
        logging.info("Running in PRODUCTION mode")
    else:
        logging.info("Running in %s mode", settings.app_env.upper())

    logging.info("ENV_FILE=%s", settings.env_file)
    logging.info("DATABASE_URL=%s", _safe_database_url(settings.database_url))
    logging.info("TELEGRAM_BOT_TOKEN suffix=****%s", token_suffix)


def _safe_database_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if not parsed.username and not parsed.password:
        return database_url

    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    netloc = f"***:***@{host}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


if __name__ == "__main__":
    asyncio.run(main())
