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
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Вернуться к предыдущему вопросу", callback_data=f"back_to:{previous_state}")]])

def get_plan_feedback_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Все устраивает", callback_data="plan_confirm")],[InlineKeyboardButton(text="✍️ Предложить изменения", callback_data="plan_edit")]])

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
    await state.clear() 
    user_id = message.from_user.id
    user = await asyncio.to_thread(get_user_by_telegram_id, user_id)

    if user and user.get('status') == 'active':
        await message.answer(f"Привет, {message.from_user.first_name}! Рад снова тебя видеть. Хочешь внести изменения в свой профиль?", 
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="✍️ Изменить профиль", callback_data="edit_profile")],
                                 [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
                             ]))
    else:
        await asyncio.to_thread(insert_user, user_id, message.from_user.full_name)
        await message.answer("Привет! Я твой персональный тренер по бегу. Чтобы составить для тебя идеальный план, мне нужно задать несколько вопросов.")
        await message.answer("Давай знакомиться. Я уже представился, а как тебя зовут?")
        await state.set_state(OnboardingState.waiting_for_name)

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
    await state.update_data(goal=message.text)
    await message.answer(QUESTIONS_MAP["waiting_for_motivation"][0], reply_markup=QUESTIONS_MAP["waiting_for_motivation"][2])
    await state.set_state(OnboardingState.waiting_for_motivation)
    
async def process_motivation(message: Message, state: FSMContext):
    await state.update_data(motivation=message.text)
    await message.answer(QUESTIONS_MAP["waiting_for_demotivation"][0], reply_markup=QUESTIONS_MAP["waiting_for_demotivation"][2])
    await state.set_state(OnboardingState.waiting_for_demotivation)

async def process_demotivation(message: Message, state: FSMContext):
    await state.update_data(demotivation=message.text)
    await message.answer(QUESTIONS_MAP["waiting_for_experience"][0], reply_markup=QUESTIONS_MAP["waiting_for_experience"][2])
    await state.set_state(OnboardingState.waiting_for_experience)

