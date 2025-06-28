import os
import httpx
from config import SUPABASE_URL, SUPABASE_KEY

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Добавление пользователя в таблицу `users`, если его ещё нет
async def insert_user(telegram_id: int, name: str):
    # 1. Проверка, существует ли пользователь
    params = {
        "select": "id",
        "telegram_id": f"eq.{telegram_id}"
    }

    async with httpx.AsyncClient() as client:
        check_response = await client.get(
            f"{SUPABASE_URL}/rest/v1/users",
            headers=headers,
            params=params
        )
        check_response.raise_for_status()
        existing_users = check_response.json()

        if existing_users:
            return existing_users[0]  # Уже существует

        # 2. Если нет — добавляем
        data = {
            "telegram_id": str(telegram_id),
            "name": name
        }

        insert_response = await client.post(
            f"{SUPABASE_URL}/rest/v1/users",
            headers=headers,
            json=data
        )
        insert_response.raise_for_status()
        return insert_response.json()

# Получение UUID (id) пользователя по telegram_id
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
