from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.orm import Session, sessionmaker

from app.access import add_unlimited_user, is_owner
from app.analytics_service import (
    cleanup_old_events,
    format_admin_stats,
    get_admin_stats,
    period_title,
)
from app.config import Settings


router = Router()


def is_owner_command_user(user, settings: Settings) -> bool:
    return user is not None and is_owner(user.id, user.username, settings)


@router.message(Command("admin_add_unlimited"))
async def admin_add_unlimited(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return

    if not is_owner_command_user(message.from_user, settings):
        await message.answer("Команда доступна только владельцу.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /admin_add_unlimited <telegram_id>")
        return

    telegram_user_id = int(parts[1])
    with session_factory() as session:
        add_unlimited_user(session, telegram_user_id)
        session.commit()

    await message.answer(
        f"Пользователь {telegram_user_id} добавлен в тариф «По-братски от Тоши»."
    )


@router.message(Command("admin_stats"))
async def admin_stats(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    await _send_admin_stats(message, settings, session_factory, "today")


@router.message(Command("admin_stats_today"))
async def admin_stats_today(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    await _send_admin_stats(message, settings, session_factory, "today")


@router.message(Command("admin_stats_7d"))
async def admin_stats_7d(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    await _send_admin_stats(message, settings, session_factory, "7d")


@router.message(Command("admin_stats_30d"))
async def admin_stats_30d(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    await _send_admin_stats(message, settings, session_factory, "30d")


@router.message(Command("admin_cleanup_analytics"))
async def admin_cleanup_analytics(
    message: Message,
    settings: Settings,
) -> None:
    if not is_owner_command_user(message.from_user, settings):
        await message.answer("Эта команда доступна только владельцу бота.")
        return

    await message.answer(
        "Удалить события аналитики старше 90 дней?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Да, удалить старые события",
                        callback_data="admin_cleanup_analytics:confirm",
                    )
                ]
            ]
        ),
    )


@router.callback_query(F.data.startswith("admin_stats:"))
async def admin_stats_callback(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if not is_owner_command_user(callback.from_user, settings):
        await callback.answer("Эта команда доступна только владельцу бота.", show_alert=True)
        return

    period = callback.data.split(":", 1)[1] if callback.data else "today"
    stats = get_admin_stats(session_factory, period)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            format_admin_stats(stats, period_title(period)),
            reply_markup=_admin_stats_keyboard(period),
        )
    await callback.answer("Готово")


@router.callback_query(F.data == "admin_cleanup_analytics:confirm")
async def admin_cleanup_analytics_callback(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if not is_owner_command_user(callback.from_user, settings):
        await callback.answer("Эта команда доступна только владельцу бота.", show_alert=True)
        return

    deleted = cleanup_old_events(session_factory, days=90)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"Готово. Удалено событий старше 90 дней: <b>{deleted}</b>."
        )
    await callback.answer("Очищено")


async def _send_admin_stats(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
    period: str,
) -> None:
    if not is_owner_command_user(message.from_user, settings):
        await message.answer("Эта команда доступна только владельцу бота.")
        return

    stats = get_admin_stats(session_factory, period)
    await message.answer(
        format_admin_stats(stats, period_title(period)),
        reply_markup=_admin_stats_keyboard(period),
    )


def _admin_stats_keyboard(active_period: str) -> InlineKeyboardMarkup:
    labels = {
        "today": "Сегодня",
        "7d": "7 дней",
        "30d": "30 дней",
    }
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("• " if period == active_period else "") + label,
                    callback_data=f"admin_stats:{period}",
                )
                for period, label in labels.items()
            ]
        ]
    )
