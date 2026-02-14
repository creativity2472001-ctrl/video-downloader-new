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

TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

VIDEO_OPTIONS = {
    'format': 'best[ext=mp4]/bestvideo+bestaudio/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
}

AUDIO_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'no_warnings': True,
}

user_language = {}

def t(user_id, key):
    lang = user_language.get(user_id, "ar")
    texts = {
        "choose_type": {"ar": "اختر نوع التحميل فيديو او صوت:", "en": "Choose download type video or audio:"},
        "video": {"ar": "فيديو 🎬", "en": "Video 🎬"},
        "audio": {"ar": "صوت 🎵", "en": "Audio 🎵"},
        "loading": {"ar": "جاري التحميل... ⏳", "en": "Downloading... ⏳"},
        "restart_msg": {"ar": "🔄 تم إعادة تشغيل البوت بنجاح.", "en": "🔄 Bot restarted successfully."},
        "help_text": {
            "ar": "📖 Download instructions:\n\n1. Go to the Instagram/TikTok/YouTube\n2. Copy the link\n3. Send it to the bot.",
            "en": "📖 Download instructions:\n\n1. Go to the Instagram/TikTok/YouTube\n2. Copy the link\n3. Send it to the bot."
        }
    }
    return texts.get(key, {}).get(lang, "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("اللغة 🌐"), KeyboardButton("المساعدة 📖")],
        [KeyboardButton("إعادة التشغيل 🔄")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("أهلاً بك! أرسل رابط الفيديو.", reply_markup=reply_markup)

async def download_and_send(chat, url, mode, user_id):
    # إرسال رسالة جاري التحميل
    loading_msg = await chat.send_message(t(user_id, "loading"))

    try:
        options = VIDEO_OPTIONS.copy() if mode == "video" else AUDIO_OPTIONS.copy()

        def download():
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info), info.get("title", "video")

        loop = asyncio.get_event_loop()
        # تنفيذ التحميل في الخلفية مهما طال الوقت
        filename, title = await loop.run_in_executor(None, download)

        if mode == "audio":
            actual_filename = os.path.splitext(filename)[0] + ".mp3"
        else:
            actual_filename = filename

        with open(actual_filename, "rb") as f:
            if mode == "audio":
                await chat.send_audio(f, caption=f"🎵 {title}")
            else:
                await chat.send_video(f, caption=f"🎬 {title}", supports_streaming=True)

        # حذف رسالة جاري التحميل فور انتهاء الإرسال بنجاح
        await loading_msg.delete()
        
        if os.path.exists(actual_filename): os.remove(actual_filename)

    except Exception:
        # تم مسح رسالة "حدث خطأ" من هنا تماماً لكي لا تظهر للمستخدم
        # سيقوم البوت بمحاولة التحميل بصمت، وإذا فشل لن يزعج المستخدم بأي رسالة
        try:
            await loading_msg.delete()
        except:
            pass

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    if text == "المساعدة 📖":
        await update.message.reply_text(t(user_id, "help_text"))
        return
    if text == "اللغة 🌐":
        keyboard = [[InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"), InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]]
        await update.message.reply_text("اختر اللغة:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    if text == "إعادة التشغيل 🔄":
        await update.message.reply_text(t(user_id, "restart_msg"))
        return

    if text.startswith("http"):
        context.user_data["url"] = text
        keyboard = [[InlineKeyboardButton(t(user_id, "video"), callback_data="video")], [InlineKeyboardButton(t(user_id, "audio"), callback_data="audio")]]
        await update.message.reply_text(t(user_id, "choose_type"), reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    url = context.user_data.get("url")

    if data in ["lang_ar", "lang_en"]:
        user_language[user_id] = "ar" if "ar" in data else "en"
        await query.edit_message_text("✅")
    elif data in ["video", "audio"]:
        await query.message.delete()
        # تشغيل مهمة التحميل كـ Task منفصلة تماماً لضمان عدم حدوث تجميد أو ظهور أخطاء وقت
        asyncio.create_task(download_and_send(update.effective_chat, url, data, user_id))

def main():
    # استخدام التوكن وتشغيل البوت بنظام يتجاهل الطلبات القديمة
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🚀 البوت يعمل بصمت تام وبدون رسائل خطأ...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
