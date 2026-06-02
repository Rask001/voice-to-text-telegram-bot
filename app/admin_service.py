import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import _sync_database_url
from app.models import AnalyticsEvent, AppConfig, Reminder, UserSettings, VoiceNote
from app.preferences import get_or_create_user_settings
from app import runtime_state
from app.tariffs import BROTHER, FREE, OWNER, PREMIUM, STANDARD, get_tariff, normalize_tariff_code


ADMIN_ONLY_MESSAGE = "Команда доступна только владельцу бота."
START_TEXT_KEY = "start_text"
MAX_START_TEXT_LENGTH = 3500
DEFAULT_START_TEXT = (
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
    "Отправь голосовое — и погнали."
)

TARIFF_ALIASES = {
    "friend": BROTHER,
    "bro": BROTHER,
}


@dataclass(frozen=True)
class AdminUserInfo:
    telegram_id: int
    username: str
    name: str
    tariff_type: str
    tariff_label: str
    registration_date: datetime | None
    used_today: int
    minutes_used_total: int
    minutes_used_this_month: int
    active_reminders: int
    transcriptions_count: int
    last_activity: datetime | None


def get_start_text(session: Session) -> str:
    config = session.get(AppConfig, START_TEXT_KEY)
    if config is None or not config.value.strip():
        return DEFAULT_START_TEXT
    return config.value


def validate_start_text(text_value: str) -> str | None:
    if not text_value.strip():
        return "Стартовый текст не должен быть пустым."
    if len(text_value) > MAX_START_TEXT_LENGTH:
        return f"Текст слишком длинный. Максимум: {MAX_START_TEXT_LENGTH} символов."
    return None


def set_start_text(session: Session, text_value: str) -> None:
    error = validate_start_text(text_value)
    if error is not None:
        raise ValueError(error)
    config = session.get(AppConfig, START_TEXT_KEY)
    if config is None:
        config = AppConfig(key=START_TEXT_KEY, value=text_value, updated_at=datetime.now())
        session.add(config)
    else:
        config.value = text_value
        config.updated_at = datetime.now()


def reset_start_text(session: Session) -> None:
    config = session.get(AppConfig, START_TEXT_KEY)
    if config is None:
        return
    session.delete(config)


def normalize_admin_tariff(tariff: str) -> str | None:
    raw = tariff.strip().lower()
    if raw in TARIFF_ALIASES:
        return TARIFF_ALIASES[raw]
    normalized = normalize_tariff_code(raw, default=None)
    return normalized if normalized in {FREE, STANDARD, PREMIUM, BROTHER, OWNER} else None


def set_user_tariff(session: Session, telegram_id: int, tariff_type: str) -> UserSettings:
    normalized = normalize_admin_tariff(tariff_type)
    if normalized is None:
        raise ValueError("Неизвестный тариф. Доступно: free, standard, premium, friend, owner.")

    settings = get_or_create_user_settings(session, telegram_id)
    settings.tariff_type = normalized
    settings.is_unlimited = normalized in {BROTHER, OWNER}
    settings.is_premium = normalized == PREMIUM
    plan = get_tariff(normalized)
    settings.daily_voice_limit = plan.daily_voice_limit or 0
    settings.minutes_limit_month = plan.minutes_limit_month or 0
    settings.minutes_limit_total = plan.minutes_limit_total or 0
    if settings.registration_date is None:
        settings.registration_date = datetime.now()
    if normalized == FREE and settings.trial_expires_at is None:
        settings.trial_expires_at = settings.registration_date + timedelta(days=3)
    session.flush()
    return settings


def add_friend_tariff(session: Session, telegram_id: int) -> UserSettings:
    return set_user_tariff(session, telegram_id, BROTHER)


def remove_friend_tariff(session: Session, telegram_id: int) -> UserSettings:
    settings = get_or_create_user_settings(session, telegram_id)
    if settings.tariff_type == BROTHER or settings.is_unlimited:
        settings.is_unlimited = False
        return set_user_tariff(session, telegram_id, FREE)
    return settings


