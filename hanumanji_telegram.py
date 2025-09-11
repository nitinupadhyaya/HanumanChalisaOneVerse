import os
import sqlite3
import pytz
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes
from verses import verses  # import from separate file

# ---------------- Config ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
DB_FILE = "progress.db"

# ---------------- DB Helpers ----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY, day INTEGER)""")
    conn.commit()
    conn.close()

def get_progress(chat_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT day FROM users WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def save_progress(chat_id, day):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (chat_id, day) VALUES (?, ?)", (chat_id, day))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT chat_id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

# ---------------- Bot Logic ----------------
def get_next_message(chat_id):
    current_day = get_progress(chat_id)
    if current_day == -1:
        return None  # user paused
    next_day = current_day + 1
    if f"day{next_day}" in verses:
        v = verses[f"day{next_day}"]
        save_progress(chat_id, next_day)
        return (
            f"📖 Day {next_day} Verse:\n\n"
            f"{v['verse']}\n\n"
            f"🌐 English: {v['translation_en']}\n"
            f"🇮🇳 Hindi: {v['translation_hi']}\n\n"
            f"✨ Meaning:\n{v['expanded']}"
        )
    else:
        return "🎉 You’ve completed all days of Hanuman Chalisa learning! Jai Hanuman 🙏"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args

    # Ensure user is in DB
    if get_progress(chat_id) == 0:
        save_progress(chat_id, 0)

    intro_text = (
        "🌺 Did you always wish to learn the Hanuman Chalisa — not just recite it, "
        "but truly understand its deep psychological and spiritual meaning?\n\n"
        "🪔 Real learning requires consistency. With this bot, we’ve made it simple: "
        "each morning, you’ll receive just one Charan (half a verse), along with its meaning and insights.\n\n"
        "✨ Stay with us for 40 days — slowly, steadily, and with devotion. "
        "Experience the power of consistency, and the divine blessings that come from truly understanding "
        "the last of our revealed texts.\n\n"
        "🙏 Welcome to your Hanuman Chalisa journey."
    )

    keyboard = [
        [InlineKeyboardButton("🔗 Share this Bot", url=f"https://t.me/{context.bot.username}?start=join")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(intro_text, reply_markup=reply_markup)

    # If joined via link, send first verse immediately
    if args and args[0] == "join":
        msg = get_next_message(chat_id)
        if msg:
            await update.message.reply_text(msg)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_progress(chat_id, -1)
    await update.message.reply_text("⏸️ You’ve paused daily verses. Type /resume anytime to continue.")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if get_progress(chat_id) == -1:
        save_progress(chat_id, 0)  # restart from beginning
    await update.message.reply_text("✅ Resumed daily verses. Jai Hanuman! 🙏")
    msg = get_next_message(chat_id)
    if msg:
        await update.message.reply_text(msg)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg = " ".join(context.args)
    for user in get_all_users():
        if get_progress(user) == -1:  # skip paused users
            continue
        try:
            await context.bot.send_message(chat_id=user, text=f"[Broadcast] {msg}")
        except Exception as e:
            print(f"⚠️ Could not send to {user}: {e}")
    await update.message.reply_text("✅ Broadcast sent.")

# ---------------- Scheduler ----------------
async def send_daily(context: ContextTypes.DEFAULT_TYPE):
    for user in get_all_users():
        if get_progress(user) == -1:  # skip paused users
            continue
        msg = get_next_message(user)
        if msg:
            try:
                await context.bot.send_message(chat_id=user, text=msg)
            except Exception as e:
                print(f"⚠️ Could not send daily verse to {user}: {e}")

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # Schedule 7:00 AM IST
    ist = pytz.timezone("Asia/Kolkata")
    app.job_queue.run_daily(send_daily, time=datetime.time(7, 0, tzinfo=ist))

    print("🤖 Bot started…")
    app.run_polling()

if __name__ == "__main__":
    main()
