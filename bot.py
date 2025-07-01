import asyncio
import logging
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, BotCommand, Update
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import BOT_TOKEN, WEBHOOK_URL
from database import supabase, get_user_by_telegram_id, insert_user, save_onboarding_data, get_full_user_profile, save_generated_plan
from llm import generate_structured_plan_with_llm
import uvicorn

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# FSM States
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

# Router
router = Router()

# Keyboards
def get_back_keyboard(previous_state: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to:{previous_state}")]
    ])

def get_plan_feedback_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Все устраивает", callback_data="plan_confirm")],
        [InlineKeyboardButton(text="✍️ Изменить", callback_data="plan_edit")]
    ])

# Prompts and Formatting
def format_prompt_for_detailed_json(profile_data: dict, week_num: int = 1) -> str:
    profile = profile_data.get('profile', {})
    preferences = profile_data.get('preferences', {})
    phases = {1: "втягивающая", 2: "ударная", 3: "ударная", 4: "восстановительная"}
    phase = phases.get(week_num, "втягивающая")
    macrocycle_info = f"Это {week_num}-я неделя 4-недельного макроцикла. Фаза: {phase}."

    prompt = f"""
Ты — экспертный тренер по бегу и питанию. Создай план тренировок и питания на 7 дней для пользователя. Ответ должен быть СТРОГО в формате JSON на русском языке.

**Структура JSON:**
{{
  "intro_summary": "Краткое приветствие с именем и анализ целей (2-3 предложения).",
  "training_plan": [
    {{"day_of_week": "Понедельник", "date": "01.07", "morning_workout": {{"type": "Легкий бег", "details": "5 км @ 6:00/км", "nutrition_notes": "Банан за 30 мин до"}}}},
    {{"day_of_week": "Вторник", "date": "02.07", "morning_workout": {{"type": "Отдых", "details": "-", "nutrition_notes": "-"}}}}
  ],
  "workout_details": [
    {{"block_name": "Силовая тренировка", "target_muscle_group": "Ноги", "reps_and_sets": "3x12", "exercises": [{{"name": "Приседания", "details": "12 раз"}}]}}
  ],
  "meal_plan": [
    {{"day_of_week": "Понедельник", "total_calories": 2000, "meals": [{{"meal_type": "Завтрак", "description": "Овсянка 80 г"}}]}}
  ],
  "shopping_list": [{{"category": "Зерновые", "items": ["Овсянка: 500 г"]}}],
  "general_recommendations": "Сон 7-8 часов, гидратация 2 л воды."
}}

**Требования:**
- Учитывай {preferences.get('training_days_per_week', 3)} дней тренировки в неделю, предпочтения: {preferences.get('preferred_days', 'пн, ср, пт')}.
- Длительная тренировка в {preferences.get('long_run_day', 'вс')}.
- {preferences.get('trainings_per_day', 1)} тренировки в день.
- Травмы: {profile.get('current_injuries', 'Нет')} и {profile.get('recurring_injuries', 'Нет')}.
- Питание: 3 приема + 1-2 перекуса, ограничения: {profile.get('dietary_restrictions', 'Нет')}.
- Используй оборудование: {profile.get('equipment', 'Нет')}.
- Темп и пульс под цель: {profile.get('goal', 'улучшение выносливости')}.

**Данные пользователя:**
- Имя: {profile.get('name', 'Пользователь')}
- Возраст: {profile.get('age', 'N/A')}
- Рост: {profile.get('height_cm', 'N/A')} см
- Вес: {profile.get('initial_weight_kg', 'N/A')} кг
- Цель: {profile.get('goal', 'N/A')}
- Опыт: {profile.get('experience', 'N/A')}
- Рекорды: {profile.get('personal_bests', {}).get('records', 'N/A')}
- Объем: {profile.get('weekly_volume_km', 'N/A')} км
- Мотивация: {profile.get('motivation', 'N/A')}
- Демотивация: {profile.get('demotivation', 'N/A')}
- Инфраструктура: {profile.get('infrastructure', 'N/A')}
- Доп. инфо: {profile.get('additional_info', 'N/A')}
- Макроцикл: {macrocycle_info}
"""
    return prompt.strip()

