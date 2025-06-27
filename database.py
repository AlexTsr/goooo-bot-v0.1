from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def insert_user(user_id: int, name: str):
    response = supabase.table("users").insert({"user_id": user_id, "name": name}).execute()
    return response
