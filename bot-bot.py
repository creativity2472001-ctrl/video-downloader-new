import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"  # ضع التوكن هنا

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
PREMIUM_USERS = {123456789}

BASE_YDL_OPTS = {
    "format": "best[ext=mp4]/best",
    "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "quiet": True,
    "nocheckcertificate": True,
    "geo_bypass": True,
}

AUDIO_OPTIONS = BASE_YDL_OPTS.copy()
AUDIO_OPTIONS.update({
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
})

LANGUAGE_DATA = {
    "en": {
        "welcome_free": "📌 Welcome! Free limit: 50MB.",
        "welcome_premium": "💎 Welcome Premium user! Limit: 200MB.",
        "send_link": "🚀 Send link",
        "choose_mode": "Choose download type:",
        "help_text": "📖 Download instructions:\n1️⃣ Open Instagram/TikTok/YouTube\n2️⃣ Choose a video\n3️⃣ Tap ↪️ Share\n4️⃣ Copy link\n5️⃣ Send it here\n⚡ You'll get it in seconds.",
        "restart_msg": "🔄 Bot restarted!",
        "invalid": "❌ Send a valid link.",
        "hourglass": ["⏳", "⌛", "⏳"]
    },
    "ar": {
        "welcome_free": "📌 مرحباً! الحد المجاني 50MB.",
        "welcome_premium": "💎 مرحباً مستخدم مدفوع! الحد 200MB.",
        "send_link": "🚀 أرسل الرابط",
        "choose_mode": "اختر نوع التحميل:",
        "help_text": "📖 طريقة التحميل:\n1️⃣ افتح Instagram/TikTok/YouTube\n2️⃣ اختر الفيديو\n3️⃣ اضغط مشاركة ↪️\n4️⃣ انسخ الرابط\n5️⃣ أرسل الرابط للبوت\n⚡ سيتم الإرسال خلال ثوانٍ.",
        "restart_msg": "🔄 تم إعادة تشغيل البوت!",
        "invalid": "❌ أرسل رابط صحيح.",
        "hourglass": ["⏳", "⌛", "⏳"]
    }
}

user_language = {}

# ----------------- START -----------------
async def start_message(message, context):
    user_id = message.from_user.id
    lang = user_language.get(user_id, "ar")
    msg = LANGUAGE_DATA[lang]["welcome_premium"] if user_id in PREMIUM_USERS else LANGUAGE_DATA[lang]["welcome_free"]

    keyboard = [
        [InlineKeyboardButton("🔄 Restart", callback_data="restart")],
        [InlineKeyboardButton("🌐 Language", callback_data="select_lang")],
        [InlineKeyboardButton("📖 Help", callback_data="help")]
    ]

    await message.reply_text(
        f"{msg}\n\n{LANGUAGE_DATA[lang]['send_link']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_message(update.message, context)

# ----------------- HELP -----------------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_language.get(user_id, "ar")
    await update.effective_message.reply_text(LANGUAGE_DATA[lang]["help_text"])

# ----------------- LANGUAGE -----------------
async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ]
    await query.message.reply_text("🌐 Choose language:", reply_markup=InlineKeyboardMarkup(keyboard))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code):
    query = update.callback_query
    user_language[query.from_user.id] = lang_code
    await query.message.reply_text("✅ Updated!")
    await start_message(query.message, context)

# ----------------- RESTART -----------------
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_language[query.from_user.id] = "ar"
    await query.message.reply_text(LANGUAGE_DATA["ar"]["restart_msg"])
    await start_message(query.message, context)

# ----------------- DOWNLOAD -----------------
as
