import os
import httpx
from config import SUPABASE_URL, SUPABASE_KEY

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ✅ Добавление пользователя в таблицу `users`
async def insert_user(telegram_id: int, name: str):
    data = {
        "telegram_id": str(telegram_id),
        "name": name
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/users",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return response.json()


# ✅ Получение UUID пользователя (id) по telegram_id
async def get_user_id_by_telegram_id(telegram_id: int) -> str | None:
    params = {
        "select": "id",
        "telegram_id": f"eq.{telegram_id}"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/users",
            headers=headers,
            params=params
        )
        response.raise_for_status()
        users = response.json()
        if users:
            return users[0]["id"]
        return None