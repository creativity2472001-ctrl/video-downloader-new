import os
import json
import logging
import asyncio
import shutil
import re
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import yt_dlp

# إعداد السجلات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# الثوابت
MAX_SIZE_MB = 80
MAX_HEIGHT = 720
DOWNLOAD_DIR = "downloads"

# تحميل ملف اللغات
try:
    with open('languages.json', 'r', encoding='utf-8') as f:
        LANGUAGES = json.load(f)
except Exception as e:
    logger.error(f"Failed to load languages.json: {e}")
    LANGUAGES = {"ar": {"welcome": "مرحباً!"}} # Fallback

# تخزين لغات المستخدمين
user_langs = {}
# منع السبام والعمليات المتزامنة
processing_users = set()

def get_text(user_id, key, **kwargs):
    lang = user_langs.get(user_id, 'ar')
    lang_data = LANGUAGES.get(lang, LANGUAGES['ar'])
    text = lang_data.get(key, LANGUAGES['ar'].get(key, key))
    return text.format(**kwargs)

def get_main_keyboard(user_id):
    lang = user_langs.get(user_id, 'ar')
    keyboard = [
        [LANGUAGES[lang]['language_btn'], LANGUAGES[lang]['help_btn']]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_langs:
        user_langs[user_id] = 'ar'
    await update.message.reply_text(
        get_text(user_id, 'welcome'),
        reply_markup=get_main_keyboard(user_id)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(get_text(user_id, 'help'))

async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🇸🇦 العربية", callback_data='lang_ar'), InlineKeyboardButton("🇺🇸 English", callback_data='lang_en')],
        [InlineKeyboardButton("🇹🇷 Türkçe", callback_data='lang_tr'), InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru')],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data='lang_de'), InlineKeyboardButton("🇫🇷 Français", callback_data='lang_fr')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(get_text(user_id, 'choose_lang'), reply_markup=reply_markup)

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang_code = query.data.split('_')[1]
    user_langs[user_id] = lang_code
    await query.answer()
    
    # حذف الرسالة الحالية وإرسال رسالة ترحيب جديدة بالأزرار المحدثة
    await query.message.delete()
    await context.bot.send_message(
        chat_id=user_id,
        text=get_text(user_id, 'lang_updated'),
        reply_markup=get_main_keyboard(user_id)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if not text: return

    # التحقق من الأزرار حسب لغة المستخدم (أو أي لغة مدعومة لضمان الاستجابة)
    is_lang_btn = any(text == LANGUAGES[l]['language_btn'] for l in LANGUAGES)
    is_help_btn = any(text == LANGUAGES[l]['help_btn'] for l in LANGUAGES)

    if is_lang_btn:
        await change_language(update, context)
    elif is_help_btn:
        await help_command(update, context)
    elif re.match(r'https?://', text):
        await process_video_link(update, context)

async def process_video_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    url = update.message.text

    if user_id in processing_users:
        return # منع السبام والعمليات المتزامنة

    processing_users.add(user_id)
    status_msg = await update.message.reply_text(get_text(user_id, 'processing'))

    try:
        # استخراج المعلومات أولاً للتحقق من الصلاحية
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # استخراج المعلومات بدون تحميل
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            
        # التحقق من أن الرابط فيديو (أو قائمة فيديوهات سيتم أخذ الأول منها)
        if not info:
            raise Exception("No info found")

        # عرض خيارات الجودة
        keyboard = [
            [InlineKeyboardButton(get_text(user_id, 'quality_480p'), callback_data=f"dl_480_{user_id}")],
            [InlineKeyboardButton(get_text(user_id, 'quality_720p'), callback_data=f"dl_720_{user_id}")],
            [InlineKeyboardButton(get_text(user_id, 'quality_best'), callback_data=f"dl_best_{user_id}")],
            [InlineKeyboardButton(get_text(user_id, 'quality_audio'), callback_data=f"dl_audio_{user_id}")]
        ]
        # حفظ الرابط في سياق المستخدم لاستخدامه لاحقاً
        context.user_data['current_url'] = url
        reply_markup = InlineKeyboardMarkup(keyboard)
        await status_msg.edit_text(get_text(user_id, 'choose_quality'), reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error extracting info: {e}")
        await status_msg.edit_text(get_text(user_id, 'error_invalid_url'))
        if user_id in processing_users:
            processing_users.remove(user_id)

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split('_')
    
    # التحقق من أن المستخدم الذي ضغط هو نفسه صاحب الطلب
    if int(data[2]) != user_id:
        await query.answer("هذا الزر ليس لك!", show_alert=True)
        return

    quality = data[1]
    url = context.user_data.get('current_url')

    if not url:
        await query.answer(get_text(user_id, 'error_generic'))
        if user_id in processing_users: processing_users.remove(user_id)
        return

    await query.answer()
    await query.edit_message_text(get_text(user_id, 'downloading'))

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_id = f"{user_id}_{quality}"
    download_path_tmpl = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    # إعدادات yt-dlp
    format_opt = f"bestvideo[height<={MAX_HEIGHT}]+bestaudio/best[height<={MAX_HEIGHT}]"
    if quality == "480":
        format_opt = "bestvideo[height<=480]+bestaudio/best[height<=480]"
    elif quality == "audio":
        format_opt = "bestaudio/best"

    ydl_opts = {
        'format': format_opt,
        'outtmpl': download_path_tmpl,
        'max_filesize': MAX_SIZE_MB * 1024 * 1024,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4' if quality != 'audio' else None,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }] if quality == 'audio' else []
    }

    actual_file_path = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            # الحصول على المسار الفعلي للملف المحمل
            actual_file_path = ydl.prepare_filename(info)
            if quality == 'audio':
                actual_file_path = os.path.splitext(actual_file_path)[0] + ".mp3"
            
            # التحقق من وجود الملف
            if not os.path.exists(actual_file_path):
                # قد يكون الاسم اختلف بسبب الإضافات
                base_name = os.path.join(DOWNLOAD_DIR, file_id)
                for f in os.listdir(DOWNLOAD_DIR):
                    if f.startswith(file_id):
                        actual_file_path = os.path.join(DOWNLOAD_DIR, f)
                        break

            # التحقق النهائي من الحجم
            file_size = os.path.getsize(actual_file_path) / (1024 * 1024)
            if file_size > MAX_SIZE_MB:
                await query.edit_message_text(get_text(user_id, 'error_size', size=round(file_size, 1)))
                return

            await query.edit_message_text(get_text(user_id, 'sending'))
            
            with open(actual_file_path, 'rb') as video_file:
                if quality == "audio":
                    await context.bot.send_audio(chat_id=user_id, audio=video_file, caption=info.get('title', ''))
                else:
                    await context.bot.send_video(chat_id=user_id, video=video_file, caption=info.get('title', ''), supports_streaming=True)
            
            # حذف رسالة الحالة بعد الإرسال بنجاح
            await query.message.delete()

    except yt_dlp.utils.DownloadError as e:
        err_str = str(e)
        if "exceeds maximum allowed filesize" in err_str:
             await query.edit_message_text(get_text(user_id, 'error_size', size=">80"))
        else:
            await query.edit_message_text(get_text(user_id, 'error_generic'))
        logger.error(f"Download error: {e}")
    except Exception as e:
        await query.edit_message_text(get_text(user_id, 'error_generic'))
        logger.error(f"Unexpected error: {e}")
    finally:
        # تنظيف الملفات
        if actual_file_path and os.path.exists(actual_file_path):
            os.remove(actual_file_path)
        # تنظيف أي ملفات متبقية بنفس الـ ID (مثل ملفات الدمج المؤقتة)
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(file_id):
                try: os.remove(os.path.join(DOWNLOAD_DIR, f))
                except: pass
        
        if user_id in processing_users:
            processing_users.remove(user_id)

def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN environment variable not set.")
        return

    # التأكد من وجود مجلد التحميلات وتنظيفه عند البدء
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR)

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(set_language, pattern='^lang_'))
    application.add_handler(CallbackQueryHandler(download_callback, pattern='^dl_'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
