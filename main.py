import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup

API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1096930119

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

conn = sqlite3.connect("database.db")
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS marriages (user1 TEXT, user2 TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT)")
conn.commit()

pending = {}

class BroadcastState(StatesGroup):
    waiting_for_message = State()

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
        "/admin – только для админа"
    )

@dp.message_handler(commands=['marry'])
async def marry(message: types.Message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].startswith('@'):
        await message.reply("❗ Формат: /marry @username")
        return
    proposer = message.from_user.username
    partner = parts[1][1:]
    if proposer == partner:
        await message.reply("😅 Нельзя жениться на себе")
        return

    pending[partner] = proposer
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💖 Принять", callback_data=f"accept_{proposer}"))
    markup.add(InlineKeyboardButton("❌ Отказать", callback_data=f"decline_{proposer}"))
    await message.reply(f"@{partner}, @{proposer} предлагает тебе брак! 💍", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('accept_'))
async def accept(callback: types.CallbackQuery):
    partner = callback.from_user.username
    proposer = callback.data.split('_')[1]
    cursor.execute("INSERT INTO marriages (user1, user2) VALUES (?, ?)", (proposer, partner))
    cursor.execute("INSERT INTO marriages (user1, user2) VALUES (?, ?)", (partner, proposer))
    conn.commit()
    await callback.message.edit_text(f"🎉 @{proposer} и @{partner} теперь пара!")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('decline_'))
async def decline(callback: types.CallbackQuery):
    proposer = callback.data.split('_')[1]
    await callback.message.edit_text(f"💔 @{callback.from_user.username} отклонил(а) предложение @{proposer}")

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
    cursor.execute("SELECT user2 FROM marriages WHERE user1=?", (user,))
    row = cursor.fetchone()
    if row:
        await message.reply(f"📜 Свидетельство: @{user} ❤️ @{row[0]}")
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

@dp.message_handler(commands=['admin'])
async def admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⛔ Доступ только для администратора")
        return

    cursor.execute("SELECT DISTINCT user1, user2 FROM marriages")
    marriages = cursor.fetchall()

    cursor.execute("SELECT user_id, username, first_name FROM users")
    users = cursor.fetchall()

    text = "📋 Админ-панель:\n"
    text += f"👥 Пользователи: {len(users)}\n"
    text += f"💑 Браков: {len(marriages)//2}\n\n"
    text += "👤 Список пользователей:\n"
    for uid, uname, fname in users:
        text += f"• {fname or ''} (@{uname or 'нет'}) — {uid}\n"

    await message.reply(text[:4096])

@dp.message_handler(commands=['broadcast'])
async def broadcast_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⛔ Только для админа")
        return
    await message.reply("✉️ Отправь сообщение (текст, фото, видео) для рассылки:")
    await BroadcastState.waiting_for_message.set()

@dp.message_handler(state=BroadcastState.waiting_for_message, content_types=types.ContentTypes.ANY)
async def broadcast_send(message: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    count = 0
    for (user_id,) in users:
        try:
            if message.text:
                await bot.send_message(user_id, message.text)
            elif message.photo:
                await bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption)
            elif message.video:
                await bot.send_video(user_id, message.video.file_id, caption=message.caption)
            count += 1
        except Exception:
            continue
    await message.reply(f"✅ Сообщение отправлено {count} пользователям")
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
