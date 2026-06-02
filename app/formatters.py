from datetime import date, datetime, timedelta
from html import escape

from app.access import AccessStatus
from app.models import Reminder
from app.preferences import normalize_response_mode
from app.tasks import TaskItem, normalize_tasks, parse_stored_tasks, sort_tasks_for_display
from app.voice_analysis import (
    VoiceAnalysis,
    format_compact_duration,
    format_duration,
    voice_type,
    water_class,
)


TELEGRAM_TEXT_LIMIT = 3900


def format_response(
    mode: str,
    transcript: str,
    analysis: dict[str, object],
) -> str:
    normalized_mode = normalize_response_mode(mode)
    action_items = normalize_tasks(analysis["action_items"])
    important_points = analysis_list(analysis["important_points"])
    summary = str(analysis["summary"])
    details = str(analysis.get("details", ""))

    if normalized_mode == "tasks":
        return format_tasks(action_items)

    if normalized_mode == "full":
        return format_details(summary, action_items, details, important_points)

    return format_short(summary, action_items)


def format_short(summary: str, action_items: list[TaskItem]) -> str:
    return "\n\n".join(
        [
            "🧠 <b>Кратко:</b>\n" + escape(trim_plain(summary, limit=450)),
            format_tasks(action_items),
        ]
    )


def format_details(
    summary: str,
    action_items: list[TaskItem],
    details: str,
    important_points: list[str],
) -> str:
    details_block = escape(trim_plain(details, limit=1000)) if details else format_list(important_points)
    return "\n\n".join(
        [
            "🧠 <b>Кратко:</b>\n" + escape(trim_plain(summary, limit=700)),
            format_tasks(action_items),
            "💡 <b>Подробнее:</b>\n" + details_block,
        ]
    )


def format_tasks(action_items: list[TaskItem]) -> str:
    return "✅ <b>Задачи:</b>\n" + format_numbered_list(action_items)


def format_share(
    summary: str,
    action_items: list[TaskItem],
    voice_analysis: VoiceAnalysis | None = None,
) -> str:
    parts = [
        "📝 <b>Расшифровка голосового</b>",
        "",
        "🧠 <b>Кратко:</b>",
        escape(trim_plain(summary, limit=700)) or "Нет краткого содержания.",
        "",
        format_tasks(action_items),
    ]
    if voice_analysis is not None:
        parts.extend(["", format_share_voice_analysis(voice_analysis)])
    parts.extend(
        [
            "",
            "🎙Создано через: @voitext_bot",
        ]
    )
    return "\n".join(parts)


def format_voice_analysis(
    voice_analysis: VoiceAnalysis,
    total_saved_seconds: int,
) -> str:
    water_emoji, water_text = water_class(voice_analysis["water_level"])
    parts = [
        "📊 <b>Анализ голосового</b>",
        "",
        f"🎙 Длительность: <b>{format_duration(voice_analysis['duration_seconds'])}</b>",
        f"🧠 Содержательная часть: <b>{format_duration(voice_analysis['meaningful_duration_seconds'])}</b>",
        "",
        f"💧 Индекс воды: <b>{voice_analysis['water_percent']}%</b>",
        f"{water_emoji} Класс воды: <b>{escape(water_text)}</b>",
        "",
        f"🗣 Многословность: <b>{voice_analysis['wordiness_score']:.1f} / 10</b>",
        f"🎭 Тип: <b>{escape(voice_type(voice_analysis['voice_type_level']))}</b>",
        "",
        f"⭐ Оценка: <b>{voice_analysis['quality_score']:.1f} / 10</b>",
    ]
    if voice_analysis["rare_title"]:
        parts.extend(["", f"🏆 Титул: <b>{escape(voice_analysis['rare_title'])}</b>"])
    if voice_analysis["memorable_quote"]:
        parts.extend(
            [
                "",
                "🎤 <b>Цитата выпуска:</b>",
                f"“{escape(voice_analysis['memorable_quote'])}”",
            ]
        )
    parts.extend(
        [
            "",
            "🤖 <b>Вердикт:</b>",
            escape(voice_analysis["verdict"]),
            "",
            "😂",
            escape(voice_analysis["meme"]),
            "",
            f"⏱ Ты сэкономил: <b>{format_duration(voice_analysis['saved_seconds'])}</b>",
            f"🏆 Всего сэкономлено: <b>{format_duration(total_saved_seconds)}</b>",
            "",
            "@voitext_bot",
        ]
    )
    return "\n".join(parts)


