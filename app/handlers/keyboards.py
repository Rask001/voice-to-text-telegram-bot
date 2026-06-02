from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.handlers.constants import (
    MENU_BACK,
    MENU_HELP,
    MENU_HISTORY,
    MENU_NEW_VOICE,
    MENU_PROFILE,
    MENU_REMINDER_CREATE,
    MENU_REMINDER_CURRENT,
    MENU_REMINDERS,
    MENU_SETTINGS,
    MODE_LABELS,
)
from app.models import Reminder, VoiceNote
from app.payment_service import STARS_TARIFFS
from app.reminder_parser import REMINDER_TIME_CHOICES
from app.tariffs import PREMIUM, STANDARD


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_NEW_VOICE), KeyboardButton(text=MENU_REMINDERS)],
            [KeyboardButton(text=MENU_PROFILE), KeyboardButton(text=MENU_HISTORY)],
            [KeyboardButton(text=MENU_SETTINGS), KeyboardButton(text=MENU_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def reminders_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=MENU_REMINDER_CREATE),
                KeyboardButton(text=MENU_REMINDER_CURRENT),
            ],
            [KeyboardButton(text=MENU_BACK)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def profile_payment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Купить тариф", callback_data="pay:show")]
        ]
    )


def payment_options_keyboard(current_tariff: str | None = None) -> InlineKeyboardMarkup:
    keyboard = []
    standard = STARS_TARIFFS[STANDARD]
    premium = STARS_TARIFFS[PREMIUM]
    if current_tariff != PREMIUM:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"⭐ Standard — {standard['amount']} Stars / 30 дней",
                    callback_data=f"pay:tariff:{STANDARD}",
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                text=f"⭐ Premium — {premium['amount']} Stars / 30 дней",
                callback_data=f"pay:tariff:{PREMIUM}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def note_keyboard(note_id: int, source: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📄 Полный текст",
                    callback_data=f"{source}_full_text:{note_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧠 Подробнее",
                    callback_data=f"{source}_details:{note_id}",
                ),
                InlineKeyboardButton(
                    text="✅ Только задачи",
                    callback_data=f"{source}_tasks:{note_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📤 Поделиться",
                    callback_data=f"{source}_share:{note_id}",
                ),
                InlineKeyboardButton(
                    text="📊 Анализ",
                    callback_data=f"{source}_analysis:{note_id}",
                ),
            ],
        ]
    )


def settings_keyboard(selected_mode: str) -> InlineKeyboardMarkup:
    keyboard = []
    for mode, label in MODE_LABELS.items():
        prefix = "• " if mode == selected_mode else ""
        keyboard.append(
            [InlineKeyboardButton(text=prefix + label, callback_data=f"settings:{mode}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def history_keyboard(notes: list[VoiceNote]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"{index}️⃣", callback_data=f"history:{note.id}")
        for index, note in enumerate(notes, start=1)
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def reminder_time_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=label,
                callback_data=f"remind_time:{choice}",
            )
        ]
        for choice, label in REMINDER_TIME_CHOICES.items()
    ]
    keyboard.append(
        [InlineKeyboardButton(text="Вписать время вручную", callback_data="remind_time:manual")]
    )
    keyboard.append([InlineKeyboardButton(text="Отмена", callback_data="remind_time:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def reminder_fallback_time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Через 1 час", callback_data="remind_time:in_1h")],
            [InlineKeyboardButton(text="Завтра 09:00", callback_data="remind_time:tomorrow_09")],
            [InlineKeyboardButton(text="Завтра 18:00", callback_data="remind_time:tomorrow_18")],
            [InlineKeyboardButton(text="Отмена", callback_data="remind_time:cancel")],
        ]
    )


def reminder_tomorrow_clarification_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Сегодня",
                    callback_data="reminder_tomorrow_today:",
                ),
                InlineKeyboardButton(
                    text="📅 Через день",
                    callback_data="reminder_tomorrow_nextday:",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="reminder_tomorrow_cancel:",
                )
            ],
        ]
    )


def reminder_action_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Выполнено",
                    callback_data=f"reminder_complete:{reminder_id}",
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"reminder_cancel:{reminder_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⏰ Через час",
                    callback_data=f"reminder_snooze_hour:{reminder_id}",
                ),
                InlineKeyboardButton(
                    text="📅 Завтра",
                    callback_data=f"reminder_snooze_tomorrow:{reminder_id}",
                ),
            ],
        ]
    )


def reminders_keyboard(reminders: list[Reminder]) -> InlineKeyboardMarkup:
    keyboard = []
    for index, reminder in enumerate(reminders, start=1):
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"✅ {index}",
                    callback_data=f"reminder_complete:{reminder.id}",
                ),
                InlineKeyboardButton(
                    text=f"🗑 {index}",
                    callback_data=f"reminder_cancel:{reminder.id}",
                ),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
