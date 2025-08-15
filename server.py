from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import config

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я слежу за новыми листингами в Portals.")

if __name__ == '__main__':
    from threading import Thread
    Thread(target=lambda: bot_app.run_polling()).start()

    import os
    port = int(os.environ.get('PORT', '10000'))  # <-- берём порт из окружения
    app.run(host='0.0.0.0', port=port)
