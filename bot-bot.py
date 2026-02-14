import os
import asyncio
import yt_dlp
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- الإعدادات الأساسية ---
TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"  # ضع التوكن هنا
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# قائمة المستخدمين المميزين (ID)
PREMIUM_USERS = {123456789}

# ملف تفضيلات المستخدمين (اللغة)
PREFS_FILE = "prefs.json"
user_prefs = {}

def load_prefs():
    global user_prefs
    if os.path.exists(PREFS_FILE):
        with open(PREFS_FILE, "r", encoding="utf-8") as f:
            user_prefs = json.load(f)

def save_prefs():
    with open(PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(user_prefs, f)

# ---------------- إعدادات yt-dlp ----------------
VIDEO_OPTS = {
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "merge_output_format": "mp4",
    "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "quiet": True,
    "postprocessors": [{
        "key": "FFmpegVideoConvertor",
        "preferedformat": "mp4"
    }]
}

AUDIO_OPTS = {
    "format": "bestaudio/best",
    "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
    "quiet": True,
}

# ---------------- اللغات ----------------
LANGUAGE_DATA = {
    "ar": {
        "welcome": "🚀 أهلاً بك في EasyDown\n\n📌 حد التحميل المجاني: 50MB\n💎 حد مستخدمي بريميوم: 200MB",
        "send_link": "أرسل رابط الفيديو الآن لنبدأ 👇",
        "choose_mode": "اختر نوع الملف المطلوب:",
        "loading": "⏳ جاري التحميل... يرجى الانتظار",
        "error": "❌ حدث خطأ: ",
        "size_error": "⚠️ عذراً! حجم الملف {size}MB يتخطى حدك المسموح ({limit}MB).",
        "invalid": "❌ يرجى إرسال رابط صحيح (YouTube, TikTok, Instagram...)",
        "done": "✅ تم التحميل بنجاح!"
    },
    "en": {
        "welcome": "🚀 Welcome to EasyDown\n\n📌 Free Limit: 50MB\n💎 Premium Limit: 200MB",
        "send_link": "Send the video link to start 👇",
        "choose_mode": "Choose file type:",
        "loading": "⏳ Downloading... please wait",
        "error": "❌ Error occurred: ",
        "size_error": "⚠️ Sorry! File size {size}MB exceeds your limit ({limit}MB).",
        "invalid": "❌ Please send a valid link.",
        "done": "✅ Downloaded successfully!"
    }
}

async def get_lang(user_id):
    return user_prefs.get(str(user_id), "ar")

async def hourglass_animation(msg, lang):
    frames = ["⏳", "⌛", "🕰️", "⏱️"]
    text = LANGUAGE_DATA[lang]["loading"]
    i = 0
    while True:
        try:
            await msg.edit_text(f"{frames[i % len(frames)]} {text}")
            i += 1
            await asyncio.sleep(0.8)
        except:
            break

# ---------------- التحميل ----------------
async def download_and_send(update, url, mode):
    user_id = update.effective_user.id
    lang = await get_lang(user_id)

    status_msg = await update.effective_message.reply_text("⏳")
    animation_task = asyncio.create_task(hourglass_animation(status_msg, lang))

    try:
        opts = AUDIO_OPTS if mode == "audio" else VIDEO_OPTS
        loop = asyncio.get_event_loop()

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

            filesize = info.get('filesize', 0) or info.get('filesize_approx', 0)
            size_mb = filesize / (1024 * 1024)
            limit = 200 if user_id in PREMIUM_USERS else 50

            if size_mb > limit:
                animation_task.cancel()
                await status_msg.edit_text(LANGUAGE_DATA[lang]["size_error"].format(size=round(size_mb, 1), limit=limit))
                await asyncio.sleep(5)
                await status_msg.delete()
                return

            await loop.run_in_executor(None, lambda: ydl.download([url]))

            ext = "mp3" if mode == "audio" else "mp4"
            filename = os.path.join(DOWNLOAD_DIR, f"{info['id']}.{ext}")

            animation_task.cancel()
            await status_msg.delete()

            with open(filename, "rb") as file:
                if mode == "audio":
                    await update.effective_message.reply_audio(file, title=info.get('title'))
                else:
                    await update.effective_message.reply_video(file, caption=LANGUAGE_DATA[lang]["done"], supports_streaming=True)

            if os.path.exists(filename):
                os.remove(filename)

    except Exception as e:
        animation_task.cancel()
        await status_msg.edit_text(f"{LANGUAGE_DATA[lang]['error']} {str(e)}")
        await asyncio.sleep(5)
        await status_msg.delete()

# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_lang(user_id)
    keyboard = [[
        InlineKeyboardButton("🇸🇦 العربية", callback_data="setlang_ar"),
        InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en"),
        InlineKeyboardButton("🔄 Restart", callback_data="restart")
    ]]
    await update.message.reply_text(
        LANGUAGE_DATA[lang]["welcome"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    lang = await get_lang(user_id)

    if not url.startswith("http"):
        await update.message.reply_text(LANGUAGE_DATA[lang]["invalid"])
        return

    context.user_data["current_url"] = url
    keyboard = [[
        InlineKeyboardButton("🎬 Video", callback_data="mode_video"),
        InlineKeyboardButton("🎵 MP3 Audio", callback_data="mode_audio")
    ]]
    await update.message.reply_text(LANGUAGE_DATA[lang]["choose_mode"], reply_markup=InlineKeyboardMarkup(keyboard))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("setlang_"):
        lang = query.data.split("_")[1]
        user_prefs[str(user_id)] = lang
        save_prefs()
        await query.message.edit_text(LANGUAGE_DATA[lang]["send_link"])

    elif query.data == "restart":
        user_prefs[str(user_id)] = "ar"
        save_prefs()
        await query.message.edit_text(LANGUAGE_DATA["ar"]["welcome"])

    elif query.data.startswith("mode_"):
        mode = query.data.split("_")[1]
        url = context.user_data.get("current_url")
        if url:
            await query.message.delete()
            await download_and_send(query, url, mode)

# ---------------- التشغيل ----------------
def main():
    load_prefs()
    print("🚀 EasyDown Bot is running...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
