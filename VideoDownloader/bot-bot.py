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

# ⚡ صيغة سريعة جدًا (بدون دمج ثقيل إن وجد mp4 جاهز)
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

# ================= Progress Hook =================

def progress_hook_factory(message, loop):
    last_percent = {"value": 0}

    def hook(d):
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', '0%').strip()
            try:
                percent = float(percent_str.replace('%', ''))
                if percent - last_percent["value"] >= 5:
                    last_percent["value"] = percent
                    asyncio.run_coroutine_threadsafe(
                        message.edit_text(f"⏳ جاري التحميل... {percent:.0f}%"),
                        loop
                    )
            except:
                pass

    return hook

# ================= Commands =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 أرسل رابط فيديو\nاختر فيديو أو صوت\n⚡ نسخة فائقة السرعة"
    )

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🔄 أرسل رابط جديد.")

# ================= Download Core =================

async def download_and_send(chat, url, mode, limit):
    loading_msg = await chat.send_message("⏳ جاري التحميل... 0%")
    loop = asyncio.get_event_loop()

    try:
        if mode == "video":
            options = VIDEO_OPTIONS_BASE.copy()
        else:
            options = AUDIO_OPTIONS.copy()

        options['progress_hooks'] = [progress_hook_factory(loading_msg, loop)]

        def download():
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info), info.get("title", "بدون عنوان")

        filename, title = await loop.run_in_executor(None, download)

        # لو صوت
        if mode == "audio":
            filename = filename.rsplit(".", 1)[0] + ".mp3"
            with open(filename, "rb") as f:
                await chat.send_audio(f, caption=f"🎵 {title}")
            await loading_msg.delete()
            os.remove(filename)
            return

        # لو فيديو
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
        await loading_msg.edit_text("❌ فشل التحميل")

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
    await query.message.delete()

    url = context.user_data.get("url")
    user_id = query.from_user.id
    limit = PREMIUM_LIMIT if user_id in PREMIUM_USERS else FREE_LIMIT

    await download_and_send(update.effective_chat, url, query.data, limit)

# ================= Main =================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 البوت يعمل بسرعة خارقة...")
    app.run_polling()

if __name__ == "__main__":
    main()
