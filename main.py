import os, asyncio, logging, sqlite3, re
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from yt_dlp import YoutubeDL
from aiohttp import web
from dotenv import load_dotenv

# --- CONFIG ---
load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- DATABASE ENGINE ---
def get_db():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        import psycopg2
        return psycopg2.connect(db_url, sslmode='require')
    return sqlite3.connect('morvi_database_v6.db', check_same_thread=False)

db = get_db()
cur = db.cursor()
cur.execute('''CREATE TABLE IF NOT EXISTS users 
               (id BIGINT PRIMARY KEY, username TEXT, lang TEXT, phone TEXT, reg_date TEXT, requests INTEGER DEFAULT 0)''')
cur.execute('''CREATE TABLE IF NOT EXISTS ads 
               (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, file_id TEXT, text TEXT, btn_text TEXT, btn_url TEXT, limit_show INTEGER, views INTEGER DEFAULT 0, created_at TEXT)''')
db.commit()

class AdminStates(StatesGroup):
    ad_type = State()
    ad_content = State()
    ad_text = State()
    ad_btn_choice = State()
    ad_btn_data = State()
    ad_limit = State()

# --- LOCALIZATION (Убран TikTok) ---
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

async def get_lang(uid):
    cur.execute("SELECT lang FROM users WHERE id=?", (uid,))
    res = cur.fetchone()
    return res[0] if res else 'uz'

# --- PUBLIC COMMANDS ---
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

# --- ADMIN ADS MANAGEMENT ---
@dp.message_handler(commands=['ads'], user_id=ADMIN_ID, state='*')
async def admin_ads_list(message: types.Message, state: FSMContext):
    await state.finish()
    cur.execute("SELECT id, text, limit_show, views, created_at FROM ads")
    all_ads = cur.fetchall()
    if not all_ads:
        return await message.answer("📝 Пока нет активных рекламных кампаний.")
        
    f_path = "ads_report.txt"
    with open(f_path, "w", encoding="utf-8") as f:
        f.write(f"ADVERTISING REPORT | {datetime.now().strftime('%Y-%m-%d')}\n" + "="*60 + "\n")
        for a in all_ads:
            clean_text = re.sub('<[^<]+?>', '', a[1])[:30]
            f.write(f"ID: {a[0]} | Текст: {clean_text}... | Лимит: {a[2]} | Просм.: {a[3]} | {a[4]}\n")
    
    await message.answer_document(
        open(f_path, "rb"), 
        caption="📋 **Список рекламы.**\n\n🗑 `/del_ad ID` — удалить\n🔄 `/reset_ad ID` — сбросить просмотры",
        parse_mode="Markdown"
    )
    os.remove(f_path)

@dp.message_handler(commands=['del_ad'], user_id=ADMIN_ID, state='*')
async def admin_del_ad(message: types.Message, state: FSMContext):
    await state.finish()
    try:
        ad_id = message.get_args()
        if not ad_id: return await message.answer("⚠️ Введите ID после команды, например: `/del_ad 5`", parse_mode="Markdown")
        cur.execute("DELETE FROM ads WHERE id=?", (ad_id,))
        db.commit()
        await message.answer(f"✅ Реклама с ID **{ad_id}** успешно удалена навсегда.", parse_mode="Markdown")
    except Exception as e: await message.answer(f"⚠️ Ошибка БД: {e}")

@dp.message_handler(commands=['reset_ad'], user_id=ADMIN_ID, state='*')
async def admin_reset_ad(message: types.Message, state: FSMContext):
    await state.finish()
    try:
        ad_id = message.get_args()
        if not ad_id: return await message.answer("⚠️ Введите ID после команды, например: `/reset_ad 5`", parse_mode="Markdown")
        cur.execute("UPDATE ads SET views = 0 WHERE id=?", (ad_id,))
        db.commit()
        await message.answer(f"🔄 Просмотры для рекламы ID **{ad_id}** обнулены. Она снова в ротации!", parse_mode="Markdown")
    except Exception as e: await message.answer(f"⚠️ Ошибка БД: {e}")