def format_share_voice_analysis(voice_analysis: VoiceAnalysis) -> str:
    return "\n".join(
        [
            f"🎙 Голосовое: <b>{format_compact_duration(voice_analysis['duration_seconds'])}</b>",
            f"🧠 Суть: <b>{format_compact_duration(voice_analysis['meaningful_duration_seconds'])}</b>",
            f"💧 Воды: <b>{voice_analysis['water_percent']}%</b>",
            f"🎭 Тип: <b>{escape(voice_type(voice_analysis['voice_type_level']))}</b>",
            "",
            "😂",
            escape(voice_analysis["meme"]),
            "",
            f"⏱ Сэкономлено: <b>{format_compact_duration(voice_analysis['saved_seconds'])}</b>",
        ]
    )


def format_history(notes) -> str:
    lines = ["📚 <b>История</b>"]
    for index, note in enumerate(notes, start=1):
        lines.extend(
            [
                "",
                f"{index}. <b>{escape(note_title(note))}</b> — {format_note_date(note.created_at)}",
                "   " + escape(trim_plain(note.summary or "Без краткого содержания.", limit=140)),
            ]
        )
    return "\n".join(lines)


def format_history_item(note) -> str:
    action_items = parse_stored_tasks(note.action_items)
    return "\n\n".join(
        [
            f"📌 <b>{escape(note_title(note))}</b>",
            f"Дата: <b>{format_note_date(note.created_at)}</b>",
            "🧠 <b>Кратко:</b>\n" + escape(trim_plain(note.summary or "", limit=700)),
            format_tasks(action_items),
        ]
    )


def note_title(note) -> str:
    if note.title:
        return note.title
    return fallback_title(note.created_at.date() if note.created_at else date.today())


def format_settings(mode: str, mode_labels: dict[str, str]) -> str:
    return (
        "<b>Настройки ответа</b>\n\n"
        f"Текущий режим: <b>{escape(mode_labels[normalize_response_mode(mode)])}</b>\n\n"
        "Выберите формат ответа после голосового:"
    )


def format_profile(
    full_name: str,
    username: str | None,
    access_status: AccessStatus,
) -> str:
    remaining = "∞" if access_status.remaining_today is None else str(access_status.remaining_today)
    daily_limit = "∞" if access_status.daily_limit is None else str(access_status.daily_limit)
    month_limit = "∞" if access_status.minutes_limit_month is None else str(access_status.minutes_limit_month)
    month_remaining = (
        "∞"
        if access_status.minutes_remaining_month is None
        else str(access_status.minutes_remaining_month)
    )
    total_limit = "∞" if access_status.minutes_limit_total is None else str(access_status.minutes_limit_total)
    total_remaining = (
        "∞"
        if access_status.minutes_remaining_total is None
        else str(access_status.minutes_remaining_total)
    )
    trial_days = (
        "—"
        if access_status.trial_days_left is None
        else str(access_status.trial_days_left)
    )
    username_text = f"@{username}" if username else "не указан"
    reset_text = f"{access_status.reset_date.isoformat()} 00:00"
    expires_text = (
        ""
        if access_status.tariff_expires_at is None
        else f"\n\nТариф активен до:\n<b>{format_datetime(access_status.tariff_expires_at)}</b>"
    )
    return (
        "👤 <b>Профиль</b>\n\n"
        f"Имя: <b>{escape(full_name)}</b>\n"
        f"Username: <b>{escape(username_text)}</b>\n\n"
        f"Тариф:\n<b>{escape(access_status.tariff)}</b>\n\n"
        f"Использовано сегодня:\n<b>{access_status.used_today}</b>\n\n"
        f"Осталось сегодня:\n<b>{remaining}</b>\n\n"
        f"Дневной лимит:\n<b>{daily_limit}</b>\n\n"
        f"Минуты в этом месяце:\n"
        f"<b>{access_status.minutes_used_this_month} / {month_limit}</b>\n\n"
        f"Осталось минут в месяце:\n<b>{month_remaining}</b>\n\n"
        f"Минуты всего:\n"
        f"<b>{access_status.minutes_used_total} / {total_limit}</b>\n\n"
        f"Осталось минут всего:\n<b>{total_remaining}</b>\n\n"
        f"⏱ Сэкономлено времени:\n<b>{format_duration(access_status.total_saved_seconds)}</b>\n\n"
        f"Осталось дней пробного периода:\n<b>{trial_days}</b>\n\n"
        f"Сброс лимита:\n<b>{reset_text}</b>"
        f"{expires_text}"
    )


