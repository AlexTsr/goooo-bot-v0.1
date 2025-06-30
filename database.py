import logging
from typing import Optional, Dict, Any
from datetime import date
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("Supabase URL and Service Key must be set")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    try:
        response = supabase.table('users').select('id, status').eq('telegram_id', telegram_id).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logging.error(f"Error fetching user by telegram_id {telegram_id}: {e}")
        return None

def insert_user(telegram_id: int, tg_name: str) -> Optional[dict]:
    try:
        existing_user = get_user_by_telegram_id(telegram_id)
        if existing_user:
            return existing_user
        insert_data = {"telegram_id": telegram_id, "tg_name": tg_name, "status": "onboarding"}
        response = supabase.table('users').insert(insert_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logging.error(f"Error inserting user {telegram_id}: {e}")
        return None

def save_onboarding_data(user_id: str, data: Dict[str, Any]) -> bool:
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
        supabase.rpc('upsert_user_onboarding_data', {
            'p_user_id': user_id,
            'p_profile_data': profile_data,
            'p_preferences_data': preferences_data
        }).execute()
        logging.info(f"Saved onboarding data for user {user_id}")
        return True
    except Exception as e:
        logging.error(f"Error saving onboarding data for user {user_id}: {e}")
        return False

def get_full_user_profile(user_id: str) -> Optional[dict]:
    try:
        response = supabase.rpc('get_user_complete_profile', {'p_user_id': user_id}).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logging.error(f"Error fetching profile for user {user_id}: {e}")
        return None

def save_generated_plan(user_id: str, week_start_date: str, plan_data: dict) -> bool:
    try:
        training_plan_data = {
            "intro_summary": plan_data.get("intro_summary"),
            "training_plan": plan_data.get("training_plan"),
            "workout_details": plan_data.get("workout_details"),
            "general_recommendations": plan_data.get("general_recommendations")
        }
        supabase.table('training_plans').insert({
            "user_id": user_id,
            "week_start_date": week_start_date,
            "plan_details": training_plan_data
        }).execute()

        meal_plan = plan_data.get("meal_plan")
        shopping_list = plan_data.get("shopping_list")
        if meal_plan:
            shopping_list_str = "\n".join(
                f"**{cat['category']}**\n" + "\n".join(f"- {item}" for item in cat.get('items', []))
                for cat in shopping_list or []
            ) if shopping_list else ""
            supabase.table('meal_plans').insert({
                "user_id": user_id,
                "week_start_date": week_start_date,
                "plan_details": meal_plan,
                "shopping_list": shopping_list_str
            }).execute()
        logging.info(f"Saved plan for user {user_id}")
        return True
    except Exception as e:
        logging.error(f"Error saving plan for user {user_id}: {e}")
        return False