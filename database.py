import logging
from typing import Optional, Dict, Any

from supabase_async import create_client, AsyncClient
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("Supabase URL and Service Key must be set.")

supabase: AsyncClient = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    try:
        response = await supabase.table('users').select('id, status').eq('telegram_id', telegram_id).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logging.error(f"Error fetching user by telegram_id {telegram_id}: {e}")
        return None

async def insert_user(telegram_id: int, tg_name: str) -> Optional[dict]:
    try:
        existing_user = await get_user_by_telegram_id(telegram_id)
        if existing_user:
            return existing_user
        insert_data = { "telegram_id": telegram_id, "tg_name": tg_name, "status": "onboarding" }
        response = await supabase.table('users').insert(insert_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logging.error(f"An exception occurred in insert_user for telegram_id {telegram_id}: {e}")
        return None

async def save_onboarding_data(user_id: str, data: Dict[str, Any]) -> bool:
    try:
        profile_data = {
            "name": data.get("name"), "age": data.get("age"), "height_cm": data.get("height"),
            "initial_weight_kg": data.get("weight"), "goal": data.get("goal"),
            "experience": data.get("experience"), "motivation": data.get("motivation"),
            "demotivation": data.get("demotivation"), "current_injuries": data.get("current_injuries"),
            "recurring_injuries": data.get("recurring_injuries"), "equipment": data.get("equipment"),
            "infrastructure": data.get("infrastructure"), "dietary_restrictions": data.get("dietary_restrictions"),
            "personal_bests": {"records": data.get("personal_bests")},
            "weekly_volume_km": data.get("weekly_volume_km"),
            "additional_info": data.get("additional_info")
        }
        preferences_data = {
            "training_days_per_week": data.get("training_days_per_week"),
            "preferred_days": data.get("preferred_days"),
            "trainings_per_day": data.get("trainings_per_day"),
            "long_run_day": data.get("long_run_day")
        }
        await supabase.rpc('upsert_user_onboarding_data', {
            'p_user_id': user_id,
            'p_profile_data': profile_data,
            'p_preferences_data': preferences_data
        }).execute()
        return True
    except Exception as e:
        logging.error(f"An error occurred in save_onboarding_data RPC for user_id {user_id}: {e}")
        return False

async def get_full_user_profile(user_id: str) -> Optional[dict]:
    try:
        response = await supabase.rpc('get_user_complete_profile', {'p_user_id': user_id}).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logging.error(f"An error occurred in get_full_user_profile for user_id {user_id}: {e}")
        return None

async def save_generated_plan(user_id: str, week_start_date: str, plan_data: dict) -> bool:
    try:
        training_plan = plan_data.get("training_plan")
        workout_details = plan_data.get("workout_details")
        if training_plan:
            full_training_details = {"schedule": training_plan, "details": workout_details}
            await supabase.table('training_plans').upsert({"user_id": user_id, "week_start_date": week_start_date, "plan_details": full_training_details}, on_conflict="user_id,week_start_date").execute()

        meal_plan = plan_data.get("meal_plan")
        shopping_list = plan_data.get("shopping_list")
        if meal_plan:
            shopping_list_str = ""
            if isinstance(shopping_list, list):
                for category in shopping_list:
                    shopping_list_str += f"**{category.get('category')}**\n"
                    for item in category.get('items', []):
                        shopping_list_str += f"- {item}\n"
            await supabase.table('meal_plans').upsert({"user_id": user_id, "week_start_date": week_start_date, "plan_details": meal_plan, "shopping_list": shopping_list_str}, on_conflict="user_id,week_start_date").execute()
        return True
    except Exception as e:
        logging.error(f"An error occurred in save_generated_plan for user {user_id}: {e}")
        return False
