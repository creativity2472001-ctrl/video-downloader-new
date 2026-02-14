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

user_language = {}

def t(user_id, key):
    lang = user_language.get(user_id, "ar")
    texts = {
        "choose_type": {"ar": "اختر نوع التحميل:", "en": "Choose download type:"},
        "video": {"ar": "🎬 فيديو سريع", "en": "🎬 Video"},
        "audio": {"ar": "🎵 صوت فقط", "en": "🎵 Audio only"},
        "loading": {"ar": "⏳ جاري التحميل...", "en": "⏳ Downloading..."},
        "restart_msg": {"ar": "🔄 البوت أعيد تشغيله، أرسل رابط جديد.", "en": "🔄 Bot restarted, send a new link."},
        "lang_set_ar": {"ar": "✅ تم اختيار اللغة العربية", "en": "✅ Arabic language set"},
        "lang_set_en": {"ar": "✅ تم اختيار اللغة الإنجليزية", "en": "✅ English language set"},
        "help_text": {
            "ar": "📖 تعليمات التحميل:\n\n1. افتح Instagram/TikTok/Pinterest/Likee/YouTube\n2. انسخ رابط الفيديو\n3. أرسله للبوت لتحصل على الفيديو أو الصوت مباشرة",
            "en": "📖 Download instructions:\n\n1. Open Instagram/TikTok/Pinterest/Likee/YouTube\n2. Copy the video link\n3. Send it to the bot to get the video or audio directly"
        }
    }
    return texts.get(key, {}).get(lang, "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("/language"), KeyboardButton("/help"), KeyboardButton("/restart")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🚀 أرسل رابط فيديو\nاختر فيديو أو صوت\n⚡ نسخة فائقة السرعة",
        reply_markup=reply_markup
    )

async def download_and_send(chat, url, mode, user_id):
    loading_msg = await chat.send_message(t(user_id, "loading"))
    try:
        options = VIDEO_OPTIONS_BASE.copy() if mode == "video" else AUDIO_OPTIONS.copy()
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
            return

        # 🔹 إرسال الفيديو كملف ليتم حفظه تلقائياً في الاستوديو
        with open(filename, "rb") as f:
            await chat.send_document(f, caption=f"🎬 {title}")

        await loading_msg.delete()

    except Exception as e:
        print(e)
        try:
            await loading_msg.delete()
        except:
            pass

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    context.user_data["url"] = url
    user_id = update.message.from_user.id
    keyboard = [
        [InlineKeyboardButton(t(user_id, "video"), callback_data="video")],
        [InlineKeyboardButton(t(user_id, "audio"), callback_data="audio")]
    ]
    await update.message.reply_text(
        t(user_id, "choose_type"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    url = context.user_data.get("url")

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
        await query.edit_message_text(t(user_id, "lang_set_ar"))
        return

    elif data == "lang_en":
        user_language[user_id] = "en"
        await query.edit_message_text(t(user_id, "lang_set_en"))
        return

    elif data == "help":
        await query.edit_message_text(t(user_id, "help_text"))
        return

    elif data == "restart":
        context.user_data.clear()
        await query.edit_message_text(t(user_id, "restart_msg"))
        return

    elif data in ["video", "audio"]:
        await query.message.delete()
        await download_and_send(update.effective_chat, url, data, user_id)
        return

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
    user_id = update.message.from_user.id
    await update.message.reply_text(t(user_id, "help_text"))

async def restart_command_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    context.user_data.clear()
    await update.message.reply_text(t(user_id, "restart_msg"))

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
