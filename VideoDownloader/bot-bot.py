import os
import asyncio
import yt_dlp
import logging
import shutil
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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ======================== ملف اللغات (مضمن مباشرة) ========================
LANGS = {
    "ar": {
        "start": "🎬 مرحباً بك في بوت التحميل!\n\nأرسل رابط فيديو وسأقوم بتحميله.",
        "help": "📖 **تعليمات التحميل:**\n\n1. اذهب إلى تطبيق انستغرام/تيك توك/يوتيوب أو غيره\n2. اختر الفيديو الذي تريده\n3. اضغط على زر المشاركة ↪️ أو النقاط الثلاث في الزاوية\n4. اضغط على \"نسخ الرابط\"\n5. أرسل الرابط إلى البوت وستحصل على الفيديو خلال ثوانٍ.",
        "choose": "🎯 اختر الجودة:",
        "video_480": "480p 🎬",
        "video_720": "720p 🎬",
        "video_auto": "أفضل جودة ✨",
        "audio": "صوت فقط 🎵",
        "wait": "⏳ جاري التحميل...",
        "error": "❌ حدث خطأ، يرجى المحاولة مرة أخرى.",
        "too_large": "⚠️ الملف كبير جداً ({0}MB)، لا يمكن إرساله.",
        "language": "🌐 اللغة",
        "help_btn": "📖 المساعدة",
        "restart_btn": "🔄 إعادة التشغيل",
        "lang_choose": "اختر لغتك:",
        "lang_done": "✅ تم تغيير اللغة بنجاح."
    },
    "en": {
        "start": "🎬 Welcome to the downloader bot!\n\nSend a video link and I'll download it.",
        "help": "📖 **Download instructions:**\n\n1. Go to the Instagram/TikTok/YouTube app or other\n2. Choose a video you like\n3. Tap the ↪️ button or the three dots in the top right corner\n4. Tap the \"Copy\" button\n5. Send the link to the bot and in a few seconds you'll get the video.",
        "choose": "🎯 Choose quality:",
        "video_480": "480p 🎬",
        "video_720": "720p 🎬",
        "video_auto": "Best Quality ✨",
        "audio": "Audio Only 🎵",
        "wait": "⏳ Downloading...",
        "error": "❌ An error occurred, please try again.",
        "too_large": "⚠️ File is too large ({0}MB), cannot send it.",
        "language": "🌐 Language",
        "help_btn": "📖 Help",
        "restart_btn": "🔄 Restart",
        "lang_choose": "Choose your language:",
        "lang_done": "✅ Language changed successfully."
    }
}

# ======================== بيانات المستخدمين ========================
users = {}

def get_text(uid, key, *args):
    # إذا لم يتم العثور على المستخدم، استخدم اللغة العربية كافتراضية
    lang = users.get(uid, "ar")
    # إذا لم يتم العثور على اللغة، استخدم الإنجليزية كاحتياط
    text = LANGS.get(lang, LANGS["en"]).get(key, "")
    return text.format(*args) if args else text

def main_keyboard(uid):
    keyboard = [
        [
            KeyboardButton(get_text(uid, "language")),
            KeyboardButton(get_text(uid, "help_btn")),
            KeyboardButton(get_text(uid, "restart_btn"))
        ]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# ======================== معالجات الأوامر والرسائل ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in users:
        users[uid] = "ar"  # تعيين اللغة الافتراضية للمستخدم الجديد
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

async def show_languages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"),
         InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ]
    await update.message.reply_text(
        get_text(uid, "lang_choose"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang_code = query.data.split('_')[1]
    users[uid] = lang_code
    
    await query.edit_message_text(get_text(uid, "lang_done"))
    
    # إرسال رسالة جديدة بلوحة المفاتيح المحدثة
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
        [
            InlineKeyboardButton(get_text(uid, "video_480"), callback_data="quality_480"),
            InlineKeyboardButton(get_text(uid, "video_720"), callback_data="quality_720"),
        ],
        [
            InlineKeyboardButton(get_text(uid, "video_auto"), callback_data="quality_best"),
            InlineKeyboardButton(get_text(uid, "audio"), callback_data="quality_audio")
        ]
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
    
    quality_choice = query.data.split('_')[1]
    is_audio = quality_choice == "audio"
    
    await query.message.delete()
    msg = await context.bot.send_message(query.message.chat_id, get_text(uid, "wait"))
    
    try:
        file_path = await download_video(url, is_audio, quality_choice)
        
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
                await context.bot.send_audio(query.message.chat_id, audio=f, caption="Downloaded by @YourBotUsername")
            else:
                await context.bot.send_video(query.message.chat_id, video=f, caption="Downloaded by @YourBotUsername")
        
        os.remove(file_path)
        
    except Exception as e:
        logger.error(f"Error during download/upload: {e}")
        try:
            await msg.edit_text(get_text(uid, "error"))
        except Exception as edit_error:
            logger.error(f"Could not edit error message: {edit_error}")

async def download_video(url, is_audio, quality):
    format_string = 'bestaudio/best' if is_audio else f'best[height<={quality}]/best' if quality != 'best' else 'best'
    
    output_template = os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s')
    
    ydl_opts = {
        'format': format_string,
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [],
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
                # yt-dlp قد لا يغير الامتداد دائماً، لذا نقوم بذلك يدوياً
                base, _ = os.path.splitext(filename)
                return base + '.mp3'
            return filename
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        return None

# ======================== التشغيل ========================
def main():
    print("🚀 بدء تشغيل البوت...")
    
    app = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start_command))
    
    # معالجات الأزرار النصية
    app.add_handler(MessageHandler(filters.Regex(f"^({LANGS['ar']['language']}|{LANGS['en']['language']})$"), show_languages_command))
    app.add_handler(MessageHandler(filters.Regex(f"^({LANGS['ar']['help_btn']}|{LANGS['en']['help_btn']})<LaTex>$"), help_command))
    app.add_handler(MessageHandler(filters.Regex(f"^({LANGS['ar']['restart_btn']}|{LANGS['en']['restart_btn']})$</LaTex>"), start_command))

    # معالج الروابط
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & (filters.Entity("url") | filters.Entity("text_link")), handle_link))
    
    # معالجات الأزرار المضمنة (CallbackQuery)
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(quality_handler_callback, pattern="^quality_"))
    
    print("✅ البوت يعمل الآن!")
    app.run_polling()

if __name__ == "__main__":
    main()
