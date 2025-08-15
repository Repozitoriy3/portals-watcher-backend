# server.py  — порядок важен!

import os
import logging
from threading import Thread
from flask import Flask, request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------- логирование ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("portals-bot")

# ---------- конфиг из ENV ----------
BOT_TOKEN   = os.environ["BOT_TOKEN"]
WEBAPP_URL  = os.environ.get("WEBAPP_URL", "https://example.com/webapp")

# ---------- Flask: СОЗДАЁМ app СРАЗУ ----------
app = Flask(__name__)

@app.get("/")
def home():
    return "Bot is running!"

# Минимальный WebApp UI
WEBAPP_HTML = """<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Portals Watcher</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;background:#0f1115;color:#eaeef6;margin:0;padding:24px}
.card{max-width:560px;margin:0 auto;background:#151923;border:1px solid #23293a;border-radius:16px;padding:16px;box-shadow:0 8px 30px rgba(0,0,0,.2)}
h1{font-size:20px;margin:0 0 12px}
input,button{width:100%;padding:10px;border-radius:12px;border:1px solid #2a3042;background:#0f1320;color:#eaeef6;margin:6px 0}
.item{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:8px 0;border-bottom:1px dashed #2a3042}
.muted{opacity:.7;font-size:12px}
</style>
<script>
const API = location.origin;
let USER_ID = null;
async function load(){
  const r = await fetch(API + "/api/watches?user_id=" + (USER_ID||123456));
  const data = await r.json();
  const list = document.getElementById("list"); list.innerHTML = "";
  data.forEach(x=>{
    const row = document.createElement("div"); row.className="item";
    row.innerHTML = `<div><div>${x.collection} — <b>${x.model}</b></div>
    <div class="muted">порог ${x.threshold_pct}%</div></div>
    <button onclick="delw(${x.id})">Удалить</button>`;
    list.appendChild(row);
  });
}
async function addw(){
  const collection = document.getElementById("collection").value.trim();
  const model = document.getElementById("model").value.trim();
  const threshold = parseFloat(document.getElementById("threshold").value || "0");
  await fetch(API + "/api/watches", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ user_id: USER_ID||123456, collection, model, threshold_pct: threshold })
  }); await load();
}
async function delw(id){
  await fetch(API + "/api/watches/" + id + "?user_id=" + (USER_ID||123456), { method:"DELETE" });
  await load();
}
window.addEventListener("DOMContentLoaded", ()=>{
  if (window.Telegram && Telegram.WebApp && Telegram.WebApp.initDataUnsafe.user){
    USER_ID = Telegram.WebApp.initDataUnsafe.user.id;
  }
  load();
});
</script>
</head><body>
  <div class="card">
    <h1>Portals Watcher</h1>
    <input id="collection" placeholder="Коллекция (например, Easter Egg)"/>
    <input id="model" placeholder="Модель (например, Monochrome)"/>
    <input id="threshold" type="number" step="1" placeholder="Порог, % ниже флора"/>
    <button onclick="addw()">Добавить</button>
    <div id="list" style="margin-top:8px"></div>
  </div>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
</body></html>"""

@app.get("/webapp")
def webapp():
    return WEBAPP_HTML

# ---------- Telegram bot (PTB v20) ----------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Open WebApp", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await update.message.reply_text("Привет! Жми кнопку и добавляй отслеживания.", reply_markup=kb)

def run_bot():
    log.info("Starting Telegram polling…")
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.run_polling(close_loop=False)

# ---------- безопасный однократный старт фонов ----------
_started = False
def start_background_once():
    global _started
    if _started: return
    _started = True
    Thread(target=run_bot, daemon=True).start()
    # если есть монитор — добавь здесь второй Thread(...)

# под Gunicorn фон стартуем перед первым HTTP-запросом
@app.before_first_request
def _kickoff():
    start_background_once()

# локальный запуск / простой сервер на Render
if __name__ == "__main__":
    start_background_once()
    port = int(os.environ.get("PORT", "10000"))
    log.info(f"HTTP on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)
