from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session, sessionmaker

from app.analytics_service import track_event
from app.config import Settings
from app.formatters import help_text
from app.handlers.keyboards import main_keyboard
from app.handlers.profile import build_profile_text


router = Router()


@router.message(CommandStart())
async def start(
    message: Message,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is not None:
        track_event(session_factory, "user_started", message.from_user, settings=settings)

    await message.answer(
        "Привет! Я <b>Voice to Text</b> — бот, который превращает голосовые "
        "в нормальный текст.\n\n"
        "Что умею:\n"
        "🎙 Расшифровываю голосовые\n"
        "🧠 Делаю краткое содержание\n"
        "✅ Выделяю задачи\n"
        "📌 Нахожу важные пункты\n"
        "📄 Показываю полный текст отдельно\n\n"
        "Как пользоваться:\n"
        "1. Просто отправь мне голосовое.\n"
        "2. Я сам расшифрую его.\n"
        "3. Верну короткий результат.\n"
        "4. Полный текст можно открыть кнопкой.\n\n"
        "Бесплатно доступно: 3 голосовых сообщения в день.\n\n"
        "Отправь голосовое — и погнали.",
        reply_markup=main_keyboard(),
    )


@router.callback_query(F.data.startswith("start:"))
async def start_callback(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    action = callback.data.split(":", 1)[1] if callback.data else ""
    if action == "voice":
        await callback.answer("Отправь обычное голосовое сообщение 🎙", show_alert=True)
    elif action == "profile":
        await callback.answer("Открываю профиль...")
        if isinstance(callback.message, Message):
            track_event(session_factory, "profile_opened", callback.from_user, settings=settings)
            await callback.message.answer(
                build_profile_text(
                    callback.from_user.id,
                    callback.from_user.full_name,
                    callback.from_user.username,
                    settings,
                    session_factory,
                ),
                reply_markup=main_keyboard(),
            )
    elif action == "help":
        await callback.answer("Открываю помощь...")
        if isinstance(callback.message, Message):
            await callback.message.answer(help_text(), reply_markup=main_keyboard())
