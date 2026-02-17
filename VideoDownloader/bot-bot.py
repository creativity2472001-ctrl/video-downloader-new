import os
import json
import sqlite3
import logging
from telegram import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Update
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# =========================
# Logging
# =========================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# =========================
# Token
# =========================
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN not set!")

# =========================
# Load Languages
# =========================
try:
    with open("languages.json", "r", encoding="utf-8") as f:
        LANG = json.load(f)
except Exception as e:
    logging.error("Error loading languages.json: %s", e)
    raise

# =========================
# Database (SQLite)
# =========================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    language TEXT
)
""")
conn.commit()

def get_lang(user_id):
    cursor.execute("SELECT language FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    return "ar"

def set_lang(user_id, lang):
    cursor.execute("""
    INSERT INTO users (user_id, language)
    VALUES (?, ?)
    ON CONFLICT(user_id) DO UPDATE SET language=excluded.language
    """, (user_id, lang))
    conn.commit()

def t(user_id, key):
    lang = get_lang(user_id)
    return LANG.get(lang, LANG["en"]).get(key, "")

# =========================
# Menu
# =========================
def main_menu(user_id):
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(t(user_id, "menu_language")),
                KeyboardButton(t(user_id, "menu_help"))
            ],
            [
                KeyboardButton(t(user_id, "menu_restart"))
            ]
        ],
        resize_keyboard=True
    )

# =========================
# Handlers
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    try:
        set_lang(user_id, get_lang(user_id))
        await update.message.reply_text(
            t(user_id, "start"),
            reply_markup=main_menu(user_id)
        )
        logging.info("User %s started bot", user_id)
    except Exception as e:
        logging.error("Start error: %s", e)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    try:
        actions = {
            t(user_id, "menu_help"): send_help,
            t(user_id, "menu_restart"): restart_bot,
            t(user_id, "menu_language"): show_languages
        }

        if text in actions:
            await actions[text](update, context)
        else:
            await update.message.reply_text(
                t(user_id, "start"),
                reply_markup=main_menu(user_id)
            )
    except Exception as e:
        logging.error("Handle text error: %s", e)

async def send_help(update, context):
    user_id = update.effective_user.id
    await update.message.reply_text(
        t(user_id, "help"),
        reply_markup=main_menu(user_id)
    )

async def restart_bot(update, context):
    user_id = update.effective_user.id
    await update.message.reply_text(
        t(user_id, "start"),
        reply_markup=main_menu(user_id)
    )

async def show_languages(update, context):
    user_id = update.effective_user.id

    keyboard = [
        [
            InlineKeyboardButton("🇸🇦 عربي", callback_data="ar"),
            InlineKeyboardButton("🇺🇸 English", callback_data="en")
        ],
        [
            InlineKeyboardButton("🇹🇷 Türkçe", callback_data="tr"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="ru")
        ],
        [
            InlineKeyboardButton("🇩🇪 Deutsch", callback_data="de"),
            InlineKeyboardButton("🇫🇷 Français", callback_data="fr")
        ]
    ]

    await update.message.reply_text(
        t(user_id, "choose_language"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        set_lang(query.from_user.id, query.data)

        await query.edit_message_text(
            t(query.from_user.id, "language_changed")
        )

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=t(query.from_user.id, "start"),
            reply_markup=main_menu(query.from_user.id)
        )

        logging.info("User %s changed language to %s",
                     query.from_user.id, query.data)

    except Exception as e:
        logging.error("Language change error: %s", e)

# =========================
# Main
# =========================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(change_language))

    logging.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
