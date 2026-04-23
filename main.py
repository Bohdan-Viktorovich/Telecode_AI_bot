import os
import logging
import asyncio
import io
import re
import urllib.request
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
LOG_ALL_USERS = "/tmp/all_history_users.txt"  # /tmp/ работает на Railway

if not API_TOKEN or not CLAUDE_KEY:
    exit("Ошибка: Проверьте переменные API_TOKEN и CLAUDE_KEY в Railway!")

# --- ШРИФТЫ: скачиваем с CDN при старте ---
FONT_PATH = "/tmp/DejaVuSans.ttf"
FONT_BOLD_PATH = "/tmp/DejaVuSans-Bold.ttf"

def download_fonts():
    fonts = {
        FONT_PATH: "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans.ttf",
        FONT_BOLD_PATH: "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans-Bold.ttf",
    }
    for path, url in fonts.items():
        if not os.path.exists(path):
            try:
                logging.info(f"Скачиваю шрифт: {path}")
                urllib.request.urlretrieve(url, path)
                logging.info(f"Готово: {path}")
            except Exception as e:
                logging.error(f"Не удалось скачать шрифт {path}: {e}")

download_fonts()

# Регистрируем шрифты
MAIN_FONT = 'Helvetica'
BOLD_FONT = 'Helvetica-Bold'
try:
    if os.path.exists(FONT_PATH):
        pdfmetrics.registerFont(TTFont('DejaVu', FONT_PATH))
        MAIN_FONT = 'DejaVu'
    if os.path.exists(FONT_BOLD_PATH):
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', FONT_BOLD_PATH))
        BOLD_FONT = 'DejaVu-Bold'
    logging.info(f"Шрифты: {MAIN_FONT} / {BOLD_FONT}")
except Exception as e:
    logging.error(f"Ошибка регистрации шрифтов, используем Helvetica: {e}")

# --- ПЕРЕВОДЫ ---
TEXTS = {
    "Русский": {
        "start": (
            "<b>Telecode AI Bot</b> 🇲🇩\n\n"
            "Создам профессиональное PDF-резюме с помощью ИИ Claude.\n"
            "Первая генерация — <b>Бесплатно!</b>"
        ),
        "btn_create": "🚀 Создать резюме",
        "ask_lang": "Выберите язык резюме:",
        "ask_name": "Введите ваше имя и фамилию:",
        "ask_pos": "Какую должность вы хотите занять?",
        "ask_exp": "Опишите ваш опыт работы:",
        "ask_skills": "Ваши ключевые навыки (через запятую):",
        "gen_wait": "⏳ Claude формирует ваше резюме...",
        "success": (
            "✅ Ваше резюме готово!\n\n"
            "📚 Резюме на английском — это половина успеха.\n"
            "Вторая половина — уверенный английский на собеседовании.\n"
            "Попробуйте урок с репетитором 👇\n"
            "👉 https://preply.sjv.io/PzrmvM"
            "С уважением, Telecode AI Bot 🇲🇩"
        ),
        "admin_mode": "🔧 Режим разработчика: бесплатная генерация.",
        "promo_total": f"🎁 Вы в числе первых {FREE_TOTAL_LIMIT} тестеров — бесплатно!",
        "promo_first": "🎁 Первая генерация в Telecode AI — бесплатно!",
        "invoice_desc": "Генерация профессионального CV через ИИ Claude",
        "pdf_footer": "Создано Telecode AI Bot",
        "prompt_lang": "русском",
    },
    "Română": {
        "start": (
            "<b>Telecode AI Bot</b> 🇲🇩\n\n"
            "Voi crea un CV PDF profesional cu ajutorul AI Claude.\n"
            "Prima generare — <b>Gratuită!</b>"
        ),
        "btn_create": "🚀 Creează CV",
        "ask_lang": "Alegeți limba CV-ului:",
        "ask_name": "Introduceți numele și prenumele:",
        "ask_pos": "Ce funcție doriți să ocupați?",
        "ask_exp": "Descrieți experiența de muncă:",
        "ask_skills": "Abilitățile cheie (separate prin virgulă):",
        "gen_wait": "⏳ Claude vă generează CV-ul...",
        "success": (
            "✅ CV-ul este gata!\n\n"
            "📚 Un CV bun e primul pas.\n"
            "Al doilea — engleza perfectă la interviu.\n"
            "Încearcă o lecție cu un profesor 👇\n"
            "👉 https://preply.sjv.io/PzrmvM"
            "Cu respect, Telecode AI Bot 🇲🇩"
        ),
        "admin_mode": "🔧 Mod dezvoltator: gratuit.",
        "promo_total": f"🎁 Ești printre primii {FREE_TOTAL_LIMIT} testeri — gratuit!",
        "promo_first": "🎁 Prima generare la Telecode AI este gratuită!",
        "invoice_desc": "Generarea unui CV profesional prin AI Claude",
        "pdf_footer": "Creat de Telecode AI Bot",
        "prompt_lang": "română",
    },
    "English": {
        "start": (
            "<b>Telecode AI Bot</b> 🇲🇩\n\n"
            "I will create a professional PDF resume using Claude AI.\n"
            "First generation — <b>Free!</b>"
        ),
        "btn_create": "🚀 Create Resume",
        "ask_lang": "Choose resume language:",
        "ask_name": "Enter your full name:",
        "ask_pos": "What position are you applying for?",
        "ask_exp": "Describe your work experience:",
        "ask_skills": "Your key skills (comma separated):",
        "gen_wait": "⏳ Claude is generating your resume...",
        "success": (
            "✅ Your resume is ready!\n\n"
            "📚 Great resume is step one.\n"
            "Step two — nail your interview in English.\n"
            "Try a lesson with a tutor 👇\n"
            "👉 https://preply.sjv.io/PzrmvM"
            "Best regards, Telecode AI Bot 🇲🇩"
        ),
        "admin_mode": "🔧 Developer Mode: free generation.",
        "promo_total": f"🎁 You are among the first {FREE_TOTAL_LIMIT} testers — it's free!",
        "promo_first": "🎁 Your first generation at Telecode AI is free!",
        "invoice_desc": "Professional CV generation via Claude AI",
        "pdf_footer": "Created by Telecode AI Bot",
        "prompt_lang": "English",
    }
}

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
claude = AsyncAnthropic(api_key=CLAUDE_KEY)
logging.basicConfig(level=logging.INFO)

