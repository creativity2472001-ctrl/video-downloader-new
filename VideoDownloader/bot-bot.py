import os
import asyncio
import yt_dlp
import json
import time
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

# ======================== الإعدادات الأساسية ========================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    print("❌ خطأ: لم يتم العثور على التوكن!")
    print("📝 يرجى وضع التوكن في متغير البيئة TELEGRAM_BOT_TOKEN")
    exit(1)

MAX_SIZE_MB = 80
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ======================== ملف اللغات ========================
LANGS = {
    "ar": {
        "start": "🎬 **مرحباً بك في بوت التحميل!**\n\nأرسل رابط فيديو وسأقوم بتحميله لك بأفضل جودة.",
        "help": "📖 **تعليمات التحميل:**\n\n1️⃣ اذهب إلى تطبيق Instagram/TikTok/Pinterest/Likee/YouTube\n2️⃣ اختر الفيديو الذي تريده\n3️⃣ اضغط على زر ↪️ أو الثلاث نقاط في الأعلى\n4️⃣ اضغط على زر **نسخ الرابط**\n5️⃣ أرسل الرابط هنا وخلال ثوانٍ ستصلك الفيديو بدون علامة مائية!\n\n💾 **للحفظ:** بعد إرسال الفيديو، اضغط على الفيديو ثم على الثلاث نقاط واختر **حفظ**.",
        "choose": "🎯 **اختر جودة التحميل:**",
        "video_480": "480p 🎬",
        "video_720": "720p 🎬",
        "video_1080": "1080p 🎬",
        "video_auto": "أفضل جودة ✨",
        "audio": "صوت فقط 🎵",
        "wait": "⏳ جاري التحميل والمعالجة... (قد يستغرق وقتاً للفيديوهات الطويلة)",
        "progress": "📥 **التحميل:** {0}%\n⚡ **السرعة:** {1}\n⏱️ **الوقت المتبقي:** {2}",
        "done": "✅ **تم التحميل بنجاح!** جاري الإرسال...",
        "error": "❌ **عذراً، حدث خطأ أثناء التحميل.**\n\n⚠️ الأسباب المحتملة:\n• الرابط غير صالح\n• الفيديو محمي\n• الموقع غير مدعوم",
        "too_large": "⚠️ **الملف كبير جداً** ({0}MB)\nالحد الأقصى المسموح به هو {1}MB.",
        "language": "اللغة 🌐",
        "help_btn": "المساعدة 📖",
        "lang_done": "✅ **تم تغيير اللغة بنجاح!**",
        "lang_choose": "🌐 **اختر لغتك المفضلة:**"
    },
    "en": {
        "start": "🎬 **Welcome to the Download Bot!**\n\nSend a video link and I'll download it in best quality.",
        "help": "📖 **Download Instructions:**\n\n1️⃣ Go to Instagram/TikTok/Pinterest/Likee/YouTube\n2️⃣ Choose a video\n3️⃣ Tap the ↪️ button or the three dots\n4️⃣ Tap **Copy Link**\n5️⃣ Send the link here and get the video without watermark!\n\n💾 **To save:** After receiving the video, tap on it, then the three dots and choose **Save**.",
        "choose": "🎯 **Choose download quality:**",
        "video_480": "480p 🎬",
        "video_720": "720p 🎬",
        "video_1080": "1080p 🎬",
        "video_auto": "Best Quality ✨",
        "audio": "Audio Only 🎵",
        "wait": "⏳ Downloading and processing... (may take time for long videos)",
        "progress": "📥 **Progress:** {0}%\n⚡ **Speed:** {1}\n⏱️ **ETA:** {2}",
        "done": "✅ **Download complete!** Sending...",
        "error": "❌ **Sorry, an error occurred.**\n\n⚠️ Possible reasons:\n• Invalid link\n• Protected video\n• Unsupported site",
        "too_large": "⚠️ **File too large** ({0}MB)\nMaximum allowed size is {1}MB.",
        "language": "Language 🌐",
        "help_btn": "Help 📖",
        "lang_done": "✅ **Language changed successfully!**",
        "lang_choose": "🌐 **Choose your preferred language:**"
    }
}

# ======================== بيانات المستخدمين ========================
users = {}

def get_text(uid, key, *args):
    lang = users.get(uid, "ar")
    text = LANGS.get(lang, LANGS["en"]).get(key, "")
    return text.format(*args) if args else text

