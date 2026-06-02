from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import ceil

from sqlalchemy.orm import Session

from app.config import Settings
from app.preferences import get_or_create_user_settings
from app.tariffs import BROTHER, FREE, OWNER, PREMIUM, STANDARD, TariffPlan, get_tariff


TRIAL_EXPIRED_MESSAGE = (
    "Пробный период закончился. Чтобы продолжить пользоваться ботом, "
    "оформите подписку.\n\n"
    "Скоро здесь появится оплата через Telegram Stars ⭐"
)

LIMIT_EXPIRED_MESSAGE = (
    "❌ Ваш лимит закончился.\n\n"
    "Чтобы продолжить пользоваться ботом, оформите подписку.\n\n"
    "Скоро здесь появится оплата через Telegram Stars ⭐"
)


@dataclass(frozen=True)
class AccessStatus:
    tariff: str
    tariff_type: str
    used_today: int
    daily_limit: int | None
    remaining_today: int | None
    reset_date: date
    is_unlimited: bool
    can_process: bool
    minutes_used_total: int
    minutes_limit_total: int | None
    minutes_used_this_month: int
    minutes_limit_month: int | None
    minutes_remaining_total: int | None
    minutes_remaining_month: int | None
    trial_expires_at: datetime | None
    trial_days_left: int | None
    max_voice_seconds: int | None
    total_saved_seconds: int
    denial_reason: str | None = None
    denial_code: str | None = None


def is_owner(user_id: int, username: str | None, settings: Settings) -> bool:
    if settings.owner_telegram_id is not None and user_id == settings.owner_telegram_id:
        return True
    return (username or "").lower() == "aaios"


def get_access_status(
    session: Session,
    user_id: int,
    username: str | None,
    settings: Settings,
) -> AccessStatus:
    user_settings = _prepare_user_settings(session, user_id, username, settings)
    plan = get_tariff(user_settings.tariff_type)
    denial_reason, denial_code = _get_static_denial(user_settings, plan)

    return _build_access_status(
        user_settings=user_settings,
        plan=plan,
        can_process=denial_reason is None,
        denial_reason=denial_reason,
        denial_code=denial_code,
    )


def check_voice_access(
    session: Session,
    user_id: int,
    username: str | None,
    settings: Settings,
    duration_seconds: int,
) -> AccessStatus:
    user_settings = _prepare_user_settings(session, user_id, username, settings)
    plan = get_tariff(user_settings.tariff_type)
    denial_reason, denial_code = _get_static_denial(user_settings, plan)

    if denial_reason is None and plan.max_voice_seconds is not None:
        if duration_seconds > plan.max_voice_seconds:
            denial_reason = (
                "Голосовое слишком длинное для вашего тарифа. "
                f"Максимум: {plan.max_voice_seconds // 60} мин."
            )
            denial_code = "voice_too_long"

    used_minutes = _billable_minutes(duration_seconds)
    if denial_reason is None and plan.minutes_limit_month is not None:
        if user_settings.minutes_used_this_month + used_minutes > plan.minutes_limit_month:
            denial_reason = LIMIT_EXPIRED_MESSAGE
            denial_code = "monthly_minutes_limit"

    if denial_reason is None and plan.minutes_limit_total is not None:
        if user_settings.minutes_used_total + used_minutes > plan.minutes_limit_total:
            denial_reason = TRIAL_EXPIRED_MESSAGE
            denial_code = "trial_minutes_limit"

    return _build_access_status(
        user_settings=user_settings,
        plan=plan,
        can_process=denial_reason is None,
        denial_reason=denial_reason,
        denial_code=denial_code,
    )


def record_voice_usage(
    session: Session,
    user_id: int,
    username: str | None,
    settings: Settings,
    duration_seconds: int,
) -> None:
    user_settings = _prepare_user_settings(session, user_id, username, settings)
    plan = get_tariff(user_settings.tariff_type)
    if plan.code == OWNER:
        return

    used_minutes = _billable_minutes(duration_seconds)
    user_settings.voices_used_today += 1
    user_settings.minutes_used_this_month += used_minutes
    user_settings.minutes_used_total += used_minutes


def add_unlimited_user(session: Session, telegram_user_id: int) -> None:
    user_settings = get_or_create_user_settings(session, telegram_user_id)
    user_settings.tariff_type = BROTHER
    user_settings.is_unlimited = True
    _apply_plan_limits(user_settings, get_tariff(BROTHER))


