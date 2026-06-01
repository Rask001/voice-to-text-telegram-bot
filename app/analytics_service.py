import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from html import escape
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
    users_with_voice: int
    voice_received: int
    voice_processed_success: int
    voice_processing_failed: int
    voice_limit_blocked: int
    audio_minutes_received: float
    audio_minutes_processed: float
    average_processing_time_seconds: float
    history_opened: int
    profile_opened: int
    share_clicked: int
    paywall_shown: int
    active_by_tariff: dict[str, int]
    new_user_activation_rate: float
    active_voice_rate: float
    success_rate: float
    limit_block_rate: float
    share_rate: float
    error_counts: dict[str, int]
    block_reason_counts: dict[str, int]


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
    text = (
        f"📊 <b>{title}</b>\n\n"
        f"Новых пользователей: <b>{stats.new_users}</b>\n"
        f"Активных пользователей: <b>{stats.active_users}</b>\n"
        f"Пользователей с голосовыми: <b>{stats.users_with_voice}</b>\n"
        f"Голосовых получено: <b>{stats.voice_received}</b>\n"
        f"Успешно обработано: <b>{stats.voice_processed_success}</b>\n"
        f"Ошибок обработки: <b>{stats.voice_processing_failed}</b>\n"
        f"Заблокировано лимитом: <b>{stats.voice_limit_blocked}</b>\n"
        f"Минут аудио получено: <b>{stats.audio_minutes_received:.1f}</b>\n"
        f"Минут успешно обработано: <b>{stats.audio_minutes_processed:.1f}</b>\n"
        f"Среднее время обработки: <b>{stats.average_processing_time_seconds:.1f} сек</b>\n"
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
        f"Активация новых: <b>{_format_percent(stats.new_user_activation_rate)}</b>\n"
        f"Голосовые от активных: <b>{_format_percent(stats.active_voice_rate)}</b>\n"
        f"Успешная обработка: <b>{_format_percent(stats.success_rate)}</b>\n"
        f"Блокировки лимитом: <b>{_format_percent(stats.limit_block_rate)}</b>\n"
        f"Доля “Поделиться”: <b>{_format_percent(stats.share_rate)}</b>"
    )
    if stats.error_counts:
        text += "\n\nОшибки:\n" + _format_counts(stats.error_counts)
    if stats.block_reason_counts:
        text += "\n\nБлокировки:\n" + _format_counts(stats.block_reason_counts)
    return text


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
    new_user_ids = {
        event.telegram_id for event in events if event.event_name == "user_started"
    }
    users_with_voice_ids = {
        event.telegram_id for event in events if event.event_name == "voice_received"
    }

    return AdminStats(
        start_date=start_date,
        end_date=end_date,
        new_users=len(new_user_ids),
        active_users=len(active_user_ids),
        users_with_voice=len(users_with_voice_ids),
        voice_received=voice_received,
        voice_processed_success=voice_processed_success,
        voice_processing_failed=counts.get("voice_processing_failed", 0),
        voice_limit_blocked=voice_limit_blocked,
        audio_minutes_received=_sum_minutes(events, "voice_received"),
        audio_minutes_processed=_sum_minutes(events, "voice_processed_success"),
        average_processing_time_seconds=_average_processing_time(events),
        history_opened=counts.get("history_opened", 0),
        profile_opened=counts.get("profile_opened", 0),
        share_clicked=share_clicked,
        paywall_shown=counts.get("paywall_shown", 0),
        active_by_tariff={tariff: len(user_ids) for tariff, user_ids in active_by_tariff.items()},
        new_user_activation_rate=_safe_ratio(
            len(new_user_ids & users_with_voice_ids),
            len(new_user_ids),
        ),
        active_voice_rate=_safe_ratio(len(users_with_voice_ids), len(active_user_ids)),
        success_rate=_safe_ratio(voice_processed_success, voice_received),
        limit_block_rate=_safe_ratio(voice_limit_blocked, voice_received),
        share_rate=_safe_ratio(share_clicked, voice_processed_success),
        error_counts=_payload_counts(events, "voice_processing_failed", "error_type"),
        block_reason_counts=_payload_counts(events, "voice_limit_blocked", "reason"),
    )


def _event_counts(events: list[AnalyticsEvent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        counts[event.event_name] = counts.get(event.event_name, 0) + 1
    return counts


def _sum_minutes(events: list[AnalyticsEvent], event_name: str) -> float:
    total_seconds = 0.0
    for event in events:
        if event.event_name != event_name:
            continue
        payload = _load_payload(event.payload_json)
        total_seconds += _as_float(payload.get("duration_seconds"))
    return total_seconds / 60


def _average_processing_time(events: list[AnalyticsEvent]) -> float:
    values = []
    for event in events:
        if event.event_name != "voice_processed_success":
            continue
        payload = _load_payload(event.payload_json)
        value = _as_float(payload.get("processing_time_seconds"))
        if value > 0:
            values.append(value)
    if not values:
        return 0.0
    return sum(values) / len(values)


def _payload_counts(
    events: list[AnalyticsEvent],
    event_name: str,
    payload_key: str,
) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for event in events:
        if event.event_name != event_name:
            continue
        payload = _load_payload(event.payload_json)
        value = payload.get(payload_key)
        if isinstance(value, str) and value.strip():
            counter[value.strip()] += 1
    return dict(counter)


def _format_counts(counts: dict[str, int]) -> str:
    return "\n".join(
        f"- {escape(key)}: <b>{value}</b>"
        for key, value in sorted(counts.items())
    )


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


def _as_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0
