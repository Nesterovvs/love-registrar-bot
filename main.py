from aiogram import Bot, Dispatcher, types
from aiohttp import web
import os, sqlite3, logging
from datetime import datetime, date

API_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# реплай‐клавиатура:
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("💍 Предложить брак"))
main_menu.add(KeyboardButton("💞 Мой супруг/супруга"), KeyboardButton("💔 Развод"))
main_menu.add(KeyboardButton("📜 Свидетельство"), KeyboardButton("📅 Годовщина"))
main_menu.add(KeyboardButton("📖 История брака"), KeyboardButton("🧾 Мой профиль"))
main_menu.add(KeyboardButton("🎁 Подарить сердечко"))
main_menu.add(KeyboardButton("📋 Список команд"))

# … здесь все хэндлеры /marry, /my_spouse и т. д. без изменений …

# Пример исправленного хэндлера callback «accept»
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("accept:"))
async def accept(callback: types.CallbackQuery):
    partner = callback.from_user
    partner_username = partner.username.lower()
    data = pending.get(partner_username)
    if not data:
        await callback.message.edit_text("❗ Предложение не найдено или устарело.")
        return

    proposer_id = data["proposer_id"]
    proposer_username = data["proposer_username"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Сохраняем в SQLite, вставляем две записи «user1<->user2»:
    cursor.execute(
        "INSERT INTO marriages (user1, user2, married_at) VALUES (?, ?, ?)",
        (proposer_username, partner_username, timestamp)
    )
    cursor.execute(
        "INSERT INTO marriages (user1, user2, married_at) VALUES (?, ?, ?)",
        (partner_username, proposer_username, timestamp)
    )
    conn.commit()

    # Убираем inline-кнопки, просто редактируем текст
    await callback.message.edit_text(f"🎉 @{proposer_username} и @{partner_username} теперь пара! 🎉")

    # Отправляем каждому новое сообщение с обычной клавиатурой
    try:
        await bot.send_message(
            proposer_id,
            f"🎉 Вы теперь в браке с @{partner_username}! Пожелаем вам счастья 💖",
            reply_markup=main_menu
        )
    except Exception:
        pass

    try:
        await bot.send_message(
            partner.id,
            f"🎉 Вы теперь в браке с @{proposer_username}! Пожелаем вам счастья 💖",
            reply_markup=main_menu
        )
    except Exception:
        pass

    del pending[partner_username]


# Пример исправленного хэндлера callback «decline»
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("decline:"))
async def decline(callback: types.CallbackQuery):
    partner = callback.from_user
    partner_username = partner.username.lower()
    data = pending.get(partner_username)
    if not data:
        await callback.message.edit_text("❗ Предложение не найдено или устарело.")
        return

    proposer_username = data["proposer_username"]
    # Просто редактируем текст без клавиатуры
    await callback.message.edit_text(f"💔 @{partner_username} отклонил(а) предложение @{proposer_username}.")
    del pending[partner_username]


# ─── setup aiohttp/webhook ──────────────────────────────────────────────────
async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    await dp.storage.close()
    await dp.storage.wait_closed()

async def handle_webhook(request: web.Request):
    data = await request.json()
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
    if not API_TOKEN or not WEBHOOK_HOST:
        logger.error("Не заданы BOT_TOKEN или WEBHOOK_HOST")
        exit(1)
    port = int(os.getenv("PORT", "8000"))
    webapp = setup_app()
    web.run_app(webapp, host="0.0.0.0", port=port)
