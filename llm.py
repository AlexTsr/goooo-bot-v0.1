import httpx
import logging
import json # Импортируем библиотеку для работы с JSON
from config import DEEPSEEK_API_KEY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
}

async def generate_structured_plan_with_llm(prompt: str) -> dict:
    """
    Отправляет промпт в DeepSeek API, запрашивает ответ в JSON
    и возвращает его в виде словаря Python.
    """
    if not DEEPSEEK_API_KEY:
        logging.error("DEEPSEEK_API_KEY is not set!")
        return {"error": "Ключ API для LLM не настроен."}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Ты — экспертный тренер по бегу. Твоя задача — на основе данных пользователя составить подробный, структурированный план тренировок и питания на неделю. Ответ должен быть строго в формате JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"} # <-- Вот это ключевое изменение
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client: # Увеличим таймаут
            response = await client.post(DEEPSEEK_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("choices") and len(data["choices"]) > 0:
                content_str = data["choices"][0]["message"]["content"]
                logging.info("Successfully received JSON response from LLM.")
                # Превращаем строку JSON в словарь Python
                return json.loads(content_str)
            else:
                logging.warning(f"LLM response is empty or invalid: {data}")
                return {"error": "Не удалось получить ответ от нейросети."}

    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error contacting LLM: {e.response.status_code} - {e.response.text}")
        return {"error": "Ошибка при обращении к сервису генерации планов."}
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON from LLM response: {e}")
        return {"error": "Нейросеть вернула некорректный формат данных."}
    except Exception as e:
        logging.error(f"An unexpected error in generate_plan_with_llm: {e}")
        return {"error": "Произошла непредвиденная ошибка."}

