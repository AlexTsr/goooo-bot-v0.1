import asyncio
import logging
from datetime import date
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- FSM (Машина состояний) для онбординга ---
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
    waiting_for_current_injuries = State()
    waiting_for_recurring_injuries = State()
    waiting_for_equipment = State()
    waiting_for_infrastructure = State()
    waiting_for_dietary_restrictions = State()

# --- Клавиатуры ---
def get_back_keyboard(previous_state: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой 'Назад'."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Вернуться к предыдущему вопросу", callback_data=f"back_to:{previous_state}")]
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
    "waiting_for_current_injuries": ("С беговым опытом закончили, переходим к проблемам - твои травмы! Есть ли у тебя сейчас травмы или проблемы, которые нужно учесть при составлении тренировок?", OnboardingState.waiting_for_current_injuries, get_back_keyboard("waiting_for_trainings_per_day")),
    "waiting_for_recurring_injuries": ("Есть ли травмы, которые прямо сейчас себя не проявляют, но часто возвращаются? Например, при высокой нагрузке или большом объёме?", OnboardingState.waiting_for_recurring_injuries, get_back_keyboard("waiting_for_current_injuries")),
    "waiting_for_equipment": ("Теперь об оборудовании и инфраструктуре. Какой спортивный инвентарь у тебя есть? Электронные часы, нагрудный пульсометр, гири, гантели, коврик для фитнеса, массажный мяч и прочее. Напиши всё!", OnboardingState.waiting_for_equipment, get_back_keyboard("waiting_for_recurring_injuries")),
    "waiting_for_infrastructure": ("Есть ли у тебя возможность посещать стадион или манеж? Если 'да', то сколько метров круг? Ходишь ли в спортзал, баню или сауну?", OnboardingState.waiting_for_infrastructure, get_back_keyboard("waiting_for_equipment")),
    "waiting_for_dietary_restrictions": ("Теперь о еде! Чтобы составить план питания, основываясь на твои предпочтения, напиши, что не любишь есть или на какие продукты у тебя аллергия?", OnboardingState.waiting_for_dietary_restrictions, get_back_keyboard("waiting_for_infrastructure")),
}

# --- Хэндлеры ---

async def command_start(message: Message, state: FSMContext):
    await state.clear() 
    user_id = message.from_user.id
    tg_name = message.from_user.full_name
    
    await message.answer("Привет! Готовлю для тебя опрос... Секунду.")
    await asyncio.to_thread(insert_user, user_id, tg_name)

    await message.answer(
        "Далее в сообщениях я запрошу у тебя информацию, которая понадобится "
        "для дальнейшей аналитики и составления персонализированного плана."
    )
    await message.answer("Давай знакомиться. Я уже представился, а как тебя зовут?")
    await state.set_state(OnboardingState.waiting_for_name)

async def process_generic_question(message: Message, state: FSMContext, current_state_key: str, next_state_key: str):
    data_key = current_state_key.replace("waiting_for_", "")
    await state.update_data({data_key: message.text})
    question_text, _, markup = QUESTIONS_MAP[next_state_key]
    await message.answer(question_text, reply_markup=markup)
    next_state = getattr(OnboardingState, next_state_key)
    await state.set_state(next_state)

async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Сколько тебе лет?", reply_markup=get_back_keyboard("waiting_for_name"))
    await state.set_state(OnboardingState.waiting_for_age)

async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи возраст числом.", reply_markup=get_back_keyboard("waiting_for_name"))
        return
    await state.update_data(age=int(message.text))
    await message.answer("Какой у тебя рост (в сантиметрах)?", reply_markup=get_back_keyboard("waiting_for_age"))
    await state.set_state(OnboardingState.waiting_for_height)