def format_my_id(telegram_id: int) -> str:
    return (
        "🆔 <b>Ваш Telegram ID</b>\n\n"
        f"<code>{telegram_id}</code>\n\n"
        "Отправьте этот ID Тоше, если он попросил."
    )


def format_reminders_list(reminders: list[Reminder]) -> str:
    if not reminders:
        return "🔔 У вас пока нет активных напоминаний."

    lines = ["🔔 <b>Активные напоминания</b>"]
    for index, reminder in enumerate(reminders, start=1):
        lines.append(
            "\n"
            f"{index}. <b>{format_datetime(reminder.remind_at)}</b>\n"
            f"{escape(reminder.task_text)}"
        )
    return "\n".join(lines)


def format_reminder_created(reminder: Reminder) -> str:
    return (
        "✅ <b>Напоминание создано</b>\n\n"
        f"🔔 {escape(reminder.task_text)}\n"
        f"📅 <b>{format_datetime(reminder.remind_at)}</b>"
    )


def format_datetime(value: datetime) -> str:
    return value.strftime("%d.%m.%Y %H:%M")


def help_text() -> str:
    return (
        "❓ <b>Помощь</b>\n\n"
        "Я работаю только с обычными voice messages 🎙\n"
        "Текст, фото, файлы, кружки и аудиофайлы пока не обрабатываю.\n\n"
        "История обработок: /history или кнопка 📚 История.\n"
        "Напоминания: /reminders или кнопка 🔔 Напомни.\n"
        "Создать напоминание вручную: /remind.\n"
        "Профиль и лимиты: /profile или кнопка 👤 Профиль.\n"
        "Ваш Telegram ID: /my_id.\n"
        "📤 Поделиться создаёт отдельный блок, который удобно переслать вручную."
    )


def format_list(items: list[str] | str) -> str:
    if not isinstance(items, list) or not items:
        return "Нет."
    return "\n".join(f"- {escape(item)}" for item in items)


def format_numbered_list(items: list[TaskItem]) -> str:
    if not items:
        return "Задачи не найдены."
    lines = []
    for index, item in enumerate(sort_tasks_for_display(items), start=1):
        text = escape(str(item["text"]))
        if item["priority"]:
            lines.append(f"{index}. <b>{text}</b> ❗")
        else:
            lines.append(f"{index}. {text}")
    return "\n".join(lines)


def analysis_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()] if value else []


def fallback_title(note_date: date) -> str:
    return f"Голосовое от {note_date.strftime('%d.%m')}"


def format_note_date(value: datetime | None) -> str:
    if value is None:
        return ""
    today = date.today()
    note_date = value.date()
    if note_date == today:
        return "сегодня"
    if note_date == today - timedelta(days=1):
        return "вчера"
    return note_date.strftime("%d.%m.%Y")


def trim(text: str, limit: int) -> str:
    return escape(trim_plain(text, limit=limit))


def trim_plain(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n..."
