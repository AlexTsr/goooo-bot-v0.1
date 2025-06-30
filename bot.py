import asyncio
import logging
import json
import sys
from datetime import date
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from config import BOT_TOKEN
from database import (
    insert_user, get_user_by_telegram_id, save_onboarding_data, 
    get_full_user_profile, save_generated_plan
)
from llm import generate_structured_plan_with_llm

# Включаем логирование
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')

# --- FSM States ---
class OnboardingState(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_height = State()
    waiting_for_weight = State()
    waiting_for_goal = State()
    waiting_for_motivation = State()
    waiting_for_demotivation = State()
    waiting_for_experience = State()
    waiting_for_personal_bests = State()
    waiting_for_days_per_week = State()
    waiting_for_preferred_days = State()
    waiting_for_trainings_per_day = State()
    waiting_for_long_run_day = State()
    waiting_for_current_injuries = State()
    waiting_for_recurring_injuries = State()
    waiting_for_equipment = State()
    waiting_for_infrastructure = State()
    waiting_for_dietary_restrictions = State()
    waiting_for_weekly_volume = State()
    waiting_for_additional_info = State()

class EditingState(StatesGroup):
    waiting_for_changes = State()

# --- Keyboards ---
def get_back_keyboard(previous_state: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой 'Назад'."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Вернуться к предыдущему вопросу", callback_data=f"back_to:{previous_state}")]
    ])

def get_plan_feedback_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для обратной связи по плану."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Все устраивает", callback_data="plan_confirm")],
        [InlineKeyboardButton(text="✍️ Предложить изменения", callback_data="plan_edit")]
    ])

# --- Инициализация бота и диспетчера ---
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)

# --- Словарь с вопросами для навигации "Назад" ---
QUESTIONS_MAP = {
    "waiting_for_name": ("Давай знакомиться. Я уже представился, а как тебя зовут?", OnboardingState.waiting_for_name, None),
    "waiting_for_age": ("Сколько тебе лет?", OnboardingState.waiting_for_age, get_back_keyboard("waiting_for_name")),
    "waiting_for_height": ("Какой у тебя рост (в сантиметрах)?", OnboardingState.waiting_for_height, get_back_keyboard("waiting_for_age")),
    "waiting_for_weight": ("Какой вес (в килограммах)?", OnboardingState.waiting_for_weight, get_back_keyboard("waiting_for_height")),
    "waiting_for_goal": ("Отлично! Теперь о твоих целях - готовишься к какому-то определенному забегу или просто хочешь улучшить свой результат на определенной дистанции?", OnboardingState.waiting_for_goal, get_back_keyboard("waiting_for_weight")),
    "waiting_for_motivation": ("Что тебя больше всего мотивирует в беге? Хорошее самочувствие, компания друзей или может это время подумать о чём-то?", OnboardingState.waiting_for_motivation, get_back_keyboard("waiting_for_goal")),
    "waiting_for_demotivation": ("Что тебя демотивирует? Лень, рутина, стеснительность, что-то еще?", OnboardingState.waiting_for_demotivation, get_back_keyboard("waiting_for_motivation")),
    "waiting_for_experience": ("Хорошо! Теперь узнаем о твоем беговом опыте. Как давно ты бегаешь?", OnboardingState.waiting_for_experience, get_back_keyboard("waiting_for_demotivation")),
    "waiting_for_personal_bests": ("У тебя есть личные рекорды, которые ты хочешь улучшить? (например: 5 км - 25:00, 10 км - 55:00)", OnboardingState.waiting_for_personal_bests, get_back_keyboard("waiting_for_experience")),
    "waiting_for_days_per_week": ("Сколько дней в неделю ты готов тренироваться?", OnboardingState.waiting_for_days_per_week, get_back_keyboard("waiting_for_personal_bests")),
    "waiting_for_preferred_days": ("В какие дни недели? (Например: пн, ср, пт)", OnboardingState.waiting_for_preferred_days, get_back_keyboard("waiting_for_days_per_week")),
    "waiting_for_trainings_per_day": ("Сколько раз в день готов тренироваться?", OnboardingState.waiting_for_trainings_per_day, get_back_keyboard("waiting_for_preferred_days")),
    "waiting_for_long_run_day": ("В какой день недели предпочитаешь бегать длительную тренировку?", OnboardingState.waiting_for_long_run_day, get_back_keyboard("waiting_for_trainings_per_day")),
    "waiting_for_current_injuries": ("С беговым опытом закончили, переходим к проблемам - твои травмы! Есть ли у тебя сейчас травмы или проблемы, которые нужно учесть при составлении тренировок?", OnboardingState.waiting_for_current_injuries, get_back_keyboard("waiting_for_long_run_day")),
    "waiting_for_recurring_injuries": ("Есть ли травмы, которые прямо сейчас себя не проявляют, но часто возвращаются? Например, при высокой нагрузке или большом объёме?", OnboardingState.waiting_for_recurring_injuries, get_back_keyboard("waiting_for_current_injuries")),
    "waiting_for_equipment": ("Теперь об оборудовании и инфраструктуре. Какой спортивный инвентарь у тебя есть? Электронные часы, нагрудный пульсометр, гири, гантели, коврик для фитнеса, массажный мяч и прочее. Напиши всё!", OnboardingState.waiting_for_equipment, get_back_keyboard("waiting_for_recurring_injuries")),
    "waiting_for_infrastructure": ("Есть ли у тебя возможность посещать стадион или манеж? Если 'да', то сколько метров круг? Ходишь ли в спортзал, баню или сауну?", OnboardingState.waiting_for_infrastructure, get_back_keyboard("waiting_for_equipment")),
    "waiting_for_dietary_restrictions": ("Теперь о еде! Чтобы составить план питания, основываясь на твои предпочтения, напиши, что не любишь есть или на какие продукты у тебя аллергия?", OnboardingState.waiting_for_dietary_restrictions, get_back_keyboard("waiting_for_infrastructure")),
    "waiting_for_weekly_volume": ("Какой твой текущий или желаемый недельный беговой объем (в км)?", OnboardingState.waiting_for_weekly_volume, get_back_keyboard("waiting_for_dietary_restrictions")),
    "waiting_for_additional_info": ("Если есть что-то, что ещё необходимо учесть в составлении плана, то сообщите это (например, ваш текущий ПАНО, предпочтения по количеству приемов пищи и прочее)", OnboardingState.waiting_for_additional_info, get_back_keyboard("waiting_for_weekly_volume")),
}

