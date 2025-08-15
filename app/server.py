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
    bot_app = ApplicationBuilder().token(config.BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    
    from threading import Thread
    Thread(target=lambda: bot_app.run_polling()).start()
    
    app.run(host='0.0.0.0', port=10000)
