import asyncio
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.orm import Session, sessionmaker

from app.access import add_unlimited_user, is_owner
from app.admin_service import (
    ADMIN_ONLY_MESSAGE,
    add_friend_tariff,
    create_database_backup,
    enrich_admin_users,
    format_admin_health,
    format_admin_user_info,
    format_admin_users,
    get_admin_user_info,
    get_broadcast_user_ids,
    get_start_text,
    list_admin_users,
    normalize_admin_tariff,
    remove_friend_tariff,
    reset_start_text,
    set_start_text,
    set_user_tariff,
    validate_start_text,
)
from app.analytics_service import (
    cleanup_old_events,
    format_admin_stats,
    get_admin_stats,
    period_title,
)
from app.config import Settings
from app.handlers.keyboards import main_keyboard
from app.tariffs import BROTHER, get_tariff


router = Router()


class AdminStates(StatesGroup):
    waiting_for_start_text = State()
    waiting_for_broadcast_text = State()
    waiting_for_broadcast_confirm = State()


def is_owner_command_user(user, settings: Settings) -> bool:
    return user is not None and is_owner(user.id, user.username, settings)


async def _deny_non_owner(message: Message, settings: Settings) -> bool:
    if is_owner_command_user(message.from_user, settings):
        return False
    await message.answer(ADMIN_ONLY_MESSAGE)
    return True


async def _deny_non_owner_callback(callback: CallbackQuery, settings: Settings) -> bool:
    if is_owner_command_user(callback.from_user, settings):
        return False
    await callback.answer(ADMIN_ONLY_MESSAGE, show_alert=True)
    return True


@router.message(Command("admin_help", "ah"))
async def admin_help(message: Message, settings: Settings) -> None:
    if await _deny_non_owner(message, settings):
        return
    await message.answer(_admin_help_text())


