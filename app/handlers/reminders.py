from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session, sessionmaker

from app.analytics_service import track_event
from app.config import Settings
from app.formatters import format_reminder_created, format_reminders_list
from app.handlers.keyboards import (
    main_keyboard,
    reminder_fallback_time_keyboard,
    reminder_time_keyboard,
    reminder_tomorrow_clarification_keyboard,
    reminders_keyboard,
)
from app.models import Reminder
from app.reminder_parser import (
    now_in_timezone,
    parse_reminder_text,
    parse_reminder_time_choice,
)
from app.reminder_service import (
    cancel_reminder,
    complete_reminder,
    create_reminder,
    get_reminder_by_id,
    get_user_reminders,
    snooze_reminder,
)


router = Router()


class ReminderCreation(StatesGroup):
    waiting_for_text = State()
    waiting_for_time = State()
    waiting_for_manual_time = State()
    waiting_for_task_after_time = State()
    waiting_for_tomorrow_clarification = State()


@router.message(Command("reminders"))
async def reminders_command(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    track_event(session_factory, "reminders_opened", message.from_user, settings=settings)
    await send_user_reminders(message, message.from_user.id, session_factory)


@router.message(Command("remind"))
async def remind_command(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    args = (command.args or "").strip()
    if args:
        parsed = parse_reminder_text(
            args,
            timezone=settings.default_timezone,
            default_time=settings.default_reminder_time,
        )
        if parsed.needs_tomorrow_clarification:
            await _ask_tomorrow_clarification(message, state, parsed)
            return
        if parsed.success and parsed.remind_at is not None:
            await state.clear()
            await _create_reminder_and_answer(
                message,
                message.from_user,
                message.from_user.id,
                parsed.task_text,
                parsed.remind_at,
                settings,
                session_factory,
                source="command_text",
            )
            return
        if parsed.needs_task and parsed.remind_at is not None:
            await state.update_data(remind_at=parsed.remind_at.isoformat())
            await state.set_state(ReminderCreation.waiting_for_task_after_time)
            await message.answer("Что напомнить?", reply_markup=main_keyboard())
            return
        if parsed.remind_at is None:
            await state.update_data(task_text=args)
            await state.set_state(ReminderCreation.waiting_for_time)
            await message.answer(
                _time_parse_error_text(),
                reply_markup=reminder_fallback_time_keyboard(),
            )
            return

    await start_reminder_creation(message, state)


async def start_reminder_creation(message: Message, state: FSMContext) -> None:
    await state.set_state(ReminderCreation.waiting_for_text)
    await message.answer(
        "Что напомнить?\n\nОтправьте текст напоминания одним сообщением.",
        reply_markup=main_keyboard(),
    )


@router.message(ReminderCreation.waiting_for_text, F.text)
async def reminder_text_received(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пришлите текст напоминания.")
        return

    parsed = parse_reminder_text(
        text,
        timezone=settings.default_timezone,
        default_time=settings.default_reminder_time,
    )
    if parsed.needs_tomorrow_clarification:
        await _ask_tomorrow_clarification(message, state, parsed)
        return
    if parsed.success and parsed.remind_at is not None and message.from_user is not None:
        await state.clear()
        await _create_reminder_and_answer(
            message,
            message.from_user,
            message.from_user.id,
            parsed.task_text,
            parsed.remind_at,
            settings,
            session_factory,
            source="fsm_text",
        )
        return
    if parsed.needs_task and parsed.remind_at is not None:
        await state.update_data(remind_at=parsed.remind_at.isoformat())
        await state.set_state(ReminderCreation.waiting_for_task_after_time)
        await message.answer("Что напомнить?", reply_markup=main_keyboard())
        return

    await state.update_data(task_text=text)
    await state.set_state(ReminderCreation.waiting_for_time)
    await message.answer(
        _ask_time_text(),
        reply_markup=reminder_time_keyboard(),
    )


@router.message(ReminderCreation.waiting_for_task_after_time, F.text)
async def reminder_task_after_time_received(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    task_text = (message.text or "").strip()
    if not task_text:
        await message.answer("Пришлите текст напоминания.")
        return
    data = await state.get_data()
    remind_at_text = str(data.get("remind_at") or "")
    if not remind_at_text:
        await state.clear()
        await message.answer("Время напоминания потерялось. Попробуйте ещё раз.", reply_markup=main_keyboard())
        return
    await state.clear()
    await _create_reminder_and_answer(
        message,
        message.from_user,
        message.from_user.id,
        task_text,
        datetime.fromisoformat(remind_at_text),
        settings,
        session_factory,
        source="task_after_time",
    )


@router.callback_query(
    ReminderCreation.waiting_for_tomorrow_clarification,
    F.data.startswith("reminder_tomorrow_"),
)
async def reminder_tomorrow_clarification_selected(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    action = callback.data.removeprefix("reminder_tomorrow_").removesuffix(":")
    if action == "cancel":
        await state.clear()
        await callback.answer("Отменено")
        if isinstance(callback.message, Message):
            await callback.message.answer("Создание напоминания отменено.", reply_markup=main_keyboard())
        return

    data = await state.get_data()
    task_text = str(data.get("task_text") or "").strip()
    today_at = str(data.get("tomorrow_today_at") or "")
    nextday_at = str(data.get("tomorrow_nextday_at") or "")
    if not task_text or not today_at or not nextday_at:
        await state.clear()
        await callback.answer("Данные потерялись. Попробуйте ещё раз.", show_alert=True)
        return

    if action == "today":
        remind_at = datetime.fromisoformat(today_at)
    elif action == "nextday":
        remind_at = datetime.fromisoformat(nextday_at)
    else:
        await callback.answer("Неизвестный выбор", show_alert=True)
        return

    await state.clear()
    await callback.answer("Напоминание создано")
    if callback.message is not None and hasattr(callback.message, "answer"):
        await _create_reminder_and_answer(
            callback.message,
            callback.from_user,
            callback.from_user.id,
            task_text,
            remind_at,
            settings,
            session_factory,
            source=f"tomorrow_clarification_{action}",
        )


@router.callback_query(ReminderCreation.waiting_for_manual_time, F.data.startswith("remind_time:"))
@router.callback_query(ReminderCreation.waiting_for_time, F.data.startswith("remind_time:"))
async def reminder_time_selected(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    choice = callback.data.split(":", 1)[1]
    if choice == "cancel":
        await state.clear()
        await callback.answer("Отменено")
        if isinstance(callback.message, Message):
            await callback.message.answer("Создание напоминания отменено.", reply_markup=main_keyboard())
        return
    if choice == "manual":
        await state.set_state(ReminderCreation.waiting_for_manual_time)
        await callback.answer("Напишите время")
        if isinstance(callback.message, Message):
            await callback.message.answer(_manual_time_prompt_text())
        return

    remind_at = parse_reminder_time_choice(
        choice,
        timezone=settings.default_timezone,
        default_time=settings.default_reminder_time,
    )
    if remind_at is None:
        await callback.answer("Не удалось выбрать время", show_alert=True)
        return

    data = await state.get_data()
    task_text = str(data.get("task_text") or "").strip()
    if not task_text:
        await state.clear()
        await callback.answer("Текст напоминания потерялся. Попробуйте ещё раз.", show_alert=True)
        return

    await state.clear()
    await callback.answer("Напоминание создано")
    if isinstance(callback.message, Message):
        await _create_reminder_and_answer(
            callback.message,
            callback.from_user,
            callback.from_user.id,
            task_text,
            remind_at,
            settings,
            session_factory,
            source="manual_button",
        )


@router.message(ReminderCreation.waiting_for_manual_time, F.text)
@router.message(ReminderCreation.waiting_for_time, F.text)
async def reminder_manual_time_received(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").strip()
    if text.lower() == "отмена":
        await state.clear()
        await message.answer("Создание напоминания отменено.", reply_markup=main_keyboard())
        return

    data = await state.get_data()
    task_text = str(data.get("task_text") or "").strip()
    if not task_text:
        await state.clear()
        await message.answer("Текст напоминания потерялся. Попробуйте ещё раз.", reply_markup=main_keyboard())
        return

    parsed = parse_reminder_text(
        f"{task_text} {text}",
        timezone=settings.default_timezone,
        default_time=settings.default_reminder_time,
    )
    if parsed.needs_tomorrow_clarification:
        await _ask_tomorrow_clarification(message, state, parsed)
        return
    if parsed.remind_at is None:
        await message.answer(
            _time_parse_error_text(),
            reply_markup=reminder_fallback_time_keyboard(),
        )
        return

    await state.clear()
    await _create_reminder_and_answer(
        message,
        message.from_user,
        message.from_user.id,
        parsed.task_text or task_text,
        parsed.remind_at,
        settings,
        session_factory,
        source="manual_text",
    )


@router.callback_query(F.data.startswith("reminder_"))
async def reminder_action_callback(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    parsed = _parse_reminder_action(callback.data)
    if parsed is None:
        await callback.answer("Неизвестное действие", show_alert=True)
        return
    action, reminder_id = parsed
    with session_factory() as session:
        reminder = get_reminder_by_id(session, reminder_id, telegram_id=callback.from_user.id)
        if reminder is None:
            await callback.answer("Напоминание не найдено.", show_alert=True)
            return
        event_name = ""
        answer_text = ""
        if action == "complete":
            complete_reminder(session, reminder)
            event_name = "reminder_completed"
            answer_text = "Готово"
        elif action == "cancel":
            cancel_reminder(session, reminder)
            event_name = "reminder_cancelled"
            answer_text = "Удалено"
        elif action == "snooze_hour":
            snooze_reminder(
                session,
                reminder,
                delta=timedelta(hours=1),
                now=now_in_timezone(settings.default_timezone),
            )
            event_name = "reminder_snoozed"
            answer_text = "Перенёс на час"
        elif action == "snooze_tomorrow":
            tomorrow_at = parse_reminder_time_choice(
                "tomorrow_09",
                timezone=settings.default_timezone,
                default_time=settings.default_reminder_time,
            )
            snooze_reminder(
                session,
                reminder,
                remind_at=tomorrow_at or datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
                + timedelta(days=1),
            )
            event_name = "reminder_snoozed"
            answer_text = "Перенёс на завтра"
        else:
            await callback.answer("Неизвестное действие", show_alert=True)
            return
        session.commit()

    track_event(
        session_factory,
        event_name,
        callback.from_user,
        {"reminder_id": reminder_id, "source": "callback"},
        settings=settings,
    )
    await callback.answer(answer_text)
    if isinstance(callback.message, Message):
        await send_user_reminders(callback.message, callback.from_user.id, session_factory)


async def send_user_reminders(
    message: Message,
    telegram_id: int,
    session_factory: sessionmaker[Session],
    empty_reply_markup=None,
) -> None:
    with session_factory() as session:
        reminders = get_user_reminders(session, telegram_id)
    await message.answer(
        format_reminders_list(reminders),
        reply_markup=reminders_keyboard(reminders) if reminders else empty_reply_markup or main_keyboard(),
    )


async def _create_reminder_and_answer(
    message: Message,
    analytics_user,
    telegram_id: int,
    task_text: str,
    remind_at: datetime,
    settings: Settings,
    session_factory: sessionmaker[Session],
    source: str,
) -> None:
    with session_factory() as session:
        reminder = create_reminder(
            session,
            telegram_id=telegram_id,
            task_text=task_text,
            remind_at=remind_at,
            timezone=settings.default_timezone,
        )
        reminder_id = reminder.id
        session.commit()
        session.refresh(reminder)
        created_text = format_reminder_created(reminder)

    track_event(
        session_factory,
        "reminder_created",
        analytics_user,
        {"reminder_id": reminder_id, "source": source},
        settings=settings,
    )
    await message.answer(created_text, reply_markup=main_keyboard())


async def _ask_tomorrow_clarification(message: Message, state: FSMContext, parsed) -> None:
    if parsed.clarification_today_at is None or parsed.clarification_nextday_at is None:
        await message.answer("Когда напомнить?", reply_markup=reminder_time_keyboard())
        return

    await state.update_data(
        task_text=parsed.task_text,
        tomorrow_today_at=parsed.clarification_today_at.isoformat(),
        tomorrow_nextday_at=parsed.clarification_nextday_at.isoformat(),
        timezone=parsed.timezone,
    )
    await state.set_state(ReminderCreation.waiting_for_tomorrow_clarification)
    await message.answer(
        "❓ <b>Уточни дату</b>\n\n"
        "Сейчас уже после полуночи 😴\n\n"
        "Что ты имеешь в виду?\n\n"
        f"1️⃣ Сегодня ({parsed.clarification_today_at.strftime('%H:%M')} через несколько часов)\n\n"
        f"2️⃣ Завтра ({parsed.clarification_nextday_at.strftime('%H:%M')} через день)",
        reply_markup=reminder_tomorrow_clarification_keyboard(),
    )


def _time_parse_error_text() -> str:
    return (
        "Не понял время. Напишите, например:\n\n"
        "через минуту\n\n"
        "через 10\n\n"
        "через 30 минут\n\n"
        "завтра 14:30\n\n"
        "18:00"
    )


def _ask_time_text() -> str:
    return (
        "Когда напомнить?\n\n"
        "Можно выбрать кнопку или написать время текстом, например:\n"
        "через минуту\n"
        "через 10\n"
        "через 30 минут\n"
        "завтра 14:30\n"
        "18:00"
    )


def _manual_time_prompt_text() -> str:
    return (
        "Напишите время, например:\n\n"
        "через минуту\n\n"
        "через 10\n\n"
        "через 30 минут\n\n"
        "завтра 14:30\n\n"
        "18:00"
    )


def _parse_reminder_action(callback_data: str) -> tuple[str, int] | None:
    for prefix in (
        "reminder_complete:",
        "reminder_cancel:",
        "reminder_snooze_hour:",
        "reminder_snooze_tomorrow:",
    ):
        if callback_data.startswith(prefix):
            action = prefix.removeprefix("reminder_").removesuffix(":")
            reminder_id_text = callback_data.removeprefix(prefix)
            try:
                return action, int(reminder_id_text)
            except ValueError:
                return None
    return None