def main_keyboard(uid):
    keyboard = [
        [KeyboardButton(get_text(uid, "language")),
         KeyboardButton(get_text(uid, "help_btn"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ======================== دوال yt-dlp ========================
def progress_hook(d, msg, uid, start_time):
    if d['status'] == 'downloading':
        try:
            if time.time() - start_time > 3:
                percent = d.get('_percent_str', '0%').strip()
                speed = d.get('_speed_str', 'N/A').strip()
                eta = d.get('_eta_str', 'N/A').strip()
                
                asyncio.run_coroutine_threadsafe(
                    msg.edit_text(get_text(uid, "progress", percent, speed, eta)),
                    asyncio.get_event_loop()
                )
                return time.time()
        except:
            pass
    return start_time

# ======================== معالجات الأوامر ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    users.setdefault(uid, "ar")
    await update.message.reply_text(
        get_text(uid, "start"),
        reply_markup=main_keyboard(uid)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        get_text(uid, "help"),
        reply_markup=main_keyboard(uid)
    )

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"),
         InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ]
    await update.message.reply_text(
        get_text(uid, "lang_choose"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = query.from_user.id
    lang = query.data.replace("lang_", "")
    users[uid] = lang
    
    await query.edit_message_text(get_text(uid, "lang_done"))
    await context.bot.send_message(
        query.message.chat_id,
        get_text(uid, "start"),
        reply_markup=main_keyboard(uid)
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    url = update.message.text.strip()
    context.user_data['url'] = url
    
    keyboard = [
        [
            InlineKeyboardButton(get_text(uid, "video_480"), callback_data="480"),
            InlineKeyboardButton(get_text(uid, "video_720"), callback_data="720"),
        ],
        [
            InlineKeyboardButton(get_text(uid, "video_1080"), callback_data="1080"),
            InlineKeyboardButton(get_text(uid, "video_auto"), callback_data="best"),
        ],
        [InlineKeyboardButton(get_text(uid, "audio"), callback_data="audio")]
    ]
    
    await update.message.reply_text(
        get_text(uid, "choose"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def quality_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = query.from_user.id
    url = context.user_data.get('url')
    quality = query.data
    
    if not url:
        await query.edit_message_text(get_text(uid, "error"))
        return
    
    await query.message.delete()
    
    msg = await context.bot.send_message(query.message.chat_id, get_text(uid, "wait"))
    filename = None
    start_time = time.time()
    
    try:
        def download():
            is_audio = (quality == "audio")
            opts = {
                'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
                'quiet': True,
                'progress_hooks': [lambda d: progress_hook(d, msg, uid, start_time)],
            }
            
            if is_audio:
                opts['format'] = 'bestaudio/best'
                opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            else:
                if quality == "480":
                    opts['format'] = 'best[height<=480]'
                elif quality == "720":
                    opts['format'] = 'best[height<=720]'
                elif quality == "1080":
                    opts['format'] = 'best[height<=1080]'
                else:
                    opts['format'] = 'best'
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
        
        loop = asyncio.get_event_loop()
        file = await loop.run_in_executor(None, download)
        
        if quality == "audio":
            file = file.replace('.webm', '.mp3').replace('.m4a', '.mp3')
        
        if not os.path.exists(file):
            base = os.path.splitext(file)[0]
            for ext in ['.mp4', '.mkv', '.webm', '.mp3']:
                if os.path.exists(base + ext):
                    file = base + ext
                    break
        
        size = os.path.getsize(file) / (1024 * 1024)
        if size > MAX_SIZE_MB:
            await msg.edit_text(get_text(uid, "too_large", round(size, 1), MAX_SIZE_MB))
            os.remove(file)
            return
        
        await msg.delete()
        with open(file, 'rb') as f:
            if quality == "audio":
                await context.bot.send_audio(query.message.chat_id, audio=f)
            else:
                await context.bot.send_video(query.message.chat_id, video=f)
        os.remove(file)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text(get_text(uid, "error"))
        if filename and os.path.exists(filename):
            try: os.remove(filename)
            except: pass

# ======================== التشغيل ========================
def main():
    print("🚀 بدء تشغيل البوت...")
    
    app = Application.builder().token(TOKEN).build()
    
    # معالجات الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^(المساعدة 📖|Help 📖)$"), help_command))
    app.add_handler(MessageHandler(filters.Regex("^(اللغة 🌐|Language 🌐)$"), language_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.Entity("url"), handle_link))
    
    # معالجات الأزرار
    app.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(quality_handler, pattern="^(480|720|1080|best|audio)$"))
    
    print("✅ البوت يعمل الآن!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