# --- Промпты и Форматирование ---
def format_prompt_for_detailed_json(profile_data: dict, week_num: int = 1) -> str:
    """Форматирует промпт для получения детального JSON по новому шаблону."""
    profile = profile_data.get('profile', {})
    preferences = profile_data.get('preferences', {})
    
    phases = {1: "втягивающая", 2: "ударная", 3: "ударная", 4: "восстановительная"}
    phase = phases.get(week_num, "втягивающая")
    macrocycle_info = f"Это {week_num}-я неделя 4-недельного макроцикла. Фаза: {phase}. Учти это при составлении плана."

    prompt = f"""
Проанализируй данные о спортсмене и создай для него персонализированный план на 7 дней.
Ответ должен быть СТРОГО в формате JSON на русском языке.

**Структура JSON:**
{{
  "intro_summary": "Персонализированное приветствие для пользователя, основанное на его данных и целях (например: 'Алексей, приятно познакомиться! ...').",
  "training_plan": [
    {{
      "day_of_week": "Понедельник",
      "date": "DD.MM",
      "morning_workout": {{ "type": "Тип тренировки (например, Легкий бег или Отдых)", "details": "Детали (например, 8 км @ 6:00/км или -)", "nutrition_notes": "Питание до/после" }},
      "evening_workout": {{ "type": "Тип (например, ОФП или Отдых)", "details": "Название блока (например, Верх тела + кор) или -", "nutrition_notes": "Питание до/после" }}
    }}
  ],
  "workout_details": [
    {{
      "block_name": "Верх тела + кор",
      "target_muscle_group": "Плечи, спина, кор",
      "reps_and_sets": "2–3 круга",
      "exercises": [
        {{"name": "Жим гирь над головой", "details": "15–20 раз"}},
        {{"name": "Тяга эспандера к груди", "details": "15 раз"}}
      ]
    }}
  ],
  "meal_plan": [
    {{
      "day_of_week": "Понедельник",
      "total_calories": 1950,
      "meals": [
        {{"meal_type": "Завтрак", "description": "Овсянка (80 г), банан + льняное масло"}},
        {{"meal_type": "Обед", "description": "Гречка (100 г), куриное филе (150 г), овощи"}},
        {{"meal_type": "Ужин", "description": "Лосось (150 г), киноа (80 г), салат"}},
        {{"meal_type": "Перекус", "description": "Творог 5% (150 г)"}}
      ]
    }}
  ],
  "shopping_list": [
      {{"category": "Зерновые/крупы", "items": ["Овсянка: 600 г", "Гречка: 300 г"]}},
      {{"category": "Белок", "items": ["Курица (филе): 450 г", "Яйца: 4 шт."]}}
  ],
  "general_recommendations": "Твои общие рекомендации по восстановлению, сну и т.д."
}}

**Требования к плану:**
- Учти, что пользователь может тренироваться 2 раза в день. Распредели нагрузку.
- Силовые блоки (ОФП/СБУ) должны быть комплексными и содержать 5-8 упражнений.
- План питания должен включать завтрак, обед, ужин и 1-2 перекуса.
- Список покупок должен быть сгруппирован по категориям.
- Интенсивность (темп, пульс) должна соответствовать целям и текущему уровню спортсмена.

**Контекст тренировочного цикла:**
{macrocycle_info}

**Данные о спортсмене:**
- Имя: {profile.get('name', 'N/A')}
- Возраст: {profile.get('age', 'N/A')}
- Рост: {profile.get('height_cm', 'N/A')} см
- Вес: {profile.get('initial_weight_kg', 'N/A')} кг
- Основная цель: {profile.get('goal', 'N/A')}
- Беговой опыт: {profile.get('experience', 'N/A')}
- Личные рекорды: {profile.get('personal_bests', {}).get('records', 'N/A')}
- Желаемый недельный объем: {profile.get('weekly_volume_km', 'не указан')} км
- Мотивация: {profile.get('motivation', 'N/A')}
- Демотивация: {profile.get('demotivation', 'N/A')}
- Дней для тренировок в неделю: {preferences.get('training_days_per_week', 'N/A')}
- Предпочтительные дни: {preferences.get('preferred_days', 'N/A')}
- Тренировок в день: {preferences.get('trainings_per_day', 'N/A')}
- День для длительной: {preferences.get('long_run_day', 'N/A')}
- Текущие травмы: {profile.get('current_injuries', 'Нет')}
- Повторяющиеся травмы: {profile.get('recurring_injuries', 'Нет')}
- Пищевые ограничения: {profile.get('dietary_restrictions', 'Нет')}
- Оборудование: {profile.get('equipment', 'Нет')}
- Инфраструктура: {profile.get('infrastructure', 'Нет')}
- Дополнительная информация от пользователя: {profile.get('additional_info', 'Нет')}
"""
    return prompt.strip()

