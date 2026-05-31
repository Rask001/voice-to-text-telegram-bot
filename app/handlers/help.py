from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.formatters import help_text
from app.handlers.keyboards import main_keyboard


router = Router()


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(help_text(), reply_markup=main_keyboard())
