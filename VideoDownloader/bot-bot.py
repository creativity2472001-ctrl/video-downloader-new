import os
import json
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

# ======================== الإعدادات الأساسية ========================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

if TOKEN == "YOUR_BOT_TOKEN_HERE":
    print("❌ خطأ: لم يتم العثور على التوكن!")
    print("📝 يرجى وضع التوكن في الكود أو في متغير البيئة TELEGRAM_BOT_TOKEN")
    exit(1)

MAX_SIZE_MB = 80
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ======================== ملف اللغات ========================
LANGS = {
    "ar": {
        "start": "🎬 **مرحباً بك في بوت التحميل!**\n\nأرسل رابط فيديو وسأقوم بتحميله لك بأفضل جودة.",
        "help": "📖 **تعليمات التحميل:**\n\n1️⃣ اذهب إلى أي تطبيق (يوتيوب، تيك توك، انستغرام)\n2️⃣ اختر الفيديو الذي تريده\n3️⃣ اضغط على **مشاركة** ثم **نسخ الرابط**\n4️⃣ أرسل الرابط هنا وسأقوم بتحميله لك فوراً!",
        "choose": "🎯 **اختر جودة التحميل:**",
        "video_auto": "أفضل جودة ✨",
        "audio": "صوت فقط 🎵",
        "wait": "⏳ جاري التحميل...",
        "done": "✅ تم التحميل بنجاح!",
        "error": "❌ حدث خطأ أثناء التحميل.",
        "too_large": "⚠️ الملف كبير جداً ({0}MB)",
        "language": "اللغة 🌐",
        "help_btn": "المساعدة 📖",
        "restart_btn": "إعادة التشغيل 🔄",
        "lang_done": "✅ تم تغيير اللغة بنجاح!"
    },
    "en": {
        "start": "🎬 **Welcome to Download Bot!**\n\nSend a video link and I'll download it.",
        "help": "📖 **Download Instructions:**\n\n1️⃣ Go to any app (YouTube, TikTok, Instagram)\n2️⃣ Choose a video\n3️⃣ Tap **Share** then **Copy Link**\n4️⃣ Send the link here and I'll download it!",
        "choose": "🎯 **Choose quality:**",
        "video_auto": "Best Quality ✨",
        "audio": "Audio Only 🎵",
        "wait": "⏳ Downloading...",
        "done": "✅ Download complete!",
        "error": "❌ Error during download.",
        "too_large": "⚠️ File too large ({0}MB)",
        "language": "Language 🌐",
        "help_btn": "Help 📖",
        "restart_btn": "Restart 🔄",
        "lang_done": "✅ Language changed!"
    }
}

# ======================== بيانات المستخدمين ========================
users_lang = {}

def get_text(uid, key, *args):
    lang = users_lang.get(uid, "ar")
    lang_data = LANGS.get(lang, LANGS["en"])
    text = lang_data.get(key, "")
    return text.format(*args) if args else text

def main_keyboard(uid):
    keyboard = [[
        KeyboardButton(get_text(uid, "language")),
        KeyboardButton(get_text(uid, "help_btn")),
        KeyboardButton(get_text(uid, "restart_btn"))
    ]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ======================== معالجات أوامر القائمة ========================
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"),
         InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ]
    await update.message.reply_text(
        "🌐 اختر لغتك:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        get_text(uid, "help"),
        reply_markup=main_keyboard(uid)
    )

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    context.user_data.clear()
    await update.message.reply_text(
        "🔄 تم إعادة التشغيل!",
        reply_markup=main_keyboard(uid)
    )
    await update.message.reply_text(
        get_text(uid, "start"),
        reply_markup=main_keyboard(uid)
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in users_lang:
        users_lang[uid] = "ar"
    await update.message.reply_text(
        get_text(uid, "start"),
        reply_markup=main_keyboard(uid)
    )

async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang_code = query.data.split('_')[1]
    users_lang[uid] = lang_code
    await query.edit_message_text(get_text(uid, "lang_done"))
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=get_text(uid, "start"),
        reply_markup=main_keyboard(uid)
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    url = update.message.text.strip()
    context.user_data['url'] = url
    
    keyboard = [
        [InlineKeyboardButton(get_text(uid, "video_auto"), callback_data="quality_best")],
        [InlineKeyboardButton(get_text(uid, "audio"), callback_data="quality_audio")]
    ]
    await update.message.reply_text(
        get_text(uid, "choose"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def quality_handler_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = query.from_user.id
    url = context.user_data.get('url')
    
    if not url:
        await query.edit_message_text(get_text(uid, "error"))
        return
    
    choice = query.data.split('_')[1]
    is_audio = choice == "audio"
    
    await query.message.delete()
    msg = await context.bot.send_message(query.message.chat_id, get_text(uid, "wait"))
    
    try:
        file_path = await download_media(url, is_audio)
        
        if not file_path:
            await msg.edit_text(get_text(uid, "error"))
            return

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > MAX_SIZE_MB:
            await msg.edit_text(get_text(uid, "too_large", round(size_mb, 1)))
            os.remove(file_path)
            return
        
        await msg.delete()
        with open(file_path, 'rb') as f:
            if is_audio:
                await context.bot.send_audio(query.message.chat_id, audio=f)
            else:
                await context.bot.send_video(query.message.chat_id, video=f)
        
        os.remove(file_path)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text(get_text(uid, "error"))

async def download_media(url, is_audio):
    format_string = 'bestaudio/best' if is_audio else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    output_template = os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s')
    
    ydl_opts = {
        'format': format_string,
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [],
        'merge_output_format': 'mp4',
    }

    if is_audio:
        ydl_opts['postprocessors'].append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if is_audio:
                base, _ = os.path.splitext(filename)
                final_filename = base + '.mp3'
                return final_filename if os.path.exists(final_filename) else None
            return filename
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        return None

# ======================== التشغيل ========================
def main():
    print("🚀 بدء تشغيل البوت...")
    
    app = Application.builder().token(TOKEN).build()
    
    # أوامر القائمة (الأهم!)
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("start", start_command))
    
    # الأزرار العادية
    app.add_handler(MessageHandler(filters.Regex("^(اللغة|Language)$"), language_command))
    app.add_handler(MessageHandler(filters.Regex("^(المساعدة|Help)$"), help_command))
    app.add_handler(MessageHandler(filters.Regex("^(إعادة التشغيل|Restart)$"), restart_command))
    
    # الروابط
    app.add_handler(MessageHandler(filters.TEXT & filters.Entity("url"), handle_link))
    
    # الأزرار التفاعلية
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(quality_handler_callback, pattern="^quality_"))
    
    print("✅ البوت يعمل الآن!")
    app.run_polling()

if __name__ == "__main__":
    main()
