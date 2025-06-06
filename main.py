import logging
import os
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext

API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1096930119

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

conn = sqlite3.connect("database.db")
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS marriages (user1 TEXT, user2 TEXT, married_at TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT)")
conn.commit()

pending = {}

class Broadcast(StatesGroup):
    waiting_message = State()

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user = message.from_user
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                   (user.id, user.username, user.first_name))
    conn.commit()
    await message.reply(
        "💍 Добро пожаловать в LoveRegistrarBot!\n"
        "Команды:\n"
        "/marry @user – предложение\n"
        "/certificate – свидетельство\n"
        "/divorce – развод\n"
        "/my_spouse – кто твой партнёр?\n"
        "/broadcast – рассылка (только для админа)"
    )

@dp.message_handler(commands=['broadcast'])
async def broadcast_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.reply("✉️ Введи сообщение для рассылки:")
    await Broadcast.waiting_message.set()

@dp.message_handler(state=Broadcast.waiting_message, content_types=types.ContentTypes.TEXT)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
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
    await message.reply(f"📢 Рассылка завершена\n✅ Успешно: {success}\n❌ Ошибок: {failed}")
    await state.finish()

@dp.message_handler(commands=['marry'])
async def marry(message: types.Message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].startswith('@'):
        await message.reply("❗ Формат: /marry @username")
        return
    proposer = message.from_user
    partner_username = parts[1][1:]

    if proposer.username == partner_username:
        await message.reply("😅 Нельзя жениться на себе")
        return

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                   (proposer.id, proposer.username, proposer.first_name))
    conn.commit()

    pending[partner_username] = {
        "proposer_id": proposer.id,
        "proposer_username": proposer.username
    }

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💖 Принять", callback_data=f"accept_{partner_username}"))
    markup.add(InlineKeyboardButton("❌ Отказать", callback_data=f"decline_{partner_username}"))

    cursor.execute("SELECT user_id FROM users WHERE username=?", (partner_username,))
    partner_row = cursor.fetchone()

    if partner_row:
        try:
            await bot.send_message(partner_row[0], f"@{partner_username}, @{proposer.username} предлагает тебе брак! 💍", reply_markup=markup)
            await message.reply(f"✅ Предложение отправлено @{partner_username}")
        except:
            await message.reply(f"❗ Не удалось отправить сообщение @{partner_username}.")
    else:
        await message.reply(f"❗ @{partner_username} ещё не писал боту. Попроси его нажать /start.")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('accept_'))
async def accept(callback: types.CallbackQuery):
    partner = callback.from_user
    proposer_username = callback.data.split('_')[1]

    proposer_data = pending.get(partner.username)
    if not proposer_data:
        await callback.message.edit_text("❗ Предложение не найдено или устарело.")
        return

    proposer_id = proposer_data["proposer_id"]
    proposer_name = proposer_data["proposer_username"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    cursor.execute("INSERT INTO marriages (user1, user2, married_at) VALUES (?, ?, ?)", (proposer_name, partner.username, timestamp))
    cursor.execute("INSERT INTO marriages (user1, user2, married_at) VALUES (?, ?, ?)", (partner.username, proposer_name, timestamp))
    conn.commit()

    await callback.message.edit_text(f"🎉 @{proposer_name} и @{partner.username} теперь пара!")

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                   (partner.id, partner.username, partner.first_name))
    conn.commit()

    try:
        await bot.send_message(proposer_id, f"🎉 Вы теперь в браке с @{partner.username}!\nПожелаем вам счастья 💖")
    except:
        pass

    try:
        await bot.send_message(partner.id, f"🎉 Вы теперь в браке с @{proposer_name}!\nПожелаем вам счастья 💖")
    except:
        pass

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('decline_'))
async def decline(callback: types.CallbackQuery):
    proposer_username = callback.data.split('_')[1]
    await callback.message.edit_text(f"💔 @{callback.from_user.username} отклонил(а) предложение @{proposer_username}")

@dp.message_handler(commands=['my_spouse'])
async def my_spouse(message: types.Message):
    user = message.from_user.username
    cursor.execute("SELECT user2 FROM marriages WHERE user1=?", (user,))
    row = cursor.fetchone()
    if row:
        await message.reply(f"💍 Ты в браке с @{row[0]}")
    else:
        await message.reply("😢 У тебя нет партнёра")

@dp.message_handler(commands=['certificate'])
async def certificate(message: types.Message):
    user = message.from_user.username
    cursor.execute("SELECT user2, married_at FROM marriages WHERE user1=?", (user,))
    row = cursor.fetchone()
    if row:
        await message.reply(f"📜 Свидетельство:\n@{user} ❤️ @{row[0]}\nДата брака: {row[1]}")
    else:
        await message.reply("💔 Нет зарегистрированного брака")

@dp.message_handler(commands=['divorce'])
async def divorce(message: types.Message):
    user = message.from_user.username
    cursor.execute("SELECT user2 FROM marriages WHERE user1=?", (user,))
    row = cursor.fetchone()
    if row:
        partner = row[0]
        cursor.execute("DELETE FROM marriages WHERE user1 IN (?, ?)", (user, partner))
        conn.commit()
        await message.reply(f"💔 Брак между @{user} и @{partner} расторгнут")
    else:
        await message.reply("❗ У тебя нет брака")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
