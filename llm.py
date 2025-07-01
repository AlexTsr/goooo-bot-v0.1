import httpx
import logging
import json
from config import DEEPSEEK_API_KEY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
}

async def generate_structured_plan_with_llm(prompt: str) -> dict:
    if not DEEPSEEK_API_KEY:
        logging.error("DEEPSEEK_API_KEY is not set!")
        return {"error": "Ключ API для LLM не настроен."}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Ты — экспертный тренер по бегу. Твоя задача — на основе данных пользователя составить подробный, структурированный план тренировок и питания на неделю. Ответ должен быть строго в формате JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(DEEPSEEK_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("choices") and len(data["choices"]) > 0:
                content_str = data["choices"][0]["message"]["content"]
                return json.loads(content_str)
            else:
                return {"error": "Не удалось получить ответ от нейросети."}
    except Exception as e:
        logging.error(f"An unexpected error in generate_plan_with_llm: {e}")
        return {"error": "Произошла непредвиденная ошибка."}
