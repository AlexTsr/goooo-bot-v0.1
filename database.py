import logging
from typing import Optional, Dict, Any

from supabase import create_client 
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logging.error("CRITICAL: SUPABASE_URL or SUPABASE_SERVICE_KEY are not set!")
    raise ValueError("Supabase URL and Service Key must be set.")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    try:
        response = supabase.table('users').select('id, status').eq('telegram_id', telegram_id).limit(1).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logging.error(f"Error fetching user by telegram_id {telegram_id}: {e}")
        return None

def insert_user(telegram_id: int, tg_name: str) -> Optional[dict]:
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
        return None
    except Exception as e:
        logging.error(f"An exception occurred in insert_user for telegram_id {telegram_id}: {e}")
        return None

def save_onboarding_data(user_id: str, data: Dict[str, Any]) -> bool:
    """
    Сохраняет или ОБНОВЛЯЕТ данные онбординга, используя upsert.
    """
    try:
        logging.info(f"Upserting onboarding data for user_id: {user_id}")
        
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
            "personal_bests": {"records": data.get("personal_bests")}
        }
        profile_data = {k: v for k, v in profile_data.items() if v is not None}
        
        # Используем upsert вместо insert
        supabase.table('user_profile').upsert(profile_data).execute()
        logging.info(f"Upserted user_profile for user_id: {user_id}")
        
        preferences_data = {
            "user_id": user_id,
            "training_days_per_week": data.get("training_days_per_week"),
            "preferred_days": data.get("preferred_days"),
            "trainings_per_day": data.get("trainings_per_day")
        }
        preferences_data = {k: v for k, v in preferences_data.items() if v is not None}
        
        # Используем upsert вместо insert
        supabase.table('training_preferences').upsert(preferences_data).execute()
        logging.info(f"Upserted training_preferences for user_id: {user_id}")

        supabase.table('users').update({"status": "active"}).eq("id", user_id).execute()
        logging.info(f"Updated user status to 'active' for user_id: {user_id}")
        
        return True

    except Exception as e:
        logging.error(f"An error occurred in save_onboarding_data for user_id {user_id}: {e}")
        return False
