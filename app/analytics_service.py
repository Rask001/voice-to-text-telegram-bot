import json
import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.access import AccessStatus
from app.access_service import check_user_access
from app.config import Settings
from app.models import AnalyticsEvent


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdminStats:
    start_date: datetime
    end_date: datetime
    new_users: int
    active_users: int
    voice_received: int
    voice_processed_success: int
    voice_processing_failed: int
    voice_limit_blocked: int
    audio_minutes_received: int
    audio_minutes_processed: int
    history_opened: int
    profile_opened: int
    share_clicked: int
    paywall_shown: int
    active_by_tariff: dict[str, int]
    activation_rate: float
    success_rate: float
    limit_block_rate: float
    share_rate: float


def track_event(
    session_factory: sessionmaker[Session],
    event_name: str,
    user: Any,
    payload: dict[str, Any] | None = None,
    settings: Settings | None = None,
    tariff_type: str | None = None,
) -> None:
    """Write analytics without affecting the user-facing scenario."""
    try:
        telegram_id = int(getattr(user, "id", user))
        username = getattr(user, "username", None)
        safe_payload = _sanitize_payload(payload or {})

        with session_factory() as session:
            resolved_tariff = tariff_type or _resolve_tariff_type(
                session,
                telegram_id,
                username,
                settings,
                safe_payload,
            )
            if resolved_tariff and "tariff_type" not in safe_payload:
                safe_payload["tariff_type"] = resolved_tariff
            session.add(
                AnalyticsEvent(
                    event_name=event_name,
                    telegram_id=telegram_id,
                    tariff_type=resolved_tariff,
                    payload_json=json.dumps(safe_payload, ensure_ascii=False),
                )
            )
            session.commit()
    except Exception:
        logger.exception("Failed to write analytics event %s", event_name)


def get_admin_stats(
    session_factory: sessionmaker[Session],
    period: str = "today",
) -> AdminStats:
    start_date, end_date = _period_bounds(period)
    return get_stats_for_period(session_factory, start_date, end_date)


def get_stats_for_period(
    session_factory: sessionmaker[Session],
    start_date: datetime,
    end_date: datetime,
) -> AdminStats:
    with session_factory() as session:
        events = list(
            session.scalars(
                select(AnalyticsEvent).where(
                    AnalyticsEvent.created_at >= start_date,
                    AnalyticsEvent.created_at < end_date,
                )
            )
        )

    return _build_stats(events, start_date, end_date)


def cleanup_old_events(session_factory: sessionmaker[Session], days: int = 90) -> int:
    cutoff = datetime.now() - timedelta(days=days)
    with session_factory() as session:
        result = session.execute(
            delete(AnalyticsEvent).where(AnalyticsEvent.created_at < cutoff)
        )
        session.commit()
        return int(result.rowcount or 0)


def format_admin_stats(stats: AdminStats, title: str) -> str:
    tariff_counts = stats.active_by_tariff
    return (
        f"📊 <b>{title}</b>\n\n"
        f"Новых пользователей: <b>{stats.new_users}</b>\n"
        f"Активных пользователей: <b>{stats.active_users}</b>\n"
        f"Голосовых получено: <b>{stats.voice_received}</b>\n"
        f"Успешно обработано: <b>{stats.voice_processed_success}</b>\n"
        f"Ошибок обработки: <b>{stats.voice_processing_failed}</b>\n"
        f"Заблокировано лимитом: <b>{stats.voice_limit_blocked}</b>\n"
        f"Минут аудио получено: <b>{stats.audio_minutes_received}</b>\n"
        f"Минут успешно обработано: <b>{stats.audio_minutes_processed}</b>\n"
        f"Открытий истории: <b>{stats.history_opened}</b>\n"
        f"Открытий профиля: <b>{stats.profile_opened}</b>\n"
        f"Нажатий “Поделиться”: <b>{stats.share_clicked}</b>\n"
        f"Показов paywall: <b>{stats.paywall_shown}</b>\n\n"
        "По тарифам:\n"
        f"Free: <b>{tariff_counts.get('free', 0)}</b> активных\n"
        f"Standard: <b>{tariff_counts.get('standard', 0)}</b> активных\n"
        f"Premium: <b>{tariff_counts.get('premium', 0)}</b> активных\n"
        f"По-братски от Тоши: <b>{tariff_counts.get('brother', 0)}</b> активных\n"
        f"Owner: <b>{tariff_counts.get('owner', 0)}</b> активных\n\n"
        "Конверсии:\n"
        f"Activation Rate: <b>{_format_percent(stats.activation_rate)}</b>\n"
        f"Success Rate: <b>{_format_percent(stats.success_rate)}</b>\n"
        f"Limit Block Rate: <b>{_format_percent(stats.limit_block_rate)}</b>\n"
        f"Share Rate: <b>{_format_percent(stats.share_rate)}</b>"
    )