def format_detailed_plan_for_user(plan_data: dict) -> str:
    """Красиво форматирует новый детальный JSON-план."""
    if "error" in plan_data:
        return f"Произошла ошибка: {plan_data['error']}"

    output = f"_{plan_data.get('intro_summary', 'Вот твой план:')}_\n\n"
    output += "### 🏃‍♂️ **План тренировок**\n\n"
    for day in plan_data.get("training_plan", []):
        output += f"**{day.get('day_of_week')} ({day.get('date')})**\n"
        mw = day.get('morning_workout')
        ew = day.get('evening_workout')
        if mw and mw.get('type') and mw.get('type').lower() != 'отдых':
            output += f"- *Утро:* {mw.get('type')} - {mw.get('details')}\n"
        if ew and ew.get('type') and ew.get('type').lower() != 'отдых':
            output += f"- *Вечер:* {ew.get('type')} - {ew.get('details')}\n"
    
    output += "\n### 💪 **Детали силовых и СБУ**\n\n"
    for block in plan_data.get("workout_details", []):
        output += f"**{block.get('block_name')}** ({block.get('reps_and_sets')})\n"
        for ex in block.get("exercises", []):
            output += f"- {ex.get('name')}: {ex.get('details')}\n"
        output += "\n"

    output += "### 🍽️ **План питания**\n\n"
    for day in plan_data.get("meal_plan", []):
        output += f"**{day.get('day_of_week')} (~{day.get('total_calories')} ккал)**\n"
        for meal in day.get("meals", []):
            output += f"- *{meal.get('meal_type')}:* {meal.get('description')}\n"
    
    output += "\n### 🛒 **Список покупок**\n\n"
    for category in plan_data.get("shopping_list", []):
        output += f"**{category.get('category')}**\n"
        for item in category.get('items', []):
            output += f"- {item}\n"
    
    output += "\n### ✅ **Общие рекомендации**\n"
    output += plan_data.get("general_recommendations", "Нет.")

    return output.strip()

# --- Хэндлеры ---
async def command_start(message: Message, state: FSMContext):
    # ... (код без изменений)
    pass

# ... (все остальные хэндлеры process_... и callback_query) ...

# --- РЕГИСТРАЦИЯ ХЭНДЛЕРОВ И ЗАПУСК БОТА ---
def register_handlers(dp: Dispatcher):
    # ... (код регистрации всех хэндлеров) ...
    pass

# --- НОВАЯ ЛОГИКА ЗАПУСКА ---
async def main():
    """Основная функция для запуска бота с надежным поллингом."""
    logging.info("--- Запуск бота ---")
    
    # 1. Регистрация хэндлеров
    register_handlers(dp)
    
    # 2. Установка команд меню
    await set_main_menu(bot)
    
    # 3. Агрессивный сброс сессии и пропуск старых апдейтов
    try:
        logging.info("Удаление вебхука и очистка старых обновлений...")
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Получаем ID последнего обновления, чтобы пропустить его
        updates = await bot.get_updates(offset=-1, limit=1)
        if updates:
            update_id = updates[-1].update_id + 1
            logging.info(f"Пропускаем обновления до ID: {update_id}")
            await bot.get_updates(offset=update_id) # "Съедаем" старые обновления
        
        logging.info("Запуск поллинга...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
    finally:
        await bot.session.close()
        logging.warning("Сессия бота закрыта.")

if __name__ == "__main__":
    asyncio.run(main())
