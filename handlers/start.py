from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from database.db import add_user


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):
    user = await add_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        name=message.from_user.full_name,
    )

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Ты добавлен в систему AladinChat.\n\n"
        "🧠 Память пользователя создана.\n"
        "💬 История сообщений готова.\n\n"
        "Система находится в разработке."
    )