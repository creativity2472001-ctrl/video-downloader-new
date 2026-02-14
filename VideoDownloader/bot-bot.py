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

# إعدادات الفيديو: تم تعديل الـ format لجلب أفضل جودة مدمجة (فيديو+صوت) دائماً
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

# ================= دالة ترجمة النصوص =================

def t(user_id, key):
    lang = user_language.get(user_id, "ar")
    texts = {
        "choose_type": {"ar": "اختر نوع التحميل فيديو او صوت:", "en": "Choose download type video or audio:"},
        "video": {"ar": "فيديو 🎬", "en": "Video 🎬"},
        "audio": {"ar": "صوت 🎵", "en": "Audio 🎵"},
        "loading": {"ar": "جاري التحميل... ⏳", "en": "Downloading... ⏳"},
        "restart_msg": {"ar": "🔄 تم إعادة تشغيل البوت بنجاح.", "en": "🔄 Bot restarted successfully."},
        "lang_set_ar": {"ar": "✅ تم اختيار اللغة العربية", "en": "✅ Arabic language set"},
        "lang_set_en": {"ar": "✅ تم اختيار اللغة الإنجليزية", "en": "✅ English language set"},
        "help_text": {
            "ar": "📖 Download instructions:\n\n1. Go to the Instagram/TikTok/Pinterest/Likee/YouTube app\n2. Choose a video you like\n3. Tap the ↪️ button or the three dots in the top right corner.\n4. Tap the \"Copy\" button.\n5. Send the link to the bot and in a few seconds you'll get the video without a watermark.",
            "en": "📖 Download instructions:\n\n1. Go to the Instagram/TikTok/Pinterest/Likee/YouTube app\n2. Choose a video you like\n3. Tap the ↪️ button or the three dots in the top right corner.\n4. Tap the \"Copy\" button.\n5. Send the link to the bot and in a few seconds you'll get the video without a watermark."
        }
    }
    return texts.get(key, {}).get(lang, "")

# ================= Commands =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إعداد أزرار القائمة السفلية كما طلبت
    keyboard = [
        [KeyboardButton("اللغة 🌐"), KeyboardButton("المساعدة 📖")],
        [KeyboardButton("إعادة التشغيل 🔄")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "أهلاً بك! أرسل رابط الفيديو وسأقوم بتحميله لك فوراً.",
        reply_markup=reply_markup
    )

# ================= Download Core =================

async def download_and_send(chat, url, mode, user_id):
    # إظهار رسالة جاري التحميل مع الساعة الرملية
    loading_msg = await chat.send_message(t(user_id, "loading"))

    try:
        options = VIDEO_OPTIONS.copy() if mode == "video" else AUDIO_OPTIONS.copy()

        def download():
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info), info.get("title", "video")

        loop = asyncio.get_event_loop()
        # استخدام executor يضمن عدم توقف البوت مهما طال وقت التحميل
        filename, title = await loop.run_in_executor(None, download)

        if mode == "audio":
            # التأكد من امتداد الملف في حالة الصوت
            base, ext = os.path.splitext(filename)
            actual_filename = base + ".mp3"
        else:
            actual_filename = filename

        # إرسال الملف
        with open(actual_filename, "rb") as f:
            if mode == "audio":
                await chat.send_audio(f, caption=f"🎵 {title}")
            else:
                await chat.send_video(f, caption=f"🎬 {title}", supports_streaming=True)

        # حذف رسالة "جاري التحميل" بعد ظهور الفيديو كما طلبت
        await loading_msg.delete()
        
        # تنظيف الملفات
        if os.path.exists(actual_filename): os.remove(actual_filename)
        if mode == "audio" and os.path.exists(filename): os.remove(filename)

    except Exception as e:
        print(f"Error: {e}")
        await loading_msg.edit_text("❌ حدث خطأ أثناء التحميل، تأكد من الرابط.")

# ================= Handlers =================

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    if text == "المساعدة 📖":
        await update.message.reply_text(t(user_id, "help_text"))
        return

    if text == "اللغة 🌐":
        keyboard = [
            [InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"),
             InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
        ]
        await update.message.reply_text("اختر اللغة / Choose language:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if text == "إعادة التشغيل 🔄":
        context.user_data.clear()
        await update.message.reply_text(t(user_id, "restart_msg"))
        return

    # إذا كان المدخل رابطاً
    if text.startswith("http"):
        context.user_data["url"] = text
        keyboard = [
            [InlineKeyboardButton(t(user_id, "video"), callback_data="video")],
            [InlineKeyboardButton(t(user_id, "audio"), callback_data="audio")]
        ]
        await update.message.reply_text(t(user_id, "choose_type"), reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    url = context.user_data.get("url")

    if data == "lang_ar":
        user_language[user_id] = "ar"
        await query.edit_message_text(t(user_id, "lang_set_ar"))
    elif data == "lang_en":
        user_language[user_id] = "en"
        await query.edit_message_text(t(user_id, "lang_set_en"))
    elif data in ["video", "audio"]:
        # حذف رسالة "اختر النوع" لتختفي كما طلبت
        await query.message.delete()
        await download_and_send(update.effective_chat, url, data, user_id)

# ================= Main =================

def main():
    # drop_pending_updates=True تمنع تكرار إرسال الفيديوهات القديمة عند التشغيل
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 البوت يعمل الآن بالمواصفات الجديدة...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
