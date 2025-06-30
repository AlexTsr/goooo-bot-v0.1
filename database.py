import logging
from typing import Optional, Dict, Any

from supabase import create_client 
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Добавляем строку для проверки версии
logging.info("--- Loading database.py version: RPC_V1 ---")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("Supabase URL and Service Key must be set.")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

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
    """Создает пользователя, если его нет."""
    try:
        existing_user = get_user_by_telegram_id(telegram_id)
        if existing_user:
            return existing_user
        insert_data = { "telegram_id": telegram_id, "tg_name": tg_name, "status": "onboarding" }
        insert_response = supabase.table('users').insert(insert_data).execute()
        if insert_response.data:
            return insert_response.data[0]
        return None
    except Exception as e:
        logging.error(f"An exception occurred in insert_user for telegram_id {telegram_id}: {e}")
        return None

def save_onboarding_data(user_id: str, data: Dict[str, Any]) -> bool:
    """
    Вызывает хранимую процедуру в БД для сохранения или обновления данных.
    """
    try:
        logging.info(f"Calling RPC for onboarding data for user_id: {user_id}")
        
        # 1. Готовим данные для profile в формате JSON
        profile_data = {
            "name": data.get("name"), "age": data.get("age"), "height_cm": data.get("height"),
            "initial_weight_kg": data.get("weight"), "goal": data.get("goal"),
            "experience": data.get("experience"), "motivation": data.get("motivation"),
            "demotivation": data.get("demotivation"), "current_injuries": data.get("current_injuries"),
            "recurring_injuries": data.get("recurring_injuries"), "equipment": data.get("equipment"),
            "infrastructure": data.get("infrastructure"), "dietary_restrictions": data.get("dietary_restrictions"),
            "personal_bests": {"records": data.get("personal_bests")}
        }
        
        # 2. Готовим данные для preferences в формате JSON
        preferences_data = {
            "training_days_per_week": data.get("training_days_per_week"),
            "preferred_days": data.get("preferred_days"),
            "trainings_per_day": data.get("trainings_per_day")
        }

        # 3. Вызываем функцию 'upsert_user_onboarding_data' в БД через RPC (Remote Procedure Call)
        supabase.rpc('upsert_user_onboarding_data', {
            'p_user_id': user_id,
            'p_profile_data': profile_data,
            'p_preferences_data': preferences_data
        }).execute()

        logging.info(f"Successfully called RPC for user_id: {user_id}")
        return True

    except Exception as e:
        logging.error(f"An error occurred in save_onboarding_data RPC for user_id {user_id}: {e}")
        return False

# добавление с LLM номер 1
def get_full_user_profile(user_id: str) -> Optional[dict]:
    """
    Собирает полную информацию о пользователе из таблиц user_profile и training_preferences.
    """
    try:
        # Вызываем хранимую процедуру, которая объединяет данные
        # Это эффективнее, чем делать несколько запросов
        response = supabase.rpc('get_user_complete_profile', {'p_user_id': user_id}).execute()
        
        if response.data:
            logging.info(f"Successfully fetched full profile for user_id: {user_id}")
            return response.data[0]
        else:
            logging.warning(f"No full profile found for user_id: {user_id}")
            return None

    except Exception as e:
        logging.error(f"An error occurred in get_full_user_profile for user_id {user_id}: {e}")
        return None
        
# добавление с LLM номер 2
def save_generated_plan(user_id: str, week_start_date: str, plan_data: dict) -> bool:
    """
    Сохраняет сгенерированный план тренировок и питания в базу данных.
    """
    try:
        # 1. Сохраняем план тренировок
        training_plan = plan_data.get("training_plan")
        if training_plan:
            supabase.table('training_plans').upsert({
                "user_id": user_id,
                "week_start_date": week_start_date,
                "plan_details": training_plan
            }).execute()
            logging.info(f"Saved training plan for user {user_id}")

        # 2. Сохраняем план питания
        meal_plan = plan_data.get("meal_plan")
        shopping_list = plan_data.get("shopping_list")
        if meal_plan:
            supabase.table('meal_plans').upsert({
                "user_id": user_id,
                "week_start_date": week_start_date,
                "plan_details": meal_plan,
                "shopping_list": "\n".join(shopping_list) if shopping_list else ""
            }).execute()
            logging.info(f"Saved meal plan for user {user_id}")
        
        return True
    except Exception as e:
        logging.error(f"An error occurred in save_generated_plan for user {user_id}: {e}")
        return False