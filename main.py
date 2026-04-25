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
ADMIN_USERNAME = "@BohdanViktorovich1"
PRICE_STARS = 100
FREE_TOTAL_LIMIT = 10
LOG_ALL_USERS = "/tmp/all_history_users.txt"

if not API_TOKEN or not CLAUDE_KEY:
    exit("Ошибка: Проверьте переменные API_TOKEN и CLAUDE_KEY в Railway!")

# --- ШРИФТЫ ---
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
    logging.error(f"Ошибка регистрации шрифтов: {e}")

# --- СТИЛИ ---
STYLES = {
    "classic": {
        "sidebar_bg":   "#2c3e50",
        "accent":       "#2980b9",
        "sidebar_text": "#ecf0f1",
    },
    "modern": {
        "sidebar_bg":   "#1a1a2e",
        "accent":       "#e94560",
        "sidebar_text": "#ffffff",
    },
    "green": {
        "sidebar_bg":   "#1b4332",
        "accent":       "#52b788",
        "sidebar_text": "#d8f3dc",
    },
}

# --- ПЕРЕВОДЫ ---
TEXTS = {
    "Русский": {
        "start": (
            "<b>Telecode AI Bot</b> 🇲🇩\n\n"
            "Создам профессиональное PDF-резюме с помощью ИИ Claude.\n"
            "Первые 10 пользователей — <b>Бесплатно!</b>"
        ),
        "btn_create":   "🚀 Создать резюме",
        "ask_lang":     "Выберите язык резюме:",
        "ask_name":     "Введите ваше имя и фамилию:",
        "ask_pos":      "Какую должность вы хотите занять?",
        "ask_exp":      "Опишите ваш опыт работы:",
        "ask_skills":   "Ваши ключевые навыки (через запятую):",
        "ask_style":    "Выберите стиль оформления:",
        "btn_classic":  "🎩 Классический",
        "btn_modern":   "🔥 Современный",
        "btn_green":    "🌿 Зелёный",
        "gen_wait":     "⏳ Claude формирует ваше резюме...",
        "success": (
            "✅ Ваше резюме готово!\n\n"
            "📚 Резюме на английском — это половина успеха.\n"
            "Вторая половина — уверенный английский на собеседовании.\n"
            "Попробуйте урок с репетитором 👇\n"
            "👉 https://preply.sjv.io/PzrmvM\n\n"
            "❓ Есть вопросы или проблема?\n"
            f"Пишите: {ADMIN_USERNAME}\n\n"
            "С уважением, Telecode AI Bot 🇲🇩"
        ),
        "admin_mode":   "🔧 Режим разработчика: бесплатная генерация.",
        "promo_total":  f"🎁 Вы в числе первых {FREE_TOTAL_LIMIT} тестеров — бесплатно!",
        "invoice_desc": "Генерация профессионального CV через ИИ Claude",
        "pdf_footer":   "Создано Telecode AI Bot",
        "prompt_lang":  "русском",
        "section_contacts":   "КОНТАКТНАЯ ИНФОРМАЦИЯ",
        "section_objective":  "ЦЕЛЬ",
        "section_experience": "ОПЫТ РАБОТЫ",
        "section_education":  "ОБРАЗОВАНИЕ",
        "section_skills":     "НАВЫКИ",
    },
    "Română": {
        "start": (
            "<b>Telecode AI Bot</b> 🇲🇩\n\n"
            "Voi crea un CV PDF profesional cu ajutorul AI Claude.\n"
            "Primii 10 utilizatori — <b>Gratuit!</b>"
        ),
        "btn_create":   "🚀 Creează CV",
        "ask_lang":     "Alegeți limba CV-ului:",
        "ask_name":     "Introduceți numele și prenumele:",
        "ask_pos":      "Ce funcție doriți să ocupați?",
        "ask_exp":      "Descrieți experiența de muncă:",
        "ask_skills":   "Abilitățile cheie (separate prin virgulă):",
        "ask_style":    "Alegeți stilul CV-ului:",
        "btn_classic":  "🎩 Clasic",
        "btn_modern":   "🔥 Modern",
        "btn_green":    "🌿 Verde",
        "gen_wait":     "⏳ Claude vă generează CV-ul...",
        "success": (
            "✅ CV-ul este gata!\n\n"
            "📚 Un CV bun e primul pas.\n"
            "Al doilea — engleza perfectă la interviu.\n"
            "Încearcă o lecție cu un profesor 👇\n"
            "👉 https://preply.sjv.io/PzrmvM\n\n"
            "❓ Ai întrebări sau o problemă?\n"
            f"Scrie: {ADMIN_USERNAME}\n\n"
            "Cu respect, Telecode AI Bot 🇲🇩"
        ),
        "admin_mode":   "🔧 Mod dezvoltator: gratuit.",
        "promo_total":  f"🎁 Ești printre primii {FREE_TOTAL_LIMIT} testeri — gratuit!",
        "invoice_desc": "Generarea unui CV profesional prin AI Claude",
        "pdf_footer":   "Creat de Telecode AI Bot",
        "prompt_lang":  "română",
        "section_contacts":   "CONTACTE",
        "section_objective":  "OBIECTIV",
        "section_experience": "EXPERIENTA",
        "section_education":  "EDUCATIE",
        "section_skills":     "ABILITATI",
    },
    "English": {
        "start": (
            "<b>Telecode AI Bot</b> 🇲🇩\n\n"
            "I will create a professional PDF resume using Claude AI.\n"
            "First 10 users — <b>Free!</b>"
        ),
        "btn_create":   "🚀 Create Resume",
        "ask_lang":     "Choose resume language:",
        "ask_name":     "Enter your full name:",
        "ask_pos":      "What position are you applying for?",
        "ask_exp":      "Describe your work experience:",
        "ask_skills":   "Your key skills (comma separated):",
        "ask_style":    "Choose your CV style:",
        "btn_classic":  "🎩 Classic",
        "btn_modern":   "🔥 Modern",
        "btn_green":    "🌿 Green",
        "gen_wait":     "⏳ Claude is generating your resume...",
        "success": (
            "✅ Your resume is ready!\n\n"
            "📚 Great resume is step one.\n"
            "Step two — nail your interview in English.\n"
            "Try a lesson with a tutor 👇\n"
            "👉 https://preply.sjv.io/PzrmvM\n\n"
            "❓ Have questions or an issue?\n"
            f"Contact: {ADMIN_USERNAME}\n\n"
            "Best regards, Telecode AI Bot 🇲🇩"
        ),
        "admin_mode":   "🔧 Developer Mode: free generation.",
        "promo_total":  f"🎁 You are among the first {FREE_TOTAL_LIMIT} testers — it's free!",
        "invoice_desc": "Professional CV generation via Claude AI",
        "pdf_footer":   "Created by Telecode AI Bot",
        "prompt_lang":  "English",
        "section_contacts":   "CONTACT INFORMATION",
        "section_objective":  "OBJECTIVE",
        "section_experience": "EXPERIENCE",
        "section_education":  "EDUCATION",
        "section_skills":     "SKILLS",
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
    style = State()

# --- ОЧИСТКА MARKDOWN ---
def clean_markdown(text: str) -> str:
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
    text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)
    return text.strip()

# --- ПАРСИНГ СЕКЦИЙ ---
def parse_sections(text: str) -> dict:
    clean = clean_markdown(text)
    KEYWORDS = {
        'КОНТАКТ': 'contacts', 'ЦЕЛЬ': 'objective',
        'ОПЫТ': 'experience', 'ОБРАЗОВАН': 'education',
        'НАВЫК': 'skills', 'О СЕБЕ': 'about', 'ПРОФИЛЬ': 'about',
        'CONTACT': 'contacts', 'OBJECTIVE': 'objective', 'PROFILE': 'about',
        'EXPERIENCE': 'experience', 'EDUCATION': 'education',
        'SKILLS': 'skills', 'ABOUT': 'about',
        'CONTACTE': 'contacts', 'OBIECTIV': 'objective',
        'EXPERIENTA': 'experience', 'EDUCATIE': 'education',
        'ABILITATI': 'skills',
    }
    sections = {}
    current = 'header'
    buf = []

    for line in clean.split('\n'):
        s = line.strip()
        matched = False
        for kw, key in KEYWORDS.items():
            if s.upper().startswith(kw):
                sections[current] = '\n'.join(buf).strip()
                current = key
                buf = []
                matched = True
                break
        if not matched:
            buf.append(s)

    sections[current] = '\n'.join(buf).strip()
    return sections

# --- ГЕНЕРАЦИЯ PDF С ДИЗАЙНОМ ---
def create_pdf(text: str, lang: str, style_key: str = "classic") -> io.BytesIO:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    st = STYLES.get(style_key, STYLES["classic"])
    footer_text = TEXTS.get(lang, TEXTS["Русский"])["pdf_footer"]

    sidebar_bg    = colors.HexColor(st["sidebar_bg"])
    accent        = colors.HexColor(st["accent"])
    sidebar_txt   = colors.HexColor(st["sidebar_text"])

    sections = parse_sections(text)

    SIDEBAR_W = 170

    # --- БОКОВАЯ ПАНЕЛЬ ---
    c.setFillColor(sidebar_bg)
    c.rect(0, 0, SIDEBAR_W, height, fill=1, stroke=0)

    # Акцентная полоска
    c.setFillColor(accent)
    c.rect(SIDEBAR_W, 0, 4, height, fill=1, stroke=0)

    # Круг с инициалами
    header_text = sections.get('header', '')
    name = header_text.split('\n')[0].strip() if header_text else ''
    initials = ''.join(w[0].upper() for w in name.split()[:2]) if name else 'CV'

    c.setFillColor(accent)
    c.circle(SIDEBAR_W / 2, height - 65, 38, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(BOLD_FONT, 18)
    c.drawCentredString(SIDEBAR_W / 2, height - 71, initials)

    # Имя
    c.setFont(BOLD_FONT, 10)
    c.setFillColor(sidebar_txt)
    name_parts = name.split()
    if len(name_parts) >= 2:
        c.drawCentredString(SIDEBAR_W / 2, height - 118, name_parts[0])
        c.drawCentredString(SIDEBAR_W / 2, height - 131, ' '.join(name_parts[1:]))
    else:
        c.drawCentredString(SIDEBAR_W / 2, height - 124, name)

    # Должность
    header_lines = [l for l in header_text.split('\n') if l.strip()]
    if len(header_lines) > 1:
        c.setFont(MAIN_FONT, 8)
        c.setFillColor(accent)
        c.drawCentredString(SIDEBAR_W / 2, height - 148, header_lines[1][:28])

    # --- ФУНКЦИЯ СЕКЦИИ В САЙДБАРЕ ---
    def sidebar_section(title, content, y):
        if not content.strip() or y < 60:
            return y
        # Заголовок
        c.setFillColor(accent)
        c.rect(10, y - 2, SIDEBAR_W - 20, 16, fill=1, stroke=0)
        c.setFont(BOLD_FONT, 7)
        c.setFillColor(colors.white)
        c.drawString(16, y + 2, title.upper())
        y -= 20

        c.setFont(MAIN_FONT, 7.5)
        c.setFillColor(sidebar_txt)
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                y -= 4
                continue
            if y < 50:
                break
            if line.startswith(('•', '-', '*')):
                line = '• ' + line.lstrip('•-* ')
            # Перенос
            max_ch = 26
            words = line.split()
            cur = ''
            for w in words:
                t = (cur + ' ' + w).strip()
                if len(t) > max_ch and cur:
                    c.drawString(14, y, cur)
                    y -= 11
                    cur = w
                else:
                    cur = t
            if cur and y >= 50:
                c.drawString(14, y, cur)
                y -= 11
        return y - 6

    sb_y = height - 165
    sb_y = sidebar_section("Контакты", sections.get('contacts', ''), sb_y)
    sb_y = sidebar_section("Навыки",   sections.get('skills', ''),   sb_y)
    sb_y = sidebar_section("О себе",   sections.get('about', ''),    sb_y)

    # --- ОСНОВНАЯ ЧАСТЬ ---
    MX = SIDEBAR_W + 14          # левый отступ основной части
    MW = width - MX - 14         # ширина основной части
    my = height - 28

    # Имя крупно
    c.setFont(BOLD_FONT, 20)
    c.setFillColor(colors.HexColor(st["sidebar_bg"]))
    c.drawString(MX, my, name[:32])
    my -= 20

    # Должность
    if len(header_lines) > 1:
        c.setFont(MAIN_FONT, 10)
        c.setFillColor(accent)
        c.drawString(MX, my, header_lines[1][:45])
        my -= 8

    # Линия
    c.setStrokeColor(accent)
    c.setLineWidth(1.5)
    c.line(MX, my, width - 14, my)
    my -= 14

    # --- ФУНКЦИЯ СЕКЦИИ В ОСНОВНОЙ ЧАСТИ ---
    def main_section(title, content, y):
        if not content.strip() or y < 60:
            return y

        # Заголовок секции
        c.setFont(BOLD_FONT, 9)
        c.setFillColor(colors.HexColor(st["sidebar_bg"]))
        c.drawString(MX, y, title.upper())
        c.setStrokeColor(accent)
        c.setLineWidth(0.8)
        c.line(MX, y - 3, width - 14, y - 3)
        y -= 15

        c.setFont(MAIN_FONT, 9)
        c.setFillColor(colors.HexColor('#333333'))

        for line in content.split('\n'):
            line = line.strip()
            if not line:
                y -= 4
                continue
            if y < 50:
                # Новая страница
                c.showPage()
                c.setFillColor(sidebar_bg)
                c.rect(0, 0, SIDEBAR_W, height, fill=1, stroke=0)
                c.setFillColor(accent)
                c.rect(SIDEBAR_W, 0, 4, height, fill=1, stroke=0)
                y = height - 28
                c.setFont(MAIN_FONT, 9)
                c.setFillColor(colors.HexColor('#333333'))

            indent = MX + 6 if line.startswith(('•', '-', '*')) else MX
            if line.startswith(('•', '-', '*')):
                line = '• ' + line.lstrip('•-* ')

            max_ch = int(MW / 5.0)
            words = line.split()
            cur = ''
            for w in words:
                t = (cur + ' ' + w).strip()
                if len(t) > max_ch and cur:
                    if y < 50:
                        break
                    c.drawString(indent, y, cur)
                    y -= 13
                    cur = w
                else:
                    cur = t
            if cur and y >= 50:
                c.drawString(indent, y, cur)
                y -= 13

        return y - 6

    my = main_section("Цель",         sections.get('objective', ''),  my)
    my = main_section("Опыт работы",  sections.get('experience', ''), my)
    my = main_section("Образование",  sections.get('education', ''),  my)

    # Колонтитул
    c.setFont(MAIN_FONT, 7)
    c.setFillColor(colors.HexColor('#aaaaaa'))
    c.drawCentredString(width / 2, 10, f"{footer_text} • @Telecode_AI_Bot")

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
async def process_skills(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('language', 'Русский')
    await state.update_data(skills=message.text)
    t = TEXTS[lang]

    # Показываем кнопки выбора стиля
    kb = types.ReplyKeyboardMarkup(keyboard=[[
        types.KeyboardButton(text=t["btn_classic"]),
        types.KeyboardButton(text=t["btn_modern"]),
        types.KeyboardButton(text=t["btn_green"]),
    ]], resize_keyboard=True)
    await message.answer(t["ask_style"], reply_markup=kb)
    await state.set_state(CVForm.style)

@dp.message(CVForm.style)
async def process_style(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('language', 'Русский')
    t = TEXTS[lang]

    # Определяем стиль по тексту кнопки
    style_map = {
        t["btn_classic"]: "classic",
        t["btn_modern"]:  "modern",
        t["btn_green"]:   "green",
    }
    style_key = style_map.get(message.text, "classic")
    await state.update_data(style=style_key)

    await message.answer("👌", reply_markup=types.ReplyKeyboardRemove())

    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        await message.answer(t["admin_mode"])
        return await generate_cv(message, state)

    if get_total_cv_count() < FREE_TOTAL_LIMIT:
        await message.answer(t["promo_total"])
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
    lang      = data.get('language', 'Русский')
    style_key = data.get('style', 'classic')
    prompt_lang = TEXTS[lang]["prompt_lang"]
    t = TEXTS[lang]

    msg = await message.answer(t["gen_wait"])

    # Жёстко запрещаем придумывать данные
    prompt = (
        f"Создай резюме на {prompt_lang} языке СТРОГО на основе данных ниже.\n"
        f"Имя: {data.get('full_name', '')}\n"
        f"Должность: {data.get('position', '')}\n"
        f"Опыт: {data.get('experience', '')}\n"
        f"Навыки: {data.get('skills', '')}\n\n"
        "КРИТИЧЕСКИ ВАЖНО:\n"
        "- Используй ТОЛЬКО данные которые указаны выше\n"
        "- НЕ придумывай телефоны, email, адреса, даты, компании, университеты\n"
        "- Если данных нет — пропусти этот раздел полностью\n"
        "- НЕ используй markdown: никаких ##, **, --, *, __\n"
        "- Первая строка: только полное имя\n"
        "- Вторая строка: только должность\n"
        "- Затем разделы ЗАГЛАВНЫМИ с двоеточием\n"
        "- Для списков только •\n"
        "- Между разделами одна пустая строка\n"
        "- Только текст резюме, без пояснений"
    )

    try:
        response = await claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        cv_text = response.content[0].text
        pdf = create_pdf(cv_text, lang, style_key)
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
            f"🌐 Язык: {lang} | 🎨 Стиль: {style_key}\n"
            f"📊 Всего: {get_total_cv_count()}",
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"Ошибка генерации: {e}")
        await msg.delete()
        await message.answer(
            f"❌ Ошибка при генерации. Попробуйте ещё раз.\n\n"
            f"Если проблема повторяется — напишите: {ADMIN_USERNAME}"
        )

    await state.clear()

async def main():
    logging.info(f"Шрифт: {MAIN_FONT}")
    logging.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
