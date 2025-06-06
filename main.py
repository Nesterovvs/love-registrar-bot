import logging
import os
import sqlite3
from datetime import datetime, date
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext

API_TOKEN = os.getenv("BOT_TOKEN")  # Убедитесь, что на Render установлена переменная окружения BOT_TOKEN
ADMIN_ID = 1096930119  # Ваш Telegram ID

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ─────────────────────────────────────────────────────────────────────────────
# Инициализируем базу данных SQLite
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS marriages (
        user1 TEXT,
        user2 TEXT,
        married_at TEXT
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS gifts (
        sender TEXT,
        receiver TEXT,
        gifted_at TEXT
    )
""")
conn.commit()

# ─────────────────────────────────────────────────────────────────────────────
# Временное хранилище для предложений (username → { proposer_id, proposer_username })
pending = {}

# Состояние для рассылки (админ)
class Broadcast(StatesGroup):
    waiting_message = State()

# ─────────────────────────────────────────────────────────────────────────────
# Настраиваем ReplyKeyboardMarkup (главное меню кнопок) под тематику LoveRegistrarBot
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)

# Первая строка: Предложить брак
main_menu.add(KeyboardButton("💍 Предложить брак"))

# Вторая строка: Мой супруг/супруга и Развод
main_menu.add(
    KeyboardButton("💞 Мой супруг/супруга"),
    KeyboardButton("💔 Развод")
)

# Третья строка: Свидетельство и Годовщина
main_menu.add(
    KeyboardButton("📜 Свидетельство"),
    KeyboardButton("📅 Годовщина")
)

# Четвёртая строка: История брака и Мой профиль
main_menu.add(
    KeyboardButton("📖 История брака"),
    KeyboardButton("🧾 Мой профиль")
)

# Пятая строка: Подарок
main_menu.add(
    KeyboardButton("🎁 Подарить сердечко")
)

# Шестая строка: Список команд (справка)
main_menu.add(KeyboardButton("📋 Список команд"))

# ─────────────────────────────────────────────────────────────────────────────
# Обработчик /start и кнопки «📋 Список команд»
@dp.message_handler(commands=['start'])
@dp.message_handler(lambda m: m.text == "📋 Список команд")
async def cmd_start(message: types.Message):
    user = message.from_user
    # Сохраняем пользователя в базе (если ещё не был)
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user.id, (user.username or "").lower(), user.first_name)
    )
    conn.commit()

    text = (
        "💍 Добро пожаловать в LoveRegistrarBot!\n\n"
        "📋 Список команд:\n"
        "💍 Предложить брак — /marry @username\n"
        "💞 Мой супруг/супруга — /my_spouse\n"
        "📜 Свидетельство — /certificate\n"
        "💔 Развод — /divorce\n"
        "📅 Годовщина — /anniversary\n"
        "📖 История брака — /marriage_story\n"
        "🎁 Подарить сердечко — /gift\n"
        "🧾 Мой профиль — /my_marriage_profile\n"
        "📋 Список команд — показать это сообщение снова\n"
        "👑 /broadcast — рассылка (только для админа)\n"
    )
    await message.reply(text, reply_markup=main_menu)

# ─────────────────────────────────────────────────────────────────────────────
# Команда /broadcast — только для админа
@dp.message_handler(commands=['broadcast'])
async def broadcast_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.reply("✉️ Введите сообщение для рассылки (или «Отмена»):", 
                        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("Отмена"))
    await Broadcast.waiting_message.set()

# Обработка отмены рассылки
@dp.message_handler(lambda m: m.text == "Отмена", state=Broadcast.waiting_message)
async def broadcast_cancel(message: types.Message, state: FSMContext):
    await message.reply("❌ Рассылка отменена.", reply_markup=main_menu)
    await state.finish()

# Обработка ввода текста для рассылки
@dp.message_handler(state=Broadcast.waiting_message, content_types=types.ContentTypes.TEXT)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.finish()
        return
    text = message.text
    success = 0
    failed = 0

    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    for (uid,) in users:
        try:
            await bot.send_message(uid, text)
            success += 1
        except:
            failed += 1

    await message.reply(f"📢 Рассылка завершена\n✅ Успешно: {success}\n❌ Ошибок: {failed}", reply_markup=main_menu)
    await state.finish()

# ─────────────────────────────────────────────────────────────────────────────
# Команда /marry @username
@dp.message_handler(commands=['marry'])
async def marry(message: types.Message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].startswith('@'):
        await message.reply("❗ Правильно: /marry @username", reply_markup=main_menu)
        return

    proposer = message.from_user
    if proposer.username is None:
        await message.reply("❗ У вас нет @username. Установите его в настройках Telegram.", reply_markup=main_menu)
        return

    partner_username = parts[1][1:].lower()
    if proposer.username.lower() == partner_username:
        await message.reply("😅 Нельзя жениться на себе.", reply_markup=main_menu)
        return

    # Сохраняем инициатора в базе, если ещё не был
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (proposer.id, proposer.username.lower(), proposer.first_name)
    )
    conn.commit()

    # Помещаем в pending
    pending[partner_username] = {
        "proposer_id": proposer.id,
        "proposer_username": proposer.username.lower()
    }

    # Кнопки для подтверждения/отказа
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("💖 Принять", callback_data=f"accept:{partner_username}"),
        InlineKeyboardButton("❌ Отказать", callback_data=f"decline:{partner_username}")
    )

    # Проверяем, писал ли партнёр боту
    cursor.execute("SELECT user_id FROM users WHERE username=?", (partner_username,))
    partner_row = cursor.fetchone()

    if partner_row:
        partner_id = partner_row[0]
        try:
            await bot.send_message(
                partner_id,
                f"@{partner_username}, @{proposer.username} предлагает тебе брак! 💍",
                reply_markup=markup
            )
            await message.reply(f"✅ Предложение отправлено @{partner_username}.", reply_markup=main_menu)
        except:
            await message.reply(f"❗ Не удалось отправить предложение @{partner_username}. Возможно, он заблокировал бота.", reply_markup=main_menu)
    else:
        await message.reply(f"❗ @{partner_username} ещё не писал боту. Попроси его сначала нажать /start.", reply_markup=main_menu)

# Обработка нажатия «Принять»
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('accept:'))
async def accept(callback: types.CallbackQuery):
    partner = callback.from_user
    if partner.username is None:
        await callback.answer("Ваш @username не задан.", show_alert=True)
        return

    partner_username = partner.username.lower()
    data = pending.get(partner_username)
    if not data:
        await callback.message.edit_text("❗ Предложение не найдено или устарело.")
        return

    proposer_id = data["proposer_id"]
    proposer_username = data["proposer_username"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Сохраняем брак в базе
    cursor.execute(
        "INSERT INTO marriages (user1, user2, married_at) VALUES (?, ?, ?)",
        (proposer_username, partner_username, timestamp)
    )
    cursor.execute(
        "INSERT INTO marriages (user1, user2, married_at) VALUES (?, ?, ?)",
        (partner_username, proposer_username, timestamp)
    )
    conn.commit()

    await callback.message.edit_text(f"🎉 @{proposer_username} и @{partner_username} теперь пара! 🎉", reply_markup=main_menu)

    # Сохраняем партнёра в базе, если ещё нет
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (partner.id, partner_username, partner.first_name)
    )
    conn.commit()

    # Уведомляем обоих участников
    try:
        await bot.send_message(
            proposer_id,
            f"🎉 Вы теперь в браке с @{partner_username}! Пожелаем вам счастья 💖",
            reply_markup=main_menu
        )
    except:
        pass

    try:
        await bot.send_message(
            partner.id,
            f"🎉 Вы теперь в браке с @{proposer_username}! Пожелаем вам счастья 💖",
            reply_markup=main_menu
        )
    except:
        pass

    # Удаляем предложение из pending
    del pending[partner_username]

# Обработка нажатия «Отказать»
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('decline:'))
async def decline(callback: types.CallbackQuery):
    partner = callback.from_user
    if partner.username is None:
        await callback.answer("Ваш @username не задан.", show_alert=True)
        return

    partner_username = partner.username.lower()
    data = pending.get(partner_username)
    if not data:
        await callback.message.edit_text("❗ Предложение не найдено или устарело.")
        return

    proposer_username = data["proposer_username"]
    await callback.message.edit_text(f"💔 @{partner_username} отклонил(а) предложение @{proposer_username}.", reply_markup=main_menu)

    del pending[partner_username]

# ─────────────────────────────────────────────────────────────────────────────
# Команда /my_spouse
@dp.message_handler(commands=['my_spouse'])
async def my_spouse(message: types.Message):
    if message.from_user.username is None:
        await message.reply("❗ Установите @username в настройках Telegram.", reply_markup=main_menu)
        return

    user = message.from_user.username.lower()
    cursor.execute("SELECT user2 FROM marriages WHERE user1=?", (user,))
    row = cursor.fetchone()
    if row:
        await message.reply(f"💍 Ты в браке с @{row[0]}.", reply_markup=main_menu)
    else:
        await message.reply("😢 У тебя нет партнёра.", reply_markup=main_menu)

# Команда /certificate (текстовое)
@dp.message_handler(commands=['certificate'])
async def certificate(message: types.Message):
    if message.from_user.username is None:
        await message.reply("❗ Установите @username в настройках Telegram.", reply_markup=main_menu)
        return

    user = message.from_user.username.lower()
    cursor.execute("SELECT user2, married_at FROM marriages WHERE user1=?", (user,))
    row = cursor.fetchone()
    if row:
        partner, married_at = row
        await message.reply(f"📜 Свидетельство:\n@{user} ❤️ @{partner}\nДата брака: {married_at}", reply_markup=main_menu)
    else:
        await message.reply("💔 Нет зарегистрированного брака.", reply_markup=main_menu)

# Команда /divorce
@dp.message_handler(commands=['divorce'])
async def divorce(message: types.Message):
    if message.from_user.username is None:
        await message.reply("❗ Установите @username в настройках Telegram.", reply_markup=main_menu)
        return

    user = message.from_user.username.lower()
    cursor.execute("SELECT user2 FROM marriages WHERE user1=?", (user,))
    row = cursor.fetchone()
    if row:
        partner = row[0]
        cursor.execute(
            "DELETE FROM marriages WHERE (user1=? AND user2=?) OR (user1=? AND user2=?)",
            (user, partner, partner, user)
        )
        conn.commit()
        await message.reply(f"💔 Брак между @{user} и @{partner} расторгнут.", reply_markup=main_menu)
    else:
        await message.reply("❗ У тебя нет брака.", reply_markup=main_menu)

# Команда /anniversary — сколько дней в браке
@dp.message_handler(commands=['anniversary'])
async def anniversary(message: types.Message):
    if message.from_user.username is None:
        await message.reply("❗ Установите @username в настройках Telegram.", reply_markup=main_menu)
        return

    user = message.from_user.username.lower()
    cursor.execute("SELECT married_at, user2 FROM marriages WHERE user1=?", (user,))
    row = cursor.fetchone()
    if not row:
        await message.reply("😢 У тебя нет брака.", reply_markup=main_menu)
        return

    married_at_str, partner = row
    married_at = datetime.strptime(married_at_str, "%Y-%m-%d %H:%M").date()
    days = (date.today() - married_at).days
    await message.reply(
        f"💞 Вы в браке с @{partner} уже {days} дн{'ей' if days % 10 in (2,3,4) and days % 100 not in (12,13,14) else 'ей'}.",
        reply_markup=main_menu
    )

# Команда /marriage_story — история брака
@dp.message_handler(commands=['marriage_story'])
async def marriage_story(message: types.Message):
    if message.from_user.username is None:
        await message.reply("❗ Установите @username в настройках Telegram.", reply_markup=main_menu)
        return

    user = message.from_user.username.lower()
    cursor.execute("SELECT user2, married_at FROM marriages WHERE user1=?", (user,))
    row = cursor.fetchone()
    if not row:
        await message.reply("😢 У тебя нет брака.", reply_markup=main_menu)
        return

    partner, married_at = row
    married_date = datetime.strptime(married_at, "%Y-%m-%d %H:%M")
    days = (date.today() - married_date.date()).days
    await message.reply(
        f"📖 История:\nВы с @{partner} поженились {married_date.strftime('%d.%m.%Y в %H:%M')}.\n"
        f"💕 Вместе: {days} дн{'ей' if days % 10 in (2,3,4) and days % 100 not in (12,13,14) else 'ей'}.",
        reply_markup=main_menu
    )

# Команда /gift — отправить подарок партнёру (ограничение 1 в день)
@dp.message_handler(commands=['gift'])
async def gift(message: types.Message):
    if message.from_user.username is None:
        await message.reply("❗ Установите @username в настройках Telegram.", reply_markup=main_menu)
        return

    sender = message.from_user.username.lower()
    cursor.execute("SELECT user2 FROM marriages WHERE user1=?", (sender,))
    row = cursor.fetchone()
    if not row:
        await message.reply("😢 У тебя нет партнёра.", reply_markup=main_menu)
        return

    receiver = row[0]
    today_str = date.today().isoformat()
    # Проверяем, был ли подарок сегодня
    cursor.execute("""
        SELECT COUNT(*) FROM gifts
        WHERE sender=? AND receiver=? AND gifted_at=?
    """, (sender, receiver, today_str))
    count_today = cursor.fetchone()[0]
    if count_today >= 1:
        await message.reply("❗ Сегодня вы уже дарили подарок. Попробуйте завтра.", reply_markup=main_menu)
        return

    # Сохраняем подарок
    cursor.execute("INSERT INTO gifts (sender, receiver, gifted_at) VALUES (?, ?, ?)", (sender, receiver, today_str))
    conn.commit()

    # Отправляем уведомление партнёру
    cursor.execute("SELECT user_id FROM users WHERE username=?", (receiver,))
    receiver_row = cursor.fetchone()
    if receiver_row:
        try:
            await bot.send_message(receiver_row[0], f"🎁 @{sender} отправил(а) тебе подарок! 💖", reply_markup=main_menu)
            await message.reply(f"🎁 Подарок отправлен @{receiver}!", reply_markup=main_menu)
        except:
            await message.reply(f"❗ Не удалось отправить подарок @{receiver}.", reply_markup=main_menu)
    else:
        await message.reply(f"❗ Не могу найти @{receiver} в базе.", reply_markup=main_menu)

# Команда /my_marriage_profile — брачный профиль
@dp.message_handler(commands=['my_marriage_profile'])
async def marriage_profile(message: types.Message):
    if message.from_user.username is None:
        await message.reply("❗ Установите @username в настройках Telegram.", reply_markup=main_menu)
        return

    user = message.from_user.username.lower()
    cursor.execute("SELECT user2, married_at FROM marriages WHERE user1=?", (user,))
    row = cursor.fetchone()
    if not row:
        await message.reply("😢 У тебя нет брака.", reply_markup=main_menu)
        return

    partner, married_at = row
    married_date = datetime.strptime(married_at, "%Y-%m-%d %H:%M")
    days = (date.today() - married_date.date()).days

    # Считаем, сколько подарков получил пользователь
    cursor.execute("SELECT COUNT(*) FROM gifts WHERE receiver=?", (user,))
    gifts_received = cursor.fetchone()[0]

    profile_text = (
        f"👤 Ты: @{user}\n"
        f"💞 Супруг: @{partner}\n"
        f"📅 Свадьба: {married_date.strftime('%d.%m.%Y')}\n"
        f"🕒 Вместе: {days} дн{'ей' if days % 10 in (2,3,4) and days % 100 not in (12,13,14) else 'ей'}\n"
        f"🎁 Подарков получено: {gifts_received}"
    )
    await message.reply(profile_text, reply_markup=main_menu)

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
