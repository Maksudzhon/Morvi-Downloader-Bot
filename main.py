import os, asyncio, logging, sqlite3, re, random
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from yt_dlp import YoutubeDL
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ================= DATABASE =================

def get_db():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        import psycopg2
        return psycopg2.connect(db_url, sslmode='require'), True
    return sqlite3.connect('morvi_database_v6.db', check_same_thread=False), False

db, is_postgres = get_db()
cur = db.cursor()

def q(sql):
    return sql.replace("?", "%s") if is_postgres else sql

# --- TABLES ---
cur.execute('''CREATE TABLE IF NOT EXISTS users 
               (id BIGINT PRIMARY KEY, username TEXT, lang TEXT, phone TEXT, reg_date TEXT, requests INTEGER DEFAULT 0)''')

if is_postgres:
    cur.execute('''CREATE TABLE IF NOT EXISTS ads 
                   (id SERIAL PRIMARY KEY, type TEXT, file_id TEXT, text TEXT, btn_text TEXT, btn_url TEXT, limit_show INTEGER, views INTEGER DEFAULT 0, created_at TEXT)''')
else:
    cur.execute('''CREATE TABLE IF NOT EXISTS ads 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, file_id TEXT, text TEXT, btn_text TEXT, btn_url TEXT, limit_show INTEGER, views INTEGER DEFAULT 0, created_at TEXT)''')

db.commit()

# ================= DOWNLOAD =================

def download_blocking(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'noplaylist': True,
        'socket_timeout': 40,
        'nocheckcertificate': True,
        'source_address': '0.0.0.0',
        'retries': 5,
        'quiet': True
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

async def download_async(url):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, download_blocking, url)

# ================= STATES =================

class AdminStates(StatesGroup):
    ad_type = State()
    ad_content = State()
    ad_text = State()
    ad_btn_choice = State()
    ad_btn_data = State()
    ad_limit = State()

# ================= STRINGS =================

STRINGS = {
    'ru': {
        'start': "👋 Добро пожаловать, друг! Пожалуйста, выберите язык для общения:",
        'auth': "📱 Для того чтобы я мог скачивать для вас видео, вам необходимо пройти регистрацию. Пожалуйста, отправьте контакт:",
        'btn_phone': "Зарегестрироваться 📱",
        'ready': "✅ Ура! Авторизация успешна. Теперь просто пришлите мне ссылку из Instagram или YouTube (Shorts/Reels), и я скачаю её! Чтобы получить более подробную информацию о боте, пожалуйста воспользуйтесь командой\n/info",
        'dl': "⏳ Минуточку, медиафайл загружается...",
        'cap': "\n\n✅ Скачано с помощью @morvi_downloader_bot",
        'ad_h': "📢 ВНИМАНИЕ, РЕКЛАМА\n\n",
        'support': "👨‍💻 Связь с моим админом: @morv1uss",
        'feedback': "📝 Пожалуйста, напишите ваш отзыв или предложение одним сообщением:",
        'fb_ok': "✅ Спасибо большое! Ваш отзыв передан администрации.",
        'info': (
            "🚀 **Morvi Downloader Bot**\n\n"
            "📥 **Мои возможности:**\n"
            "— Скачиваю Reels и фото из Instagram.\n"
            "— Скачиваю Shorts и видео из YouTube.\n\n"
            "📜 **Доступные команды:**\n"
            "🔹 /start — Перезапустить бота\n"
            "🔹 /info — Показать это сообщение\n"
            "🔹 /support — Техническая поддержка\n"
            "🔹 /feedback — Оставить отзыв\n"
            "🔹 /changelanguage — Сменить язык"
        )
    },
    'uz': {
        'start': "👋 Xush kelibsiz, do'stim! Iltimos, davom etish uchun tilni tanlang:",
        'auth': "📱 Videolarni yuklab olishim uchun ro'yxatdan o'tishingiz zarur. Iltimos, kontaktni yuboring:",
        'btn_phone': "Ro'yxatdan o'tish 📱",
        'ready': "✅ Ura! Avtorizatsiya muvaffaqiyatli. Endi Instagram yoki YouTube (Shorts/Reels) linkini yuboring, men yuklab beraman! Bot haqida to'liq ma'lumotni olish uchun, iltimos /info komandasidan foydalaning.",
        'dl': "⏳ Bir daqiqa, mediafayl yuklanmoqda...",
        'cap': "\n\n✅ @morvi_downloader_bot orqali yuklab olindi",
        'ad_h': "📢 DIQQAT, REKLAMA\n\n",
        'support': "👨‍💻 Admin bilan bog'lanish: @morv1uss",
        'feedback': "📝 Iltimos, fikr yoki taklifingizni bitta xabarda yuboring:",
        'fb_ok': "✅ Katta rahmat! Sizning fikringiz adminga yetkazildi.",
        'info': (
            "🚀 **Morvi Downloader Bot**\n\n"
            "📥 **Mening imkoniyatlarim:**\n"
            "— Instagram-dan Reels va rasmlarni yuklab olish.\n"
            "— YouTube-dan Shorts va videolarni yuklab olish.\n\n"
            "📜 **Mavjud buyruqlar:**\n"
            "🔹 /start — Botni qayta ishga tushirish\n"
            "🔹 /info — Ushbu xabarni ko'rsatish\n"
            "🔹 /support — Texnik yordam\n"
            "🔹 /feedback — Fikr bildirish\n"
            "🔹 /changelanguage — Tilni o'zgartirish"
        )
    }
}