async def process_height(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи рост числом.", reply_markup=get_back_keyboard("waiting_for_age"))
        return
    await state.update_data(height=int(message.text))
    await message.answer("Какой вес (в килограммах)?", reply_markup=get_back_keyboard("waiting_for_height"))
    await state.set_state(OnboardingState.waiting_for_weight)

async def process_weight(message: Message, state: FSMContext):
    try:
        weight = float(message.text.replace(',', '.'))
        await state.update_data(weight=weight)
        await message.answer(QUESTIONS_MAP["waiting_for_goal"][0], reply_markup=QUESTIONS_MAP["waiting_for_goal"][2])
        await state.set_state(OnboardingState.waiting_for_goal)
    except ValueError:
        await message.answer("Пожалуйста, введи вес числом (например, 75.5).", reply_markup=get_back_keyboard("waiting_for_weight"))

async def process_goal(message: Message, state: FSMContext):
    await process_generic_question(message, state, "waiting_for_goal", "waiting_for_motivation")

async def process_motivation(message: Message, state: FSMContext):
    await process_generic_question(message, state, "waiting_for_motivation", "waiting_for_demotivation")

async def process_demotivation(message: Message, state: FSMContext):
    await process_generic_question(message, state, "waiting_for_demotivation", "waiting_for_experience")

async def process_experience(message: Message, state: FSMContext):
    await process_generic_question(message, state, "waiting_for_experience", "waiting_for_personal_bests")

async def process_personal_bests(message: Message, state: FSMContext):
    await process_generic_question(message, state, "waiting_for_personal_bests", "waiting_for_days_per_week")

async def process_days_per_week(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи количество дней числом.", reply_markup=get_back_keyboard("waiting_for_personal_bests"))
        return
    await state.update_data(training_days_per_week=int(message.text))
    await message.answer(QUESTIONS_MAP["waiting_for_preferred_days"][0], reply_markup=QUESTIONS_MAP["waiting_for_preferred_days"][2])
    await state.set_state(OnboardingState.waiting_for_preferred_days)

async def process_preferred_days(message: Message, state: FSMContext):
    await process_generic_question(message, state, "waiting_for_preferred_days", "waiting_for_trainings_per_day")

async def process_trainings_per_day(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи количество тренировок числом.", reply_markup=get_back_keyboard("waiting_for_preferred_days"))
        return
    await state.update_data(trainings_per_day=int(message.text))
    await message.answer(QUESTIONS_MAP["waiting_for_current_injuries"][0], reply_markup=QUESTIONS_MAP["waiting_for_current_injuries"][2])
    await state.set_state(OnboardingState.waiting_for_current_injuries)

async def process_current_injuries(message: Message, state: FSMContext):
    await process_generic_question(message, state, "waiting_for_current_injuries", "waiting_for_recurring_injuries")

async def process_recurring_injuries(message: Message, state: FSMContext):
    await process_generic_question(message, state, "waiting_for_recurring_injuries", "waiting_for_equipment")

async def process_equipment(message: Message, state: FSMContext):
    await process_generic_question(message, state, "waiting_for_equipment", "waiting_for_infrastructure")

async def process_infrastructure(message: Message, state: FSMContext):
    await process_generic_question(message, state, "waiting_for_infrastructure", "waiting_for_dietary_restrictions")
    

# --- Добавление промтов LLM ---
def format_prompt_for_json_llm(profile_data: dict) -> str:
    """Форматирует данные пользователя в промпт, который просит LLM вернуть JSON."""
    profile = profile_data.get('profile', {})
    preferences = profile_data.get('preferences', {})
    
    prompt = f"""
Проанализируй данные о спортсмене и создай для него персонализированный план тренировок и питания на 7 дней.
Ответ должен быть СТРОГО в формате JSON, со следующей структурой:
{{
  "training_plan": {{
    "monday": {{"type": "...", "details": "...", "time_of_day": "..."}},
    "tuesday": {{"type": "...", "details": "...", "time_of_day": "..."}},
    ... (и так для всех 7 дней)
  }},
  "meal_plan": {{
    "summary": {{"daily_calories": ..., "protein_g": ..., "fat_g": ..., "carbs_g": ...}},
    "monday": {{"breakfast": "...", "lunch": "...", "dinner": "...", "snacks": ["...", "..."]}},
    ... (и так для всех 7 дней)
  }},
  "shopping_list": ["Продукт 1, вес/кол-во", "Продукт 2, вес/кол-во", ...],
  "general_recommendations": "Твои общие рекомендации по восстановлению, сну и т.д."
}}

ДАННЫЕ О СПОРТСМЕНЕ:
- Имя: {profile.get('name', 'Не указано')}
- Возраст: {profile.get('age', 'Не указано')}
- Рост: {profile.get('height_cm', 'Не указано')} см
- Вес: {profile.get('initial_weight_kg', 'Не указано')} кг
- Основная цель: {profile.get('goal', 'Не указано')}
- Беговой опыт: {profile.get('experience', 'Не указано')}
- Личные рекорды: {profile.get('personal_bests', {}).get('records', 'Не указано')}
- Мотивация: {profile.get('motivation', 'Не указано')}
- Демотивация: {profile.get('demotivation', 'Не указано')}
- Дней для тренировок в неделю: {preferences.get('training_days_per_week', 'Не указано')}
- Предпочтительные дни: {preferences.get('preferred_days', 'Не указано')}
- Текущие травмы: {profile.get('current_injuries', 'Нет')}
- Повторяющиеся травмы: {profile.get('recurring_injuries', 'Нет')}
- Пищевые ограничения: {profile.get('dietary_restrictions', 'Нет')}
- Оборудование: {profile.get('equipment', 'Нет')}
- Инфраструктура: {profile.get('infrastructure', 'Нет')}
"""
    return prompt.strip()

def format_plan_for_user(plan_data: dict) -> str:
    """Красиво форматирует JSON-план для отправки пользователю."""
    if "error" in plan_data:
        return f"Произошла ошибка: {plan_data['error']}"

    output = "### 🏃‍♂️ Ваш план тренировок\n\n"
    training_plan = plan_data.get("training_plan", {})
    for day, details in training_plan.items():
        output += f"**{day.capitalize()}:** {details.get('type', '')} - {details.get('details', '')}\n"

    output += "\n### 🍽️ Ваш план питания\n\n"
    meal_plan = plan_data.get("meal_plan", {})
    summary = meal_plan.get("summary", {})
    output += f"**Средняя калорийность:** {summary.get('daily_calories', 'N/A')} ккал\n"
    for day, meals in meal_plan.items():
        if day == "summary": continue
        output += f"**{day.capitalize()}:**\n"
        output += f"  - Завтрак: {meals.get('breakfast', '')}\n"
        output += f"  - Обед: {meals.get('lunch', '')}\n"
        output += f"  - Ужин: {meals.get('dinner', '')}\n"

    output += "\n### 🛒 Список покупок\n"
    shopping_list = plan_data.get("shopping_list", [])
    output += ", ".join(shopping_list) + "\n"

    output += "\n### ✅ Общие рекомендации\n"
    output += plan_data.get("general_recommendations", "")

    return output

async def process_dietary_restrictions(message: Message, state: FSMContext):
    """Последний шаг онбординга. Сохраняем данные, вызываем LLM, форматируем и сохраняем план."""
    await state.update_data(dietary_restrictions=message.text)
    user_data = await state.get_data()
    telegram_id = message.from_user.id
    await message.answer("Спасибо! Сохраняю твой профиль...")
    
    user = await asyncio.to_thread(get_user_by_telegram_id, telegram_id)
    if user:
        user_db_id = user['id']
        success = await asyncio.to_thread(save_onboarding_data, user_db_id, user_data)
        
        if success:
            await message.answer("Отлично! Профиль сохранен. Генерирую твой первый план. Это может занять до минуты...", parse_mode=None) # Убираем parse_mode, чтобы не было конфликтов
            
            full_profile = await asyncio.to_thread(get_full_user_profile, user_db_id)
            if full_profile:
                prompt = format_prompt_for_json_llm(full_profile)
                
                # Вызываем LLM для получения СТРУКТУРИРОВАННОГО плана
                plan_json = await generate_structured_plan_with_llm(prompt)
                
                if "error" not in plan_json:
                    # Форматируем красивый ответ для пользователя
                    formatted_plan = format_plan_for_user(plan_json)
                    await message.answer(formatted_plan, parse_mode=ParseMode.MARKDOWN)

                    # Сохраняем структурированный план в БД
                    today = date.today().isoformat()
                    await asyncio.to_thread(save_generated_plan, user_db_id, today, plan_json)
                else:
                    await message.answer(f"Ошибка генерации плана: {plan_json['error']}")
            else:
                await message.answer("Не удалось получить данные твоего профиля для генерации плана.")
        else:
            await message.answer("Произошла ошибка при сохранении профиля.")
    else:
        await message.answer("Не смог найти твой профиль для сохранения.")
    await state.clear()

# --- Хэндлер для кнопки "Назад" ---
@dp.callback_query(F.data.startswith("back_to:"))
async def navigate_back(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопки 'Назад'."""
    previous_state_name = callback.data.split(":")[1]
    question_data = QUESTIONS_MAP.get(previous_state_name)
    
    if question_data:
        question_text, new_state, markup = question_data
        await callback.message.edit_text(question_text, reply_markup=markup)
        await state.set_state(new_state)
    await callback.answer()

# --- РЕГИСТРАЦИЯ ХЭНДЛЕРОВ И ЗАПУСК БОТА ---

def register_handlers(dp: Dispatcher):
    """Регистрирует все хэндлеры сообщений."""
    dp.message.register(command_start, F.text.startswith("/start"))
    dp.message.register(process_name, OnboardingState.waiting_for_name)
    dp.message.register(process_age, OnboardingState.waiting_for_age)
    dp.message.register(process_height, OnboardingState.waiting_for_height)
    dp.message.register(process_weight, OnboardingState.waiting_for_weight)
    dp.message.register(process_goal, OnboardingState.waiting_for_goal)
    dp.message.register(process_motivation, OnboardingState.waiting_for_motivation)
    dp.message.register(process_demotivation, OnboardingState.waiting_for_demotivation)
    dp.message.register(process_experience, OnboardingState.waiting_for_experience)
    dp.message.register(process_personal_bests, OnboardingState.waiting_for_personal_bests)
    dp.message.register(process_days_per_week, OnboardingState.waiting_for_days_per_week)
    dp.message.register(process_preferred_days, OnboardingState.waiting_for_preferred_days)
    dp.message.register(process_trainings_per_day, OnboardingState.waiting_for_trainings_per_day)
    dp.message.register(process_current_injuries, OnboardingState.waiting_for_current_injuries)
    dp.message.register(process_recurring_injuries, OnboardingState.waiting_for_recurring_injuries)
    dp.message.register(process_equipment, OnboardingState.waiting_for_equipment)
    dp.message.register(process_infrastructure, OnboardingState.waiting_for_infrastructure)
    dp.message.register(process_dietary_restrictions, OnboardingState.waiting_for_dietary_restrictions)

async def main():
    """Основная функция для запуска бота."""
    register_handlers(dp)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
