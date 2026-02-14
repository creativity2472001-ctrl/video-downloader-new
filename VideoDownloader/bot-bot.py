import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"  # ضع توكن البوت هنا

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

user_language = {}  # لتخزين لغة المستخدم

# ================= Commands =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ✅ زر القائمة الصغيرة (ReplyKeyboard) يظهر من البداية
    keyboard = [
        [KeyboardButton("/language"), KeyboardButton("/help"), KeyboardButton("/restart")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "🚀 أرسل رابط فيديو\nاختر فيديو أو صوت\n⚡ نسخة فائقة السرعة",
        reply_markup=reply_markup
    )

# ================= Download Core =================

async def download_and_send(chat, url, mode, limit):
    loading_msg = await chat.send_message("⏳ جاري التحميل...")

    try:
        if mode == "video":
            options = VIDEO_OPTIONS_BASE.copy()
        else:
            options = AUDIO_OPTIONS.copy()

        def download():
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info), info.get("title", "بدون عنوان")

        loop = asyncio.get_event_loop()
        filename, title = await loop.run_in_executor(None, download)

        if mode == "audio":
            filename = filename.rsplit(".", 1)[0] + ".mp3"
            with open(filename, "rb") as f:
                await chat.send_audio(f, caption=f"🎵 {title}")
            await loading_msg.delete()
            os.remove(filename)
            return

        if os.path.getsize(filename) > limit:
            await loading_msg.edit_text("⚠️ الحجم كبير — سيتم إرسال الصوت فقط")
            await download_and_send(chat, url, "audio", limit)
            return

        with open(filename, "rb") as f:
            await chat.send_video(
                f,
                caption=f"🎬 {title}",
                supports_streaming=True
            )

        await loading_msg.delete()
        os.remove(filename)

    except Exception as e:
        print(e)
        try:
            await loading_msg.delete()
        except:
            pass

# ================= Handlers =================

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    context.user_data["url"] = url

    keyboard = [
        [InlineKeyboardButton("🎬 فيديو سريع", callback_data="video")],
        [InlineKeyboardButton("🎵 صوت فقط", callback_data="audio")]
    ]

    await update.message.reply_text(
        "اختر نوع التحميل:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    url = context.user_data.get("url")
    limit = PREMIUM_LIMIT if user_id in PREMIUM_USERS else FREE_LIMIT

    # ===== LANGUAGE MENU =====
    if data == "language":
        keyboard = [
            [InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"),
             InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
        ]
        await query.edit_message_text(
            "اختر اللغة / Choose language:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    elif data == "lang_ar":
        user_language[user_id] = "ar"
        await query.edit_message_text("✅ تم اختيار اللغة العربية")
        return

    elif data == "lang_en":
        user_language[user_id] = "en"
        await query.edit_message_text("✅ Language set to English")
        return

    # ===== HELP =====
    elif data == "help":
        help_text = """📖 تعليمات التحميل:

1. افتح Instagram/TikTok/Pinterest/Likee/YouTube
2. انسخ رابط الفيديو الذي تريد
3. أرسله للبوت لتحصل على الفيديو أو الصوت مباشرة"""
        await query.edit_message_text(help_text)
        return

    # ===== RESTART =====
    elif data == "restart":
        context.user_data.clear()
        await query.edit_message_text("🔄 البوت أعيد تشغيله، أرسل رابط جديد.")
        return

    # ===== VIDEO / AUDIO =====
    elif data in ["video", "audio"]:
        await query.message.delete()
        await download_and_send(update.effective_chat, url, data, limit)
        return

# ================= COMMAND HANDLERS FOR REPLY KEYBOARD =================

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"),
         InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ]
    await update.message.reply_text(
        "اختر اللغة / Choose language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """📖 تعليمات التحميل:

1. افتح Instagram/TikTok/Pinterest/Likee/YouTube
2. انسخ رابط الفيديو الذي تريد
3. أرسله للبوت لتحصل على الفيديو أو الصوت مباشرة"""
    await update.message.reply_text(help_text)

async def restart_command_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🔄 البوت أعيد تشغيله، أرسل رابط جديد.")

# ================= Main =================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("restart", restart_command_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 البوت يعمل بسرعة خارقة...")
    app.run_polling()

if __name__ == "__main__":
    main()
