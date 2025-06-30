import httpx
import logging
from config import DEEPSEEK_API_KEY # Добавим этот ключ в конфиг

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Адрес API DeepSeek
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

# Заголовки для запроса
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
}

async def generate_plan_with_llm(prompt: str) -> str:
    """
    Отправляет промпт в DeepSeek API и возвращает сгенерированный ответ.
    """
    if not DEEPSEEK_API_KEY:
        logging.error("DEEPSEEK_API_KEY is not set!")
        return "Ошибка: Ключ API для LLM не настроен."

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Ты — экспертный тренер по бегу. Твоя задача — на основе данных пользователя составить подробный, структурированный и мотивирующий план тренировок и питания на неделю. План должен быть четким и понятным."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(DEEPSEEK_API_URL, headers=headers, json=payload)
            response.raise_for_status() # Проверка на ошибки HTTP (4xx, 5xx)
            
            data = response.json()
            
            if data.get("choices") and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                logging.info("Successfully received response from LLM.")
                return content
            else:
                logging.warning(f"LLM response is empty or invalid: {data}")
                return "Не удалось получить ответ от нейросети. Попробуйте позже."

    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error occurred while contacting LLM: {e.response.status_code} - {e.response.text}")
        return "Произошла ошибка при обращении к сервису генерации планов."
    except Exception as e:
        logging.error(f"An unexpected error occurred in generate_plan_with_llm: {e}")
        return "Произошла непредвиденная ошибка."

