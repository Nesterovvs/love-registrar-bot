from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# ⚠️ Этот токен скомпрометирован. Замени его через @BotFather!
BOT_TOKEN = '7927255180:AAHOriBODDYe0Sutdb-adIdR6YCu1EbgWnI'

async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ахмат сила")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, respond))
    print("Бот запущен. Ахмат сила.")
    app.run_polling()

if __name__ == '__main__':
    main()
