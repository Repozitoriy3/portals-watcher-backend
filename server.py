import os
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
TG_API_ID = os.environ.get("TG_API_ID")  # если нужно
TG_API_HASH = os.environ.get("TG_API_HASH")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://example.com")

app = Flask(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я слежу за новыми листингами в Portals.")

def run_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.run_polling()

if __name__ == "__main__":
    # запускаем бота в отдельном потоке
    from threading import Thread
    Thread(target=run_bot, daemon=True).start()

    port = int(os.environ.get("PORT", "10000"))
    app.route("/")(lambda: "Bot is running!")
    app.run(host="0.0.0.0", port=port)
