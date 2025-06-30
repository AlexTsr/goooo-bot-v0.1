import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN

# --- 1. Настраиваем детальное логирование ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
)
logger = logging.getLogger(__name__)

# --- 2. Основная функция ---
async def main():
    if not BOT_TOKEN:
        logger.critical("!!! КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не найден. Бот не может запуститься.")
        return

    logger.info("--- Запуск минимального диагностического бота ---")
    logger.info(f"Токен бота присутствует. Начинается с: {BOT_TOKEN[:5]}...")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Диспетчер пока пустой, нам не нужны обработчики
    dp = Dispatcher()

    # --- 3. Агрессивный сброс сессии ---
    try:
        logger.info("Попытка удалить существующий вебхук...")
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Вебхук успешно удален. Ожидание 3 секунды перед запуском...")
        await asyncio.sleep(3) # Даем серверам Telegram время на обработку
    except Exception as e:
        logger.error(f"Произошла ошибка при удалении вебхука: {e}")
        # Все равно продолжаем, это может быть не фатально

    # --- 4. Запуск опроса ---
    logger.info("Попытка запуска опроса (polling)...")
    try:
        # Этот процесс будет работать, пока бот не будет остановлен.
        # Если здесь возникнет ошибка, мы увидим ее в логах.
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"!!! КРИТИЧЕСКАЯ ОШИБКА при запуске опроса: {e}", exc_info=True)
    finally:
        logger.warning("Опрос остановлен.")
        await bot.session.close()
        logger.info("Сессия бота закрыта.")

# --- 5. Запуск ---
if __name__ == "__main__":
    logger.info("--- Скрипт bot.py запущен ---")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем (KeyboardInterrupt).")

