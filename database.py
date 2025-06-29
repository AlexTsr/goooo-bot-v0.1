import logging
from supabase_async import create_client, AsyncClient
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Создаем асинхронный клиент Supabase, который будет использоваться во всех функциях
# Мы используем service_role ключ, который имеет полные права доступа к БД
supabase: AsyncClient = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

logging.basicConfig(level=logging.INFO)

async def insert_user(telegram_id: int, tg_name: str):
    """
    Добавляет пользователя в таблицу `users`, если его ещё нет.
    Использует новый, правильный способ работы с БД.
    """
    try:
        # 1. Проверяем, существует ли пользователь
        response = await supabase.table('users').select('id').eq('telegram_id', telegram_id).execute()
        
        # response.data будет списком. Если он не пустой, пользователь существует.
        if response.data:
            logging.info(f"User {telegram_id} already exists.")
            # Возвращаем данные существующего пользователя
            return response.data[0]

        # 2. Если пользователя нет — добавляем его
        logging.info(f"User {telegram_id} not found. Creating new user.")
        insert_data = {
            "telegram_id": telegram_id,
            "tg_name": tg_name,
            "status": "onboarding" # Сразу ставим статус "проходит онбординг"
        }
        
        insert_response = await supabase.table('users').insert(insert_data).execute()

        # Проверяем, что вставка прошла успешно
        if insert_response.data:
            logging.info(f"User {telegram_id} created successfully.")
            return insert_response.data[0]
        else:
            logging.error(f"Failed to insert user {telegram_id}. Response: {insert_response}")
            return None

    except Exception as e:
        logging.error(f"An error occurred in insert_user for telegram_id {telegram_id}: {e}")
        # Выводим детали ошибки, если они есть
        if hasattr(e, 'message'):
            logging.error(f"Error details: {e.message}")
        return None

# В будущем здесь будут другие функции для работы с БД:
# async def save_onboarding_data(...)
# async def create_training_plan(...)
# и так далее.
