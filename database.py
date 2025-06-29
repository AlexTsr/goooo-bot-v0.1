import logging
from typing import Optional

# Импортируем из официальной библиотеки supabase
from supabase.lib.client_async import create_async_client, AsyncClient
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)

# --- Правильный способ создания асинхронного клиента ---
# Мы не можем создать клиент на верхнем уровне модуля, т.к. его создание - асинхронная операция.
# Поэтому мы будем создавать его один раз при первом вызове и переиспользовать.
_supabase_client: Optional[AsyncClient] = None

async def get_supabase_client() -> AsyncClient:
    """
    Асинхронно инициализирует и возвращает клиент Supabase.
    Использует "ленивую" инициализацию, чтобы клиент создавался только один раз.
    """
    global _supabase_client
    if _supabase_client is None:
        logging.info("Initializing Supabase client for the first time...")
        # Используем service_role ключ, который имеет полные права доступа к БД
        _supabase_client = await create_async_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logging.info("Supabase client initialized.")
    return _supabase_client

# --- Функции для работы с БД ---

async def insert_user(telegram_id: int, tg_name: str) -> Optional[dict]:
    """
    Добавляет пользователя в таблицу `users`, если его ещё нет.
    """
    try:
        # Получаем клиент
        supabase = await get_supabase_client()
        
        # 1. Проверяем, существует ли пользователь
        response = await supabase.table('users').select('id, status').eq('telegram_id', telegram_id).single().execute()
        
        # single() вернет данные, если запись найдена, или None. Это удобнее.
        if response.data:
            logging.info(f"User {telegram_id} already exists with status: {response.data.get('status')}")
            return response.data

        # 2. Если пользователя нет — добавляем его
        logging.info(f"User {telegram_id} not found. Creating new user.")
        insert_data = {
            "telegram_id": telegram_id,
            "tg_name": tg_name,
            "status": "onboarding"
        }
        
        insert_response = await supabase.table('users').insert(insert_data).execute()

        if insert_response.data:
            logging.info(f"User {telegram_id} created successfully.")
            return insert_response.data[0]
        else:
            # Логируем ошибку, если она есть в ответе от Supabase
            logging.error(f"Failed to insert user {telegram_id}. Response: {insert_response}")
            return None

    except Exception as e:
        logging.error(f"An error occurred in insert_user for telegram_id {telegram_id}: {e}")
        return None

# В будущем здесь будут другие функции для работы с БД:
# async def save_user_profile(user_id: str, data: dict):
#     supabase = await get_supabase_client()
#     ...