async def process_experience(message: Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await message.answer(QUESTIONS_MAP["waiting_for_personal_bests"][0], reply_markup=QUESTIONS_MAP["waiting_for_personal_bests"][2])
    await state.set_state(OnboardingState.waiting_for_personal_bests)

async def process_personal_bests(message: Message, state: FSMContext):
    await state.update_data(personal_bests=message.text)
    await message.answer(QUESTIONS_MAP["waiting_for_days_per_week"][0], reply_markup=QUESTIONS_MAP["waiting_for_days_per_week"][2])
    await state.set_state(OnboardingState.waiting_for_days_per_week)

async def process_days_per_week(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи количество дней числом.", reply_markup=get_back_keyboard("waiting_for_personal_bests"))
        return
    await state.update_data(training_days_per_week=int(message.text))
    await message.answer(QUESTIONS_MAP["waiting_for_preferred_days"][0], reply_markup=QUESTIONS_MAP["waiting_for_preferred_days"][2])
    await state.set_state(OnboardingState.waiting_for_preferred_days)

async def process_preferred_days(message: Message, state: FSMContext):
    await state.update_data(preferred_days=message.text)
    await message.answer(QUESTIONS_MAP["waiting_for_trainings_per_day"][0], reply_markup=QUESTIONS_MAP["waiting_for_trainings_per_day"][2])
    await state.set_state(OnboardingState.waiting_for_trainings_per_day)

async def process_trainings_per_day(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи количество тренировок числом.", reply_markup=get_back_keyboard("waiting_for_preferred_days"))
        return
    await state.update_data(trainings_per_day=int(message.text))
    await message.answer(QUESTIONS_MAP["waiting_for_long_run_day"][0], reply_markup=QUESTIONS_MAP["waiting_for_long_run_day"][2])
    await state.set_state(OnboardingState.waiting_for_long_run_day)

async def process_long_run_day(message: Message, state: FSMContext):
    user_data = await state.get_data()
    preferred_days = user_data.get("preferred_days", "").lower()
    long_run_day_input = message.text.lower()

    if long_run_day_input not in [day.strip() for day in preferred_days.split(',')]:
        await message.answer(
            f"Ты ранее указал, что можешь заниматься в эти дни: {preferred_days}.\n"
            "Пожалуйста, выбери день для длительной тренировки из этого списка.",
            reply_markup=get_back_keyboard("waiting_for_trainings_per_day")
        )
        return
    
    await state.update_data(long_run_day=message.text)
    await message.answer(QUESTIONS_MAP["waiting_for_current_injuries"][0], reply_markup=QUESTIONS_MAP["waiting_for_current_injuries"][2])
    await state.set_state(OnboardingState.waiting_for_current_injuries)

async def process_current_injuries(message: Message, state: FSMContext):
    await state.update_data(current_injuries=message.text)
    await message.answer(QUESTIONS_MAP["waiting_for_recurring_injuries"][0], reply_markup=QUESTIONS_MAP["waiting_for_recurring_injuries"][2])
    await state.set_state(OnboardingState.waiting_for_recurring_injuries)

async def process_recurring_injuries(message: Message, state: FSMContext):
    await state.update_data(recurring_injuries=message.text)
    await message.answer(QUESTIONS_MAP["waiting_for_equipment"][0], reply_markup=QUESTIONS_MAP["waiting_for_equipment"][2])
    await state.set_state(OnboardingState.waiting_for_equipment)

async def process_equipment(message: Message, state: FSMContext):
    await state.update_data(equipment=message.text)
    await message.answer(QUESTIONS_MAP["waiting_for_infrastructure"][0], reply_markup=QUESTIONS_MAP["waiting_for_infrastructure"][2])
    await state.set_state(OnboardingState.waiting_for_infrastructure)

async def process_infrastructure(message: Message, state: FSMContext):
    await state.update_data(infrastructure=message.text)
    await message.answer(QUESTIONS_MAP["waiting_for_dietary_restrictions"][0], reply_markup=QUESTIONS_MAP["waiting_for_dietary_restrictions"][2])
    await state.set_state(OnboardingState.waiting_for_dietary_restrictions)

async def process_dietary_restrictions(message: Message, state: FSMContext):
    await state.update_data(dietary_restrictions=message.text)
    await message.answer(QUESTIONS_MAP["waiting_for_weekly_volume"][0], reply_markup=QUESTIONS_MAP["waiting_for_weekly_volume"][2])
    await state.set_state(OnboardingState.waiting_for_weekly_volume)

async def process_weekly_volume(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи объем числом.", reply_markup=get_back_keyboard("waiting_for_dietary_restrictions"))
        return
    await state.update_data(weekly_volume_km=int(message.text))
    await message.answer(QUESTIONS_MAP["waiting_for_additional_info"][0], reply_markup=QUESTIONS_MAP["waiting_for_additional_info"][2])
    await state.set_state(OnboardingState.waiting_for_additional_info)

async def process_additional_info(message: Message, state: FSMContext):
    await state.update_data(additional_info=message.text)
    user_data = await state.get_data()
    telegram_id = message.from_user.id
    await message.answer("Спасибо! Сохраняю твой профиль...")
    
    user = await asyncio.to_thread(get_user_by_telegram_id, telegram_id)
    if user:
        user_db_id = user['id']
        success = await asyncio.to_thread(save_onboarding_data, user_db_id, user_data)
        
        if success:
            await message.answer("Отлично! Профиль сохранен. Генерирую твой первый план. Это может занять до минуты...", parse_mode=None)
            
            full_profile = await asyncio.to_thread(get_full_user_profile, user_db_id)
            if full_profile:
                prompt = format_prompt_for_detailed_json(full_profile)
                
                plan_json = await generate_structured_plan_with_llm(prompt)
                
                if "error" not in plan_json:
                    formatted_plan = format_detailed_plan_for_user(plan_json)
                    await message.answer(formatted_plan, parse_mode=ParseMode.MARKDOWN, reply_markup=get_plan_feedback_keyboard())
                    await state.update_data(last_generated_plan=plan_json)
                else:
                    await message.answer(f"Ошибка генерации плана: {plan_json['error']}")
            else:
                await message.answer("Не удалось получить данные твоего профиля для генерации плана.")
        else:
            await message.answer("Произошла ошибка при сохранении профиля.")
    else:
        await message.answer("Не смог найти твой профиль для сохранения.")
    await state.set_state(None)

async def navigate_back(callback: CallbackQuery, state: FSMContext):
    previous_state_name = callback.data.split(":")[1]
    question_data = QUESTIONS_MAP.get(previous_state_name)
    
    if question_data:
        question_text, new_state, markup = question_data
        await callback.message.edit_text(question_text, reply_markup=markup)
        await state.set_state(new_state)
    await callback.answer()

@dp.callback_query(F.data == "plan_confirm")
async def confirm_plan(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Отлично! Хорошей тренировочной недели. Жду твой отчет в воскресенье.")
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == "plan_edit")
async def edit_plan_request(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Дай знать, что ты хочешь изменить или уточнить в плане?")
    await state.set_state(EditingState.waiting_for_changes)
    await callback.answer()

@dp.message(EditingState.waiting_for_changes)
async def process_plan_changes(message: Message, state: FSMContext):
    user_changes = message.text
    user_data = await state.get_data()
    last_plan = user_data.get("last_generated_plan")
    
    await message.answer("Понял тебя. Отправляю твои правки тренеру-ИИ для корректировки плана. Это может занять минуту...")

    edit_prompt = f"""
Вот первоначальный план, который я сгенерировал для пользователя:
{json.dumps(last_plan, indent=2, ensure_ascii=False)}

Пользователь попросил внести следующие изменения:
"{user_changes}"

Пожалуйста, перегенерируй полный план в том же формате JSON, но с учетом этих правок. Убедись, что новый ответ также содержит все ключи: intro_summary, training_plan, workout_details, meal_plan, shopping_list, general_recommendations.
"""
    plan_json = await generate_structured_plan_with_llm(edit_prompt)
    if "error" not in plan_json:
        formatted_plan = format_detailed_plan_for_user(plan_json)
        await message.answer(formatted_plan, parse_mode=ParseMode.MARKDOWN, reply_markup=get_plan_feedback_keyboard())
        await state.update_data(last_generated_plan=plan_json)
    else:
        await message.answer(f"Ошибка генерации плана: {plan_json['error']}")
    
    await state.set_state(None)

async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(command="/start", description="Начать знакомство / Обновить профиль")
    ]
    await bot.set_my_commands(main_menu_commands)

def register_handlers(dp: Dispatcher):
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
    dp.message.register(process_long_run_day, OnboardingState.waiting_for_long_run_day)
    dp.message.register(process_current_injuries, OnboardingState.waiting_for_current_injuries)
    dp.message.register(process_recurring_injuries, OnboardingState.waiting_for_recurring_injuries)
    dp.message.register(process_equipment, OnboardingState.waiting_for_equipment)
    dp.message.register(process_infrastructure, OnboardingState.waiting_for_infrastructure)
    dp.message.register(process_dietary_restrictions, OnboardingState.waiting_for_dietary_restrictions)
    dp.message.register(process_weekly_volume, OnboardingState.waiting_for_weekly_volume)
    dp.message.register(process_additional_info, OnboardingState.waiting_for_additional_info)
    
    dp.callback_query.register(navigate_back, F.data.startswith("back_to:"))
    dp.callback_query.register(restart_onboarding, F.data == "edit_profile")
    dp.callback_query.register(cancel_action, F.data == "cancel_action")
    dp.callback_query.register(confirm_plan, F.data == "plan_confirm")
    dp.callback_query.register(edit_plan_request, F.data == "plan_edit")
    
    dp.message.register(process_plan_changes, EditingState.waiting_for_changes)

async def main():
    """Основная функция для запуска бота с надежным поллингом."""
    logging.info("--- Запуск бота ---")
    
    register_handlers(dp)
    await set_main_menu(bot)
    
    try:
        logging.info("Удаление вебхука и очистка старых обновлений...")
        await bot.delete_webhook(drop_pending_updates=True)
        
        updates = await bot.get_updates(offset=-1, limit=1)
        if updates:
            update_id = updates[-1].update_id + 1
            logging.info(f"Пропускаем обновления до ID: {update_id}")
            await bot.get_updates(offset=update_id)
        
        logging.info("Запуск поллинга...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
    finally:
        await bot.session.close()
        logging.warning("Сессия бота закрыта.")

if __name__ == "__main__":
    asyncio.run(main())
