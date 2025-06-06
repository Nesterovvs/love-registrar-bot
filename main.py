from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = '7927255180:AAHOriBODDYe0Sutdb-adIdR6YCu1EbgWnI'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Ахмат сила 💪", callback_data="ahmat")]
    ])
    await update.message.reply_text("Нажми на кнопку:", reply_markup=keyboard)

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "ahmat":
        await query.message.reply_text("Ахмат сила")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_button))
    print("Бот с inline-кнопкой запущен.")
    app.run_polling()

if __name__ == '__main__':
    main()
