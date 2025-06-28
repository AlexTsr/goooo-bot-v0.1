import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database import insert_user

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(F.text.startswith('/start'))
async def start(message: Message):
    insert_user(message.from_user.id, message.from_user.full_name)
    await message.answer("Привет! Я Goooo — помогу с планами тренировок и питания.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
