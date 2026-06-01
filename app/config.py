from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    env_file: str = ".env"
    app_env: str = "production"
    database_url: str = "sqlite:///data/bot.db"
    openai_transcribe_model: str = "gpt-4o-mini-transcribe"
    openai_text_model: str = "gpt-5-mini"
    daily_voice_limit: int = 5
    max_voice_seconds: int = 900
    default_response_mode: str = "short"
    owner_telegram_id: int | None = None
    unlimited_user_ids: tuple[int, ...] = ()


def get_settings() -> Settings:
    env_file = os.getenv("ENV_FILE", ".env").strip() or ".env"
    load_dotenv(dotenv_path=env_file, override=True)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    return Settings(
        telegram_bot_token=token,
        openai_api_key=openai_key,
        env_file=env_file,
        app_env=os.getenv("APP_ENV", _infer_app_env(env_file)).strip().lower(),
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/bot.db"),
        openai_transcribe_model=os.getenv(
            "OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"
        ),
        openai_text_model=os.getenv("OPENAI_TEXT_MODEL", "gpt-5-mini"),
        daily_voice_limit=int(os.getenv("DAILY_VOICE_LIMIT", "5")),
        max_voice_seconds=int(os.getenv("MAX_VOICE_SECONDS", "900")),
        default_response_mode=os.getenv("DEFAULT_RESPONSE_MODE", "short").strip().lower(),
        owner_telegram_id=_parse_optional_int(os.getenv("OWNER_TELEGRAM_ID", "")),
        unlimited_user_ids=_parse_int_list(os.getenv("UNLIMITED_USER_IDS", "")),
    )


def _infer_app_env(env_file: str) -> str:
    env_name = Path(env_file).name.lower()
    if "local" in env_name:
        return "local"
    if "production" in env_name or env_name == ".env":
        return "production"
    return "custom"


def _parse_optional_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    return int(value)


def _parse_int_list(value: str) -> tuple[int, ...]:
    ids = []
    for item in value.split(","):
        item = item.strip()
        if item:
            ids.append(int(item))
    return tuple(ids)