# --- ЛОГИКА ПОЛЬЗОВАТЕЛЕЙ ---

async def notify_admin(user: types.User):
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🔔 <b>Новый пользователь!</b>\n"
            f"👤 {user.full_name}\n"
            f"🆔 <code>{user.id}</code>\n"
            f"🔗 @{user.username or 'нет'}",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка уведомления: {e}")

def get_total_cv_count() -> int:
    if not os.path.exists(LOG_ALL_USERS):
        return 0
    with open(LOG_ALL_USERS, "r") as f:
        return len(f.readlines())

def has_user_made_cv(user_id: int) -> bool:
    if not os.path.exists(LOG_ALL_USERS):
        return False
    with open(LOG_ALL_USERS, "r") as f:
        return str(user_id) in f.read()

def log_cv_generation(user_id: int):
    with open(LOG_ALL_USERS, "a") as f:
        f.write(f"{user_id}\n")

# --- FSM ---
class CVForm(StatesGroup):
    language = State()
    full_name = State()
    position = State()
    experience = State()
    skills = State()

# --- ОЧИСТКА MARKDOWN ---
def clean_markdown(text: str) -> str:
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
    text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)
    return text.strip()

# --- ГЕНЕРАЦИЯ PDF ---
def create_pdf(text: str, lang: str) -> io.BytesIO:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    footer_text = TEXTS.get(lang, TEXTS["Русский"])["pdf_footer"]

    margin = 0.8 * inch
    usable_width = width - 2 * margin
    y = height - margin

    clean_text = clean_markdown(text)

    HEADER_KEYWORDS = [
        'КОНТАКТ', 'ЦЕЛЬ', 'ОПЫТ', 'ОБРАЗОВАН', 'НАВЫК', 'О СЕБЕ',
        'CONTACT', 'OBJECTIVE', 'EXPERIENCE', 'EDUCATION', 'SKILLS', 'ABOUT',
        'CONTACTE', 'OBIECTIV', 'EXPERIENTA', 'EDUCATIE', 'ABILITATI', 'DESPRE'
    ]

    for line in clean_text.split('\n'):
        line = line.strip()

        if not line:
            y -= 8
            continue

        if y < margin + 0.5 * inch:
            c.showPage()
            y = height - margin

        is_header = (
            any(line.upper().startswith(kw) for kw in HEADER_KEYWORDS)
            or (line.endswith(':') and len(line) < 50 and not line.startswith('•'))
        )
        is_bullet = line.startswith(('•', '·', '*'))

        if is_header:
            c.setFont(BOLD_FONT, 11)
            c.setFillColor(colors.HexColor('#1a1a2e'))
            line_height = 15
            # Линия под заголовком
            c.setStrokeColor(colors.HexColor('#dddddd'))
            c.setLineWidth(0.5)
            c.line(margin, y - 3, width - margin, y - 3)
            y -= 5
        elif is_bullet:
            c.setFont(MAIN_FONT, 10)
            c.setFillColor(colors.HexColor('#333333'))
            line_height = 14
            line = '   ' + line
        else:
            c.setFont(MAIN_FONT, 10)
            c.setFillColor(colors.HexColor('#222222'))
            line_height = 14

        # Перенос длинных строк
        max_chars = int(usable_width / 5.5)
        words = line.split(' ')
        current_line = ''

        for word in words:
            test = (current_line + ' ' + word).strip()
            if len(test) > max_chars and current_line:
                if y < margin + 0.3 * inch:
                    c.showPage()
                    y = height - margin
                    c.setFont(BOLD_FONT if is_header else MAIN_FONT, 11 if is_header else 10)
                c.drawString(margin, y, current_line)
                y -= line_height
                current_line = word
            else:
                current_line = test

        if current_line:
            if y < margin + 0.3 * inch:
                c.showPage()
                y = height - margin
            c.drawString(margin, y, current_line)
            y -= line_height

        if is_header:
            y -= 3

    # Колонтитул
    c.setFont(MAIN_FONT, 8)
    c.setFillColor(colors.HexColor('#aaaaaa'))
    c.drawCentredString(width / 2, 0.35 * inch, f"{footer_text} • @Telecode_AI_Bot")

    c.save()
    buffer.seek(0)
    return buffer