def format_detailed_plan_for_user(plan_data: dict) -> str:
    if "error" in plan_data:
        return f"Ошибка: {plan_data['error']}"
    
    output = f"_{plan_data.get('intro_summary', 'Ваш план:')}_\n\n"
    output += "### 🏃‍♂️ Тренировки\n"
    for day in plan_data.get("training_plan", []):
        output += f"**{day['day_of_week']} ({day['date']})**\n"
        if day.get("morning_workout", {}).get("type") != "Отдых":
            output += f"- Утро: {day['morning_workout']['type']} - {day['morning_workout']['details']}\n"
        if day.get("evening_workout", {}).get("type") != "Отдых":
            output += f"- Вечер: {day['evening_workout']['type']} - {day['evening_workout']['details']}\n"
    
    output += "\n### 💪 Силовые/СБУ\n"
    for block in plan_data.get("workout_details", []):
        output += f"**{block['block_name']} ({block['reps_and_sets']})**\n"
        for ex in block.get("exercises", []):
            output += f"- {ex['name']}: {ex['details']}\n"
    
    output += "\n### 🍽️ Питание\n"
    for day in plan_data.get("meal_plan", []):
        output += f"**{day['day_of_week']} (~{day['total_calories']} ккал)**\n"
        for meal in day.get("meals", []):
            output += f"- {meal['meal_type']}: {meal['description']}\n"
    
    output += "\n### 🛒 Список покупок\n"
    for cat in plan_data.get("shopping_list", []):
        output += f"**{cat['category']}**\n"
        for item in cat.get("items", []):
            output += f"- {item}\n"
    
    output += "\n### ✅ Рекомендации\n"
    output += plan_data.get("general_recommendations", "Нет рекомендаций.")
    
    return output.strip()

# Handlers
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)

@router.message(F.text == "/start")
async def command_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    user = await asyncio.to_thread(get_user_by_telegram_id, user_id)

    if user and user.get('status') == 'active':
        await message.answer(f"Привет, {message.from_user.first_name}! Хочешь обновить профиль?",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="✍️ Обновить", callback_data="edit_profile")],
                                 [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
                             ]))
    else:
        await asyncio.to_thread(insert_user, user_id, message.from_user.full_name)
        await message.answer("Привет! Я твой тренер по бегу. Как тебя зовут?")
        await state.set_state(OnboardingState.waiting_for_name)

