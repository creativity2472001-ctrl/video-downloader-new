import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"

DOWNLOAD_DIR = "downloads"
FREE_LIMIT = 50 * 1024 * 1024
PREMIUM_LIMIT = 200 * 1024 * 1024
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

PREMIUM_USERS = {123456789}

VIDEO_OPTIONS_BASE = {
    'format': '18/22/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'noplaylist': True,
    'concurrent_fragment_downloads': 8,
    'quiet': True
}

AUDIO_OPTIONS = {
    'format': 'bestaudio',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True
}

# ====================== النصوص متعددة اللغات ======================
TEXTS = {
    "start": {
        "AR": "🚀 مرحباً! أرسل رابط الفيديو وسيظهر لك الخيارات:",
        "EN": "🚀 Welcome! Send the video link and choose an option:"
    },
    "choose_option": {
        "AR": "اختر الخيار:",
        "EN": "Choose an option:"
    },
    "loading": {
        "AR": "⏳ جاري التحميل...",
        "EN": "⏳ Loading..."
    },
    "help": {
        "AR": "📖 طريقة الاستخدام:\n1️⃣ أرسل الرابط\n2️⃣ اختر فيديو أو صوت\n3️⃣ الفيديو الكبير يتم ضغطه تلقائياً",
        "EN": "📖 How to use:\n1️⃣ Send the link\n2️⃣ Choose video or audio\n3️⃣ Large videos will be compressed automatically"
    },
    "restart": {
        "AR": "🔄 أرسل رابط جديد.",
        "EN": "🔄 Send a new link."
    },
    "large_file": {
        "AR": "⚠️ الحجم كبير — سيتم إرسال الصوت فقط",
        "EN": "⚠️ File too large — only audio will be sent"
    },
    "fail": {
        "AR": "❌ فشل التحميل",
        "EN": "❌ Download failed"
    },
    "language_choose": {
        "AR": "🌐 اختر اللغة:",
        "EN": "🌐 Choose language:"
    }
}

def get_text(key, lang):
    return TEXTS.get(key, {}).get(lang, "")

# ================= Commands =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lang"] = context.user_data.get("lang", "AR")
    lang = context.user_data["lang"]

    keyboard = [
        [InlineKeyboardButton("🎬 تحميل فيديو", callback_data="video")],
        [InlineKeyboardButton("🎵 تحميل صوت", callback_data="audio")],
        [InlineKeyboardButton("🌐 اللغة / Language", callback_data="language")],
        [InlineKeyboardButton("📖 المساعدة", callback_data="help")],
        [InlineKeyboardButton("🔄 إعادة التشغيل", callback_data="restart")]
    ]

    await update.message.reply_text(
        get_text("start", lang),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(get_text("restart", "AR"))

# ================= Download Core =================
async def download_and_send(chat, url, mode, limit, lang):
    loading_msg = await chat.send_message(get_text("loading", lang))
    loop = asyncio.get_event_loop()

    try:
        options = VIDEO_OPTIONS_BASE.copy() if mode == "video" else AUDIO_OPTIONS.copy()

        def download():
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info), info.get("title", "بدون عنوان")

        filename, title = await loop.run_in_executor(None, download)

        if mode == "audio":
            filename = filename.rsplit(".", 1)[0] + ".mp3"
            with open(filename, "rb") as f:
                await chat.send_audio(f, caption=f"🎵 {title}")
            await loading_msg.delete()
            os.remove(filename)
            return

        if os.path.getsize(filename) > limit:
            await loading_msg.edit_text(get_text("large_file", lang))
            await download_and_send(chat, url, "audio", limit, lang)
            return

        with open(filename, "rb") as f:
            await chat.send_video(f, caption=f"🎬 {title}", supports_streaming=True)

        await loading_msg.delete()
        os.remove(filename)

    except Exception as e:
        print(e)
        await loading_msg.edit_text(get_text("fail", lang))

# ================= Handlers =================
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    context.user_data["url"] = url
    lang = context.user_data.get("lang", "AR")

    keyboard = [
        [InlineKeyboardButton("🎬 تحميل فيديو", callback_data="video")],
        [InlineKeyboardButton("🎵 تحميل صوت", callback_data="audio")],
        [InlineKeyboardButton("🌐 اللغة / Language", callback_data="language")],
        [InlineKeyboardButton("📖 المساعدة", callback_data="help")],
        [InlineKeyboardButton("🔄 إعادة التشغيل", callback_data="restart")]
    ]

    await update.message.reply_text(get_text("choose_option", lang), reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()

    url = context.user_data.get("url")
    user_id = query.from_user.id
    lang = context.user_data.get("lang", "AR")
    limit = PREMIUM_LIMIT if user_id in PREMIUM_USERS else FREE_LIMIT

    if query.data == "video":
        await download_and_send(update.effective_chat, url, "video", limit, lang)
    elif query.data == "audio":
        await download_and_send(update.effective_chat, url, "audio", limit, lang)
    elif query.data == "restart":
        context.user_data.clear()
        await update.effective_chat.send_message(get_text("restart", lang))
    elif query.data == "help":
        await update.effective_chat.send_message(get_text("help", lang))
    elif query.data == "language":
        keyboard = [
            [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
            [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
        ]
        await update.effective_chat.send_message(get_text("language_choose", lang), reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data.startswith("lang_"):
        new_lang = "AR" if query.data == "lang_ar" else "EN"
        context.user_data["lang"] = new_lang
        await update.effective_chat.send_message(f"✅ اللغة تم تغييرها إلى {'العربية' if new_lang=='AR' else 'English'}")

# ================= Main =================
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 البوت جاهز للتشغيل (متعدد اللغات)...")
    app.run_polling()

if __name__ == "__main__":
    main()
