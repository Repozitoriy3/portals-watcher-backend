import os
import asyncio
import aiosqlite
from threading import Thread
from flask import Flask, request, jsonify
from telegram import Update, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from aportalsmp.auth import update_auth
from aportalsmp.gifts import filterFloors, giftsFloors, marketActivity
from aportalsmp.utils.functions import toShortName

# ====== конфиг из ENV ======
BOT_TOKEN = os.environ["BOT_TOKEN"]
TG_API_ID = int(os.environ.get("TG_API_ID", "0")) or None
TG_API_HASH = os.environ.get("TG_API_HASH") or None
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://example.com")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "20"))
DB_PATH = os.environ.get("DB_PATH", "data.db")

# ====== Flask (HTTP) ======
app = Flask(__name__)

@app.get("/")
def home():
    return "Bot is running!"

# ====== DB helpers ======
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY,
  chat_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS watches(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  collection TEXT NOT NULL,
  model TEXT NOT NULL,
  threshold_pct REAL NOT NULL DEFAULT 0.0,
  UNIQUE(user_id, collection, model)
);
"""

async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()

# ====== Portals auth ======
_auth_cache: str | None = None

async def get_auth() -> str:
    global _auth_cache
    if _auth_cache:
        return _auth_cache
    if TG_API_ID and TG_API_HASH:
        _auth_cache = await update_auth(api_id=TG_API_ID, api_hash=TG_API_HASH)
        return _auth_cache
    # если вдруг нет api_id/hash — можно упасть понятной ошибкой
    raise RuntimeError("No Portals auth (set TG_API_ID/TG_API_HASH in env).")

# ====== Floors & activity ======
async def get_model_floor(collection: str, model: str) -> float:
    auth = await get_auth()
    floors = await filterFloors(gift_name=collection, authData=auth)
    for m, fl in floors.models.items():
        if m.lower() == model.lower():
            return float(fl)
    gf = await giftsFloors(auth)
    return float(gf.floor(toShortName(collection)))

async def get_latest_listings(limit: int = 100):
    auth = await get_auth()
    return await marketActivity(
        sort="latest", offset=0, limit=limit,
        activityType="listing", authData=auth
    )

# ====== Bot ======
application = ApplicationBuilder().token(BOT_TOKEN).build()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # сохраним chat_id → user_id для уведомлений
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users(user_id, chat_id) VALUES(?, ?)",
            (update.effective_user.id, update.effective_chat.id)
        )
        await db.commit()

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="Open WebApp",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    ]])
    await update.message.reply_text(
        "Привет! Открой мини-апп и добавь отслеживания.",
        reply_markup=kb
    )

application.add_handler(CommandHandler("start", cmd_start))

def run_bot():
    application.run_polling()

# ====== Мониторинг листингов ======
_seen_ids: set[str] = set()
_model_floor_cache: dict[tuple[str, str], float] = {}

async def monitor_loop():
    await db_init()
    while True:
        try:
            acts = await get_latest_listings(limit=100)
            if not acts:
                await asyncio.sleep(POLL_SECONDS); continue

            for act in acts:
                aid = str(act.id)
                if aid in _seen_ids:
                    continue
                _seen_ids.add(aid)

                nft = act.nft
                collection = nft.name
                model = nft.model
                price = float(act.amount)
                url = f"https://t.me/portals_market_bot?startapp=nft:{nft.tg_id}"

                # подписчики на эту пару
                async with aiosqlite.connect(DB_PATH) as db:
                    cur = await db.execute(
                        "SELECT w.user_id, w.threshold_pct, u.chat_id "
                        "FROM watches w JOIN users u ON u.user_id=w.user_id "
                        "WHERE w.collection=? AND w.model=?",
                        (collection, model)
                    )
                    rows = await cur.fetchall()

                if not rows:
                    continue

                # актуальный floor
                key = (collection, model)
                cur_floor = _model_floor_cache.get(key)
                if cur_floor is None:
                    try:
                        cur_floor = await get_model_floor(collection, model)
                    except Exception:
                        continue
                    _model_floor_cache[key] = cur_floor

                # отправим тем, у кого условие сработало
                for user_id, threshold_pct, chat_id in rows:
                    below_floor = price < cur_floor
                    below_threshold = price <= cur_floor * (1 - threshold_pct/100.0)
                    if below_floor or below_threshold:
                        text = (
                            "🛎️ Подрез флора на Portals!\n"
                            f"Коллекция: {collection}\n"
                            f"Модель: {model}\n"
                            f"Цена: {price:g} (floor: {cur_floor:g}, порог: {threshold_pct:g}%)\n"
                            f"{url}"
                        )
                        try:
                            await application.bot.send_message(chat_id, text, disable_web_page_preview=True)
                        except Exception:
                            pass

                        if price < cur_floor:
                            _model_floor_cache[key] = price

        except Exception:
            # можно логировать/прислать админу
            pass
        await asyncio.sleep(POLL_SECONDS)

def run_monitor():
    asyncio.run(monitor_loop())

# ====== API для мини-аппа ======
@app.get("/api/watches")
async def list_watches():
    user_id = int(request.args.get("user_id"))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, collection, model, threshold_pct FROM watches WHERE user_id=?",
            (user_id,)
        )
        rows = await cur.fetchall()
    return jsonify([
        {"id": r[0], "collection": r[1], "model": r[2], "threshold_pct": r[3]}
    for r in rows])

@app.post("/api/watches")
async def add_watch():
    data = request.get_json(force=True)
    user_id = int(data["user_id"])
    collection = data["collection"]
    model = data["model"]
    threshold_pct = float(data.get("threshold_pct", 0.0))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users(user_id, chat_id) VALUES(?, ?)",
            (user_id, 0)
        )
        await db.execute(
            "INSERT OR REPLACE INTO watches(user_id, collection, model, threshold_pct) "
            "VALUES(?, ?, ?, ?)",
            (user_id, collection, model, threshold_pct)
        )
        await db.commit()
    return jsonify({"ok": True})

@app.delete("/api/watches/<int:watch_id>")
async def delete_watch(watch_id: int):
    user_id = int(request.args.get("user_id"))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM watches WHERE id=? AND user_id=?",
            (watch_id, user_id)
        )
        await db.commit()
        if cur.rowcount == 0:
            return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True})

# ====== Мини-апп (минимальный UI, 1 файл) ======
# Откроется по /webapp (этот URL укажем в BotFather как Web App)
WEBAPP_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Portals Watcher</title>
<style>
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;
       background:#0f1115;color:#eaeef6;margin:0;padding:24px}
  .card{max-width:560px;margin:0 auto;background:#151923;border:1px solid #23293a;
        border-radius:16px;padding:16px;box-shadow:0 8px 30px rgba(0,0,0,.2)}
  h1{font-size:20px;margin:0 0 12px}
  input,button{width:100%;padding:10px;border-radius:12px;border:1px solid #2a3042;
               background:#0f1320;color:#eaeef6;margin:6px 0}
  .item{display:flex;justify-content:space-between;gap:8px;align-items:center;
        padding:8px 0;border-bottom:1px dashed #2a3042}
  .muted{opacity:.7;font-size:12px}
</style>
<script>
const API = "{{API_BASE}}";
let USER_ID = null;

async function load(){
  const r = await fetch(API + "/api/watches?user_id=" + USER_ID);
  const data = await r.json();
  const list = document.getElementById("list");
  list.innerHTML = "";
  data.forEach(x=>{
    const row = document.createElement("div");
    row.className = "item";
    row.innerHTML = \`
      <div>
        <div>\${x.collection} — <b>\${x.model}</b></div>
        <div class="muted">порог \${x.threshold_pct}%</div>
      </div>
      <button onclick="del(\${x.id})">Удалить</button>\`;
    list.appendChild(row);
  });
}

async function add(){
  const collection = document.getElementById("collection").value.trim();
  const model = document.getElementById("model").value.trim();
  const threshold = parseFloat(document.getElementById("threshold").value || "0");
  await fetch(API + "/api/watches", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ user_id: USER_ID, collection, model, threshold_pct: threshold })
  });
  await load();
}

async function del(id){
  await fetch(API + "/api/watches/" + id + "?user_id=" + USER_ID, { method: "DELETE" });
  await load();
}

window.addEventListener("DOMContentLoaded", async ()=>{
  if (window.Telegram && Telegram.WebApp && Telegram.WebApp.initDataUnsafe.user){
    USER_ID = Telegram.WebApp.initDataUnsafe.user.id;
  } else {
    // для теста в браузере
    USER_ID = 123456;
  }
  await load();
});
</script>
</head>
<body>
  <div class="card">
    <h1>Portals Watcher</h1>
    <input id="collection" placeholder="Коллекция (например, Easter Egg)"/>
    <input id="model" placeholder="Модель (например, Monochrome)"/>
    <input id="threshold" type="number" step="1" placeholder="Порог, % ниже флора"/>
    <button onclick="add()">Добавить</button>
    <div id="list" style="margin-top:8px"></div>
  </div>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
</body>
</html>"""

@app.get("/webapp")
def webapp():
    # подставим API адрес (сам сервис)
    api_base = request.host_url.rstrip("/")
    return WEBAPP_HTML.replace("{{API_BASE}}", api_base)

# ====== запуск ======
def main():
    # 1) стартуем бота в отдельном потоке
    Thread(target=run_bot, daemon=True).start()
    # 2) стартуем мониторинг в отдельном потоке
    Thread(target=run_monitor, daemon=True).start()
    # 3) поднимаем HTTP
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
