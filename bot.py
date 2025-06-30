import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from config import BOT_TOKEN
from database import insert_user

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# --- FSM (Машина состояний) для онбординга ---
class OnboardingState(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    # ... и так далее для всех вопросов

# --- Инициализация бота и диспетчера ---
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)


# --- ХЭНДЛЕРЫ ---

async def command_start(message: Message, state: FSMContext):
    """
    Этот хэндлер вызывается при старте.
    """
    await state.clear() # На всякий случай сбрасываем состояние, если пользователь перезапускает
    user_id = message.from_user.id
    tg_name = message.from_user.full_name
    
    logging.info(f"Processing /start command for user {user_id}")
    await insert_user(user_id, tg_name)

    await message.answer(
        "Привет! Далее в сообщениях я запрошу у тебя информацию, которая понадобится "
        "для дальнейшей аналитики и составления персонализированного плана."
    )
    await message.answer("Давай знакомиться. Я уже представился, а как тебя зовут?")
    await state.set_state(OnboardingState.waiting_for_name)


async def process_name(message: Message, state: FSMContext):
    """
    Этот хэндлер сработает, как только пользователь пришлет свое имя.
    """
    await state.update_data(name=message.text)
    await message.answer("Сколько тебе лет?")
    await state.set_state(OnboardingState.waiting_for_age)
    

# --- РЕГИСТРАЦИЯ ХЭНДЛЕРОВ И ЗАПУСК БОТА ---

async def main():
    """Основная функция для запуска бота."""
    dp.message.register(command_start, F.text.startswith("/start"))
    dp.message.register(process_name, OnboardingState.waiting_for_name)
    
    # --- ИСПРАВЛЕНИЕ ДЛЯ TelegramConflictError ---
    # Перед запуском поллинга, мы удаляем вебхук и все накопленные обновления.
    # Это гарантирует, что только наш текущий экземпляр бота будет активен.
    await bot.delete_webhook(drop_pending_updates=True)
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
