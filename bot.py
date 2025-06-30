import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from config import BOT_TOKEN
from database import insert_user, get_user_by_telegram_id, save_onboarding_data

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- FSM States ---
# Состояния остались те же, все отлично
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

# --- Keyboards ---
def get_back_keyboard(previous_state: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Вернуться к предыдущему вопросу", callback_data=f"back_to:{previous_state}")]
    ])

# --- Bot and Dispatcher Initialization ---
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)

# --- Onboarding Handlers ---

async def command_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    tg_name = message.from_user.full_name
    await asyncio.to_thread(insert_user, user_id, tg_name)
    await message.answer(
        "Привет! Далее в сообщениях я запрошу у тебя информацию, которая понадобится "
        "для дальнейшей аналитики и составления персонализированного плана."
    )
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

# ИСПРАВЛЕНИЕ: Добавил клавиатуру "Назад" ко всем вопросам
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
        await message.answer("Отлично! Теперь о твоих целях - готовишься к какому-то определенному забегу или просто хочешь улучшить свой результат на определенной дистанции?", reply_markup=get_back_keyboard("waiting_for_weight"))
        await state.set_state(OnboardingState.waiting_for_goal)
    except ValueError:
        await message.answer("Пожалуйста, введи вес числом (например, 75.5).", reply_markup=get_back_keyboard("waiting_for_weight"))

async def process_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await message.answer("Что тебя больше всего мотивирует в беге? Хорошее самочувствие, компания друзей или может это время подумать о чём-то?", reply_markup=get_back_keyboard("waiting_for_goal"))
    await state.set_state(OnboardingState.waiting_for_motivation)
    
async def process_motivation(message: Message, state: FSMContext):
    await state.update_data(motivation=message.text)
    await message.answer("Что тебя демотивирует? Лень, рутина, стеснительность, что-то еще?", reply_markup=get_back_keyboard("waiting_for_motivation"))
    await state.set_state(OnboardingState.waiting_for_demotivation)

async def process_demotivation(message: Message, state: FSMContext):
    await state.update_data(demotivation=message.text)
    await message.answer("Хорошо! Теперь узнаем о твоем беговом опыте. Как давно ты бегаешь?", reply_markup=get_back_keyboard("waiting_for_demotivation"))
    await state.set_state(OnboardingState.waiting_for_experience)

