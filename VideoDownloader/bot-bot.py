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

# ======================== تحميل ملف اللغات ========================
try:
    with open('languages.json', 'r', encoding='utf-8') as f:
        LANGS = json.load(f)
except FileNotFoundError:
    print("❌ خطأ: ملف 'languages.json' غير موجود!")
    exit(1)
except json.JSONDecodeError:
    print("❌ خطأ: ملف 'languages.json' يحتوي على خطأ في التنسيق.")
    exit(1)

# ======================== بيانات المستخدمين ========================
users_lang = {}

def get_text(uid, key, *args):
    lang = users_lang.get(uid, "ar")
    lang_data = LANGS.get(lang, LANGS["en"])
    text = lang_data.get(key, f"<{key}>")
    return text.format(*args) if args else text

def main_keyboard(uid):
    # تمت إعادة إضافة زر إعادة التشغيل
    keyboard = [[
        KeyboardButton(get_text(uid, "language")),
        KeyboardButton(get_text(uid, "help_btn")),
        KeyboardButton(get_text(uid, "restart_btn"))
    ]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ======================== معالجات الأوامر والرسائل ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in users_lang:
        users_lang[uid] = "ar"
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
    keyboard = []
    lang_buttons = [
        InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"),
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
        InlineKeyboardButton("🇹🇷 Türkçe", callback_data="lang_tr"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
    ]
    for i in range(0, len(lang_buttons), 2):
        keyboard.append(lang_buttons[i:i+2])

    await update.message.reply_text(
        "Choose your language / اختر لغتك:",
        reply_markup=InlineKeyboardMarkup(keyboard)
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
        
        await msg.edit_text(get_text(uid, "done"))
        caption_text = f"Downloaded via @{context.bot.username}"
        with open(file_path, 'rb') as f:
            if is_audio:
                await context.bot.send_audio(query.message.chat_id, audio=f, caption=caption_text)
            else:
                await context.bot.send_video(query.message.chat_id, video=f, caption=caption_text)
        
        os.remove(file_path)
        await msg.delete()
        
    except Exception as e:
        logger.error(f"Error during download/upload: {e}")
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
    
    app.add_handler(CommandHandler("start", start_command))
    
    # بناء معالجات الأزرار النصية ديناميكياً
    all_lang_buttons = [LANGS[lang]['language'] for lang in LANGS]
    all_help_buttons = [LANGS[lang]['help_btn'] for lang in LANGS]
    all_restart_buttons = [LANGS[lang]['restart_btn'] for lang in LANGS] # تمت إضافة هذا السطر
    
    app.add_handler(MessageHandler(filters.Text(all_lang_buttons), show_languages_command))
    app.add_handler(MessageHandler(filters.Text(all_help_buttons), help_command))
    app.add_handler(MessageHandler(filters.Text(all_restart_buttons), start_command)) # تمت إضافة هذا السطر

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & (filters.Entity("url") | filters.Entity("text_link")), handle_link))
    
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(quality_handler_callback, pattern="^quality_"))
    
    print("✅ البوت يعمل الآن!")
    app.run_polling()

if __name__ == "__main__":
    main()
