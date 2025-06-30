import logging
from typing import Optional

# Импортируем только create_client.
from supabase import create_client 
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Проверяем, что переменные окружения загружены правильно.
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logging.error("CRITICAL: SUPABASE_URL or SUPABASE_SERVICE_KEY are not set!")
    raise ValueError("Supabase URL and Service Key must be set.")
else:
    logging.info(f"Supabase URL: {SUPABASE_URL}")
    logging.info(f"Supabase Service Key is present. Starts with: '{SUPABASE_SERVICE_KEY[:5]}...'")

# Создаем СИНХРОННЫЙ клиент
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# --- СИНХРОННЫЕ Функции для работы с БД ---

def insert_user(telegram_id: int, tg_name: str) -> Optional[dict]:
    """
    СИНХРОННО добавляет пользователя в таблицу `users`, если его ещё нет.
    """
    try:
        # 1. Проверяем, существует ли пользователь (БЕЗ AWAIT)
        response = supabase.table('users').select('id, status').eq('telegram_id', telegram_id).limit(1).execute()
        
        if response.data:
            user_data = response.data[0]
            logging.info(f"User {telegram_id} already exists with status: {user_data.get('status')}")
            return user_data

        # 2. Если пользователя нет — добавляем его
        logging.info(f"User {telegram_id} not found. Creating new user.")
        insert_data = { "telegram_id": telegram_id, "tg_name": tg_name, "status": "onboarding" }
        
        insert_response = supabase.table('users').insert(insert_data).execute()

        if hasattr(insert_response, 'error') and insert_response.error:
            logging.error(f"Failed to insert user {telegram_id}. DB Error: {insert_response.error.message}")
            return None
        
        if insert_response.data:
            logging.info(f"User {telegram_id} created successfully.")
            return insert_response.data[0]
        else:
            logging.warning(f"Insert op for user {telegram_id} returned no data and no error.")
            return None

    except Exception as e:
        logging.error(f"An exception occurred in insert_user for telegram_id {telegram_id}: {e}")
        return None

