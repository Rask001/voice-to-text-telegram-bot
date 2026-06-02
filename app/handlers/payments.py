from datetime import datetime
from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.orm import Session, sessionmaker

from app.access_service import check_user_access
from app.config import Settings
from app.handlers.keyboards import main_keyboard, payment_options_keyboard
from app.payment_service import (
    STARS_CURRENCY,
    STARS_TARIFFS,
    can_buy_tariff,
    create_payment_payload,
    create_pending_payment,
    process_successful_payment,
    validate_payment_payload,
)
from app.preferences import get_or_create_user_settings
from app.tariffs import get_tariff


router = Router()


@router.callback_query(F.data == "pay:show")
async def show_payment_options(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None:
        return
    with session_factory() as session:
        user_settings = get_or_create_user_settings(session, callback.from_user.id)
        access_status = check_user_access(
            session,
            callback.from_user.id,
            callback.from_user.username,
            settings,
        )
        allowed, reason = _can_show_payment_options(user_settings)
        session.commit()

    if not allowed:
        await callback.answer(reason or "Покупка тарифа сейчас не нужна.", show_alert=True)
        return

    await callback.answer("Выберите тариф")
    if callback.message is not None:
        await callback.message.answer(
            "⭐ <b>Выберите тариф</b>\n\n"
            "Standard — 199 Stars / 30 дней\n"
            "Premium — 499 Stars / 30 дней",
            reply_markup=payment_options_keyboard(access_status.tariff_type),
        )


@router.callback_query(F.data.startswith("pay:tariff:"))
async def buy_tariff(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None:
        return
    tariff = (callback.data or "").split(":")[-1]
    config = STARS_TARIFFS.get(tariff)
    if config is None:
        await callback.answer("Неизвестный тариф.", show_alert=True)
        return

    with session_factory() as session:
        user_settings = get_or_create_user_settings(session, callback.from_user.id)
        check_user_access(session, callback.from_user.id, callback.from_user.username, settings)
        allowed, reason = can_buy_tariff(user_settings, tariff)
        if not allowed:
            session.commit()
            await callback.answer(reason or "Этот тариф сейчас недоступен.", show_alert=True)
            return
        payload = create_payment_payload(tariff, callback.from_user.id)
        create_pending_payment(session, callback.from_user.id, tariff, payload)
        session.commit()

    await callback.answer("Открываю оплату...")
    if callback.message is None:
        return

    label = str(config["label"])
    amount = int(config["amount"])
    await callback.message.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"Тариф {label} на 30 дней",
        description=f"{label}: доступ к расшифровкам на 30 дней через Telegram Stars.",
        payload=payload,
        provider_token="",
        currency=STARS_CURRENCY,
        prices=[LabeledPrice(label=f"{label} / 30 дней", amount=amount)],
    )


@router.pre_checkout_query()
async def pre_checkout(
    pre_checkout_query: PreCheckoutQuery,
    session_factory: sessionmaker[Session],
) -> None:
    payload = pre_checkout_query.invoice_payload
    currency = pre_checkout_query.currency
    amount = pre_checkout_query.total_amount
    ok, reason, parsed = validate_payment_payload(
        payload,
        pre_checkout_query.from_user.id,
        currency,
        amount,
    )
    if ok and parsed is not None:
        with session_factory() as session:
            user_settings = get_or_create_user_settings(session, pre_checkout_query.from_user.id)
            allowed, reason = can_buy_tariff(user_settings, parsed.tariff)
            session.commit()
        if allowed:
            await pre_checkout_query.answer(ok=True)
            return

    await pre_checkout_query.answer(
        ok=False,
        error_message=reason or "Не удалось проверить оплату.",
    )


@router.message(F.successful_payment)
async def successful_payment(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.successful_payment is None:
        return

    payment = message.successful_payment
    try:
        with session_factory() as session:
            result = process_successful_payment(
                session=session,
                telegram_id=message.from_user.id,
                payload=payment.invoice_payload,
                currency=payment.currency,
                amount=payment.total_amount,
                telegram_payment_charge_id=payment.telegram_payment_charge_id,
                provider_payment_charge_id=payment.provider_payment_charge_id,
            )
            session.commit()
    except ValueError:
        await message.answer(
            "Оплата получена, но я не смог проверить тариф. Напишите владельцу бота.",
            reply_markup=main_keyboard(),
        )
        return

    if result.duplicate:
        await message.answer("Эта оплата уже была обработана.", reply_markup=main_keyboard())
        return

    if result.preserved_special_access:
        await message.answer(
            "✅ Оплата прошла\n\n"
            "У вас уже особый доступ, поэтому текущий тариф сохранён.",
            reply_markup=main_keyboard(),
        )
        return

    tariff_label = get_tariff(result.tariff).label
    expires_text = _format_expires_at(result.expires_at)
    await message.answer(
        "✅ <b>Оплата прошла</b>\n\n"
        f"Тариф <b>{escape(tariff_label)}</b> активирован до <b>{expires_text}</b>.",
        reply_markup=main_keyboard(),
    )


def _can_show_payment_options(user_settings) -> tuple[bool, str | None]:
    allowed, reason = can_buy_tariff(user_settings, "standard")
    if allowed:
        return True, None
    allowed, _ = can_buy_tariff(user_settings, "premium")
    if allowed:
        return True, None
    return False, reason


def _format_expires_at(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%d.%m.%Y")
