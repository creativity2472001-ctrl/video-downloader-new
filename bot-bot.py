import os
import asyncio
import yt_dlp
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8373058261:AAHpQtkK6ULlqVydm6FDNaVYz-LFqFPQqJ8"

DOWNLOAD_DIR = "downloads"
FREE_LIMIT = 50 * 1024 * 1024
PREMIUM_LIMIT = 200 * 1024 * 1024
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

PREMIUM_USERS = {123456789}

VIDEO_OPTIONS = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'quiet': True
}

AUDIO_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'restrictfilenames': True,
    'noplaylist': True,
    'quiet': True
}

LANGUAGE_DATA = {
    "en": {
        "welcome_free": "📌 Welcome! Your free limit is 50MB.",
        "welcome_premium": "💎 Welcome Premium user! Your limit is 200MB.",
        "send_link": "Send a video link.",
        "choose_mode": "Choose what to download:",
        "help_text":
        "📖 *Download Instructions*\n\n"
        "1️⃣ Open Instagram / TikTok / YouTube\n"
        "2️⃣ Choose the video\n"
        "3️⃣ Tap ↪️ Share\n"
        "4️⃣ Tap *Copy Link*\n"
        "5️⃣ Send the link here\n\n"
        "⚡ The bot will send the video or audio in seconds.",
        "restart_msg": "🔄 Bot restarted!"
    },
    "ar": {
        "welcome_free": "📌 مرحباً! لديك حد 50MB.",
        "welcome_premium": "💎 مرحباً مستخدم النسخة المدفوعة! لديك حد 200MB.",
        "send_link": "أرسل رابط الفيديو.",
        "choose_mode": "اختر ما تريد تحميله:",
        "help_text":
        "📖 *طريقة التحميل*\n\n"
        "1️⃣ افتح Instagram أو TikTok أو YouTube\n"
        "2️⃣ اختر الفيديو\n"
        "3️⃣ اضغط مشاركة ↪️\n"
        "4️⃣ اضغط نسخ الرابط\n"
        "5️⃣ أرسل الرابط للبوت\n\n"
        "⚡ سيتم إرسال الفيديو أو الصوت خلال ثوانٍ.",
        "restart_msg": "🔄 تم إعادة تشغيل البوت!"
    }
}

user_language = {}

# ----------------- START MESSAGE -----------------
async def start_message(message, context):
    user_id = message.from_user.id
    lang = user_language.get(user_id, "ar")

    if user_id in PREMIUM_USERS:
        msg = LANGUAGE_DATA[lang]["welcome_premium"]
    else:
        msg = LANGUAGE_DATA[lang]["welcome_free"]

    keyboard = [
        [InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("🌐 Language", callback_data="select_lang")],
        [InlineKeyboardButton("🔄 Restart", callback_data="restart")]
    ]

    await message.reply_text(
        f"{msg}\n\n{LANGUAGE_DATA[lang]['send_link']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_message(update.message, context)

# ----------------- HELP -----------------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    lang = user_language.get(user_id, "ar")

    await update.message.reply_text(
        LANGUAGE_DATA[lang]["help_text"],
        parse_mode="Markdown"
    )

# ----------------- LANGUAGE -----------------
async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ]
    await query.message.reply_text(
        "🌐 Choose your language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code):
    query = update.callback_query
    user_language[query.from_user.id] = lang_code
    await query.message.reply_text("✅ Language updated!")
    await start_message(query.message, context)

# ----------------- RESTART -----------------
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_language[query.from_user.id] = "ar"
    await query.message.reply_text(LANGUAGE_DATA["ar"]["restart_msg"])
    await start_message(query.message, context)

# ----------------- DOWNLOAD -----------------
def get_video_info(url):
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        return ydl.extract_info(url, download=False)

async def download_and_send(message, url, mode, limit):
    status = await message.reply_text("🔍 جاري التحليل...")

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: get_video_info(url))
        title = info.get("title", "video")

        await status.edit_text("⬇️ جاري التحميل...")

        if mode == "audio":
            with yt_dlp.YoutubeDL(AUDIO_OPTIONS) as ydl:
                info_downloaded = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info_downloaded).rsplit(".", 1)[0] + ".mp3"

            with open(filename, "rb") as f:
                await message.reply_audio(f, caption=f"🎵 {title}")
            os.remove(filename)

        else:
            with yt_dlp.YoutubeDL(VIDEO_OPTIONS) as ydl:
                info_downloaded = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info_downloaded)

            with open(filename, "rb") as f:
                await message.reply_video(f, caption=f"🎬 {title}")
            os.remove(filename)

        await status.delete()

    except Exception as e:
        print(e)
        await status.edit_text("❌ فشل التحميل.")

# ----------------- HANDLE LINK -----------------
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not url.startswith("http"):
        await update.message.reply_text("❌ أرسل رابط صحيح.")
        return

    context.user_data["url"] = url

    keyboard = [
        [InlineKeyboardButton("🎬 فيديو", callback_data="video")],
        [InlineKeyboardButton("🎵 صوت", callback_data="audio")]
    ]

    await update.message.reply_text(
        "اختر نوع التحميل:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ----------------- BUTTON HANDLER -----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "help":
        await help_command(update, context)
    elif data == "select_lang":
        await select_language(update, context)
    elif data == "restart":
        await restart(update, context)
    elif data in ["lang_ar", "lang_en"]:
        await set_language(update, context, data.split("_")[1])
    else:
        url = context.user_data.get("url")
        if url:
            limit = PREMIUM_LIMIT if query.from_user.id in PREMIUM_USERS else FREE_LIMIT
            await download_and_send(query.message, url, data, limit)

# ----------------- MAIN -----------------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
