from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from config import BOT_TOKEN
from database import insert_user

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    insert_user(message.from_user.id, message.from_user.full_name)
    await message.reply("Привет! Я Goooo — помогу с планами тренировок и питания.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
