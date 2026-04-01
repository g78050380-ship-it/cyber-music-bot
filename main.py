import os
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from yt_dlp import YoutubeDL

# --- КОНФІГУРАЦІЯ ---
TOKEN = "8219019886:AAHVCWzhM8mIivY_V5m0eZ-QbkudUqfm-68"
ADMIN_ID = 5493592842  # Твій ID Власника

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Кеш для назв треків (щоб не ламалися кнопки через довгі назви)
TRACK_CACHE = {}

class UserStates(StatesGroup):
    waiting_for_playlist_name = State()
    waiting_for_broadcast = State()

ydl_opts = {
    'format': 'm4a/bestaudio/best',
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
}

# --- БАЗА ДАНИХ (ПРО МАКС) ---
def init_db():
    with sqlite3.connect('cyber_music.db') as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)')
        c.execute('CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER, yt_id TEXT, title TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS playlists (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS playlist_tracks (playlist_id INTEGER, yt_id TEXT, title TEXT)')
        conn.commit()

def save_user(user_id):
    with sqlite3.connect('cyber_music.db') as conn:
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO users (id) VALUES (?)', (user_id,))
        conn.commit()

# --- ГОЛОВНЕ МЕНЮ ---
def main_menu_kb():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="🔍 Пошук Треку 🎧"), types.KeyboardButton(text="🔥 Світові Хіти 🌍"))
    builder.row(types.KeyboardButton(text="❤️ Моє Обране ⭐️"), types.KeyboardButton(text="🗂 Мої Плейлисти 💿"))
    builder.row(types.KeyboardButton(text="👤 Мій Профіль 🤖"))
    return builder.as_markup(resize_keyboard=True)

# --- СТАРТ ТА ПРОФІЛЬ ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    save_user(message.from_user.id)
    await message.answer("🎧") # Ті самі навушники для стилю
    welcome_text = (
        f"🌌 **Йоу, {message.from_user.first_name}! Вітаю в CyberMusic!** ⚡️\n\n"
        "Я твій особистий музичний дилер. Качай треки, створюй свої плейлисти та кайфуй від ідеального звуку.\n\n"
        "👇 **Тисни на кнопки нижче і погнали!** 👇"
    )
    await message.answer(welcome_text, reply_markup=main_menu_kb(), parse_mode="Markdown")

@dp.message(F.text == "👤 Мій Профіль 🤖")
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    with sqlite3.connect('cyber_music.db') as conn:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM favorites WHERE user_id = ?', (user_id,))
        fav_count = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM playlists WHERE user_id = ?', (user_id,))
        pl_count = c.fetchone()[0]
    
    profile_text = (
        f"💠 **ТВІЙ КІБЕР-ПРОФІЛЬ** 💠\n\n"
        f"👤 **Слухач:** `{message.from_user.first_name}`\n"
        f"🔑 **ID:** `{user_id}`\n\n"
        f"❤️ **В обраному:** {fav_count} треків\n"
        f"🗂 **Плейлистів:** {pl_count} шт.\n\n"
        f"🔋 *Статус: VIP Music Lover*"
    )
    await message.answer(profile_text, parse_mode="Markdown")

# --- ЛОГІКА ПЛЕЙЛИСТІВ ---
@dp.message(F.text == "🗂 Мої Плейлисти 💿")
async def my_playlists(message: types.Message):
    user_id = message.from_user.id
    with sqlite3.connect('cyber_music.db') as conn:
        c = conn.cursor()
        c.execute('SELECT id, name FROM playlists WHERE user_id = ?', (user_id,))
        playlists = c.fetchall()

    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Створити новий плейлист", callback_data="create_playlist")
    
    if playlists:
        for pl_id, name in playlists:
            kb.button(text=f"💿 {name}", callback_data=f"viewpl_{pl_id}")
    
    kb.adjust(1)
    await message.answer("🗂 **Твої Плейлисти:**\nОбери існуючий або створи новий!", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "create_playlist")
