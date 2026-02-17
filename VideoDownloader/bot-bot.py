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
    # لغة احتياطية في حال فشل الملف
    LANGUAGES = {"ar": {"welcome": "مرحباً!", "language_btn": "🌐 اللغة", "help_btn": "📖 المساعدة"}}

# تخزين لغات المستخدمين
user_langs = {}
# منع العمليات المتزامنة
processing_users = set()

def get_text(user_id, key, **kwargs):
    lang = user_langs.get(user_id, 'ar')
    lang_data = LANGUAGES.get(lang, LANGUAGES['ar'])
    text = lang_data.get(key, LANGUAGES['ar'].get(key, key))
    return text.format(**kwargs)

def get_main_keyboard(user_id):
    lang = user_langs.get(user_id, 'ar')
    # زرين فقط كما طلبت في المتطلبات
    keyboard = [
        [LANGUAGES[lang]['language_btn'], LANGUAGES[lang]['help_btn']]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_langs:
        user_langs[user_id] = 'ar'
    
    # تنظيف حالة المستخدم عند إعادة التشغيل
    if user_id in processing_users:
        processing_users.remove(user_id)
        
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
    
    # تحديث الرسالة وتغيير الكيبورد فوراً
    await query.edit_message_text(get_text(user_id, 'lang_updated'))
    await context.bot.send_message(
        chat_id=user_id,
        text=get_text(user_id, 'welcome'),
        reply_markup=get_main_keyboard(user_id)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if not text: return

    # التحقق من الأزرار (بناءً على جميع اللغات لضمان الاستجابة)
    is_lang_btn = any(text == LANGUAGES[l].get('language_btn') for l in LANGUAGES)
    is_help_btn = any(text == LANGUAGES[l].get('help_btn') for l in LANGUAGES)

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
        return 

    processing_users.add(user_id)
    status_msg = await update.message.reply_text(get_text(user_id, 'processing'))

    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            
        if not info: raise Exception("No info")

        context.user_data['current_url'] = url
        keyboard = [
            [InlineKeyboardButton(get_text(user_id, 'quality_480p'), callback_data=f"dl_480_{user_id}")],
            [InlineKeyboardButton(get_text(user_id, 'quality_720p'), callback_data=f"dl_720_{user_id}")],
            [InlineKeyboardButton(get_text(user_id, 'quality_best'), callback_data=f"dl_best_{user_id}")],
            [InlineKeyboardButton(get_text(user_id, 'quality_audio'), callback_data=f"dl_audio_{user_id}")]
        ]
        await status_msg.edit_text(get_text(user_id, 'choose_quality'), reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(get_text(user_id, 'error_invalid_url'))
        if user_id in processing_users: processing_users.remove(user_id)

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split('_')
    
    if int(data[2]) != user_id:
        await query.answer("Error!", show_alert=True)
        return

    quality = data[1]
    url = context.user_data.get('current_url')

    await query.answer()
    await query.edit_message_text(get_text(user_id, 'downloading'))

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_id = f"{user_id}_{quality}"
    download_path_tmpl = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    # إعدادات yt-dlp الذكية
    format_opt = f"bestvideo[height<={MAX_HEIGHT}]+bestaudio/best[height<={MAX_HEIGHT}]"
    if quality == "480": format_opt = "bestvideo[height<=480]+bestaudio/best[height<=480]"
    elif quality == "audio": format_opt = "bestaudio/best"

    ydl_opts = {
        'format': format_opt,
        'outtmpl': download_path_tmpl,
        'max_filesize': MAX_SIZE_MB * 1024 * 1024,
        'quiet': True,
        'merge_output_format': 'mp4' if quality != 'audio' else None,
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}] if quality == 'audio' else []
    }

    actual_file_path = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            actual_file_path = ydl.prepare_filename(info)
            if quality == 'audio': actual_file_path = os.path.splitext(actual_file_path)[0] + ".mp3"
            
            # التحقق من وجود الملف والحجم
            if not os.path.exists(actual_file_path):
                for f in os.listdir(DOWNLOAD_DIR):
                    if f.startswith(file_id):
                        actual_file_path = os.path.join(DOWNLOAD_DIR, f)
                        break

            file_size = os.path.getsize(actual_file_path) / (1024 * 1024)
            if file_size > MAX_SIZE_MB:
                await query.edit_message_text(get_text(user_id, 'error_size', size=round(file_size, 1)))
                return

            await query.edit_message_text(get_text(user_id, 'sending'))
            with open(actual_file_path, 'rb') as f:
                if quality == "audio": await context.bot.send_audio(chat_id=user_id, audio=f, caption=info.get('title', ''))
                else: await context.bot.send_video(chat_id=user_id, video=f, caption=info.get('title', ''), supports_streaming=True)
            
            await query.message.delete()

    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text(get_text(user_id, 'error_generic'))
    finally:
        if actual_file_path and os.path.exists(actual_file_path): os.remove(actual_file_path)
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(file_id):
                try: os.remove(os.path.join(DOWNLOAD_DIR, f))
                except: pass
        if user_id in processing_users: processing_users.remove(user_id)

def main():
    # تأكد من وضع التوكن هنا أو استخدامه كمتغير بيئة
    token = os.environ.get("TELEGRAM_TOKEN") or "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"
    
    if os.path.exists(DOWNLOAD_DIR): shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR)

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(set_language, pattern='^lang_'))
    application.add_handler(CallbackQueryHandler(download_callback, pattern='^dl_'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
