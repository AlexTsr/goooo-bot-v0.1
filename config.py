import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://goooo-bot-web.onrender.com/webhook")

if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY, DEEPSEEK_API_KEY, WEBHOOK_URL]):
    raise ValueError("Missing required environment variables")