def get_admin_user_info(session: Session, telegram_id: int) -> AdminUserInfo:
    user_settings = get_or_create_user_settings(session, telegram_id)
    plan = get_tariff(user_settings.tariff_type)
    active_reminders = _count(
        session,
        select(func.count())
        .select_from(Reminder)
        .where(
            Reminder.telegram_id == telegram_id,
            Reminder.status.in_(["pending", "sending"]),
        ),
    )
    transcriptions_count = _count(
        session,
        select(func.count()).select_from(VoiceNote).where(VoiceNote.telegram_user_id == telegram_id),
    )
    last_activity = _last_activity(session, telegram_id)
    return AdminUserInfo(
        telegram_id=telegram_id,
        username="-",
        name="-",
        tariff_type=plan.code,
        tariff_label=plan.label,
        registration_date=user_settings.registration_date,
        used_today=user_settings.voices_used_today,
        minutes_used_total=user_settings.minutes_used_total,
        minutes_used_this_month=user_settings.minutes_used_this_month,
        active_reminders=active_reminders,
        transcriptions_count=transcriptions_count,
        last_activity=last_activity,
    )


def format_admin_user_info(info: AdminUserInfo) -> str:
    return (
        "👤 <b>Пользователь</b>\n\n"
        f"Telegram ID: <code>{info.telegram_id}</code>\n"
        f"Username: {escape(info.username)}\n"
        f"Имя: {escape(info.name)}\n"
        f"Тариф: <b>{escape(info.tariff_label)}</b> ({escape(info.tariff_type)})\n"
        f"Дата регистрации: {_format_dt(info.registration_date)}\n"
        f"Использовано сегодня: <b>{info.used_today}</b>\n"
        f"Минут всего: <b>{info.minutes_used_total}</b>\n"
        f"Минут в этом месяце: <b>{info.minutes_used_this_month}</b>\n"
        f"Активные напоминания: <b>{info.active_reminders}</b>\n"
        f"Расшифровок: <b>{info.transcriptions_count}</b>\n"
        f"Последняя активность: {_format_dt(info.last_activity)}"
    )


def list_admin_users(session: Session, limit: int = 10, tariff_filter: str | None = None) -> list[UserSettings]:
    limit = max(1, min(limit, 50))
    query = select(UserSettings).order_by(UserSettings.registration_date.desc()).limit(limit)
    if tariff_filter:
        normalized = normalize_admin_tariff(tariff_filter)
        if normalized is None:
            return []
        query = (
            select(UserSettings)
            .where(UserSettings.tariff_type == normalized)
            .order_by(UserSettings.registration_date.desc())
            .limit(limit)
        )
    return list(session.scalars(query))


def format_admin_users(users: list[UserSettings]) -> str:
    if not users:
        return "Пользователи не найдены."
    lines = ["👥 <b>Последние пользователи</b>"]
    for index, user_settings in enumerate(users, start=1):
        last_activity = _format_dt(getattr(user_settings, "_last_activity", None))
        username = getattr(user_settings, "_username", "-")
        lines.append(
            "\n"
            f"{index}. <code>{user_settings.telegram_user_id}</code>\n"
            f"Username: {escape(str(username or '-'))}\n"
            f"Тариф: <b>{escape(user_settings.tariff_type)}</b>\n"
            f"Регистрация: {_format_dt(user_settings.registration_date)}\n"
            f"Последняя активность: {last_activity}"
        )
    return "\n".join(lines)


def enrich_admin_users(session: Session, users: list[UserSettings]) -> list[UserSettings]:
    for user_settings in users:
        setattr(user_settings, "_last_activity", _last_activity(session, user_settings.telegram_user_id))
        setattr(user_settings, "_username", "-")
    return users