@router.message(Command("start_text"))
async def start_text(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if await _deny_non_owner(message, settings):
        return
    with session_factory() as session:
        text = get_start_text(session)
    await message.answer(f"Текущий стартовый текст:\n\n{text}")


@router.message(Command("set_start_text"))
async def set_start_text_command(
    message: Message,
    state: FSMContext,
    settings: Settings,
) -> None:
    if await _deny_non_owner(message, settings):
        return
    await state.set_state(AdminStates.waiting_for_start_text)
    await message.answer(
        "Отправьте новый стартовый текст одним сообщением.\n"
        "Для отмены: /cancel"
    )


@router.message(AdminStates.waiting_for_start_text, F.text)
async def start_text_received(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if await _deny_non_owner(message, settings):
        return
    text = (message.text or "").strip()
    if text == "/cancel":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_keyboard())
        return
    error = validate_start_text(text)
    if error:
        await message.answer(error)
        return
    with session_factory() as session:
        set_start_text(session, text)
        session.commit()
    await state.clear()
    await message.answer("✅ Стартовый текст обновлён.", reply_markup=main_keyboard())


@router.message(Command("reset_start_text"))
async def reset_start_text_command(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if await _deny_non_owner(message, settings):
        return
    with session_factory() as session:
        reset_start_text(session)
        session.commit()
    await message.answer("✅ Стартовый текст возвращён по умолчанию.")


@router.message(Command("user"))
async def admin_user_info(
    message: Message,
    command: CommandObject,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if await _deny_non_owner(message, settings):
        return
    telegram_id = _parse_telegram_id(command.args)
    if telegram_id is None:
        await message.answer("Использование: /user <telegram_id>")
        return
    with session_factory() as session:
        info = get_admin_user_info(session, telegram_id)
        session.commit()
    await message.answer(format_admin_user_info(info))


@router.message(Command("set_tariff", "tf"))
async def set_tariff_command(
    message: Message,
    command: CommandObject,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if await _deny_non_owner(message, settings):
        return
    parts = (command.args or "").split()
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer("Использование: /set_tariff <telegram_id> <free|standard|premium|friend|owner>")
        return
    telegram_id = int(parts[0])
    tariff_type = normalize_admin_tariff(parts[1])
    if tariff_type is None:
        await message.answer("Неизвестный тариф. Доступно: free, standard, premium, friend, owner.")
        return
    with session_factory() as session:
        set_user_tariff(session, telegram_id, tariff_type)
        session.commit()
    await message.answer(
        f"✅ Пользователю <code>{telegram_id}</code> назначен тариф "
        f"<b>{escape(get_tariff(tariff_type).label)}</b>."
    )


@router.message(Command("add_friend", "bro"))
async def add_friend_command(
    message: Message,
    command: CommandObject,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if await _deny_non_owner(message, settings):
        return
    telegram_id = _parse_telegram_id(command.args)
    if telegram_id is None:
        await message.answer("Использование: /add_friend <telegram_id>")
        return
    with session_factory() as session:
        add_friend_tariff(session, telegram_id)
        session.commit()
    await message.answer("✅ Пользователь добавлен на тариф “по-братски от Тоши”.")


@router.message(Command("remove_friend", "unbro"))
async def remove_friend_command(
    message: Message,
    command: CommandObject,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if await _deny_non_owner(message, settings):
        return
    telegram_id = _parse_telegram_id(command.args)
    if telegram_id is None:
        await message.answer("Использование: /remove_friend <telegram_id>")
        return
    with session_factory() as session:
        remove_friend_tariff(session, telegram_id)
        session.commit()
    await message.answer("✅ Пользователь возвращён на тариф Free.")


@router.message(Command("admin_users"))
async def admin_users(
    message: Message,
    command: CommandObject,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if await _deny_non_owner(message, settings):
        return
    limit, tariff_filter = _parse_admin_users_args(command.args)
    with session_factory() as session:
        users = list_admin_users(session, limit=limit, tariff_filter=tariff_filter)
        users = enrich_admin_users(session, users)
    await message.answer(format_admin_users(users))


@router.message(Command("admin_backup"))
async def admin_backup(message: Message, settings: Settings) -> None:
    if await _deny_non_owner(message, settings):
        return
    try:
        backup_path = create_database_backup(settings)
    except Exception as exc:
        await message.answer(f"Не удалось создать backup: {escape(str(exc))}")
        return
    await message.answer(f"✅ Backup создан: <code>{escape(str(backup_path))}</code>")


@router.message(Command("admin_health"))
async def admin_health(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if await _deny_non_owner(message, settings):
        return
    await message.answer(format_admin_health(session_factory, settings))


@router.message(Command("admin_broadcast"))
async def admin_broadcast(
    message: Message,
    state: FSMContext,
    settings: Settings,
) -> None:
    if await _deny_non_owner(message, settings):
        return
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await message.answer(
        "Отправьте текст рассылки одним сообщением.\n"
        "Для отмены: /cancel"
    )


@router.message(AdminStates.waiting_for_broadcast_text, F.text)
async def admin_broadcast_text_received(
    message: Message,
    state: FSMContext,
    settings: Settings,
) -> None:
    if await _deny_non_owner(message, settings):
        return
    text = (message.text or "").strip()
    if text == "/cancel":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_keyboard())
        return
    if not text:
        await message.answer("Текст рассылки не должен быть пустым.")
        return
    if len(text) > 3500:
        await message.answer("Текст слишком длинный. Максимум: 3500 символов.")
        return
    await state.update_data(broadcast_text=text)
    await state.set_state(AdminStates.waiting_for_broadcast_confirm)
    await message.answer(
        "Отправить рассылку всем активным пользователям?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Отправить", callback_data="admin_broadcast:send"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast:cancel"),
                ]
            ]
        ),
    )


@router.callback_query(AdminStates.waiting_for_broadcast_confirm, F.data.startswith("admin_broadcast:"))
async def admin_broadcast_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if await _deny_non_owner_callback(callback, settings):
        return
    action = callback.data.split(":", 1)[1] if callback.data else "cancel"
    if action == "cancel":
        await state.clear()
        await callback.answer("Отменено")
        if isinstance(callback.message, Message):
            await callback.message.answer("Действие отменено.", reply_markup=main_keyboard())
        return

    data = await state.get_data()
    text = str(data.get("broadcast_text") or "").strip()
    await state.clear()
    await callback.answer("Запускаю рассылку")
    if not text:
        if isinstance(callback.message, Message):
            await callback.message.answer("Текст рассылки потерялся. Попробуйте ещё раз.")
        return

    with session_factory() as session:
        user_ids = get_broadcast_user_ids(session)

    success = 0
    failed = 0
    bot = callback.bot
    for telegram_id in user_ids:
        try:
            await bot.send_message(telegram_id, text)
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"Рассылка завершена. Успешно: <b>{success}</b>. Ошибок: <b>{failed}</b>.",
            reply_markup=main_keyboard(),
        )


@router.message(Command("cancel"))
async def cancel_admin_mode(
    message: Message,
    state: FSMContext,
    settings: Settings,
) -> None:
    if await _deny_non_owner(message, settings):
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_keyboard())


@router.message(Command("admin_add_unlimited"))
async def admin_add_unlimited(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return

    if not is_owner_command_user(message.from_user, settings):
        await message.answer(ADMIN_ONLY_MESSAGE)
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


@router.message(Command("admin_stats", "stats"))
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
    if await _deny_non_owner(message, settings):
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
    if await _deny_non_owner_callback(callback, settings):
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
    if await _deny_non_owner_callback(callback, settings):
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
    if await _deny_non_owner(message, settings):
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


def _admin_help_text() -> str:
    return (
        "🛠 <b>Админ-команды</b>\n\n"
        "/start_text — показать текущий стартовый текст\n"
        "/set_start_text — изменить стартовый текст\n"
        "/reset_start_text — вернуть стартовый текст по умолчанию\n\n"
        "/user — информация о пользователе\n"
        "/set_tariff — назначить тариф\n"
        "/tf — коротко назначить тариф\n"
        "/add_friend — выдать тариф “по-братски от Тоши”\n"
        "/bro — коротко выдать тариф “по-братски от Тоши”\n"
        "/remove_friend — убрать тариф “по-братски от Тоши”\n"
        "/unbro — коротко убрать тариф “по-братски от Тоши”\n\n"
        "/admin_stats — статистика\n"
        "/stats — короткая статистика\n"
        "/admin_health — состояние системы\n"
        "/admin_users — список последних пользователей\n"
        "/admin_broadcast — рассылка\n"
        "/admin_backup — создать backup SQLite\n"
        "/cancel — отменить текущий админский сценарий"
    )


def _parse_telegram_id(args: str | None) -> int | None:
    value = (args or "").strip().split()
    if len(value) != 1 or not value[0].isdigit():
        return None
    return int(value[0])


def _parse_admin_users_args(args: str | None) -> tuple[int, str | None]:
    limit = 10
    tariff_filter = None
    for part in (args or "").split():
        if part.isdigit():
            limit = int(part)
        elif part.startswith("tariff="):
            value = part.split("=", 1)[1].strip()
            tariff_filter = BROTHER if value == "friend" else value
    return limit, tariff_filter
