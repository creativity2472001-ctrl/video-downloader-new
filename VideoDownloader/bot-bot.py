import os
import asyncio
import yt_dlp
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

FREE_LIMIT = 50 * 1024 * 1024
PREMIUM_LIMIT = 200 * 1024 * 1024
PREMIUM_USERS = {123456789}

# 🔥 خيارات قوية تجبر إنستغرام على فيديو حقيقي
VIDEO_OPTIONS = {
    'format': 'bv*+ba/bestvideo+bestaudio/best',
    'merge_output_format': 'mp4',
    'outtmpl': f'{DOWNLOAD_DIR}/%(id)s.%(ext)s',
    'noplaylist': True,
    'quiet': True,
    'concurrent_fragment_downloads': 8,
    'retries': 10,
    'fragment_retries': 10,
    'continuedl': True,
}

AUDIO_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(id)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'noplaylist': True,
}

TEXTS = {
    "choose": {"AR": "اختر نوع التحميل:", "EN": "Choose download type:"},
    "loading": {"AR": "⏳ جاري التحميل...", "EN": "⏳ Loading..."},
}

def get_text(key, lang):
    return TEXTS[key][lang]

# ================= Commands =================

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("language", "🌐 اللغة / Language"),
        BotCommand("help", "📖 المساعدة"),
        BotCommand("restart", "🔄 إعادة التشغيل")
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lang"] = context.user_data.get("lang", "AR")
    await update.message.reply_text("🚀 أرسل الرابط لتحميل الفيديو أو الصوت")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🔄 أرسل رابط جديد.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل رابط ثم اختر فيديو أو صوت.")

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ]
    await update.message.reply_text("اختر اللغة:", reply_markup=InlineKeyboardMarkup(keyboard))

# ================= Download =================

async def download_and_send(chat, url, mode, limit, lang):
    loading_msg = await chat.send_message(get_text("loading", lang))
    loop = asyncio.get_event_loop()

    try:
        options = VIDEO_OPTIONS.copy() if mode == "video" else AUDIO_OPTIONS.copy()

        def download():
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info), info.get("title", "Video")

        filename, title = await loop.run_in_executor(None, download)

        if mode == "audio":
            filename = filename.rsplit(".", 1)[0] + ".mp3"
            with open(filename, "rb") as f:
                await chat.send_audio(f, caption=f"🎵 {title}")
        else:
            with open(filename, "rb") as f:
                await chat.send_video(
                    f,
                    caption=f"🎬 {title}",
                    supports_streaming=True
                )

        await loading_msg.delete()
        os.remove(filename)

    except Exception as e:
        print("Download error:", e)
        await loading_msg.delete()

# ================= Handlers =================

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["url"] = update.message.text.strip()
    lang = context.user_data.get("lang", "AR")

    keyboard = [
        [InlineKeyboardButton("🎬 فيديو", callback_data="video")],
        [InlineKeyboardButton("🎵 صوت", callback_data="audio")]
    ]

    await update.message.reply_text(
        get_text("choose", lang),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()

    lang = context.user_data.get("lang", "AR")
    url = context.user_data.get("url")

    if query.data == "video":
        await download_and_send(update.effective_chat, url, "video", FREE_LIMIT, lang)

    elif query.data == "audio":
        await download_and_send(update.effective_chat, url, "audio", FREE_LIMIT, lang)

    elif query.data == "lang_ar":
        context.user_data["lang"] = "AR"
        await update.effective_chat.send_message("✅ تم تغيير اللغة إلى العربية")

    elif query.data == "lang_en":
        context.user_data["lang"] = "EN"
        await update.effective_chat.send_message("✅ Language changed to English")

# ================= Main =================

def main():
    app = Application.builder().token(TOKEN).post_init(set_commands).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
