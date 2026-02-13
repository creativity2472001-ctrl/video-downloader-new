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
        "help_text": "📖 Download instructions:\n1️⃣ Open Instagram/TikTok/YouTube\n2️⃣ Choose a video\n3️⃣ Tap ↪️ Share\n4️⃣ Copy link\n5️⃣ Send it here\n⚡ You'll receive it in seconds.",
        "restart_msg": "🔄 Bot restarted!",
        "invalid": "❌ Send a valid link."
    },
    "ar": {
        "welcome_free": "📌 مرحباً! الحد المجاني 50MB.",
        "welcome_premium": "💎 مرحباً مستخدم مدفوع! الحد 200MB.",
        "send_link": "🚀 أرسل الرابط",
        "choose_mode": "اختر نوع التحميل:",
        "help_text": "📖 طريقة التحميل:\n1️⃣ افتح Instagram/TikTok/YouTube\n2️⃣ اختر الفيديو\n3️⃣ اضغط مشاركة ↪️\n4️⃣ انسخ الرابط\n5️⃣ أرسل الرابط للبوت\n⚡ سيتم الإرسال خلال ثوانٍ.",
        "restart_msg": "🔄 تم إعادة تشغيل البوت!",
        "invalid": "❌ أرسل رابط صحيح."
    }
}

user_language = {}

# ----------------- START -----------------
async def start_message(message, context):
    user_id = message.from_user.id
    lang = user_language.get(user_id, "ar")
    msg = LANGUAGE_DATA[lang]["welcome_premium"] if user_id in PREMIUM_USERS else LANGUAGE_DATA[lang]["welcome_free"]

    keyboard = [
        [InlineKeyboardButton("🌐 " + ("English" if lang == "en" else "عربي"), callback_data="select_lang")],
        [InlineKeyboardButton("🔄 Restart", callback_data="restart"),
         InlineKeyboardButton("📖 Help", callback_data="help")]
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
    await query.message.edit_text("✅ Updated language!")
    await start_message(query.message, context)

# ----------------- RESTART -----------------
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_language[query.from_user.id] = "ar"
    await query.message.reply_text(LANGUAGE_DATA["ar"]["restart_msg"])
    await start_message(query.message, context)

# ----------------- DOWNLOAD -----------------
async def download_and_send(message, url, mode):
    user_id = message.from_user.id
    lang = user_language.get(user_id, "ar")

    # إزالة أزرار الفيديو/الصوت قبل التحميل
    await message.edit_reply_markup(reply_markup=None)

    # ⏳ ساعة رمليه حقيقية تتحرك كسائل
    status = await message.reply_text("⏳ Loading...")
    sand_levels = ["⬛⬛⬛⬛⬛", "🟫⬛⬛⬛⬛", "🟫🟫⬛⬛⬛", "🟫🟫🟫⬛⬛", "🟫🟫🟫🟫⬛", "🟫🟫🟫🟫🟫"]
    async def animate_hourglass(msg):
        try:
            while True:
                for i in range(len(sand_levels)):
                    text = f"⏳\n{sand_levels[i]}\n{''.join(reversed(sand_levels[i]))}"
                    await msg.edit_text(text)
                    await asyncio.sleep(0.6)
        except asyncio.CancelledError:
            pass

    animation_task = asyncio.create_task(animate_hourglass(status))

    try:
        loop = asyncio.get_event_loop()

        if mode == "audio":
            with yt_dlp.YoutubeDL(AUDIO_OPTIONS) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"
            await message.reply_audio(open(filename, "rb"))
            os.remove(filename)
        else:
            with yt_dlp.YoutubeDL(BASE_YDL_OPTS) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info)
            await message.reply_video(open(filename, "rb"))
            os.remove(filename)

        animation_task.cancel()
        await status.delete()

    except Exception as e:
        print(e)
        animation_task.cancel()
        await status.delete()

# ----------------- HANDLE LINK -----------------
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    lang = user_language.get(user_id, "ar")

    if not url.startswith("http"):
        await update.message.reply_text(LANGUAGE_DATA[lang]["invalid"])
        return

    context.user_data["url"] = url

    keyboard = [
        [InlineKeyboardButton("🎬 Video", callback_data="video")],
        [InlineKeyboardButton("🎵 Audio", callback_data="audio")]
    ]

    await update.message.reply_text(
        LANGUAGE_DATA[lang]["choose_mode"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ----------------- BUTTON -----------------
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
    elif data in ["video", "audio"]:
        url = context.user_data.get("url")
        if url:
            await download_and_send(query.message, url, data)

# ----------------- MAIN -----------------
def main():
    app = Application.builder().token(TOKEN).build()

    commands = [
        BotCommand("start", "Start bot"),
        BotCommand("help", "Help"),
    ]

    async def set_commands(app):
        await app.bot.set_my_commands(commands)

    app.post_init = set_commands

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