def period_title(period: str) -> str:
    if period == "7d":
        return "Статистика за 7 дней"
    if period == "30d":
        return "Статистика за 30 дней"
    return "Статистика за сегодня"


def _build_stats(events: list[AnalyticsEvent], start_date: datetime, end_date: datetime) -> AdminStats:
    counts = _event_counts(events)
    active_user_ids = {
        event.telegram_id
        for event in events
        if event.event_name
        not in {
            "user_started",
            "paywall_shown",
        }
    }
    active_by_tariff: dict[str, set[int]] = {}
    for event in events:
        if event.telegram_id not in active_user_ids:
            continue
        tariff = event.tariff_type or "unknown"
        active_by_tariff.setdefault(tariff, set()).add(event.telegram_id)

    voice_received = counts.get("voice_received", 0)
    voice_processed_success = counts.get("voice_processed_success", 0)
    voice_limit_blocked = counts.get("voice_limit_blocked", 0)
    share_clicked = counts.get("share_clicked", 0)

    return AdminStats(
        start_date=start_date,
        end_date=end_date,
        new_users=len({event.telegram_id for event in events if event.event_name == "user_started"}),
        active_users=len(active_user_ids),
        voice_received=voice_received,
        voice_processed_success=voice_processed_success,
        voice_processing_failed=counts.get("voice_processing_failed", 0),
        voice_limit_blocked=voice_limit_blocked,
        audio_minutes_received=_sum_minutes(events, "voice_received"),
        audio_minutes_processed=_sum_minutes(events, "voice_processed_success"),
        history_opened=counts.get("history_opened", 0),
        profile_opened=counts.get("profile_opened", 0),
        share_clicked=share_clicked,
        paywall_shown=counts.get("paywall_shown", 0),
        active_by_tariff={tariff: len(user_ids) for tariff, user_ids in active_by_tariff.items()},
        activation_rate=_safe_ratio(voice_received, counts.get("user_started", 0)),
        success_rate=_safe_ratio(voice_processed_success, voice_received),
        limit_block_rate=_safe_ratio(voice_limit_blocked, voice_received),
        share_rate=_safe_ratio(share_clicked, voice_processed_success),
    )


def _event_counts(events: list[AnalyticsEvent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        counts[event.event_name] = counts.get(event.event_name, 0) + 1
    return counts


def _sum_minutes(events: list[AnalyticsEvent], event_name: str) -> int:
    total_seconds = 0
    for event in events:
        if event.event_name != event_name:
            continue
        payload = _load_payload(event.payload_json)
        total_seconds += int(payload.get("duration_seconds") or 0)
    return round(total_seconds / 60)


def _period_bounds(period: str) -> tuple[datetime, datetime]:
    now = datetime.now()
    today_start = datetime.combine(now.date(), time.min)
    if period == "7d":
        return today_start - timedelta(days=6), now
    if period == "30d":
        return today_start - timedelta(days=29), now
    return today_start, now


def _resolve_tariff_type(
    session: Session,
    telegram_id: int,
    username: str | None,
    settings: Settings | None,
    payload: dict[str, Any],
) -> str:
    if isinstance(payload.get("tariff_type"), str):
        return str(payload["tariff_type"])
    if settings is None:
        event = session.scalar(
            select(AnalyticsEvent)
            .where(AnalyticsEvent.telegram_id == telegram_id)
            .order_by(AnalyticsEvent.created_at.desc())
            .limit(1)
        )
        return event.tariff_type if event is not None else ""
    status: AccessStatus = check_user_access(session, telegram_id, username, settings)
    return status.tariff_type


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "duration_seconds",
        "error_type",
        "error_message_short",
        "transcription_id",
        "used_minutes",
        "remaining_minutes",
        "remaining_daily_messages",
        "reason",
        "source",
        "tariff_type",
        "processing_time_seconds",
    }
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in allowed:
            continue
        if value is None:
            continue
        if key == "error_message_short":
            sanitized[key] = str(value)[:160]
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)[:160]
    return sanitized


def _load_payload(payload_json: str | None) -> dict[str, Any]:
    if not payload_json:
        return {}
    try:
        value = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"
