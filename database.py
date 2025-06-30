import logging
from typing import Optional, Dict, Any

# Импортируем только create_client.
from supabase import create_client 
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Проверяем, что переменные окружения загружены правильно.
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logging.error("CRITICAL: SUPABASE_URL or SUPABASE_SERVICE_KEY are not set!")
    raise ValueError("Supabase URL and Service Key must be set.")

# Создаем СИНХРОННЫЙ клиент
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# --- СИНХРОННЫЕ Функции для работы с БД ---

def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    """Находит пользователя по его telegram_id и возвращает его запись из таблицы users."""
    try:
        response = supabase.table('users').select('id, status').eq('telegram_id', telegram_id).limit(1).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logging.error(f"Error fetching user by telegram_id {telegram_id}: {e}")
        return None

def insert_user(telegram_id: int, tg_name: str) -> Optional[dict]:
    """
    СИНХРОННО добавляет пользователя в таблицу `users`, если его ещё нет.
    """
    try:
        existing_user = get_user_by_telegram_id(telegram_id)
        if existing_user:
            logging.info(f"User {telegram_id} already exists with status: {existing_user.get('status')}")
            return existing_user

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

def save_onboarding_data(user_id: str, data: Dict[str, Any]) -> bool:
    """
    Сохраняет данные онбординга в таблицы user_profile и training_preferences,
    а затем обновляет статус пользователя на 'active'.
    """
    try:
        logging.info(f"Saving onboarding data for user_id: {user_id}")
        
        # 1. Сохраняем данные в user_profile
        profile_data = {
            "user_id": user_id,
            "name": data.get("name"),
            "age": data.get("age"),
            "height_cm": data.get("height"),
            "initial_weight_kg": data.get("weight"),
            "goal": data.get("goal"),
            "experience": data.get("experience"),
            "motivation": data.get("motivation"),
            "demotivation": data.get("demotivation"),
            "current_injuries": data.get("current_injuries"),
            "recurring_injuries": data.get("recurring_injuries"),
            "equipment": data.get("equipment"),
            "infrastructure": data.get("infrastructure"),
            "dietary_restrictions": data.get("dietary_restrictions"),
            "personal_bests": {"records": data.get("personal_bests")} # Сохраняем как JSON
        }
        # Удаляем ключи с None, чтобы не перезаписывать их в БД
        profile_data = {k: v for k, v in profile_data.items() if v is not None}
        
        supabase.table('user_profile').insert(profile_data).execute()
        logging.info(f"Saved user_profile for user_id: {user_id}")
        
        # 2. Сохраняем данные в training_preferences
        preferences_data = {
            "user_id": user_id,
            "training_days_per_week": data.get("training_days_per_week"),
            "preferred_days": data.get("preferred_days"),
            "trainings_per_day": data.get("trainings_per_day")
        }
        preferences_data = {k: v for k, v in preferences_data.items() if v is not None}
        
        supabase.table('training_preferences').insert(preferences_data).execute()
        logging.info(f"Saved training_preferences for user_id: {user_id}")

        # 3. Обновляем статус пользователя на 'active'
        supabase.table('users').update({"status": "active"}).eq("id", user_id).execute()
        logging.info(f"Updated user status to 'active' for user_id: {user_id}")
        
        return True

    except Exception as e:
        logging.error(f"An error occurred in save_onboarding_data for user_id {user_id}: {e}")
        return False
