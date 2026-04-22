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

FREE_TOTAL_LIMIT = 10
LOG_ALL_USERS = "all_history_users.txt"

# --- СЛОВАРЬ ПЕРЕВОДОВ ---
TEXTS = {
    "Русский": {
        "start": "<b>Telecode_AI_Bot</b> 🇲🇩\n\nСоздам профессиональное PDF-резюме с помощью ИИ Claude.\nПервая генерация для новых пользователей — <b>Бесплатно</b>!",
        "btn_create": "🚀 Создать резюме",
        "ask_lang": "Выберите язык резюме:",
        "ask_name": "Введите ваше имя и фамилию:",
        "ask_pos": "Какую должность вы хотите занять?",
        "ask_exp": "Опишите ваш опыт работы:",
        "ask_skills": "Ваши ключевые навыки (через запятую):",
        "gen_wait": "⏳ Claude формирует ваше резюме...",
        "success": "✅ Ваше резюме готово!\n\nС уважением, Telecode 🇲🇩",
        "admin_mode": "🔧 Режим разработчика: Бесплатно.",
        "promo_total": f"🎁 Акция! Вы в числе первых {FREE_TOTAL_LIMIT} тестеров. Это бесплатно!",
        "promo_first": "🎁 Подарок! Ваша первая генерация в Telecode — бесплатно.",
        "invoice_desc": "Генерация профессионального CV",
        "pdf_footer": "Создано Telecode_AI_Bot"
    },
    "Română": {
        "start": "<b>Telecode_AI_Bot</b> 🇲🇩\n\nVoi crea un CV PDF profesional cu ajutorul AI Claude.\nPrima generare pentru utilizatorii noi este <b>Gratuită</b>!",
        "btn_create": "🚀 Creează CV",
        "ask_lang": "Alegeți limba CV-ului:",
        "ask_name": "Introduceți numele și prenumele:",
        "ask_pos": "Ce funcție doriți să ocupați?",
        "ask_exp": "Descrieți experiența de muncă:",
        "ask_skills": "Abilitățile cheie (separate prin virgulă):",
        "gen_wait": "⏳ Claude vă generează CV-ul...",
        "success": "✅ CV-ul este gata!\n\nCu respect, Telecode 🇲🇩",
        "admin_mode": "🔧 Mod dezvoltator: Gratuit.",
        "promo_total": f"🎁 Promoție! Sunteți printre primii {FREE_TOTAL_LIMIT} testeri. Este gratuit!",
        "promo_first": "🎁 Cadou! Prima generare la Telecode este gratuită.",
        "invoice_desc": "Generarea unui CV profesional",
        "pdf_footer": "Creat de Telecode_AI_Bot"
    },
    "English": {
        "start": "<b>Telecode_AI_Bot</b> 🇲🇩\n\nI will create a professional PDF resume using Claude AI.\nFirst generation for new users is <b>Free</b>!",
        "btn_create": "🚀 Create Resume",
        "ask_lang": "Choose resume language:",
        "ask_name": "Enter your full name:",
        "ask_pos": "What position are you applying for?",
        "ask_exp": "Describe your work experience:",
        "ask_skills": "Your key skills (comma separated):",
        "gen_wait": "⏳ Claude is generating your resume...",
        "success": "✅ Your resume is ready!\n\nBest regards, Telecode 🇲🇩",
        "admin_mode": "🔧 Developer Mode: Free.",
        "promo_total": f"🎁 Promo! You are among the first {FREE_TOTAL_LIMIT} testers. It's free!",
        "promo_first": "🎁 Gift! Your first generation at Telecode is free.",
        "invoice_desc": "Professional CV Generation",
        "pdf_footer": "Created by Telecode_AI_Bot"
    }
}

# Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
claude = AsyncAnthropic(api_key=CLAUDE_KEY)
logging.basicConfig(level=logging.INFO)

# --- ФУНКЦИИ ЛОГИКИ ---
def get_total_cv_count():
    if not os.path.exists(LOG_ALL_USERS): return 0
    with open(LOG_ALL_USERS, "r") as f: return len(f.readlines())

def has_user_made_cv(user_id):
    if not os.path.exists(LOG_ALL_USERS): return False
    with open(LOG_ALL_USERS, "r") as f: return str(user_id) in f.read()

def log_cv_generation(user_id):
    with open(LOG_ALL_USERS, "a") as f: f.write(f"{user_id}\n")