# --- OTHER ADMIN COMMANDS ---
@dp.message_handler(commands=['list'], user_id=ADMIN_ID, state='*')
async def admin_users_list(message: types.Message, state: FSMContext):
    await state.finish()
    cur.execute("SELECT id, username, phone, reg_date FROM users")
    users = cur.fetchall()
    f_path = "users_list.txt"
    with open(f_path, "w", encoding="utf-8") as f:
        for u in users: f.write(f"ID: {u[0]} | @{u[1]} | {u[2]} | Дата: {u[3]}\n")
    await message.answer_document(open(f_path, "rb"), caption=f"📄 Всего зарегистрировано {len(users)} юзеров.")
    os.remove(f_path)

@dp.message_handler(commands=['admin'], user_id=ADMIN_ID, state='*')
async def admin_menu(message: types.Message, state: FSMContext):
    await state.finish()
    kb = ReplyKeyboardMarkup(resize_keyboard=True).add("➕ Добавить рекламу")
    await message.answer("🛠 **Панель администратора**\n\n📜 `/ads` — список рекламы\n📄 `/list` — список юзеров", reply_markup=kb, parse_mode="Markdown")

# --- AD CREATION FSM ---
@dp.message_handler(lambda m: m.text == "➕ Добавить рекламу", user_id=ADMIN_ID, state='*')
async def ad_step1(message: types.Message, state: FSMContext):
    await state.finish()
    await AdminStates.ad_type.set()
    kb = ReplyKeyboardMarkup(resize_keyboard=True).add("Photo", "Video", "Text", "Отмена")
    await message.answer("🆕 **Создание новой рекламы**\n\nПожалуйста, выберите тип контента:", reply_markup=kb, parse_mode="Markdown")