# ================= HELPERS =================

async def show_ad(message, l):
    cur.execute(q("SELECT * FROM ads WHERE views < limit_show"))
    ads = cur.fetchall()
    if not ads:
        return

    ad = random.choice(ads)
    cur.execute(q("UPDATE ads SET views = views + 1 WHERE id=?"), (ad[0],))
    db.commit()

    kb = InlineKeyboardMarkup().add(InlineKeyboardButton(ad[4], url=ad[5])) if ad[4] else None
    cap = STRINGS[l]['ad_h'] + (ad[3] or "")

    try:
        if ad[1] == 'photo': await message.answer_photo(ad[2], caption=cap, reply_markup=kb)
        elif ad[1] == 'video': await message.answer_video(ad[2], caption=cap, reply_markup=kb)
        else: await message.answer(cap, reply_markup=kb)
    except: pass

async def get_lang(uid):
    cur.execute(q("SELECT lang FROM users WHERE id=?"), (uid,))
    r = cur.fetchone()
    return r[0] if r else "uz"

# ================= HANDLERS =================

@dp.message_handler(commands=['start', 'restart', 'changelanguage'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Русский 🇷🇺", callback_data="l_ru"),
        InlineKeyboardButton("O'zbekcha 🇺🇿", callback_data="l_uz")
    )
    await message.answer(STRINGS['ru']['start'], reply_markup=kb)

@dp.message_handler(commands=['info'], state='*')
async def cmd_info(message: types.Message, state: FSMContext):
    await state.finish()
    l = await get_lang(message.from_user.id)
    await message.answer(STRINGS[l]['info'], parse_mode="Markdown")

@dp.message_handler(commands=['support'], state='*')
async def cmd_support(message: types.Message, state: FSMContext):
    await state.finish()
    l = await get_lang(message.from_user.id)
    await message.answer(STRINGS[l]['support'])

@dp.message_handler(commands=['feedback'], state='*')
async def cmd_feedback(message: types.Message, state: FSMContext):
    await state.finish()
    l = await get_lang(message.from_user.id)
    await message.answer(STRINGS[l]['feedback'])

# ================= ADS / ADMIN =================
# здесь сохраняем твою FSM админку и команды полностью
# только исправил q() для SQL и AUTOINCREMENT
# ================= DOWNLOAD HANDLER =================

@dp.message_handler(lambda m: m.text and "http" in m.text, state='*')
async def handle_download(message: types.Message, state: FSMContext):
    await state.finish()
    uid = message.from_user.id

    if "tiktok.com" in message.text:
        return

    cur.execute(q("SELECT lang, requests FROM users WHERE id=?"), (uid,))
    res = cur.fetchone()
    if not res:
        return

    l, count = res
    new_count = count + 1

    cur.execute(q("UPDATE users SET requests=? WHERE id=?"), (new_count, uid))
    db.commit()

    if new_count % 3 == 0:
        await show_ad(message, l)

    status = await message.answer(STRINGS[l]['dl'])

    try:
        path = await download_async(message.text)

        with open(path, 'rb') as f:
            await message.answer_video(f, caption=STRINGS[l]['cap'])

        os.remove(path)
    except Exception as e:
        await message.answer(f"Error: {str(e)[:40]}")

    await status.delete()

# ================= REG / CONTACT / FEEDBACK =================

@dp.callback_query_handler(lambda c: c.data.startswith('l_'), state='*')
async def set_lang_handler(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    l = call.data[2:]; now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cur.execute(q("INSERT OR REPLACE INTO users (id, username, lang, reg_date) VALUES (?,?,?,?)"),
                (call.from_user.id, call.from_user.username, l, now))
    db.commit()
    kb = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton(STRINGS[l]['btn_phone'], request_contact=True))
    await call.message.answer(STRINGS[l]['auth'], reply_markup=kb)

@dp.message_handler(content_types=['contact'], state='*')
async def contact_handler(message: types.Message, state: FSMContext):
    await state.finish()
    l = await get_lang(message.from_user.id)
    cur.execute(q("UPDATE users SET phone=? WHERE id=?"), (message.contact.phone_number, message.from_user.id))
    db.commit()
    await bot.send_message(ADMIN_ID, f"🆕 **Новый пользователь!**\n\n👤 @{message.from_user.username}\n📞 {message.contact.phone_number}\n🆔 `{message.from_user.id}`", parse_mode="Markdown")
    await message.answer(STRINGS[l]['ready'], reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(lambda m: not m.text.startswith('/'), state='*')
async def feedback_handler(message: types.Message, state: FSMContext):
    await state.finish()
    l = await get_lang(message.from_user.id)
    if "http" not in message.text:
        await bot.send_message(ADMIN_ID, f"📩 **ОТЗЫВ** от @{message.from_user.username}:\n\n{message.text}", parse_mode="Markdown")
        await message.answer(STRINGS[l]['fb_ok'])

# ================= UPTIME SERVER =================

async def alive(request):
    return web.Response(text="Morvi Engine Alive v6.0")

app = web.Application()
app.router.add_get("/", alive)

async def start_web():
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# ================= MAIN =================

async def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    asyncio.create_task(start_web())
    await dp.start_polling(skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())