# main.py

import os
import sqlite3
import logging
from datetime import date, datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

# ─── Конфигурация ────────────────────────────────────────────────────────────

API_TOKEN    = os.getenv("BOT_TOKEN")                       # токен бота
WEBHOOK_HOST  = os.getenv("WEBHOOK_HOST", "")                # например https://your-app.onrender.com
WEBHOOK_PATH  = "/webhook"
WEBHOOK_URL   = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

if not API_TOKEN:
    logging.error("Не задан BOT_TOKEN")
    exit(1)

# ─── Логирование ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Инициализация бота ──────────────────────────────────────────────────────
bot = Bot(token=API_TOKEN)
dp  = Dispatcher(bot)

# ─── Подключаемся к SQLite ────────────────────────────────────────────────────
conn   = sqlite3.connect("database.db")
cursor = conn.cursor()

# Таблица браков
cursor.execute("""
CREATE TABLE IF NOT EXISTS marriages (
    user1 TEXT,
    user2 TEXT,
    married_at TEXT
)
""")
# Таблица пользователей
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT
)
""")
# Таблица подарков (sender→receiver, gifted_at = YYYY-MM-DD)
cursor.execute("""
CREATE TABLE IF NOT EXISTS gifts (
    sender TEXT,
    receiver TEXT,
    gifted_at TEXT
)
""")
conn.commit()

# ─── «Отложенные» предложения (пока не приняты) ─────────────────────────────────
# key = partner_username, value = {"proposer_id": int, "proposer_username": str}
pending = {}

# ─── Reply-клавиатура с самыми важными кнопками ─────────────────────────────────
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("💍 Предложить брак"))
main_menu.add(KeyboardButton("💞 Мой супруг/супруга"), KeyboardButton("💔 Развод"))
main_menu.add(KeyboardButton("🎁 Подарить сердечко"))
main_menu.add(KeyboardButton("📋 Список команд"))

# ─── Хэндлер /start и «📋 Список команд» ────────────────────────────────────────
@dp.message_handler(commands=['start'])
@dp.message_handler(lambda m: m.text == "📋 Список команд")
async def cmd_start(message: types.Message):
    user = message.from_user
    # Сохраняем пользователя (если ещё нет)
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user.id, (user.username or "").lower(), user.first_name)
    )
    conn.commit()

    text = (
        "📋 <b>Список команд</b>:\n\n"
        "💍 /marry @username — предложить брак\n"
        "💞 /my_spouse — узнать супруга/супругу\n"
        "💔 /divorce — расторгнуть брак\n"
        "🎁 /gift — подарить сердечко (1 раз в день)\n"
        "📋 Список команд — показать это сообщение снова\n"
    )
    await message.reply(text, parse_mode="HTML", reply_markup=main_menu)

# ─── Хэндлер /marry @username ──────────────────────────────────────────────────
@dp.message_handler(commands=['marry'])
async def cmd_marry(message: types.Message):
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].startswith('@'):
        await message.reply("❗ Правильно: <code>/marry @username</code>", parse_mode="HTML", reply_markup=main_menu)
        return

    proposer = message.from_user
    if proposer.username is None:
        await message.reply("❗ У вас нет @username. Установите его в Telegram-настройках.", reply_markup=main_menu)
        return

    partner_username = parts[1][1:].lower()
    if proposer.username.lower() == partner_username:
        await message.reply("😅 Нельзя жениться на себе.", reply_markup=main_menu)
        return

    # Сохраняем инициатора в users (если нет)
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (proposer.id, proposer.username.lower(), proposer.first_name)
    )
    conn.commit()

    pending[partner_username] = {
        "proposer_id": proposer.id,
        "proposer_username": proposer.username.lower()
    }

    # Inline-кнопки «Принять / Отказать»
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💖 Принять", callback_data=f"accept:{partner_username}"),
        types.InlineKeyboardButton("❌ Отказать", callback_data=f"decline:{partner_username}")
    )

    # Ищем ID партнёра
    cursor.execute("SELECT user_id FROM users WHERE username=?", (partner_username,))
    row = cursor.fetchone()
    if row:
        partner_id = row[0]
        try:
            await bot.send_message(
                partner_id,
                f"@{partner_username}, @{proposer.username} предлагает тебе брак! 💍",
                reply_markup=markup
            )
            await message.reply(f"✅ Предложение отправлено @{partner_username}.", reply_markup=main_menu)
        except Exception:
            await message.reply(
                f"❗ Не удалось отправить предложение @{partner_username}. Возможно, бот не в контакте с этим пользователем.",
                reply_markup=main_menu
            )
    else:
        await message.reply(
            f"❗ @{partner_username} ещё не запускал бота. Попроси его сначала нажать /start.",
            reply_markup=main_menu
        )

# ─── Callback «accept» ─────────────────────────────────────────────────────────
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("accept:"))
async def callback_accept(callback: types.CallbackQuery):
    partner = callback.from_user
    if partner.username is None:
        await callback.answer("❗ У вас нет @username.", show_alert=True)
        return

    partner_username = partner.username.lower()
    data = pending.get(partner_username)
    if not data:
        await callback.message.edit_text("❗ Предложение не найдено или устарело.")
        return

    proposer_id = data["proposer_id"]
    proposer_username = data["proposer_username"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Сохраняем двусторонний брак
    cursor.execute(
        "INSERT INTO marriages (user1, user2, married_at) VALUES (?, ?, ?)",
        (proposer_username, partner_username, timestamp)
    )
    cursor.execute(
        "INSERT INTO marriages (user1, user2, married_at) VALUES (?, ?, ?)",
        (partner_username, proposer_username, timestamp)
    )
    conn.commit()

    # Убираем inline-кнопки, меняем текст
    await callback.message.edit_text(f"🎉 @{proposer_username} и @{partner_username} теперь пара! 🎉")

    # Сообщаем инициатору
    try:
        await bot.send_message(
            proposer_id,
            f"🎉 Вы теперь в браке с @{partner_username}! 💖",
            reply_markup=main_menu
        )
    except:
        pass
    # Сообщаем партнёру
    try:
        await bot.send_message(
            partner.id,
            f"🎉 Вы теперь в браке с @{proposer_username}! 💖",
            reply_markup=main_menu
        )
    except:
        pass

    del pending[partner_username]

# ─── Callback «decline» ────────────────────────────────────────────────────────
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("decline:"))
async def callback_decline(callback: types.CallbackQuery):
    partner = callback.from_user
    if partner.username is None:
        await callback.answer("❗ У вас нет @username.", show_alert=True)
        return

    partner_username = partner.username.lower()
    data = pending.get(partner_username)
    if not data:
        await callback.message.edit_text("❗ Предложение не найдено или устарело.")
        return

    proposer_username = data["proposer_username"]
    await callback.message.edit_text(f"💔 @{partner_username} отклонил(а) предложение @{proposer_username}.")

    del pending[partner_username]

# ─── Хэндлер /my_spouse ────────────────────────────────────────────────────────
@dp.message_handler(commands=['my_spouse'])
async def cmd_my_spouse(message: types.Message):
    if message.from_user.username is None:
        await message.reply("❗ Установите @username.", reply_markup=main_menu)
        return

    user = message.from_user.username.lower()
    cursor.execute("SELECT user2 FROM marriages WHERE user1=?", (user,))
    row = cursor.fetchone()
    if row:
        await message.reply(f"💞 Ты в браке с @{row[0]}.", reply_markup=main_menu)
    else:
        await message.reply("😢 У тебя нет супруга(и).", reply_markup=main_menu)

# ─── Хэндлер /divorce ──────────────────────────────────────────────────────────
@dp.message_handler(commands=['divorce'])
async def cmd_divorce(message: types.Message):
    if message.from_user.username is None:
        await message.reply("❗ Установите @username.", reply_markup=main_menu)
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

# ─── Хэндлер /gift ─────────────────────────────────────────────────────────────
@dp.message_handler(commands=['gift'])
async def cmd_gift(message: types.Message):
    if message.from_user.username is None:
        await message.reply("❗ Установите @username.", reply_markup=main_menu)
        return

    sender = message.from_user.username.lower()
    cursor.execute("SELECT user2 FROM marriages WHERE user1=?", (sender,))
    row = cursor.fetchone()
    if not row:
        await message.reply("😢 У тебя нет супруга(и).", reply_markup=main_menu)
        return

    receiver = row[0]
    today_str = date.today().isoformat()
    cursor.execute(
        "SELECT COUNT(*) FROM gifts WHERE sender=? AND receiver=? AND gifted_at=?",
        (sender, receiver, today_str)
    )
    count_today = cursor.fetchone()[0]
    if count_today >= 1:
        await message.reply("❗ Сегодня вы уже дарили сердечко. Попробуйте завтра.", reply_markup=main_menu)
        return

    cursor.execute("INSERT INTO gifts (sender, receiver, gifted_at) VALUES (?, ?, ?)",
                   (sender, receiver, today_str))
    conn.commit()

    cursor.execute("SELECT user_id FROM users WHERE username=?", (receiver,))
    receiver_row = cursor.fetchone()
    if receiver_row:
        try:
            await bot.send_message(
                receiver_row[0],
                f"🎁 @{sender} отправил(а) тебе ❤️!",
                reply_markup=main_menu
            )
            await message.reply(f"🎁 Подарок отправлен @{receiver}!", reply_markup=main_menu)
        except:
            await message.reply(f"❗ Не удалось отправить подарок @{receiver}.", reply_markup=main_menu)
    else:
        await message.reply(f"❗ Невозможно найти @{receiver} в базе.", reply_markup=main_menu)

# ─── Webhook (aiohttp) ─────────────────────────────────────────────────────────
async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook установлен: %s", WEBHOOK_URL)

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    await dp.storage.close()
    await dp.storage.wait_closed()
    logger.info("Webhook удалён")

async def handle_webhook(request: web.Request):
    data   = await request.json()
    update = types.Update.to_object(data)
    await dp.process_update(update)
    return web.Response(text="OK")

def setup_app():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app

if __name__ == "__main__":
    # Проверяем, что WEBHOOK_HOST задан
    if not WEBHOOK_HOST:
        logger.error("Не задан WEBHOOK_HOST")
        exit(1)

    port = int(os.getenv("PORT", "8000"))
    webapp = setup_app()
    web.run_app(webapp, host="0.0.0.0", port=port)
