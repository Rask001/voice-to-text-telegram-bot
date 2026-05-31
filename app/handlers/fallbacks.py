from aiogram import F, Router
from aiogram.types import Message

from app.handlers.keyboards import main_keyboard


router = Router()


@router.message(F.text)
async def text_fallback(message: Message) -> None:
    await message.answer(
        "Я пока работаю с голосовыми сообщениями 🎙\n\n"
        "Отправь voice message — я расшифрую его, сделаю краткое содержание "
        "и выделю задачи.",
        reply_markup=main_keyboard(),
    )


@router.message(F.photo | F.document | F.video | F.video_note | F.audio)
async def unsupported_media(message: Message) -> None:
    await message.answer(
        "Пока я работаю только с обычными голосовыми сообщениями 🎙\n\n"
        "Фото, файлы, кружки и аудиофайлы добавим позже.",
        reply_markup=main_keyboard(),
    )


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(
        "Пока я работаю только с обычными голосовыми сообщениями 🎙\n\n"
        "Отправь voice message — я расшифрую его, сделаю краткое содержание "
        "и выделю задачи.",
        reply_markup=main_keyboard(),
    )
