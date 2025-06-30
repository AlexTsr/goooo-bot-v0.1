import logging
from typing import Optional

# Импортируем только create_client.
from supabase import create_client 
# AsyncClient убран, т.к. он не предназначен для прямого импорта.
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Проверяем, что переменные окружения загружены правильно.
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logging.error("CRITICAL: SUPABASE_URL or SUPABASE_SERVICE_KEY are not set in environment variables!")
    raise ValueError("Supabase URL and Service Key must be set.")
else:
    logging.info(f"Supabase URL: {SUPABASE_URL}")
    logging.info(f"Supabase Service Key is present. Starts with: '{SUPABASE_SERVICE_KEY[:5]}...'")

# Создаем клиент, используя service_role ключ
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# --- Функции для работы с БД ---

async def insert_user(telegram_id: int, tg_name: str) -> Optional[dict]:
    """
    Добавляет пользователя в таблицу `users`, если его ещё нет.
    """
    try:
        # 1. Проверяем, существует ли пользователь
        response = await supabase.table('users').select('id, status').eq('telegram_id', telegram_id).single().execute()
        
        # single() вернет данные, если запись найдена, или None.
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

        # --- ИСПРАВЛЕННЫЙ БЛОК ПРОВЕРКИ ---
        # Сначала проверяем, есть ли в ответе ошибка
        if hasattr(insert_response, 'error') and insert_response.error:
            logging.error(f"Failed to insert user {telegram_id}. DB Error: {insert_response.error.message}")
            return None
        
        # Если ошибки нет, проверяем наличие данных
        if insert_response.data:
            logging.info(f"User {telegram_id} created successfully.")
            return insert_response.data[0]
        else:
            # На случай, если нет ни ошибки, ни данных
            logging.warning(f"Insert operation for user {telegram_id} returned no data and no error.")
            return None
        # --- КОНЕЦ ИСПРАВЛЕННОГО БЛОКА ---

    except Exception as e:
        logging.error(f"An exception occurred in insert_user for telegram_id {telegram_id}: {e}")
        return None

# В будущем здесь будут другие функции для работы с БД:
# async def save_user_profile(user_id: str, data: dict):
#     response = await supabase.table('user_profile').insert(...).execute()
#     ...