class CVForm(StatesGroup):
    language = State()
    full_name = State()
    position = State()
    experience = State()
    skills = State()

def clean_markdown(text):
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'^-{3,}$', '─' * 50, text, flags=re.MULTILINE)
    return text.strip()

def create_pdf(text, lang_name):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = "font.ttf"
    footer_text = TEXTS.get(lang_name, TEXTS["English"])["pdf_footer"]

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
        c.drawString(margin, y, line[:95])
        y -= 15
    
    c.setFont(main_font, 8)
    c.setFillColor(colors.grey)
    c.drawCentredString(width/2, 0.5 * inch, f"{footer_text} • @Telecode_AI_Bot")
    c.save()
    buffer.seek(0)
    return buffer

# --- ХЕНДЛЕРЫ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    # Отправляем уведомление тебе (только если это не ты сам нажал старт)
    if message.from_user.id != ADMIN_ID:
        await notify_admin(message.from_user)

    # Стандартное приветствие
    t = TEXTS["Русский"]
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t["btn_create"], callback_data="start_cv")]
    ])
    await message.answer(t["start"], parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "start_cv")
async def start_survey(callback: types.CallbackQuery, state: FSMContext):
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="Русский"), types.KeyboardButton(text="Română"), types.KeyboardButton(text="English")]
    ], resize_keyboard=True)
    await callback.message.answer(TEXTS["Русский"]["ask_lang"], reply_markup=kb)
    await state.set_state(CVForm.language)

@dp.message(CVForm.language)
async def process_lang(message: types.Message, state: FSMContext):
    lang = message.text if message.text in TEXTS else "Русский"
    await state.update_data(language=lang)
    await message.answer(TEXTS[lang]["ask_name"], reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(CVForm.full_name)

@dp.message(CVForm.full_name)
async def process_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data['language']
    await state.update_data(full_name=message.text)
    await message.answer(TEXTS[lang]["ask_pos"])
    await state.set_state(CVForm.position)

@dp.message(CVForm.position)
async def process_pos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data['language']
    await state.update_data(position=message.text)
    await message.answer(TEXTS[lang]["ask_exp"])
    await state.set_state(CVForm.experience)

@dp.message(CVForm.experience)
async def process_exp(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data['language']
    await state.update_data(experience=message.text)
    await message.answer(TEXTS[lang]["ask_skills"])
    await state.set_state(CVForm.skills)

@dp.message(CVForm.skills)
async def request_payment(message: types.Message, state: FSMContext):
    await state.update_data(skills=message.text)
    data = await state.get_data()
    lang = data['language']
    t = TEXTS[lang]

async def notify_admin(user: types.User):
    try:
        text = (
            f"🔔 <b>Новый пользователь в боте!</b>\n\n"
            f"👤 Имя: {user.full_name}\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"🔗 Юзернейм: @{user.username if user.username else 'нет'}"
        )
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление админу: {e}")
    
    user_id = message.from_user.id
    total_done = get_total_cv_count()
    user_already_did = has_user_made_cv(user_id)

    if user_id == ADMIN_ID:
        await message.answer(t["admin_mode"])
        return await generate_cv(message, state)

    if total_done < FREE_TOTAL_LIMIT:
        await message.answer(t["promo_total"])
        return await generate_cv(message, state)

    if not user_already_did:
        await message.answer(t["promo_first"])
        return await generate_cv(message, state)

    await message.answer_invoice(
        title="PDF CV", description=t["invoice_desc"],
        payload="cv_pay", currency="XTR",
        prices=[types.LabeledPrice(label="CV", amount=PRICE_STARS)],
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
    lang = data['language']
    t = TEXTS[lang]
    msg = await message.answer(t["gen_wait"])
    
    prompt = (
        f"Create a professional resume in {lang}.\n"
        f"Name: {data['full_name']}\nPosition: {data['position']}\n"
        f"Experience: {data['experience']}\nSkills: {data['skills']}\n"
        "NO MARKDOWN. Use CAPITAL HEADERS."
    )

    try:
        response = await claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        pdf = create_pdf(response.content[0].text, lang)
        log_cv_generation(message.from_user.id)
        
        await msg.delete()
        await bot.send_document(
            message.chat.id, 
            types.BufferedInputFile(pdf.read(), filename="Telecode_AI_Bot.pdf"),
            caption=t["success"]
        )
    except Exception as e:
        await message.answer(f"❌ Error: {e}")
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
