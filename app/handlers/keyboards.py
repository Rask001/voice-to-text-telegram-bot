from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.handlers.constants import (
    MENU_HELP,
    MENU_HISTORY,
    MENU_NEW_VOICE,
    MENU_PROFILE,
    MENU_SETTINGS,
    MODE_LABELS,
)
from app.models import VoiceNote


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_NEW_VOICE)],
            [KeyboardButton(text=MENU_PROFILE), KeyboardButton(text=MENU_HISTORY)],
            [KeyboardButton(text=MENU_SETTINGS), KeyboardButton(text=MENU_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


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
                )
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
