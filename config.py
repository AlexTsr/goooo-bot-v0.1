import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
# Ключ service_role, который мы добавили в Render
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") 
