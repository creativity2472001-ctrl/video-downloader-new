import os
import asyncio
import yt_dlp
import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

# إعداد التسجيل لمتابعة ما يحدث في الخلفية
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# ضع التوكن الخاص بك هنا مباشرة
# ---------------------------------------------------------
TOKEN = "ضع_التوكن_هنا" 
# ---------------------------------------------------------

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_ytdl_options(mode, filename_template):
    # خيارات متقدمة جداً لتجاوز الحماية ومحاكاة المتصفح
    common_opts = {
        'outtmpl': filename_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': True, # لا يتوقف عند الأخطاء البسيطة
        'no_color': True,
        'geo_bypass': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.google.com/',
        'retries': 10, # يحاول 10 مرات قبل اليأس
        'fragment_retries': 10,
        'socket_timeout': 60,
    }
    
    if mode == "video":
        # محاولة الحصول على أفضل توافق (صورة وصوت)
        common_opts.update({
            'format': 'bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        })
    else: # mode == "audio"
        common_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    return common_opts

user_language = {}

def t(user_id, key):
    lang = user_language.get(user_id, "ar")
    texts = {
        "choose_type": {"ar": "اختر نوع التحميل:", "en": "Choose type:"},
        "video": {"ar": "فيديو 🎬", "en": "Video 🎬"},
        "audio": {"ar": "صوت 🎵", "en": "Audio 🎵"},
        "loading": {"ar": "جاري التحميل... (قد يستغرق وقتاً للفيديوهات الطويلة) ⏳", "en": "Downloading... (may take time for long videos) ⏳"},
        "restart_msg": {"ar": "🔄 تم البدء من جديد.", "en": "🔄 Restarted."},
        "error_msg": {"ar": "❌ حدثت مشكلة في هذا الرابط، سأحاول مرة أخرى بطريقة مختلفة...", "en": "❌ Issue with this link, retrying differently..."},
        "file_too_large": {"ar": "⚠️ الملف كبير جداً (أكثر من 50MB)، تيليجرام قد لا يسمح بإرساله.", "en": "⚠️ File too large (>50MB)."},
        "help_text": {"ar": "📖 أرسل أي رابط وسأحاول تحميله لك مهما كان.", "en": "📖 Send any link and I'll try to download it."}
    }
    return texts.get(key, {}).get(lang, "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("اللغة 🌐"), KeyboardButton("المساعدة 📖")], [KeyboardButton("إعادة التشغيل 🔄")]]
    await update.message.reply_text("مرحباً بك! أنا جاهز لتحميل أي فيديو تريده. فقط أرسل الرابط.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def download_and_send(chat, url, mode, user_id):
    loading_msg = await chat.send_message(t(user_id, "loading"))
    actual_filename = None
    
    try:
        unique_id = f"{user_id}_{int(time.time())}"
        filename_template = f'{DOWNLOAD_DIR}/{unique_id}_%(title)s.%(ext)s'
        
        def download():
            # محاولة التحميل مع خيارات قوية
            with yt_dlp.YoutubeDL(get_ytdl_options(mode, filename_template)) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info: return None
                return {
                    'filename': ydl.prepare_filename(info),
                    'title': info.get("title", "video"),
                    'width': info.get("width"),
                    'height': info.get("height"),
                    'duration': info.get("duration")
                }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, download)
        
        if not result:
            # محاولة ثانية بخيارات أبسط في حال فشل الأولى
            def retry_download():
                opts = get_ytdl_options(mode, filename_template)
                opts['format'] = 'best' # اختيار أي شيء متاح
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info: return None
                    return {'filename': ydl.prepare_filename(info), 'title': info.get("title", "video")}
            
            result = await loop.run_in_executor(None, retry_download)

        if not result: raise Exception("Failed to download after retries")

        filename = result['filename']
        actual_filename = filename
        
        # التأكد من وجود الملف وتصحيح الامتداد
        base = os.path.splitext(filename)[0]
        for ext in ['.mp4', '.mkv', '.webm', '.mp3']:
            if os.path.exists(base + ext):
                actual_filename = base + ext
                break

        if not os.path.exists(actual_filename): raise Exception("File not found")

        with open(actual_filename, "rb") as f:
            if mode == "audio":
                await chat.send_audio(audio=f, caption=f"🎵 {result.get('title')}")
            else:
                await chat.send_video(
                    video=f, 
                    caption=f"🎬 {result.get('title')}", 
                    supports_streaming=True,
                    width=result.get('width'),
                    height=result.get('height'),
                    duration=result.get('duration')
                )

        await loading_msg.delete()
        
    except Exception as e:
        logger.error(f"Final Error: {e}")
        try: await loading_msg.edit_text("❌ عذراً، هذا الرابط محمي جداً أو الفيديو غير متاح حالياً.")
        except: pass
            
    finally:
        if actual_filename and os.path.exists(actual_filename):
            try: os.remove(actual_filename)
            except: pass

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, user_id = update.message.text, update.message.from_user.id
    if "http" in text:
        # استخراج الرابط فقط من النص
        url = text[text.find("http"):].split()[0]
        context.user_data["url"] = url
        keyboard = [[InlineKeyboardButton(t(user_id, "video"), callback_data="video")], [InlineKeyboardButton(t(user_id, "audio"), callback_data="audio")]]
        await update.message.reply_text(t(user_id, "choose_type"), reply_markup=InlineKeyboardMarkup(keyboard))
    elif text == "اللغة 🌐":
        keyboard = [[InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"), InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]]
        await update.message.reply_text("اختر اللغة:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif text == "المساعدة 📖":
        await update.message.reply_text(t(user_id, "help_text"))
    elif text == "إعادة التشغيل 🔄":
        await update.message.reply_text(t(user_id, "restart_msg"))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, user_id, url = query.data, query.from_user.id, context.user_data.get("url")

    if data.startswith("lang_"):
        user_language[user_id] = data.split("_")[1]
        await query.edit_message_text("✅ تم التحديث")
    elif data in ["video", "audio"]:
        if not url: return
        await query.message.delete()
        asyncio.create_task(download_and_send(update.effective_chat, url, data, user_id))

def main():
    if TOKEN == "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA": return print("❌ يرجى وضع التوكن!")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 البوت القوي يعمل الآن...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
