import os
import asyncio
import yt_dlp
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ====== ضع التوكن هنا ======
TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"

DOWNLOAD_DIR = "downloads"
FREE_LIMIT = 50 * 1024 * 1024
PREMIUM_LIMIT = 200 * 1024 * 1024
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

PREMIUM_USERS = {123456789}

# ===== خيارات تحميل الفيديو سريع + بدون زوم =====
VIDEO_OPTIONS = {
    'format': 'bestvideo+bestaudio/best',
    'merge_output_format': 'mp4',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
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

# ================= نصوص متعددة اللغات =================
TEXTS = {
    "choose": {"AR": "اختر نوع التحميل:", "EN": "Choose download type:"},
    "loading": {"AR": "⏳ جاري التحميل...", "EN": "⏳ Loading..."},
    "fail": {"AR": "❌ فشل التحميل", "EN": "❌ Download failed"},
    "large_file": {"AR": "⚠️ الحجم كبير — سيتم إرسال الصوت فقط", "EN": "⚠️ File too large — only audio will be sent"},
}

def get_text(key, lang):
    return TEXTS.get(key, {}).get(lang, "")

# ================= Commands قائمة البوت =================
async def set_commands(app):
    commands = [
        BotCommand("language", "🌐 اللغة / Language"),
        BotCommand("help", "📖 المساعدة"),
        BotCommand("restart", "🔄 إعادة التشغيل")
    ]
    await app.bot.set_my_commands(commands)

# ================= Commands Handlers =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lang"] = context.user_data.get("lang", "AR")
    await update.message.reply_text("🚀 أرسل الرابط لتحميل الفيديو أو الصوت")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🔄 أرسل رابط جديد.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "AR")
    text = "📖 استخدم البوت:\n1️⃣ أرسل رابط\n2️⃣ اختر فيديو أو صوت\n3️⃣ سيتم التحميل بسرعة عالية"
    await update.message.reply_text(text)

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ]
    lang = context.user_data.get("lang", "AR")
    await update.message.reply_text(get_text("choose", lang), reply_markup=InlineKeyboardMarkup(keyboard))

# ================= Download =================
async def download_and_send(chat, url, mode, limit, lang):
    loading_msg = await chat.send_message(get_text("loading", lang))
    loop = asyncio.get_event_loop()
    try:
        options = VIDEO_OPTIONS.copy() if mode == "video" else AUDIO_OPTIONS.copy()

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

        # لو فيديو كبير جدًا
        if os.path.getsize(filename) > limit:
            await loading_msg.edit_text(get_text("large_file", lang))
            await download_and_send(chat, url, "audio", limit, lang)
            return

        # إرسال الفيديو
        with open(filename, "rb") as f:
            await chat.send_video(f, caption=f"🎬 {title}", supports_streaming=True)
        await loading_msg.delete()
        os.remove(filename)

    except Exception as e:
        print(e)
        await loading_msg.edit_text(get_text("fail", lang))

# ================= Link Handler =================
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    context.user_data["url"] = url
    lang = context.user_data.get("lang", "AR")

    keyboard = [
        [InlineKeyboardButton("🎬 فيديو", callback_data="video")],
        [InlineKeyboardButton("🎵 صوت", callback_data="audio")]
    ]

    await update.message.reply_text(get_text("choose", lang), reply_markup=InlineKeyboardMarkup(keyboard))

# ================= Button Handler =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()  # الزر يختفي فورًا

    user_id = query.from_user.id
    lang = context.user_data.get("lang", "AR")
    limit = PREMIUM_LIMIT if user_id in PREMIUM_USERS else FREE_LIMIT

    if query.data in ["video", "audio"]:
        url = context.user_data.get("url")
        await download_and_send(update.effective_chat, url, query.data, limit, lang)
    elif query.data.startswith("lang_"):
        context.user_data["lang"] = "AR" if query.data == "lang_ar" else "EN"
        await update.effective_chat.send_message(f"✅ اللغة تم تغييرها إلى {'العربية' if context.user_data['lang']=='AR' else 'English'}")

# ================= Main =================
def main():
    app = Application.builder().token(TOKEN).post_init(set_commands).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 البوت جاهز للعمل – تحميل سريع + ساعة رمليه")
    app.run_polling()

if __name__ == "__main__":
    main()
