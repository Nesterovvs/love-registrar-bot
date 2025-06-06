from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

# ⚠️ ВСТАВЬ СВОЙ АКТУАЛЬНЫЙ ТОКЕН!
BOT_TOKEN = '7927255180:AAHOriBODDYe0Sutdb-adIdR6YCu1EbgWnI'

# Команда /start — показывает кнопку
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup([["Дуся Роналдо"]], resize_keyboard=True)
    await update.message.reply_text("Нажми кнопку или напиши что-нибудь:", reply_markup=keyboard)

# Ответ на любое сообщение
async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Дуся Роналдо")

# Запуск
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, respond))
    print("Бот запущен. Дуся Роналдо.")
    app.run_polling()

if __name__ == '__main__':
    main()