# --- ХЕНДЛЕРЫ ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    t = TEXTS["Русский"]
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text=t["btn_create"], callback_data="start_cv")
    ]])
    await message.answer(t["start"], parse_mode="HTML", reply_markup=kb)
    if message.from_user.id != ADMIN_ID:
        await notify_admin(message.from_user)

@dp.callback_query(F.data == "start_cv")
async def start_survey(callback: types.CallbackQuery, state: FSMContext):
    kb = types.ReplyKeyboardMarkup(keyboard=[[
        types.KeyboardButton(text="Русский"),
        types.KeyboardButton(text="Română"),
        types.KeyboardButton(text="English")
    ]], resize_keyboard=True)
    await callback.message.answer(TEXTS["Русский"]["ask_lang"], reply_markup=kb)
    await callback.answer()
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
    lang = data.get('language', 'Русский')
    await state.update_data(full_name=message.text)
    await message.answer(TEXTS[lang]["ask_pos"])
    await state.set_state(CVForm.position)

@dp.message(CVForm.position)
async def process_pos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('language', 'Русский')
    await state.update_data(position=message.text)
    await message.answer(TEXTS[lang]["ask_exp"])
    await state.set_state(CVForm.experience)

@dp.message(CVForm.experience)
async def process_exp(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('language', 'Русский')
    await state.update_data(experience=message.text)
    await message.answer(TEXTS[lang]["ask_skills"])
    await state.set_state(CVForm.skills)

@dp.message(CVForm.skills)
async def request_payment(message: types.Message, state: FSMContext):
    await state.update_data(skills=message.text)
    data = await state.get_data()
    lang = data.get('language', 'Русский')
    t = TEXTS[lang]
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        await message.answer(t["admin_mode"])
        return await generate_cv(message, state)

    if get_total_cv_count() < FREE_TOTAL_LIMIT:
        await message.answer(t["promo_total"])
        return await generate_cv(message, state)

    if not has_user_made_cv(user_id):
        await message.answer(t["promo_first"])
        return await generate_cv(message, state)

    await message.answer_invoice(
        title="PDF CV — Telecode AI",
        description=t["invoice_desc"],
        payload="cv_pay",
        currency="XTR",
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
    lang = data.get('language', 'Русский')
    prompt_lang = TEXTS[lang]["prompt_lang"]
    t = TEXTS[lang]

    msg = await message.answer(t["gen_wait"])

    prompt = (
        f"Ты профессиональный HR-консультант. Создай резюме на {prompt_lang} языке.\n"
        f"Имя: {data.get('full_name', '')}\n"
        f"Должность: {data.get('position', '')}\n"
        f"Опыт: {data.get('experience', '')}\n"
        f"Навыки: {data.get('skills', '')}\n\n"
        "СТРОГИЕ ПРАВИЛА:\n"
        "- ЗАПРЕЩЕНО использовать markdown: никаких ##, **, --, *, __\n"
        "- Заголовки разделов ТОЛЬКО заглавными буквами с двоеточием в конце\n"
        "- Для списков только символ •\n"
        "- Разделы: КОНТАКТНАЯ ИНФОРМАЦИЯ: / ЦЕЛЬ: / ОПЫТ РАБОТЫ: / ОБРАЗОВАНИЕ: / НАВЫКИ:\n"
        "- Между разделами одна пустая строка\n"
        "- Только текст резюме без пояснений"
    )

    try:
        response = await claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        cv_text = response.content[0].text
        pdf = create_pdf(cv_text, lang)
        log_cv_generation(message.from_user.id)

        await msg.delete()
        await bot.send_document(
            message.chat.id,
            types.BufferedInputFile(pdf.read(), filename="CV_Telecode_AI.pdf"),
            caption=t["success"]
        )

        await bot.send_message(
            ADMIN_ID,
            f"📄 <b>Резюме создано!</b>\n"
            f"👤 {message.from_user.full_name} (@{message.from_user.username or 'нет'})\n"
            f"🌐 Язык: {lang}\n"
            f"📊 Всего: {get_total_cv_count()}",
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"Ошибка генерации: {e}")
        await msg.delete()
        await message.answer(f"❌ Ошибка при генерации. Попробуйте ещё раз.\n\nДетали: {e}")

    await state.clear()

async def main():
    logging.info(f"Используемый шрифт: {MAIN_FONT}")
    logging.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
