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
        logging.error("DEEPSEEK_API_KEY is not set")
        return {"error": "API key for LLM is not configured"}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Ты — экспертный тренер по бегу и питанию. Создай план тренировок и питания на 7 дней в формате JSON на русском языке. Все поля обязательны."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(DEEPSEEK_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("choices") and data["choices"][0]["message"]["content"]:
                return json.loads(data["choices"][0]["message"]["content"])
            return {"error": "Empty or invalid LLM response"}
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
        return {"error": "Failed to contact LLM service"}
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        return {"error": "Invalid JSON format from LLM"}
    except Exception as e:
        logging.error(f"Unexpected error in LLM: {e}")
        return {"error": "Unexpected error occurred"}