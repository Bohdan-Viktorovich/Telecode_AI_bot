import os
import logging
import asyncio
import io
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from anthropic import AsyncAnthropic

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch
from reportlab.lib import colors

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv("API_TOKEN")
CLAUDE_KEY = os.getenv("CLAUDE_KEY")
ADMIN_ID = 7262437300
PRICE_STARS = 100

# Настройки акций
FREE_TOTAL_LIMIT = 10  # Общий лимит на старте
LOG_ALL_USERS = "all_history_users.txt" # Все, кто когда-либо делал

if not API_TOKEN or not CLAUDE_KEY:
    exit("Ошибка: Проверьте переменные API_TOKEN и CLAUDE_KEY в Railway!")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
claude = AsyncAnthropic(api_key=CLAUDE_KEY)

logging.basicConfig(level=logging.INFO)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_total_cv_count():
    """Считает общее количество сделанных резюме в системе"""
    if not os.path.exists(LOG_ALL_USERS): return 0
    with open(LOG_ALL_USERS, "r") as f:
        return len(f.readlines())

def has_user_made_cv(user_id):
    """Проверяет, делал ли этот конкретный юзер резюме раньше"""
    if not os.path.exists(LOG_ALL_USERS): return False
    with open(LOG_ALL_USERS, "r") as f:
        return str(user_id) in f.read()

def log_cv_generation(user_id):
    """Записывает ID пользователя после успешной генерации"""
    with open(LOG_ALL_USERS, "a") as f:
        f.write(f"{user_id}\n")

# --- FSM СОСТОЯНИЯ ---
class CVForm(StatesGroup):
    language = State()
    full_name = State()
    position = State()
    experience = State()
    skills = State()

# --- ОЧИСТКА MARKDOWN ---
def clean_markdown(text):
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'^-{3,}$', '─' * 50, text, flags=re.MULTILINE)
    text = re.sub(r'^\s{2,}', '', text, flags=re.MULTILINE)
    return text.strip()

# --- ГЕНЕРАЦИЯ PDF ---
def create_pdf(text):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = "font.ttf"

    try:
        pdfmetrics.registerFont(TTFont('CustomFont', font_name))
        main_font = 'CustomFont'
    except:
        main_font = 'Helvetica'

    clean_text = clean_markdown(text)
    margin = 0.75 * inch
    y = height - margin
    
    c.setFont(main_font, 10)
    for line in clean_text.split('\n'):
        if y < 1 * inch:
            c.showPage()
            y = height - margin
            c.setFont(main_font, 10)
        
        # Визуальное выделение заголовков
        is_header = any(line.startswith(kw) for kw in ['КОНТАКТ', 'ЦЕЛЬ', 'ОПЫТ', 'ОБРАЗОВАН', 'НАВЫК']) or line.endswith(':')
        if is_header:
            c.setFont(main_font, 11)
            c.setFillColor(colors.HexColor('#1a1a2e'))
        else:
            c.setFont(main_font, 10)
            c.setFillColor(colors.black)

        c.drawString(margin, y, line[:95])
        y -= 15
    
    c.setFont(main_font, 8)
    c.setFillColor(colors.grey)
    c.drawCentredString(width/2, 0.5 * inch, "Создано Telecode CV Agent • @Scouter999_bot")
    
    c.save()
    buffer.seek(0)
    return buffer

# --- ХЕНДЛЕРЫ ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🚀 Создать резюме", callback_data="start_cv")]
    ])
    await message.answer(
        "<b>Telecode CV Agent</b> 🇲🇩\n\nСоздам профессиональное PDF-резюме с помощью ИИ Claude.\n"
        "Первая генерация для новых пользователей — <b>Бесплатно</b>!", 
        parse_mode="HTML", reply_markup=kb
    )

@dp.callback_query(F.data == "start_cv")
async def start_survey(callback: types.CallbackQuery, state: FSMContext):
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="Русский"), types.KeyboardButton(text="Română"), types.KeyboardButton(text="English")]
    ], resize_keyboard=True)
    await callback.message.answer("Выберите язык резюме:", reply_markup=kb)
    await state.set_state(CVForm.language)

@dp.message(CVForm.language)
async def process_lang(message: types.Message, state: FSMContext):
    await state.update_data(language=message.text)
    await message.answer("Введите ваше имя и фамилию:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(CVForm.full_name)

@dp.message(CVForm.full_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("Какую должность вы хотите занять?")
    await state.set_state(CVForm.position)

@dp.message(CVForm.position)
async def process_pos(message: types.Message, state: FSMContext):
    await state.update_data(position=message.text)
    await message.answer("Опишите ваш опыт работы:")
    await state.set_state(CVForm.experience)

@dp.message(CVForm.experience)
async def process_exp(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await message.answer("Ваши ключевые навыки (через запятую):")
    await state.set_state(CVForm.skills)

@dp.message(CVForm.skills)
async def request_payment(message: types.Message, state: FSMContext):
    await state.update_data(skills=message.text)
    
    user_id = message.from_user.id
    total_done = get_total_cv_count()
    user_already_did = has_user_made_cv(user_id)

    # 1. ТЫ (АДМИН)
    if user_id == ADMIN_ID:
        await message.answer("🔧 Режим разработчика: Бесплатно.")
        return await generate_cv(message, state)

    # 2. ОБЩАЯ АКЦИЯ (Первые 10 в системе)
    if total_done < FREE_TOTAL_LIMIT:
        await message.answer(f"🎁 Акция! Вы в числе первых {FREE_TOTAL_LIMIT} тестеров. Это бесплатно!")
        return await generate_cv(message, state)

    # 3. ПЕРСОНАЛЬНЫЙ БОНУС (Первый раз для юзера)
    if not user_already_did:
        await message.answer("🎁 Подарок! Ваша первая генерация в Telecode — бесплатно.")
        return await generate_cv(message, state)

    # 4. ПЛАТНО (Если не админ, не в первых 10 и уже делал раньше)
    await message.answer_invoice(
        title="PDF Резюме", description="Генерация CV",
        payload="cv_pay", currency="XTR",
        prices=[types.LabeledPrice(label="Генерация", amount=PRICE_STARS)],
        provider_token=""
    )

@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.successful_payment)
async def on_success(message: types.Message, state: FSMContext):
    await generate_cv(message, state)

async def generate_cv(message: types.Message, state: FSMContext):
    data = await state.get_data()
    msg = await message.answer("⏳ Claude формирует ваше резюме...")
    
    prompt = (
        f"Создай профессиональное резюме на {data['language']}.\n"
        f"Имя: {data['full_name']}\nДолжность: {data['position']}\n"
        f"Опыт: {data['experience']}\nНавыки: {data['skills']}\n"
        "БЕЗ MARKDOWN. Заголовки капсом."
    )

    try:
        response = await claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        pdf = create_pdf(response.content[0].text)
        log_cv_generation(message.from_user.id) # Логируем успех
        
        await msg.delete()
        await bot.send_document(
            message.chat.id, 
            types.BufferedInputFile(pdf.read(), filename="CV_Telecode.pdf"),
            caption="✅ Готово! С уважением, Telecode 🇲🇩"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