def create_database_backup(settings: Settings) -> Path:
    database_url = _sync_database_url(settings.database_url)
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Backup сейчас поддерживает только SQLite.")

    db_path = Path(database_url.removeprefix("sqlite:///"))
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite база не найдена: {db_path}")

    backups_dir = Path("backups")
    backups_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backups_dir / f"bot_backup_{datetime.now():%Y-%m-%d_%H-%M-%S}.db"
    shutil.copy2(db_path, backup_path)
    return backup_path


def get_broadcast_user_ids(session: Session) -> list[int]:
    ids = session.scalars(select(UserSettings.telegram_user_id).order_by(UserSettings.id.asc()))
    return [int(value) for value in ids]


def format_admin_health(session_factory: sessionmaker[Session], settings: Settings) -> str:
    db_ok, db_detail = _check_database(session_factory)
    ffmpeg_path = shutil.which("ffmpeg")
    pending, failed = _reminder_counts(session_factory)
    disk = shutil.disk_usage(Path.cwd())
    free_gb = disk.free / (1024**3)

    lines = [
        "🩺 <b>Admin Health</b>",
        "",
        "OK bot: polling is running",
        f"ENV_FILE: <code>{escape(settings.env_file)}</code>",
        f"Mode: <b>{escape(settings.app_env)}</b>",
        f"{'OK' if db_ok else 'FAIL'} SQLite: {escape(db_detail)}",
        f"{'OK' if ffmpeg_path else 'FAIL'} ffmpeg: {escape(ffmpeg_path or 'not found')}",
        f"{'OK' if settings.openai_api_key else 'FAIL'} OpenAI key: configured",
        f"{'OK' if settings.deepseek_api_key else 'FAIL'} DeepSeek key: configured",
        f"{'OK' if runtime_state.REMINDER_SCHEDULER_STARTED else 'FAIL'} scheduler: {'running' if runtime_state.REMINDER_SCHEDULER_STARTED else 'not started'}",
        f"Pending reminders: <b>{pending}</b>",
        f"Failed reminders: <b>{failed}</b>",
        f"Uptime: <b>{_format_uptime(runtime_state.uptime_seconds())}</b>",
        f"Python: <b>{escape(sys.version.split()[0])}</b>",
        f"Free disk: <b>{free_gb:.1f} GB</b>",
    ]
    return "\n".join(lines)


def _count(session: Session, query) -> int:
    value = session.scalar(query)
    return int(value or 0)


def _last_activity(session: Session, telegram_id: int) -> datetime | None:
    analytics_at = session.scalar(
        select(func.max(AnalyticsEvent.created_at)).where(AnalyticsEvent.telegram_id == telegram_id)
    )
    voice_at = session.scalar(
        select(func.max(VoiceNote.created_at)).where(VoiceNote.telegram_user_id == telegram_id)
    )
    candidates = [value for value in [analytics_at, voice_at] if value is not None]
    return max(candidates) if candidates else None


def _check_database(session_factory: sessionmaker[Session]) -> tuple[bool, str]:
    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        return True, "available"
    except Exception as exc:
        return False, repr(exc)


def _reminder_counts(session_factory: sessionmaker[Session]) -> tuple[int, int]:
    try:
        with session_factory() as session:
            pending = _count(
                session,
                select(func.count()).select_from(Reminder).where(Reminder.status == "pending"),
            )
            failed = _count(
                session,
                select(func.count()).select_from(Reminder).where(Reminder.status == "failed"),
            )
            return pending, failed
    except Exception:
        return 0, 0


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "-"
    return escape(value.strftime("%d.%m.%Y %H:%M"))


def _format_uptime(total_seconds: int) -> str:
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days:
        return f"{days}д {hours}ч {minutes}м"
    if hours:
        return f"{hours}ч {minutes}м"
    if minutes:
        return f"{minutes}м {seconds}с"
    return f"{seconds}с"
