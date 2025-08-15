# settings.py — только конфигурация, без запуска кода!

import os

# Телеграм
BOT_TOKEN   = os.environ["BOT_TOKEN"]  # токен бота из Render → Environment

# WebApp (UI)
WEBAPP_URL  = os.environ.get("WEBAPP_URL", "https://portals-sniper-bot.onrender.com/webapp")

# Параметры Portals (если используешь)
TG_API_ID   = os.environ.get("TG_API_ID")       # str или None
TG_API_HASH = os.environ.get("TG_API_HASH")     # str или None

# Мониторинг/БД (по желанию)
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "20"))
DB_PATH      = os.environ.get("DB_PATH", "data.db")

# Флаги/настройки (можно расширять)
DEBUG = os.environ.get("DEBUG", "0") == "1"