def _prepare_user_settings(session: Session, user_id: int, username: str | None, settings: Settings):
    user_settings = get_or_create_user_settings(session, user_id)
    now = datetime.now()

    if user_settings.registration_date is None:
        user_settings.registration_date = now
    if user_settings.trial_expires_at is None:
        user_settings.trial_expires_at = user_settings.registration_date + timedelta(days=3)

    desired_tariff = _resolve_tariff_type(user_settings, user_id, username, settings)
    if user_settings.tariff_type != desired_tariff:
        user_settings.tariff_type = desired_tariff

    plan = get_tariff(user_settings.tariff_type)
    _reset_period_counters(user_settings, now)
    _apply_plan_limits(user_settings, plan)
    return user_settings


def _resolve_tariff_type(user_settings, user_id: int, username: str | None, settings: Settings) -> str:
    if is_owner(user_id, username, settings):
        return OWNER
    if user_settings.tariff_type == OWNER:
        return OWNER
    if user_id in settings.unlimited_user_ids or bool(user_settings.is_unlimited):
        return BROTHER
    if bool(user_settings.is_premium):
        return PREMIUM
    if user_settings.tariff_type in {STANDARD, PREMIUM, BROTHER}:
        return user_settings.tariff_type
    return FREE


def _reset_period_counters(user_settings, now: datetime) -> None:
    today = now.date()
    current_month = now.strftime("%Y-%m")

    if user_settings.usage_date != today:
        user_settings.usage_date = today
        user_settings.voices_used_today = 0

    if user_settings.minutes_month_key != current_month:
        user_settings.minutes_month_key = current_month
        user_settings.minutes_used_this_month = 0


def _apply_plan_limits(user_settings, plan: TariffPlan) -> None:
    user_settings.daily_voice_limit = plan.daily_voice_limit or 0
    user_settings.minutes_limit_month = plan.minutes_limit_month or 0
    user_settings.minutes_limit_total = plan.minutes_limit_total or 0


def _get_static_denial(user_settings, plan: TariffPlan) -> tuple[str | None, str | None]:
    now = datetime.now()

    if plan.code == OWNER:
        return None, None

    if plan.code == FREE:
        if user_settings.trial_expires_at and now > user_settings.trial_expires_at:
            return TRIAL_EXPIRED_MESSAGE, "trial_expired"
        if user_settings.minutes_used_total >= (plan.minutes_limit_total or 0):
            return TRIAL_EXPIRED_MESSAGE, "trial_minutes_limit"

    if plan.daily_voice_limit is not None:
        if user_settings.voices_used_today >= plan.daily_voice_limit:
            return LIMIT_EXPIRED_MESSAGE, "daily_voice_limit"

    if plan.minutes_limit_month is not None:
        if user_settings.minutes_used_this_month >= plan.minutes_limit_month:
            return LIMIT_EXPIRED_MESSAGE, "monthly_minutes_limit"

    return None, None


def _build_access_status(
    user_settings,
    plan: TariffPlan,
    can_process: bool,
    denial_reason: str | None,
    denial_code: str | None,
) -> AccessStatus:
    trial_days_left = _trial_days_left(user_settings.trial_expires_at) if plan.code == FREE else None
    remaining_today = None
    if plan.daily_voice_limit is not None:
        remaining_today = max(plan.daily_voice_limit - user_settings.voices_used_today, 0)

    remaining_month = None
    if plan.minutes_limit_month is not None:
        remaining_month = max(plan.minutes_limit_month - user_settings.minutes_used_this_month, 0)

    remaining_total = None
    if plan.minutes_limit_total is not None:
        remaining_total = max(plan.minutes_limit_total - user_settings.minutes_used_total, 0)

    return AccessStatus(
        tariff=plan.label,
        tariff_type=plan.code,
        used_today=user_settings.voices_used_today,
        daily_limit=plan.daily_voice_limit,
        remaining_today=remaining_today,
        reset_date=date.today() + timedelta(days=1),
        is_unlimited=plan.code == OWNER,
        can_process=can_process,
        minutes_used_total=user_settings.minutes_used_total,
        minutes_limit_total=plan.minutes_limit_total,
        minutes_used_this_month=user_settings.minutes_used_this_month,
        minutes_limit_month=plan.minutes_limit_month,
        minutes_remaining_total=remaining_total,
        minutes_remaining_month=remaining_month,
        trial_expires_at=user_settings.trial_expires_at,
        trial_days_left=trial_days_left,
        max_voice_seconds=plan.max_voice_seconds,
        total_saved_seconds=user_settings.total_saved_seconds or 0,
        denial_reason=denial_reason,
        denial_code=denial_code,
    )


def _trial_days_left(trial_expires_at: datetime | None) -> int | None:
    if trial_expires_at is None:
        return None
    seconds_left = (trial_expires_at - datetime.now()).total_seconds()
    if seconds_left <= 0:
        return 0
    return ceil(seconds_left / 86400)


def _billable_minutes(duration_seconds: int) -> int:
    return max(1, ceil(duration_seconds / 60))