@router.message(OnboardingState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 255:
        await message.answer("Имя должно быть не пустым и до 255 символов. Попробуй еще.")
        return
    await state.update_data(name=name)
    await message.answer("Сколько тебе лет?", reply_markup=get_back_keyboard("waiting_for_name"))
    await state.set_state(OnboardingState.waiting_for_age)

@router.message(OnboardingState.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if age < 16 or age > 100:
            await message.answer("Возраст от 16 до 100. Попробуй еще.")
            return
        await state.update_data(age=age)
        await message.answer("Какой рост (см)?", reply_markup=get_back_keyboard("waiting_for_name"))
        await state.set_state(OnboardingState.waiting_for_height)
    except ValueError:
        await message.answer("Введите число.")

@router.message(OnboardingState.waiting_for_height)
async def process_height(message: Message, state: FSMContext):
    try:
        height = int(message.text)
        if height < 100 or height > 250:
            await message.answer("Рост от 100 до 250 см. Попробуй еще.")
            return
        await state.update_data(height=height)
        await message.answer("Какой вес (кг)?", reply_markup=get_back_keyboard("waiting_for_age"))
        await state.set_state(OnboardingState.waiting_for_weight)
    except ValueError:
        await message.answer("Введите число.")

@router.message(OnboardingState.waiting_for_weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        weight = float(message.text)
        if weight < 30 or weight > 200:
            await message.answer("Вес от 30 до 200 кг. Попробуй еще.")
            return
        await state.update_data(weight=weight)
        await message.answer("Какая цель (например, забег 10к)?", reply_markup=get_back_keyboard("waiting_for_height"))
        await state.set_state(OnboardingState.waiting_for_goal)
    except ValueError:
        await message.answer("Введите число.")

@router.message(OnboardingState.waiting_for_goal)
async def process_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text.strip())
    await message.answer("Что мотивирует в беге?", reply_markup=get_back_keyboard("waiting_for_weight"))
    await state.set_state(OnboardingState.waiting_for_motivation)

@router.message(OnboardingState.waiting_for_motivation)
async def process_motivation(message: Message, state: FSMContext):
    await state.update_data(motivation=message.text.strip())
    await message.answer("Что демотивирует?", reply_markup=get_back_keyboard("waiting_for_goal"))
    await state.set_state(OnboardingState.waiting_for_demotivation)

@router.message(OnboardingState.waiting_for_demotivation)
async def process_demotivation(message: Message, state: FSMContext):
    await state.update_data(demotivation=message.text.strip())
    await message.answer("Какой беговой опыт?", reply_markup=get_back_keyboard("waiting_for_motivation"))
    await state.set_state(OnboardingState.waiting_for_experience)

@router.message(OnboardingState.waiting_for_experience)
async def process_experience(message: Message, state: FSMContext):
    await state.update_data(experience=message.text.strip())
    await message.answer("Личные рекорды (например, 5к - 25:00)?", reply_markup=get_back_keyboard("waiting_for_demotivation"))
    await state.set_state(OnboardingState.waiting_for_personal_bests)

@router.message(OnboardingState.waiting_for_personal_bests)
async def process_personal_bests(message: Message, state: FSMContext):
    await state.update_data(personal_bests=message.text.strip())
    await message.answer("Сколько дней в неделю тренироваться?", reply_markup=get_back_keyboard("waiting_for_experience"))
    await state.set_state(OnboardingState.waiting_for_days_per_week)

@router.message(OnboardingState.waiting_for_days_per_week)
async def process_days_per_week(message: Message, state: FSMContext):
    try:
        days = int(message.text)
        if days < 1 or days > 7:
            await message.answer("От 1 до 7 дней. Попробуй еще.")
            return
        await state.update_data(training_days_per_week=days)
        await message.answer("Какие дни (пн, ср, пт)?", reply_markup=get_back_keyboard("waiting_for_personal_bests"))
        await state.set_state(OnboardingState.waiting_for_preferred_days)
    except ValueError:
        await message.answer("Введите число.")

@router.message(OnboardingState.waiting_for_preferred_days)
async def process_preferred_days(message: Message, state: FSMContext):
    days = [d.strip().lower() for d in message.text.split(',')]
    valid_days = {'пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'}
    if not all(d in valid_days for d in days):
        await message.answer("Укажи дни (пн, вт, ср...) через запятую.")
        return
    await state.update_data(preferred_days=message.text.strip())
    await message.answer("Сколько тренировок в день?", reply_markup=get_back_keyboard("waiting_for_days_per_week"))
    await state.set_state(OnboardingState.waiting_for_trainings_per_day)

@router.message(OnboardingState.waiting_for_trainings_per_day)
async def process_trainings_per_day(message: Message, state: FSMContext):
    try:
        trainings = int(message.text)
        if trainings < 1 or trainings > 2:
            await message.answer("1 или 2 тренировки. Попробуй еще.")
            return
        await state.update_data(trainings_per_day=trainings)
        await message.answer("День для длительной тренировки?", reply_markup=get_back_keyboard("waiting_for_preferred_days"))
        await state.set_state(OnboardingState.waiting_for_long_run_day)
    except ValueError:
        await message.answer("Введите число.")

@router.message(OnboardingState.waiting_for_long_run_day)
async def process_long_run_day(message: Message, state: FSMContext):
    day = message.text.strip().lower()
    valid_days = {'пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'}
    if day not in valid_days:
        await message.answer("Укажи день (пн, вт...).")
        return
    await state.update_data(long_run_day=day)
    await message.answer("Текущие травмы?", reply_markup=get_back_keyboard("waiting_for_trainings_per_day"))
    await state.set_state(OnboardingState.waiting_for_current_injuries)

@router.message(OnboardingState.waiting_for_current_injuries)
async def process_current_injuries(message: Message, state: FSMContext):
    await state.update_data(current_injuries=message.text.strip())
    await message.answer("Повторяющиеся травмы?", reply_markup=get_back_keyboard("waiting_for_long_run_day"))
    await state.set_state(OnboardingState.waiting_for_recurring_injuries)

@router.message(OnboardingState.waiting_for_recurring_injuries)
async def process_recurring_injuries(message: Message, state: FSMContext):
    await state.update_data(recurring_injuries=message.text.strip())
    await message.answer("Какой инвентарь есть?", reply_markup=get_back_keyboard("waiting_for_current_injuries"))
    await state.set_state(OnboardingState.waiting_for_equipment)

@router.message(OnboardingState.waiting_for_equipment)
async def process_equipment(message: Message, state: FSMContext):
    await state.update_data(equipment=message.text.strip())
    await message.answer("Инфраструктура (стадион, зал)?", reply_markup=get_back_keyboard("waiting_for_recurring_injuries"))
    await state.set_state(OnboardingState.waiting_for_infrastructure)

@router.message(OnboardingState.waiting_for_infrastructure)
async def process_infrastructure(message: Message, state: FSMContext):
    await state.update_data(infrastructure=message.text.strip())
    await message.answer("Пищевые ограничения?", reply_markup=get_back_keyboard("waiting_for_equipment"))
    await state.set_state(OnboardingState.waiting_for_dietary_restrictions)

@router.message(OnboardingState.waiting_for_dietary_restrictions)
async def process_dietary_restrictions(message: Message, state: FSMContext):
    await state.update_data(dietary_restrictions=message.text.strip())
    await message.answer("Недельный объем (км)?", reply_markup=get_back_keyboard("waiting_for_infrastructure"))
    await state.set_state(OnboardingState.waiting_for_weekly_volume)

@router.message(OnboardingState.waiting_for_weekly_volume)
async def process_weekly_volume(message: Message, state: FSMContext):
    try:
        volume = int(message.text)
        if volume < 0 or volume > 200:
            await message.answer("Объем от 0 до 200 км. Попробуй еще.")
            return
        await state.update_data(weekly_volume_km=volume)
        await message.answer("Дополнительная информация?", reply_markup=get_back_keyboard("waiting_for_dietary_restrictions"))
        await state.set_state(OnboardingState.waiting_for_additional_info)
    except ValueError:
        await message.answer("Введите число.")

@router.message(OnboardingState.waiting_for_additional_info)
async def process_additional_info(message: Message, state: FSMContext):
    await state.update_data(additional_info=message.text.strip())
    user_data = await state.get_data()
    telegram_id = message.from_user.id
    await message.answer("Сохраняю профиль...")

    user = await asyncio.to_thread(get_user_by_telegram_id, telegram_id)
    if user:
        if await asyncio.to_thread(save_onboarding_data, user['id'], user_data):
            await message.answer("Генерирую план (до 1 мин)...")
            profile = await asyncio.to_thread(get_full_user_profile, user['id'])
            if profile:
                prompt = format_prompt_for_detailed_json(profile)
                plan = await generate_structured_plan_with_llm(prompt)
                if "error" not in plan:
                    await asyncio.to_thread(save_generated_plan, user['id'], datetime.now().strftime("%Y-%m-%d"), plan)
                    await message.answer(format_detailed_plan_for_user(plan), parse_mode=ParseMode.MARKDOWN, reply_markup=get_plan_feedback_keyboard())
                    await state.update_data(last_plan=plan)
                else:
                    await message.answer(f"Ошибка генерации: {plan['error']}")
            else:
                await message.answer("Ошибка получения профиля.")
        else:
            await message.answer("Ошибка сохранения профиля.")
    await state.set_state(None)

@router.callback_query(F.data == "edit_profile")
async def restart_onboarding(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Обновим профиль. Как тебя зовут?")
    await state.set_state(OnboardingState.waiting_for_name)
    await callback.answer()

@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отмена. Используй /start.")
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "plan_confirm")
async def confirm_plan(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Отлично! Удачной недели!")
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "plan_edit")
async def edit_plan_request(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Что изменить?")
    await state.set_state(EditingState.waiting_for_changes)
    await callback.answer()

@router.message(EditingState.waiting_for_changes)
async def process_plan_changes(message: Message, state: FSMContext):
    changes = message.text.strip()
    user_data = await state.get_data()
    last_plan = user_data.get("last_plan")
    
    await message.answer("Обновляю план (до 1 мин)...")
    if last_plan:
        prompt = f"Исходный план: {json.dumps(last_plan, ensure_ascii=False)}\nИзменения: {changes}\nПерегенерируй полный план в том же формате JSON."
        new_plan = await generate_structured_plan_with_llm(prompt)
        if "error" not in new_plan:
            await asyncio.to_thread(save_generated_plan, message.from_user.id, datetime.now().strftime("%Y-%m-%d"), new_plan)
            await message.answer(format_detailed_plan_for_user(new_plan), parse_mode=ParseMode.MARKDOWN, reply_markup=get_plan_feedback_keyboard())
            await state.update_data(last_plan=new_plan)
        else:
            await message.answer(f"Ошибка: {new_plan['error']}")
    await state.set_state(None)

# Daily Notifications
async def send_daily_plan(bot: Bot, user_id: int, plan_data: dict):
    today = datetime.now().strftime("%A")
    today_plan = next((d for d in plan_data.get("training_plan", []) if d["day_of_week"].lower() == today.lower()), None)
    today_meal = next((d for d in plan_data.get("meal_plan", []) if d["day_of_week"].lower() == today.lower()), None)
    
    if today_plan or today_meal:
        message = f"📅 План на {today}\n\n"
        if today_plan and today_plan.get("morning_workout", {}).get("type") != "Отдых":
            message += f"- Утро: {today_plan['morning_workout']['type']} - {today_plan['morning_workout']['details']}\n"
        if today_meal:
            message += f"\n🍽️ Питание (~{today_meal['total_calories']} ккал)\n"
            for meal in today_meal.get("meals", []):
                message += f"- {meal['meal_type']}: {meal['description']}\n"
        try:
            await bot.send_message(chat_id=user_id, text=message, parse_mode=ParseMode.MARKDOWN)
            logging.info(f"Sent daily plan to {user_id}")
        except Exception as e:
            logging.error(f"Failed to send to {user_id}: {e}")

async def schedule_daily_notifications(bot: Bot):
    scheduler = AsyncIOScheduler()
    scheduler.start()
    try:
        users = supabase.table('users').select('telegram_id, id').eq('status', 'active').execute().data
        for user in users:
            last_plan = supabase.table('training_plans').select('plan_details').eq('user_id', user['id']).order('created_at', desc=True).limit(1).execute().data
            if last_plan:
                scheduler.add_job(
                    send_daily_plan,
                    CronTrigger(hour=7, minute=0, timezone="Europe/Berlin"),  # 7:00 AM CET
                    args=[bot, user['telegram_id'], last_plan[0]['plan_details']]
                )
                logging.info(f"Scheduled for {user['telegram_id']}")
    except Exception as e:
        logging.error(f"Error scheduling notifications: {e}")

# ASGI-приложение для uvicorn
async def set_main_menu(bot: Bot):
    commands = [
        BotCommand(command="start", description="Начать работу"),
        BotCommand(command="help", description="Получить помощь")
    ]
    await bot.set_my_commands(commands)

async def on_startup(bot: Bot):
    logging.info("Starting bot...")
    await schedule_daily_notifications(bot)
    await set_main_menu(bot)
    await bot.set_webhook(url=WEBHOOK_URL)

async def on_shutdown(bot: Bot):
    logging.info("Shutting down bot...")
    await bot.delete_webhook()
    await bot.session.close()

# Запуск приложения
dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)

# ASGI-приложение для uvicorn
async def app(scope, receive, send):
    if scope["type"] == "http" or scope["type"] == "websocket":
        # Чтение данных из webhook
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)

        # Парсинг обновления из Telegram
        try:
            update = Update(**json.loads(body.decode()))
            # Передача обновления в Dispatcher
            await dp.feed_webhook_update(bot=bot, update=update)
        except Exception as e:
            logging.error(f"Error processing webhook update: {e}")
    else:
        await send({"type": "http.response.start", "status": 400, "headers": [[b"content-type", b"text/plain"]]})
        await send({"type": "http.response.body", "body": b"Unsupported request type"})

async def start_webhook():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    port = int(os.getenv("PORT", 8443))
    logging.info(f"Starting webhook on port {port} with URL {WEBHOOK_URL}")
    await on_startup(bot)
    config = uvicorn.Config(app=app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
    await on_shutdown(bot)

if __name__ == "__main__":
    asyncio.run(start_webhook())