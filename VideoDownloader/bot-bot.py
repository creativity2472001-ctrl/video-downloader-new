import os
import asyncio
import yt_dlp
import json
import time
import logging
import shutil
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)
from telegram.constants import ParseMode

# ======================== الإعدادات الأساسية ========================
# التوكن سيؤخذ من متغير البيئة (آمن لـ GitHub)
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

# ======================== ملف اللغات (مضمن مباشرة) ========================
LANGS = {
    "ar": {
        "start": "🎬 مرحباً بك في بوت التحميل!\n\nأرسل رابط فيديو وسأقوم بتحميله.",
        "help": "📖 **التعليمات:**\n\n1️⃣ اذهب إلى أي تطبيق\n2️⃣ انسخ رابط الفيديو\n3️⃣ أرسله هنا",
        "choose": "🎯 اختر الجودة:",
        "video_480": "480p 🎬",
        "video_720": "720p 🎬",
        "video_1080": "1080p 🎬",
        "video_auto": "أفضل جودة ✨",
        "audio": "صوت فقط 🎵",
        "wait": "⏳ جاري التحميل...",
        "progress": "📥 التحميل: {0}%",
        "error": "❌ حدث خطأ",
        "too_large": "⚠️ الملف كبير جداً ({0}MB)",
        "language": "🌐 اللغة",
        "help_btn": "📖 المساعدة",
        "lang_done": "✅ تم تغيير اللغة"
    },
    "en": {
        "start": "🎬 Welcome!\n\nSend a video link.",
        "help": "📖 **Instructions:**\n\n1️⃣ Go to any app\n2️⃣ Copy video link\n3️⃣ Send it here",
        "choose": "🎯 Choose quality:",
        "video_480": "480p 🎬",
        "video_720": "720p 🎬",
        "video_1080": "1080p 🎬",
        "video_auto": "Best Quality ✨",
        "audio": "Audio Only 🎵",
        "wait": "⏳ Downloading...",
        "progress": "📥 Progress: {0}%",
        "error": "❌ Error",
        "too_large": "⚠️ File too large ({0}MB)",
        "language": "🌐 Language",
        "help_btn": "📖 Help",
        "lang_done": "✅ Language changed"
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

# ======================== معالج الأوامر ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    users.setdefault(uid, "ar")
    await update.message.reply_text(
        get_text(uid, "start"),
        reply_markup=main_keyboard(uid)
    )

async def help_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        get_text(uid, "help"),
        reply_markup=main_keyboard(uid)
    )

async def show_languages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇸🇦 عربي", callback_data="ar"),
         InlineKeyboardButton("🇺🇸 English", callback_data="en")]
    ]
    await update.message.reply_text(
        "Choose language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    users[uid] = query.data
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
            InlineKeyboardButton(get_text(uid, "video_480"), callback_data="video_480"),
            InlineKeyboardButton(get_text(uid, "video_720"), callback_data="video_720"),
        ],
        [
            InlineKeyboardButton(get_text(uid, "video_auto"), callback_data="video_best"),
            InlineKeyboardButton(get_text(uid, "audio"), callback_data="audio")
        ]
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
    
    if not url:
        await query.edit_message_text(get_text(uid, "error"))
        return
    
    is_audio = query.data == "audio"
    quality = query.data.replace("video_", "") if not is_audio else 'best'
    
    await query.message.delete()
    
    # بدء التحميل
    msg = await context.bot.send_message(query.message.chat_id, get_text(uid, "wait"))
    
    try:
        def download():
            opts = {
                'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
                'quiet': True,
                'format': 'bestaudio/best' if is_audio else 'best',
            }
            if is_audio:
                opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                }]
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
        
        loop = asyncio.get_event_loop()
        file = await loop.run_in_executor(None, download)
        
        if is_audio:
            file = file.replace('.webm', '.mp3').replace('.m4a', '.mp3')
        
        size = os.path.getsize(file) / (1024 * 1024)
        if size > MAX_SIZE_MB:
            await msg.edit_text(get_text(uid, "too_large", round(size, 1)))
            os.remove(file)
            return
        
        await msg.delete()
        with open(file, 'rb') as f:
            if is_audio:
                await context.bot.send_audio(query.message.chat_id, audio=f)
            else:
                await context.bot.send_video(query.message.chat_id, video=f)
        os.remove(file)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text(get_text(uid, "error"))

# ======================== التشغيل ========================
def main():
    print("🚀 بدء تشغيل البوت...")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.Regex("^(Language|اللغة)$"), show_languages
    ))
    app.add_handler(MessageHandler(
        filters.Regex("^(Help|المساعدة)$"), help_msg
    ))
    app.add_handler(MessageHandler(filters.TEXT & filters.Entity("url"), handle_link))
    app.add_handler(CallbackQueryHandler(set_language, pattern="^(ar|en)$"))
    app.add_handler(CallbackQueryHandler(quality_handler, pattern="^(video_|audio)"))
    
    print("✅ البوت يعمل الآن!")
    app.run_polling()

if __name__ == "__main__":
    main()
