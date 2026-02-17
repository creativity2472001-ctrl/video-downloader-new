import os
import asyncio
import yt_dlp
import logging
import json
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

# --- إعدادات البوت ---
TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"
USE_WEBHOOK = False  # اجعلها True عند التشغيل على سيرفر يدعم Webhook
WEBHOOK_URL = "https://your-domain.com/path"
PORT = int(os.environ.get('PORT', 8443))
# --------------------

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# تحميل اللغات من ملف JSON
def load_languages():
    try:
        with open('languages.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading languages.json: {e}")
        return {}

LANGS = load_languages()
user_prefs = {}  # {user_id: {'lang': 'ar', 'last_request': 0, 'is_processing': False}}

def get_text(user_id, key, *args):
    prefs = user_prefs.get(user_id, {'lang': 'ar'})
    lang = prefs.get('lang', 'ar')
    text = LANGS.get(lang, LANGS['en']).get(key, "")
    if args:
        return text.format(*args)
    return text

# دالة تحديث شريط التقدم
def progress_hook(d, context, chat_id, message_id, user_id):
    if d['status'] == 'downloading':
        p = d.get('_percent_str', '0%').replace('%', '')
        try:
            p_float = float(p)
            # تحديث الرسالة كل 20% لتجنب حظر تيليجرام (Flood)
            last_p = context.user_data.get('last_progress', 0)
            if p_float - last_p >= 20 or p_float >= 99:
                context.user_data['last_progress'] = p_float
                loop = asyncio.get_event_loop()
                loop.create_task(context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=get_text(user_id, "progress", p.strip())
                ))
        except: pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_prefs: user_prefs[user_id] = {'lang': 'ar', 'last_request': 0, 'is_processing': False}
    keyboard = [[KeyboardButton("اللغة 🌐"), KeyboardButton("المساعدة 📖")]]
    await update.message.reply_text(get_text(user_id, "start"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, user_id = update.message.text, update.effective_user.id
    if user_id not in user_prefs: user_prefs[user_id] = {'lang': 'ar', 'last_request': 0, 'is_processing': False}

    if text == "المساعدة 📖":
        await update.message.reply_text(get_text(user_id, "help"))
    elif text == "اللغة 🌐":
        keyboard = [
            [InlineKeyboardButton("🇸🇦 عربي", callback_data="set_ar"), InlineKeyboardButton("🇺🇸 English", callback_data="set_en")],
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="set_ru"), InlineKeyboardButton("🇩🇪 Deutsch", callback_data="set_de")]
        ]
        await update.message.reply_text("Choose language:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif "http" in text:
        # نظام منع السبام
        current_time = time.time()
        if user_prefs[user_id]['is_processing'] or (current_time - user_prefs[user_id]['last_request'] < 5):
            await update.message.reply_text(get_text(user_id, "spam"))
            return

        context.user_data["url"] = text
        keyboard = [[InlineKeyboardButton(get_text(user_id, "video"), callback_data="dl_video"),
                     InlineKeyboardButton(get_text(user_id, "audio"), callback_data="dl_audio")]]
        await update.message.reply_text(get_text(user_id, "choose"), reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id, data = query.from_user.id, query.data

    if data.startswith("set_"):
        user_prefs[user_id]['lang'] = data.split("_")[1]
        await query.edit_message_text(get_text(user_id, "lang_done"))
    
    elif data.startswith("dl_"):
        mode = data.split("_")[1]
        url = context.user_data.get("url")
        if not url: return
        
        user_prefs[user_id]['is_processing'] = True
        user_prefs[user_id]['last_request'] = time.time()
        context.user_data['last_progress'] = 0
        
        await query.message.delete()
        msg = await context.bot.send_message(chat_id=query.message.chat_id, text=get_text(user_id, "wait"))
        
        try:
            unique_name = f"{DOWNLOAD_DIR}/{user_id}_{int(time.time())}"
            ydl_opts = {
                'outtmpl': f"{unique_name}.%(ext)s",
                'quiet': True, 'noplaylist': True,
                'progress_hooks': [lambda d: progress_hook(d, context, query.message.chat_id, msg.message_id, user_id)],
            }
            
            if mode == "video":
                ydl_opts.update({
                    'format': 'bestvideo[ext=mp4][filesize<50M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<50M]/best',
                    'merge_output_format': 'mp4',
                    'postprocessor_args': {'ffmpeg': ['-c:v', 'libx264', '-preset', 'veryfast', '-c:a', 'aac']}
                })
            else:
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]
                })

            def download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return ydl.prepare_filename(info), info.get('title', 'video'), info.get('width'), info.get('height'), info.get('duration')

            loop = asyncio.get_event_loop()
            filename, title, w, h, d = await loop.run_in_executor(None, download)
            
            final_file = filename
            if mode == "audio" and not filename.endswith(".mp3"): final_file = os.path.splitext(filename)[0] + ".mp3"
            
            if os.path.getsize(final_file) > 50 * 1024 * 1024:
                await msg.edit_text(get_text(user_id, "too_large"))
            else:
                with open(final_file, "rb") as f:
                    if mode == "audio": await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, caption=f"🎵 {title}")
                    else: await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=f"🎬 {title}", width=w, height=h, duration=d, supports_streaming=True)
                await msg.delete()
            
            if os.path.exists(final_file): os.remove(final_file)
            
        except Exception as e:
            logger.error(f"Error: {e}")
            await msg.edit_text(get_text(user_id, "error"))
        finally:
            user_prefs[user_id]['is_processing'] = False

def main():
    if TOKEN == "ضع_التوكن_هنا": return print("❌ يرجى وضع التوكن!")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    
    if USE_WEBHOOK:
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
    else:
        print("🚀 البوت يعمل بنظام Polling...")
        app.run_polling()

if __name__ == "__main__":
    main()
