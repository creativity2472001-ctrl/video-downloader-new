import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"  # ضع التوكن هنا

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

PREMIUM_USERS = {123456789}  # ضع ID المستخدمين المدفوعين هنا

# ---------------- إعدادات yt-dlp ----------------
BASE_YDL_OPTS = {
    "format": "bestvideo+bestaudio/best",
    "merge_output_format": "mp4",
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

# ---------------- اللغات ----------------
LANGUAGE_DATA = {
    "ar": {
        "welcome_free": "📌 مرحباً! الحد المجاني 50MB.",
        "welcome_premium": "💎 مرحباً مستخدم مدفوع! الحد 200MB.",
        "send_link": "🚀 أرسل الرابط",
        "choose_mode": "اختر نوع التحميل:",
        "help_text": "📖 طريقة التحميل:\n1️⃣ افتح المنصة\n2️⃣ انسخ الرابط\n3️⃣ أرسله للبوت\n⚡ سيتم الإرسال خلال ثوانٍ.",
        "restart_msg": "🔄 تم إعادة تشغيل البوت!",
        "invalid": "❌ أرسل رابط صحيح."
    },
    "en": {
        "welcome_free": "📌 Welcome! Free limit 50MB.",
        "welcome_premium": "💎 Welcome Premium user! Limit 200MB.",
        "send_link": "🚀 Send link",
        "choose_mode": "Choose download type:",
        "help_text": "📖 How to download:\n1️⃣ Open platform\n2️⃣ Copy link\n3️⃣ Send it here\n⚡ You'll receive it in seconds.",
        "restart_msg": "🔄 Bot restarted!",
        "invalid": "❌ Send a valid link."
    }
}

user_language = {}

# ---------------- START ----------------
async def start_message(message, context):
    user_id = message.from_user.id
    lang = user_language.get(user_id, "ar")

    welcome = LANGUAGE_DATA[lang]["welcome_premium"] if user_id in PREMIUM_USERS else LANGUAGE_DATA[lang]["welcome_free"]

    keyboard = [[
        InlineKeyboardButton("🌐 Language", callback_data="select_lang"),
        InlineKeyboardButton("📖 Help", callback_data="help"),
        InlineKeyboardButton("🔄 Restart", callback_data="restart")
    ]]

    await message.reply_text(
        f"{welcome}\n\n{LANGUAGE_DATA[lang]['send_link']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_message(update.message, context)

# ---------------- HELP ----------------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_language.get(user_id, "ar")
    await update.effective_message.reply_text(LANGUAGE_DATA[lang]["help_text"])

# ---------------- LANGUAGE ----------------
async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [[
        InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"),
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
    ]]
    await query.message.reply_text("🌐 اختر اللغة:", reply_markup=InlineKeyboardMarkup(keyboard))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code):
    query = update.callback_query
    user_language[query.from_user.id] = lang_code
    await query.message.reply_text("✅ تم تحديث اللغة!")
    await start_message(query.message, context)

# ---------------- RESTART ----------------
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_language[query.from_user.id] = "ar"
    await query.message.reply_text(LANGUAGE_DATA["ar"]["restart_msg"])
    await start_message(query.message, context)

# ---------------- التحميل مع ساعة رملية ----------------
async def download_and_send(message, url, mode):
    hourglass_msg = await message.reply_text("⏳ جاري التحميل...")

    async def hourglass_animation():
        frames = ["⏳", "⌛", "🕰️", "⏱️"]
        i = 0
        while True:
            try:
                await hourglass_msg.edit_text(frames[i % len(frames)] + " جاري التحميل...")
                i += 1
                await asyncio.sleep(0.7)
            except:
                break

    animation_task = asyncio.create_task(hourglass_animation())

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

            await message.reply_video(
                open(filename, "rb"),
                supports_streaming=True
            )
            os.remove(filename)

    except Exception as e:
        await message.reply_text(f"❌ حدث خطأ أثناء التحميل: {str(e)}")

    finally:
        animation_task.cancel()
        await hourglass_msg.delete()

# ---------------- استقبال الرابط ----------------
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    lang = user_language.get(user_id, "ar")

    if not url.startswith("http"):
        await update.message.reply_text(LANGUAGE_DATA[lang]["invalid"])
        return

    context.user_data["url"] = url

    keyboard = [[
        InlineKeyboardButton("🎬 Video", callback_data="video"),
        InlineKeyboardButton("🎵 Audio", callback_data="audio")
    ]]

    await update.message.reply_text(
        LANGUAGE_DATA[lang]["choose_mode"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------- الأزرار ----------------
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
            # حذف رسالة "اختر نوع التحميل" مع الأزرار
            await query.message.delete()
            await download_and_send(query.message, url, data)

# ---------------- تشغيل البوت ----------------
def main():
    app = Application.builder().token(TOKEN).build()

    commands = [
        BotCommand("start", "Start"),
        BotCommand("help", "Help"),
    ]

    async def set_commands(app):
        await app.bot.set_my_commands(commands)

    app.post_init = set_commands

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
