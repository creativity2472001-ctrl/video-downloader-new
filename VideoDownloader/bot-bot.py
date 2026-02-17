import os
import asyncio
import yt_dlp
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# ضع التوكن الخاص بك هنا
# ---------------------------------------------------------
TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA" 
# ---------------------------------------------------------

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_ytdl_options(mode, filename_template):
    if mode == "video":
        return {
            # نطلب أفضل فيديو mp4 وأفضل صوت m4a لضمان التوافق التام مع مشغل تيليجرام
            'format': 'bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[ext=mp4]/best',
            'outtmpl': filename_template,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
            # استخدام ffmpeg لضمان دمج صحيح للصورة والصوت
            'postprocessor_args': {
                'ffmpeg': ['-c:v', 'copy', '-c:a', 'copy']
            },
        }
    else: # mode == "audio"
        return {
            'format': 'bestaudio/best',
            'outtmpl': filename_template,
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
        "loading": {"ar": "جاري التحميل والمعالجة... ⏳", "en": "Downloading and processing... ⏳"},
        "restart_msg": {"ar": "🔄 تم إعادة تشغيل البوت بنجاح.", "en": "🔄 Bot restarted successfully."},
        "error_msg": {"ar": "❌ عذراً، حدث خطأ. تأكد من الرابط أو حاول مرة أخرى لاحقاً.", "en": "❌ Error. Check the link or try again later."},
        "file_too_large": {"ar": "❌ الملف كبير جداً (أكثر من 50MB).", "en": "❌ File too large (>50MB)."},
        "help_text": {
            "ar": "📖 أرسل رابط فيديو وسأقوم بتحميله لك بأعلى جودة متوافقة مع تيليجرام.",
            "en": "📖 Send a video link and I will download it in the best Telegram-compatible quality."
        }
    }
    return texts.get(key, {}).get(lang, "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("اللغة 🌐"), KeyboardButton("المساعدة 📖")], [KeyboardButton("إعادة التشغيل 🔄")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("أهلاً بك! أرسل الرابط للتحميل فوراً.", reply_markup=reply_markup)

async def download_and_send(chat, url, mode, user_id):
    loading_msg = await chat.send_message(t(user_id, "loading"))
    actual_filename = None
    
    try:
        unique_id = f"{user_id}_{int(asyncio.get_event_loop().time())}"
        filename_template = f'{DOWNLOAD_DIR}/{unique_id}_%(title)s.%(ext)s'
        options = get_ytdl_options(mode, filename_template)
        
        def download():
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                return {
                    'filename': ydl.prepare_filename(info),
                    'title': info.get("title", "video"),
                    'width': info.get("width"),
                    'height': info.get("height"),
                    'duration': info.get("duration")
                }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, download)
        filename = result['filename']

        if mode == "audio":
            actual_filename = os.path.splitext(filename)[0] + ".mp3"
        else:
            # التأكد من الامتداد الصحيح بعد الدمج
            if not filename.endswith(".mp4"):
                actual_filename = os.path.splitext(filename)[0] + ".mp4"
            else:
                actual_filename = filename

        if not os.path.exists(actual_filename):
            # محاولة البحث عن الملف إذا تغير امتداده أثناء الدمج
            base = os.path.splitext(filename)[0]
            for ext in ['.mp4', '.mkv', '.webm']:
                if os.path.exists(base + ext):
                    actual_filename = base + ext
                    break

        file_size = os.path.getsize(actual_filename) / (1024 * 1024)
        if file_size > 50:
            await chat.send_message(t(user_id, "file_too_large"))
        else:
            with open(actual_filename, "rb") as f:
                if mode == "audio":
                    await chat.send_audio(audio=f, caption=f"🎵 {result['title']}")
                else:
                    await chat.send_video(
                        video=f, 
                        caption=f"🎬 {result['title']}", 
                        supports_streaming=True,
                        width=result['width'],
                        height=result['height'],
                        duration=result['duration']
                    )

        await loading_msg.delete()
        
    except Exception as e:
        logger.error(f"Error: {e}")
        try: await loading_msg.edit_text(t(user_id, "error_msg"))
        except: await chat.send_message(t(user_id, "error_msg"))
            
    finally:
        if actual_filename and os.path.exists(actual_filename):
            try: os.remove(actual_filename)
            except: pass

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    if text == "المساعدة 📖":
        await update.message.reply_text(t(user_id, "help_text"))
    elif text == "اللغة 🌐":
        keyboard = [[InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"), InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]]
        await update.message.reply_text("اختر اللغة:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif text == "إعادة التشغيل 🔄":
        context.user_data.clear()
        await update.message.reply_text(t(user_id, "restart_msg"))
    elif text.startswith("http"):
        context.user_data["url"] = text
        keyboard = [[InlineKeyboardButton(t(user_id, "video"), callback_data="video")], [InlineKeyboardButton(t(user_id, "audio"), callback_data="audio")]]
        await update.message.reply_text(t(user_id, "choose_type"), reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, user_id, url = query.data, query.from_user.id, context.user_data.get("url")

    if data.startswith("lang_"):
        user_language[user_id] = data.split("_")[1]
        await query.edit_message_text("✅ تم تحديث اللغة" if user_language[user_id]=="ar" else "✅ Language updated")
    elif data in ["video", "audio"]:
        if not url: return
        await query.message.delete()
        asyncio.create_task(download_and_send(update.effective_chat, url, data, user_id))

def main():
    if TOKEN == "ضع_التوكن_هنا":
        print("❌ خطأ: يرجى وضع التوكن داخل الكود.")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 البوت يعمل الآن... اضغط Ctrl+C للإيقاف")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
