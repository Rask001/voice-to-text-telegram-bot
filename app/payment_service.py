from dataclasses import dataclass
from datetime import datetime, timedelta
from secrets import token_urlsafe

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Payment, UserSettings
from app.preferences import get_or_create_user_settings
from app.tariffs import BROTHER, FREE, OWNER, PREMIUM, STANDARD, get_tariff, normalize_tariff_code


PAYMENT_PROVIDER = "telegram_stars"
STARS_CURRENCY = "XTR"
TARIFF_DURATION_DAYS = 30

STARS_TARIFFS = {
    STANDARD: {
        "label": "Standard",
        "amount": 199,
        "days": TARIFF_DURATION_DAYS,
    },
    PREMIUM: {
        "label": "Premium",
        "amount": 499,
        "days": TARIFF_DURATION_DAYS,
    },
}


@dataclass(frozen=True)
class PaymentPayload:
    tariff: str
    telegram_id: int
    timestamp: int
    nonce: str


@dataclass(frozen=True)
class ActivationResult:
    activated: bool
    duplicate: bool
    tariff: str
    expires_at: datetime | None
    preserved_special_access: bool = False


def is_paid_tariff(tariff: str | None) -> bool:
    return normalize_tariff_code(tariff, default=None) in STARS_TARIFFS


def can_buy_tariff(user_settings: UserSettings, tariff: str) -> tuple[bool, str | None]:
    normalized = normalize_tariff_code(tariff, default=None)
    if normalized not in STARS_TARIFFS:
        return False, "Неизвестный тариф."

    current = normalize_tariff_code(user_settings.tariff_type)
    if current in {OWNER, BROTHER} or bool(user_settings.is_unlimited):
        return (
            False,
            "У вас уже особый доступ. Покупка тарифа не нужна.",
        )
    if current == PREMIUM and normalized == STANDARD:
        return (
            False,
            "У вас уже Premium. Standard будет шагом назад, поэтому я не буду его оформлять.",
        )
    return True, None


def create_payment_payload(tariff: str, telegram_id: int) -> str:
    normalized = normalize_tariff_code(tariff, default=None)
    if normalized not in STARS_TARIFFS:
        raise ValueError("Unknown paid tariff.")
    return f"stars:{normalized}:{int(telegram_id)}:{int(datetime.now().timestamp())}:{token_urlsafe(6)}"


def parse_payment_payload(payload: str) -> PaymentPayload | None:
    parts = (payload or "").split(":")
    if len(parts) != 5 or parts[0] != "stars":
        return None
    tariff = normalize_tariff_code(parts[1], default=None)
    if tariff not in STARS_TARIFFS:
        return None
    try:
        telegram_id = int(parts[2])
        timestamp = int(parts[3])
    except ValueError:
        return None
    if not parts[4]:
        return None
    return PaymentPayload(
        tariff=tariff,
        telegram_id=telegram_id,
        timestamp=timestamp,
        nonce=parts[4],
    )


def expected_amount(tariff: str) -> int | None:
    normalized = normalize_tariff_code(tariff, default=None)
    config = STARS_TARIFFS.get(normalized or "")
    return int(config["amount"]) if config else None


def validate_payment_payload(
    payload: str,
    telegram_id: int,
    currency: str,
    amount: int,
) -> tuple[bool, str | None, PaymentPayload | None]:
    parsed = parse_payment_payload(payload)
    if parsed is None:
        return False, "Некорректный payload оплаты.", None
    if parsed.telegram_id != telegram_id:
        return False, "Оплата создана для другого пользователя.", parsed
    if currency != STARS_CURRENCY:
        return False, "Некорректная валюта.", parsed
    expected = expected_amount(parsed.tariff)
    if expected is None or int(amount) != expected:
        return False, "Некорректная сумма оплаты.", parsed
    return True, None, parsed


def create_pending_payment(
    session: Session,
    telegram_id: int,
    tariff: str,
    payload: str,
) -> Payment:
    normalized = normalize_tariff_code(tariff, default=None)
    amount = expected_amount(normalized or "")
    if normalized not in STARS_TARIFFS or amount is None:
        raise ValueError("Unknown paid tariff.")

    payment = Payment(
        telegram_id=telegram_id,
        provider=PAYMENT_PROVIDER,
        currency=STARS_CURRENCY,
        amount=amount,
        tariff=normalized,
        payload=payload,
        status="pending",
        created_at=datetime.now(),
    )
    session.add(payment)
    session.flush()
    return payment


