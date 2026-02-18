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
    CallbackQueryHandler,
)

# ===== إعدادات البوت =====
TOKEN = "ضع_التوكن_هنا"
MAX_SIZE_MB = 80
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
# ========================

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== اللغات =====
def load_languages():
    try:
        with open('languages.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading languages.json: {e}")
        return {}

LANGS = load_languages()
user_prefs = {}  # {user_id: {'lang': 'ar', 'queue': asyncio.Queue()}}

def get_text(user_id, key, *args):
    lang = user_prefs.get(user_id, {}).get('lang', 'ar')
    text = LANGS.get(lang, LANGS.get('en', {})).get(key, "")
    return text.format(*args) if args else text

# ===== شريط التقدم =====
def progress_hook(d, context, chat_id, message_id, user_id):
    if d['status'] == 'downloading':
        p = d.get('_percent_str', '0%').replace('%','')
        try:
            p_float = float(p)
            last_p = context.user_data.get('last_progress', 0)
            if p_float - last_p >= 25 or p_float >= 99:
                context.user_data['last_progress'] = p_float
                loop = asyncio.get_event_loop()
                loop.create_task(context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=get_text(user_id, "progress", p.strip())
                ))
        except: pass

# ===== عامل الطابور =====
async def worker(user_id, context):
    queue = user_prefs[user_id]['queue']
    while True:
        task = await queue.get()
        try:
            await download_and_send_task(task, context)
        except Exception as e:
            logger.error(f"Worker Task Error: {e}")
        finally:
            queue.task_done()

# ===== تحميل الفيديو والصوت =====
async def download_and_send_task(task, context):
    chat_id, user_id, url, mode, quality = task['chat_id'], task['user_id'], task['url'], task['mode'], task['quality']
    msg = await context.bot.send_message(chat_id=chat_id, text=get_text(user_id, "wait"))
    actual_filename = None
    try:
        unique_name = f"{DOWNLOAD_DIR}/{user_id}_{int(time.time())}"
        ydl_opts = {
            'outtmpl': f"{unique_name}.%(ext)s",
            'quiet': True,
            'noplaylist': True,
            'progress_hooks': [lambda d: progress_hook(d, context, chat_id, msg.message_id, user_id)]
        }

        if mode == "video":
            height = 720 if quality == "720" else 480
            ydl_opts.update({
                'format': f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best',
                'merge_output_format': 'mp4',
                'postprocessor_args': {'ffmpeg': ['-c:v','libx264','-preset','veryfast','-c:a','aac']}
            })
        else:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}]
            })

        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info), info.get('title','video'), info.get('width'), info.get('height'), info.get('duration')

        loop = asyncio.get_event_loop()
        filename, title, w, h, d = await loop.run_in_executor(None, download)
        actual_filename = filename
        if mode == "audio" and not filename.endswith(".mp3"):
            actual_filename = os.path.splitext(filename)[0] + ".mp3"

        file_size_mb = os.path.getsize(actual_filename)/(1024*1024)
        if file_size_mb > MAX_SIZE_MB:
            await msg.edit_text(get_text(user_id, "too_large", round(file_size_mb,1)))
            return

        with open(actual_filename,"rb") as f:
            if mode=="audio":
                await context.bot.send_audio(chat_id=chat_id, audio=f, caption=f"🎵 {title}")
            else:
                await context.bot.send_video(chat_id=chat_id, video=f, caption=f"🎬 {title}", width=w, height=h, duration=d, supports_streaming=True)
        await msg.delete()

    except Exception as e:
        logger.error(f"Download Error: {e}")
        try:
            await msg.edit_text(get_text(user_id, "error"))
        except: pass
    finally:
        if actual_filename and os.path.exists(actual_filename):
            try: os.remove(actual_filename)
            except: pass

# ===== دوال الأوامر =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_prefs:
        user_prefs[user_id] = {'lang':'ar','queue':asyncio.Queue()}
        asyncio.create_task(worker(user_id, context))
    keyboard = [
        [KeyboardButton("/language"), KeyboardButton("/help"), KeyboardButton("/restart")]
    ]
    await update.message.reply_text(get_text(user_id,"start"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(get_text(user_id,"help"))

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [
        [
            InlineKeyboardButton("🇸🇦 العربية", callback_data="set_ar"),
            InlineKeyboardButton("🇺🇸 English", callback_data="set_en")
        ],
        [
            InlineKeyboardButton("🇷🇺 Русский", callback_data="set_ru"),
            InlineKeyboardButton("🇹🇷 Türkçe", callback_data="set_tr")
        ],
        [
            InlineKeyboardButton("🇩🇪 Deutsch", callback_data="set_de"),
            InlineKeyboardButton("🇫🇷 Français", callback_data="set_fr")
        ]
    ]
    await update.message.reply_text("Choose language:", reply_markup=InlineKeyboardMarkup(keyboard))

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_prefs:
        user_prefs[user_id]['queue'] = asyncio.Queue()
        asyncio.create_task(worker(user_id, context))
    await update.message.reply_text("🔄 Bot restarted successfully.")

# ===== التعامل مع الرسائل العادية =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    if user_id not in user_prefs:
        user_prefs[user_id] = {'lang':'ar','queue':asyncio.Queue()}
        asyncio.create_task(worker(user_id, context))

    # التحقق إذا كانت الرسالة رابط
    if "http" in text:
        # فحص الحجم قبل التحميل
        try:
            with yt_dlp.YoutubeDL({'quiet':True,'noplaylist':True}) as ydl:
                info = ydl.extract_info(text, download=False)
                size = info.get('filesize') or info.get('filesize_approx')
                if size and size > MAX_SIZE_MB*1024*1024:
                    await update.message.reply_text(get_text(user_id,"too_large", round(size/(1024*1024),1)))
                    return
        except: pass

        context.user_data["url"] = text
        keyboard = [
            [InlineKeyboardButton(get_text(user_id,"video_480"), callback_data="dl_video_480"),
             InlineKeyboardButton(get_text(user_id,"video_720"), callback_data="dl_video_720")],
            [InlineKeyboardButton(get_text(user_id,"video_auto"), callback_data="dl_video_auto")],
            [InlineKeyboardButton(get_text(user_id,"audio"), callback_data="dl_audio")]
        ]
        await update.message.reply_text(get_text(user_id,"choose"), reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(get_text(user_id,"start"))

# ===== التعامل مع أزرار Inline =====
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("set_"):
        user_prefs[user_id]['lang'] = data.split("_")[1]
        await query.edit_message_text(get_text(user_id,"lang_done"))

    elif data.startswith("dl_"):
        parts = data.split("_")
        mode = parts[1]
        quality = parts[2] if len(parts)>2 else "auto"
        url = context.user_data.get("url")
        if not url: return

        await query.message.delete()
        await user_prefs[user_id]['queue'].put({
            'chat_id': query.message.chat_id,
            'user_id': user_id,
            'url': url,
            'mode': mode,
            'quality': quality
        })

# ===== تشغيل البوت =====
def main():
    if TOKEN=="ضع_التوكن_هنا": return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    print("🚀 Bot running now...")
    app.run_polling()

if __name__=="__main__":
    main()
