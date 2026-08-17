import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from dotenv import load_dotenv

from database.db import init_db, close_db
from handlers.start import router as start_router


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден")


dp = Dispatcher()

dp.include_router(start_router)


async def main():
    print("Запуск AladinChat...")

    await init_db()

    bot = Bot(token=BOT_TOKEN)

    print("AladinChat запущен!")

    try:
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())