@dp.message_handler(state=AdminStates.ad_type)
async def ad_step2(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.finish()
        return await admin_menu(message, state)
        
    await state.update_data(tp=message.text.lower())
    await AdminStates.next()
    await message.answer(f"📥 Теперь, пожалуйста, отправьте сам контент ({message.text}):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("Отмена"))

@dp.message_handler(content_types=['any'], state=AdminStates.ad_content)
async def ad_step3(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.finish()
        return await admin_menu(message, state)
        
    f_id = message.photo[-1].file_id if message.photo else (message.video.file_id if message.video else message.text)
    await state.update_data(fid=f_id)
    await AdminStates.next()
    await message.answer("📝 Введите рекламный текст (подпись к медиа):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("Отмена"))

@dp.message_handler(state=AdminStates.ad_text)
async def ad_step4(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.finish()
        return await admin_menu(message, state)
        
    await state.update_data(txt=message.text)
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Да ✅", callback_data="y"), InlineKeyboardButton("Нет ❌", callback_data="n"))
    await AdminStates.next()
    await message.answer("🔗 Добавить кнопку со ссылкой под рекламу?", reply_markup=kb)

@dp.callback_query_handler(state=AdminStates.ad_btn_choice)
async def ad_step5(call: types.CallbackQuery, state: FSMContext):
    if call.data == 'n':
        await AdminStates.ad_limit.set()
        await call.message.answer("🔢 Пожалуйста, введите лимит показов рекламы (число):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("Отмена"))
    else:
        await AdminStates.next()
        await call.message.answer("⌨️ Введите через пробел: ТекстКнопки Ссылка\n\nПример: `МойКанал https://t.me/super_channel`", parse_mode="Markdown")

@dp.message_handler(state=AdminStates.ad_btn_data)
async def ad_step6(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.finish()
        return await admin_menu(message, state)
        
    p = message.text.split(maxsplit=1)
    if len(p) < 2: 
        return await message.answer("⚠️ Ошибка формата! Введите Текст Кнопки и Ссылку через пробел.", parse_mode="Markdown")
        
    await state.update_data(bt=p[0], bu=p[1])
    await AdminStates.next()
    await message.answer("🔢 И последний шаг. Пожалуйста, введите лимит показов (число):")

@dp.message_handler(state=AdminStates.ad_limit)
async def ad_step_fin(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.finish()
        return await admin_menu(message, state)
        
    d = await state.get_data()
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        cur.execute("INSERT INTO ads (type, file_id, text, btn_text, btn_url, limit_show, created_at) VALUES (?,?,?,?,?,?,?)",
                    (d['tp'], d['fid'], d['txt'], d.get('bt'), d.get('bu'), int(message.text), date))
        db.commit()
        await state.finish()
        await message.answer("✅ Отлично! Реклама успешно создана и добавлена в ротацию.")
        await admin_menu(message, state)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка при сохранении в БД: {e}")
        await state.finish()

# --- DOWN LOGIC & AD LOGIC ---
@dp.message_handler(lambda m: "http" in m.text, state='*')
async def handle_download(message: types.Message, state: FSMContext):
    await state.finish()
    uid = message.from_user.id
    
    # Игнорируем TikTok ссылки
    if "tiktok.com" in message.text or "vt.tiktok" in message.text:
        return

    cur.execute("SELECT lang, requests FROM users WHERE id=?", (uid,))
    res = cur.fetchone()
    if not res: return
    l, count = res
    new_count = count + 1
    cur.execute("UPDATE users SET requests=? WHERE id=?", (new_count, uid))
    db.commit()

    if new_count % 3 == 0:
        cur.execute("SELECT * FROM ads WHERE views < limit_show ORDER BY RANDOM() LIMIT 1")
        ad = cur.fetchone()
        if ad:
            cur.execute("UPDATE ads SET views = views + 1 WHERE id=?", (ad[0],))
            db.commit()
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton(ad[4], url=ad[5])) if ad[4] else None
            cap = STRINGS[l]['ad_h'] + ad[3]
            try:
                if ad[1] == 'photo': await message.answer_photo(ad[2], caption=cap, reply_markup=kb)
                elif ad[1] == 'video': await message.answer_video(ad[2], caption=cap, reply_markup=kb)
                else: await message.answer(cap, reply_markup=kb)
            except: pass

    status = await message.answer(STRINGS[l]['dl'])
    try:
        # Обновленные настройки ydl_opts (для борьбы с таймаутом SSL и IPv6)
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
            info = ydl.extract_info(message.text, download=True)
            path = ydl.prepare_filename(info)
        
        with open(path, 'rb') as f:
            await message.answer_video(f, caption=STRINGS[l]['cap'])
        
        os.remove(path)

    except Exception as e:
        await message.answer(f"Error: {str(e)[:40]}")

    await status.delete()

# --- REGS & FEEDBACK ---
@dp.callback_query_handler(lambda c: c.data.startswith('l_'), state='*')
async def set_lang_handler(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    l = call.data[2:]; now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cur.execute("INSERT OR REPLACE INTO users (id, username, lang, reg_date) VALUES (?,?,?,?)", (call.from_user.id, call.from_user.username, l, now))
    db.commit()
    kb = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton(STRINGS[l]['btn_phone'], request_contact=True))
    await call.message.answer(STRINGS[l]['auth'], reply_markup=kb)

@dp.message_handler(content_types=['contact'], state='*')
async def contact_handler(message: types.Message, state: FSMContext):
    await state.finish()
    l = await get_lang(message.from_user.id)
    cur.execute("UPDATE users SET phone=? WHERE id=?", (message.contact.phone_number, message.from_user.id))
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

# --- UPTIME SERVER ---
# --- UPTIME SERVER ---
async def h(r): 
    return web.Response(text="Morvi Engine Alive v6.0")

app = web.Application()
app.router.add_get("/", h)

if __name__ == '__main__':
    if not os.path.exists('downloads'): 
        os.makedirs('downloads')
    
    # Render динамически назначает порт через переменную окружения PORT
    port = int(os.environ.get("PORT", 8080))
    
    loop = asyncio.get_event_loop()
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    
    # Запускаем веб-сервер на нужном порту
    loop.create_task(web.TCPSite(runner, '0.0.0.0', port).start())
    
    executor.start_polling(dp, skip_updates=True)