def process_successful_payment(
    session: Session,
    telegram_id: int,
    payload: str,
    currency: str,
    amount: int,
    telegram_payment_charge_id: str,
    provider_payment_charge_id: str = "",
) -> ActivationResult:
    ok, error, parsed = validate_payment_payload(payload, telegram_id, currency, amount)
    if not ok or parsed is None:
        payment = Payment(
            telegram_id=telegram_id,
            provider=PAYMENT_PROVIDER,
            currency=currency,
            amount=amount,
            tariff=parsed.tariff if parsed else "",
            payload=payload,
            telegram_payment_charge_id=telegram_payment_charge_id,
            provider_payment_charge_id=provider_payment_charge_id,
            status="failed",
            created_at=datetime.now(),
        )
        session.add(payment)
        session.flush()
        raise ValueError(error or "Payment validation failed.")

    existing_paid = session.scalar(
        select(Payment).where(
            Payment.telegram_payment_charge_id == telegram_payment_charge_id,
            Payment.status == "paid",
        )
    )
    if existing_paid is not None:
        duplicate_payment = Payment(
            telegram_id=telegram_id,
            provider=PAYMENT_PROVIDER,
            currency=currency,
            amount=amount,
            tariff=existing_paid.tariff,
            payload=payload,
            telegram_payment_charge_id=telegram_payment_charge_id,
            provider_payment_charge_id=provider_payment_charge_id,
            status="duplicate",
            created_at=datetime.now(),
        )
        session.add(duplicate_payment)
        session.flush()
        return ActivationResult(
            activated=False,
            duplicate=True,
            tariff=existing_paid.tariff,
            expires_at=None,
        )

    payment = session.scalar(select(Payment).where(Payment.payload == payload))
    if payment is None:
        payment = Payment(
            telegram_id=telegram_id,
            provider=PAYMENT_PROVIDER,
            currency=currency,
            amount=amount,
            tariff=parsed.tariff,
            payload=payload,
            created_at=datetime.now(),
        )
        session.add(payment)

    payment.currency = currency
    payment.amount = amount
    payment.tariff = parsed.tariff
    payment.telegram_payment_charge_id = telegram_payment_charge_id
    payment.provider_payment_charge_id = provider_payment_charge_id
    payment.status = "paid"
    payment.paid_at = datetime.now()

    user_settings = get_or_create_user_settings(session, telegram_id)
    if _has_special_access(user_settings):
        session.flush()
        return ActivationResult(
            activated=False,
            duplicate=False,
            tariff=user_settings.tariff_type,
            expires_at=user_settings.tariff_expires_at,
            preserved_special_access=True,
        )

    expires_at = activate_paid_tariff(user_settings, parsed.tariff, payment.paid_at)
    session.flush()
    return ActivationResult(
        activated=True,
        duplicate=False,
        tariff=parsed.tariff,
        expires_at=expires_at,
    )


def activate_paid_tariff(user_settings: UserSettings, tariff: str, paid_at: datetime) -> datetime:
    normalized = normalize_tariff_code(tariff, default=None)
    if normalized not in STARS_TARIFFS:
        raise ValueError("Unknown paid tariff.")

    now = paid_at or datetime.now()
    current_tariff = normalize_tariff_code(user_settings.tariff_type)
    current_expires = user_settings.tariff_expires_at
    if current_tariff == normalized and current_expires is not None and current_expires > now:
        starts_at = current_expires
    else:
        starts_at = now

    expires_at = starts_at + timedelta(days=int(STARS_TARIFFS[normalized]["days"]))
    plan = get_tariff(normalized)
    user_settings.tariff_type = normalized
    user_settings.is_unlimited = False
    user_settings.is_premium = normalized == PREMIUM
    user_settings.daily_voice_limit = plan.daily_voice_limit or 0
    user_settings.minutes_limit_month = plan.minutes_limit_month or 0
    user_settings.minutes_limit_total = plan.minutes_limit_total or 0
    user_settings.tariff_expires_at = expires_at
    if user_settings.registration_date is None:
        user_settings.registration_date = now
    if normalized != FREE:
        user_settings.trial_expires_at = user_settings.trial_expires_at
    return expires_at


def _has_special_access(user_settings: UserSettings) -> bool:
    current = normalize_tariff_code(user_settings.tariff_type)
    return current in {OWNER, BROTHER} or bool(user_settings.is_unlimited)
