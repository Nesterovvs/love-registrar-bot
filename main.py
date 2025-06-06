from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
import json
import os

BOT_TOKEN = '7927255180:AAHOriBODDYe0Sutdb-adIdR6YCu1EbgWnI'
ADMIN_ID = 1096930119
USERS_FILE = "users.json"

# Загружаем список пользователей
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return set(json.load(f))
    return set()

# Сохраняем список пользователей
def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users.add(user_id)
    save_users(users)
    keyboard = ReplyKeyboardMarkup([["Дуся Роналдо"]], resize_keyboard=True)
    await update.message.reply_text("Нажми кнопку или напиши что-нибудь:", reply_markup=keyboard)

# Ответ на любое сообщение
async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users.add(user_id)
    save_users(users)
    await update.message.reply_text("Дуся Роналдо")

# Команда /рассылка только для админа
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У тебя нет доступа к этой команде.")
        return
    if not context.args:
        await update.message.reply_text("Напиши текст после команды /рассылка")
        return
    message_text = ' '.join(context.args)
    success = 0
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            success += 1
        except:
            pass
    await update.message.reply_text(f"Рассылка отправлена {success} пользователям.")

# Хранилище пользователей
users = load_users()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("рассылка", broadcast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, respond))
    print("Бот запущен с кнопкой и рассылкой.")
    app.run_polling()

if __name__ == '__main__':
    main()
