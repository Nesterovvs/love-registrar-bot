from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
import json
import os

BOT_TOKEN = '7927255180:AAHOriBODDYe0Sutdb-adIdR6YCu1EbgWnI'
ADMIN_ID = 1096930119
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users.add(user_id)
    save_users(users)

    buttons = [["Дуся Роналдо 💪"]]
    if user_id == ADMIN_ID:
        buttons.append(["📢 Рассылка", "📊 Кол-во юзеров"])

    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("Добро пожаловать!", reply_markup=keyboard)

async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users.add(user_id)
    save_users(users)

    text = update.message.text
    if user_id == ADMIN_ID:
        if text == "📢 Рассылка":
            await update.message.reply_text("Отправь текст, фото или голосовое для рассылки.")
            context.user_data["awaiting_broadcast"] = True
            return
        elif text == "📊 Кол-во юзеров":
            await update.message.reply_text(f"Пользователей в базе: {len(users)}")
            return

        if context.user_data.get("awaiting_broadcast"):
            success = 0
            if update.message.photo:
                photo_file_id = update.message.photo[-1].file_id
                for uid in users:
                    try:
                        await context.bot.send_photo(chat_id=uid, photo=photo_file_id)
                        success += 1
                    except:
                        pass
            elif update.message.voice:
                voice_file_id = update.message.voice.file_id
                for uid in users:
                    try:
                        await context.bot.send_voice(chat_id=uid, voice=voice_file_id)
                        success += 1
                    except:
                        pass
            elif text:
                for uid in users:
                    try:
                        await context.bot.send_message(chat_id=uid, text=text)
                        success += 1
                    except:
                        pass
            await update.message.reply_text(f"Рассылка отправлена {success} пользователям.")
            context.user_data["awaiting_broadcast"] = False
            return

    await update.message.reply_text("Дуся Роналдо")

users = load_users()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL, respond))
    print("Бот с кнопкой, медиа-рассылкой и админ-панелью запущен.")
    app.run_polling()

if __name__ == '__main__':
    main()