async def ask_playlist_name(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("⌨️ **Введи назву для нового плейлиста:**\n*(Наприклад: Тренування 🏋️‍♂️, Релакс 🧘‍♂️)*")
    await state.set_state(UserStates.waiting_for_playlist_name)
    await callback.answer()

@dp.message(StateFilter(UserStates.waiting_for_playlist_name))
async def save_playlist_name(message: types.Message, state: FSMContext):
    name = message.text[:30] # Обмежуємо довжину
    user_id = message.from_user.id
    with sqlite3.connect('cyber_music.db') as conn:
        c = conn.cursor()
        c.execute('INSERT INTO playlists (user_id, name) VALUES (?, ?)', (user_id, name))
        conn.commit()
    await message.answer(f"✅ Плейлист **'{name}'** успішно створено! Тепер ти можеш додавати туди треки.")
    await state.clear()

@dp.callback_query(F.data.startswith("viewpl_"))
async def view_playlist_tracks(callback: types.CallbackQuery):
    pl_id = callback.data.split("_")[1]
    with sqlite3.connect('cyber_music.db') as conn:
        c = conn.cursor()
        c.execute('SELECT name FROM playlists WHERE id = ?', (pl_id,))
        pl_name = c.fetchone()[0]
        c.execute('SELECT yt_id, title FROM playlist_tracks WHERE playlist_id = ?', (pl_id,))
        tracks = c.fetchall()

    if not tracks:
        return await callback.message.answer(f"🪫 Плейлист **{pl_name}** порожній. Шукай музику і додавай сюди!")

    kb = InlineKeyboardBuilder()
    for yt_id, title in tracks:
        short_title = (title[:30] + '..') if len(title) > 30 else title
        kb.button(text=f"▶️ {short_title}", callback_data=f"dl_{yt_id}")
    kb.adjust(1)
    await callback.message.answer(f"💿 **Плейлист:** {pl_name}\nТисни на трек, щоб слухати:", reply_markup=kb.as_markup())
    await callback.answer()

# --- ДОДАВАННЯ В ПЛЕЙЛИСТ/ОБРАНЕ ---
@dp.callback_query(F.data.startswith("addfav_"))
async def add_to_favorites(callback: types.CallbackQuery):
    video_id = callback.data.split("_")[1]
    title = TRACK_CACHE.get(video_id, "Невідомий трек")
    user_id = callback.from_user.id

    with sqlite3.connect('cyber_music.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM favorites WHERE user_id = ? AND yt_id = ?', (user_id, video_id))
        if c.fetchone():
            await callback.answer("⚠️ Вже є у твоєму Обраному!", show_alert=True)
        else:
            c.execute('INSERT INTO favorites (user_id, yt_id, title) VALUES (?, ?, ?)', (user_id, video_id, title))
            conn.commit()
            await callback.answer("❤️ Трек залетів у твоє Обране!", show_alert=True)

@dp.callback_query(F.data.startswith("addpl_"))
async def ask_where_to_add(callback: types.CallbackQuery):
    video_id = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    with sqlite3.connect('cyber_music.db') as conn:
        c = conn.cursor()
        c.execute('SELECT id, name FROM playlists WHERE user_id = ?', (user_id,))
        playlists = c.fetchall()

    if not playlists:
        return await callback.answer("❌ У тебе ще немає плейлистів! Створи їх у розділі 'Мої Плейлисти'.", show_alert=True)

    kb = InlineKeyboardBuilder()
    for pl_id, name in playlists:
        # Передаємо plid і videoid
        kb.button(text=f"💿 {name}", callback_data=f"save2pl_{pl_id}_{video_id}")
    kb.adjust(1)
    await callback.message.answer("🗂 **В який плейлист додати цей трек?**", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("save2pl_"))
async def save_to_playlist_db(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    pl_id, video_id = parts[1], parts[2]
    title = TRACK_CACHE.get(video_id, "Невідомий трек")

    with sqlite3.connect('cyber_music.db') as conn:
        c = conn.cursor()
        c.execute('INSERT INTO playlist_tracks (playlist_id, yt_id, title) VALUES (?, ?, ?)', (pl_id, video_id, title))
        conn.commit()
    
    await callback.message.delete()
    await callback.answer("✅ Трек успішно додано в плейлист!", show_alert=True)

# --- ПОШУК І СКАЧУВАННЯ ---
@dp.message(F.text.in_(["🔍 Пошук Треку 🎧", "🔥 Світові Хіти 🌍", "❤️ Моє Обране ⭐️"]))
async def handle_menu(message: types.Message):
    if message.text == "🔍 Пошук Треку 🎧":
        await message.answer("🚀 **Пиши назву трека або артиста прямо сюди!**")
    elif message.text == "🔥 Світові Хіти 🌍":
        await search_logic(message, "Global top hits 2026")
    elif message.text == "❤️ Моє Обране ⭐️":
        user_id = message.from_user.id
        with sqlite3.connect('cyber_music.db') as conn:
            c = conn.cursor()
            c.execute('SELECT yt_id, title FROM favorites WHERE user_id = ?', (user_id,))
            favs = c.fetchall()
        if not favs:
            return await message.answer("💔 Твоє обране пусте. Шукай музику і тисни ❤️!")
        kb = InlineKeyboardBuilder()
        for yt_id, title in favs:
            short_title = (title[:30] + '..') if len(title) > 30 else title
            kb.button(text=f"▶️ {short_title}", callback_data=f"dl_{yt_id}")
        kb.adjust(1)
        await message.answer("❤️ **Твої улюблені треки:**", reply_markup=kb.as_markup())

@dp.message(F.text)
async def manual_search(message: types.Message):
    await search_logic(message, message.text)

async def search_logic(message: types.Message, query: str):
    status = await message.answer(f"🌐 **Сканую мережу за запитом:** `{query}`...")
    try:
        search_opts = {'format': 'bestaudio', 'noplaylist': True, 'quiet': True, 'extract_flat': True}
        with YoutubeDL(search_opts) as ydl:
            results = ydl.extract_info(f"ytsearch5:{query}", download=False)['entries']

        if not results:
            return await status.edit_text("❌ Глухо. Нічого не знайшов.")

        kb = InlineKeyboardBuilder()
        for res in results:
            title = res.get('title')
            TRACK_CACHE[res['id']] = title # Кешуємо назву
            short_title = (title[:35] + '..') if len(title) > 35 else title
            kb.button(text=f"🎧 {short_title}", callback_data=f"dl_{res['id']}")
        kb.adjust(1)
        
        await status.delete()
        await message.answer("🎶 **Знайшов! Обирай свій вайб:**", reply_markup=kb.as_markup())
    except Exception as e:
        await status.edit_text("⚠️ Сервера YouTube перевантажені. Спробуй ще раз.")

@dp.callback_query(F.data.startswith("dl_"))
async def download_audio(callback: types.CallbackQuery):
    video_id = callback.data.split("_")[1]
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    status = await callback.message.answer("📥 **Завантажую аудіо... Готуй вуха!** 🎧")
    await callback.answer()

    try:
        if not os.path.exists('downloads'): os.makedirs('downloads')
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = f"downloads/{video_id}.m4a"
            title = info.get('title', 'Track')

        # ФУЛЛ КНОПКИ ДЛЯ ТРЕКУ
        track_kb = InlineKeyboardBuilder()
        track_kb.button(text="❤️ В Обране", callback_data=f"addfav_{video_id}")
        track_kb.button(text="🗂 В Плейлист", callback_data=f"addpl_{video_id}")
        track_kb.adjust(2)

        audio = types.FSInputFile(file_path)
        # Жодного імені розробника. Тільки ім'я слухача.
        await callback.message.answer_audio(
            audio=audio,
            title=title,
            caption=f"🎧 Слухає: {callback.from_user.first_name}",
            reply_markup=track_kb.as_markup()
        )
        
        await status.delete()
        if os.path.exists(file_path): os.remove(file_path)

    except Exception as e:
        await status.edit_text("❌ Помилка завантаження.")

# --- ЗАПУСК ---
async def main():
    init_db() 
    print("🚀 [БОТ ЗАРЯДЖЕНИЙ НА 100% І ГОТОВИЙ РВАТИ] 🚀")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())