# settings.py — только конфигурация, без запуска кода!

import os

# Телеграм
BOT_TOKEN   = os.environ["8014699150:AAGCv098wTf8ZWvVC8xE1U0mp9SBXr2LPUQ"]  # токен бота из Render → Environment

# WebApp (UI)
WEBAPP_URL  = os.environ.get("WEBAPP_URL", "https://portals-sniper-bot.onrender.com/webapp")

# Параметры Portals (если используешь)
TG_API_ID   = os.environ.get("29751945")       # str или None
TG_API_HASH = os.environ.get("4bf0d79c4eab9bfc88f9368bf250031a")     # str или None

# Мониторинг/БД (по желанию)
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "20"))
DB_PATH      = os.environ.get("DB_PATH", "data.db")

# Флаги/настройки (можно расширять)
DEBUG = os.environ.get("DEBUG", "0") == "1"