async def process_experience(message: Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await message.answer("У тебя есть личные рекорды, которые ты хочешь улучшить? (например: 5 км - 25:00, 10 км - 55:00)", reply_markup=get_back_keyboard("waiting_for_experience"))
    await state.set_state(OnboardingState.waiting_for_personal_bests)

async def process_personal_bests(message: Message, state: FSMContext):
    await state.update_data(personal_bests=message.text)
    await message.answer("Сколько дней в неделю ты готов тренироваться?", reply_markup=get_back_keyboard("waiting_for_personal_bests"))
    await state.set_state(OnboardingState.waiting_for_days_per_week)

async def process_days_per_week(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи количество дней числом.", reply_markup=get_back_keyboard("waiting_for_personal_bests"))
        return
    await state.update_data(training_days_per_week=int(message.text))
    await message.answer("В какие дни недели? (Например: пн, ср, пт)", reply_markup=get_back_keyboard("waiting_for_days_per_week"))
    await state.set_state(OnboardingState.waiting_for_preferred_days)

async def process_preferred_days(message: Message, state: FSMContext):
    await state.update_data(preferred_days=message.text)
    await message.answer("Сколько раз в день готов тренироваться?", reply_markup=get_back_keyboard("waiting_for_preferred_days"))
    await state.set_state(OnboardingState.waiting_for_trainings_per_day)

async def process_trainings_per_day(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи количество тренировок числом.", reply_markup=get_back_keyboard("waiting_for_preferred_days"))
        return
    await state.update_data(trainings_per_day=int(message.text))
    await message.answer("С беговым опытом закончили, переходим к проблемам - твои травмы! Есть ли у тебя сейчас травмы или проблемы, которые нужно учесть при составлении тренировок?", reply_markup=get_back_keyboard("waiting_for_trainings_per_day"))
    await state.set_state(OnboardingState.waiting_for_current_injuries)

async def process_current_injuries(message: Message, state: FSMContext):
    await state.update_data(current_injuries=message.text)
    await message.answer("Есть ли травмы, которые прямо сейчас себя не проявляют, но часто возвращаются? Например, при высокой нагрузке или большом объёме?", reply_markup=get_back_keyboard("waiting_for_current_injuries"))
    await state.set_state(OnboardingState.waiting_for_recurring_injuries)

async def process_recurring_injuries(message: Message, state: FSMContext):
    await state.update_data(recurring_injuries=message.text)
    await message.answer("Теперь об оборудовании и инфраструктуре. Какой спортивный инвентарь у тебя есть? Электронные часы, нагрудный пульсометр, гири, гантели, коврик для фитнеса, массажный мяч и прочее. Напиши всё!", reply_markup=get_back_keyboard("waiting_for_recurring_injuries"))
    await state.set_state(OnboardingState.waiting_for_equipment)

async def process_equipment(message: Message, state: FSMContext):
    await state.update_data(equipment=message.text)
    await message.answer("Есть ли у тебя возможность посещать стадион или манеж? Если 'да', то сколько метров круг? Ходишь ли в спортзал, баню или сауну?", reply_markup=get_back_keyboard("waiting_for_equipment"))
    await state.set_state(OnboardingState.waiting_for_infrastructure)

async def process_infrastructure(message: Message, state: FSMContext):
    await state.update_data(infrastructure=message.text)
    await message.answer("Теперь о еде! Чтобы составить план питания, основываясь на твои предпочтения, напиши, что не любишь есть или на какие продукты у тебя аллергия?", reply_markup=get_back_keyboard("waiting_for_infrastructure"))
    await state.set_state(OnboardingState.waiting_for_dietary_restrictions)
    
async def process_dietary_restrictions(message: Message, state: FSMContext):
    await state.update_data(dietary_restrictions=message.text)
    user_data = await state.get_data()
    telegram_id = message.from_user.id
    await message.answer("Спасибо! Сохраняю твой профиль...")
    
    user = await asyncio.to_thread(get_user_by_telegram_id, telegram_id)
    if user:
        user_db_id = user['id']
        success = await asyncio.to_thread(save_onboarding_data, user_db_id, user_data)
        if success:
            await message.answer("Отлично! Твой профиль создан и сохранен.")
        else:
            await message.answer("Произошла ошибка при сохранении профиля.")
    else:
        await message.answer("Не смог найти твой профиль для сохранения.")
    await state.clear()


# --- Back Button Handler ---
# ИСПРАВЛЕНИЕ: Вынес словарь вопросов в глобальную область, чтобы не дублировать код
QUESTIONS_MAP = {
    "waiting_for_name": ("Давай знакомиться. Я уже представился, а как тебя зовут?", OnboardingState.waiting_for_name, None),
    "waiting_for_age": ("Сколько тебе лет?", OnboardingState.waiting_for_age, get_back_keyboard("waiting_for_name")),
    "waiting_for_height": ("Какой у тебя рост (в сантиметрах)?", OnboardingState.waiting_for_height, get_back_keyboard("waiting_for_age")),
    "waiting_for_weight": ("Какой вес (в килограммах)?", OnboardingState.waiting_for_weight, get_back_keyboard("waiting_for_height")),
    # ИСПРАВЛЕНИЕ: Указал правильное предыдущее состояние
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
    # ИСПРАВЛЕНИЕ: Указал правильное состояние
    "waiting_for_infrastructure": ("Есть ли у тебя возможность посещать стадион или манеж? Если 'да', то сколько метров круг? Ходишь ли в спортзал, баню или сауну?", OnboardingState.waiting_for_infrastructure, get_back_keyboard("waiting_for_equipment")),
    "waiting_for_dietary_restrictions": ("Теперь о еде! Чтобы составить план питания, основываясь на твои предпочтения, напиши, что не любишь есть или на какие продукты у тебя аллергия?", OnboardingState.waiting_for_dietary_restrictions, get_back_keyboard("waiting_for_infrastructure")),
}

@dp.callback_query(F.data.startswith("back_to:"))
async def navigate_back(callback: CallbackQuery, state: FSMContext):
    previous_state_name = callback.data.split(":")[1]
    question_text, new_state, markup = QUESTIONS_MAP.get(previous_state_name)
    
    await callback.message.edit_text(question_text, reply_markup=markup)
    await state.set_state(new_state)
    await callback.answer()


# --- Handler Registration ---
def register_handlers(dp: Dispatcher):
    # ИСПРАВЛЕНИЕ: Зарегистрировал все обработчики
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

# --- Main App Runner ---
async def main():
    register_handlers(dp)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
