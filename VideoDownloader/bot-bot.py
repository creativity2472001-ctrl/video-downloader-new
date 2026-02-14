import os
import yt_dlp
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"

user_language = {}


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📋 Menu")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "🎬 Send me a video link\nارسل رابط فيديو",
        reply_markup=reply_markup
    )


# ================= MENU =================
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌐 Language", callback_data="language")],
        [InlineKeyboardButton("📖 Help", callback_data="help")],
        [InlineKeyboardButton("🔄 Restart", callback_data="restart")],
    ]

    await update.message.reply_text(
        "📋 Menu:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ================= HANDLE LINK =================
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text

    if not url.startswith("http"):
        return

    context.user_data["url"] = url

    keyboard = [
        [
            InlineKeyboardButton("🎥 Video", callback_data="video"),
            InlineKeyboardButton("🎵 Audio", callback_data="audio"),
        ]
    ]

    await update.message.reply_text(
        "اختر نوع التحميل:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ================= DOWNLOAD =================
async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    url = context.user_data.get("url")
    if not url:
        return

    await query.delete_message()

    loading_msg = await query.message.chat.send_message("⏳ جاري التحميل...")

    ydl_opts = {
        "outtmpl": "downloaded.%(ext)s",
        "quiet": True,
    }

    if query.data == "audio":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        ydl_opts.update({
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        file_name = [f for f in os.listdir() if f.startswith("downloaded.")][0]

        if query.data == "audio":
            await query.message.chat.send_audio(open(file_name, "rb"))
        else:
            await query.message.chat.send_video(open(file_name, "rb"))

        os.remove(file_name)
        await loading_msg.delete()

    except Exception as e:
        await loading_msg.edit_text("❌ حدث خطأ أثناء التحميل")


# ================= LANGUAGE =================
async def language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"),
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
        ]
    ]

    await query.edit_message_text(
        "اختر اللغة / Choose language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "lang_ar":
        user_language[query.from_user.id] = "ar"
        await query.edit_message_text("✅ تم اختيار اللغة العربية")
    else:
        user_language[query.from_user.id] = "en"
        await query.edit_message_text("✅ Language set to English")


# ================= HELP =================
async def help_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = """
📖 Download instructions:

1. Go to the Instagram/TikTok/Pinterest/Likee/YouTube app
2. Choose a video you like
3. Tap the ↪️ button or the three dots
4. Tap the "Copy" button
5. Send the link to the bot
"""

    await query.edit_message_text(text)


# ================= RESTART =================
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔄 Restarted. Send a new link.")


# ================= MAIN =================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("📋 Menu"), menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(download_handler, pattern="video|audio"))
    app.add_handler(CallbackQueryHandler(language_menu, pattern="language"))
    app.add_handler(CallbackQueryHandler(set_language, pattern="lang_"))
    app.add_handler(CallbackQueryHandler(help_message, pattern="help"))
    app.add_handler(CallbackQueryHandler(restart, pattern="restart"))

    app.run_polling()


if __name__ == "__main__":
    main()
