import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties # <-- Импортируем новый класс
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from config import BOT_TOKEN
from database import insert_user

# Включаем логирование, чтобы видеть в консоли все шаги
logging.basicConfig(level=logging.INFO)

# --- FSM (Машина состояний) для онбординга ---
# Здесь мы определим все шаги (состояния), которые пройдет пользователь
class OnboardingState(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_height = State()
    # ... и так далее для всех вопросов из onboarding.txt
    # Мы добавим их по мере написания кода

# --- Инициализация бота и диспетчера ---

# Используем MemoryStorage, но помним, что для продакшена лучше Redis
storage = MemoryStorage()

# Вот исправленная строка:
# Мы передаем параметры по умолчанию через специальный объект DefaultBotProperties
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)


# --- ХЭНДЛЕРЫ ---

# Этот хэндлер будет срабатывать на команду /start
async def command_start(message: Message, state: FSMContext):
    """
    Этот хэндлер вызывается при старте. Он добавляет пользователя в БД,
    приветствует его и запускает процесс онбординга (переводит в первое состояние).
    """
    user_id = message.from_user.id
    tg_name = message.from_user.full_name
    
    # Добавляем пользователя в БД (функция осталась прежней)
    await insert_user(user_id, tg_name)

    # Приветственное сообщение из файла onboarding.txt
    await message.answer(
        "Привет! Далее в сообщениях я запрошу у тебя информацию, которая понадобится "
        "для дальнейшей аналитики и составления персонализированного плана. Опрос разбит "
        "на несколько блоков - о тебе,о твоих целях и мотивациях, о беговом опыте и травмах, "
        "об инвентаре и доступной спортивной инфраструктуре, о пищевых предпочтениях."
    )
    # Задаем первый вопрос и переводим FSM в состояние ожидания имени
    await message.answer("Давай знакомиться. Я уже представился, а как тебя зовут?")
    await state.set_state(OnboardingState.waiting_for_name)


# Этот хэндлер будет ловить ответ на вопрос "Как тебя зовут?"
async def process_name(message: Message, state: FSMContext):
    """
    Этот хэндлер сработает, как только пользователь пришлет свое имя.
    Он сохранит имя и задаст следующий вопрос.
    """
    # Сохраняем имя во временное хранилище FSM
    await state.update_data(name=message.text)
    
    # Задаем следующий вопрос
    await message.answer("Сколько тебе лет?")
    
    # Переводим машину в следующее состояние
    await state.set_state(OnboardingState.waiting_for_age)
    
# Сюда мы будем добавлять обработчики для остальных вопросов...


# --- РЕГИСТРАЦИЯ ХЭНДЛЕРОВ И ЗАПУСК БОТА ---

async def main():
    """Основная функция для запуска бота."""
    # Регистрируем хэндлеры в диспетчере
    dp.message.register(command_start, F.text.startswith("/start"))
    
    # Регистрируем хэндлер для состояния "ожидания имени"
    dp.message.register(process_name, OnboardingState.waiting_for_name)

    # Запускаем поллинг (опрос серверов Telegram на наличие новых сообщений)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
