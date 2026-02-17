import os
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

# --- ضع التوكن الخاص بك هنا ---
TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"
# ----------------------------

# إعداد التسجيل لرؤية الأخطاء في الـ CMD
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# قاموس اللغات
user_lang = {}

def get_text(user_id, key):
    lang = user_lang.get(user_id, "ar")
    texts = {
        "start": {"ar": "أهلاً بك! أرسل رابط فيديو للتحميل.", "en": "Welcome! Send a video link to download."},
        "choose": {"ar": "اختر نوع التحميل:", "en": "Choose download type:"},
        "video": {"ar": "فيديو 🎬", "en": "Video 🎬"},
        "audio": {"ar": "صوت 🎵", "en": "Audio 🎵"},
        "wait": {"ar": "جاري التحميل... يرجى الانتظار ⏳", "en": "Downloading... please wait ⏳"},
        "error": {"ar": "❌ حدث خطأ، تأكد من الرابط وحاول مرة أخرى.", "en": "❌ Error, check the link and try again."},
        "help": {"ar": "📖 أرسل رابط فيديو من يوتيوب أو تيك توك أو إنستغرام وسأقوم بتحميله لك.", "en": "📖 Send a video link from YouTube, TikTok, or Instagram and I will download it."},
        "lang_done": {"ar": "✅ تم اختيار اللغة العربية", "en": "✅ English language set"}
    }
    return texts[key][lang]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("اللغة 🌐"), KeyboardButton("المساعدة 📖")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(get_text(update.effective_user.id, "start"), reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "المساعدة 📖":
        await update.message.reply_text(get_text(user_id, "help"))
    elif text == "اللغة 🌐":
        keyboard = [[InlineKeyboardButton("🇸🇦 عربي", callback_data="set_ar"), 
                     InlineKeyboardButton("🇺🇸 English", callback_data="set_en")]]
        await update.message.reply_text("اختر اللغة / Choose language:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif "http" in text:
        context.user_data["url"] = text
        keyboard = [[InlineKeyboardButton(get_text(user_id, "video"), callback_data="dl_video"),
                     InlineKeyboardButton(get_text(user_id, "audio"), callback_data="dl_audio")]]
        await update.message.reply_text(get_text(user_id, "choose"), reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("set_"):
        user_lang[user_id] = data.split("_")[1]
        await query.edit_message_text(get_text(user_id, "lang_done"))
    
    elif data.startswith("dl_"):
        mode = data.split("_")[1]
        url = context.user_data.get("url")
        if not url: return
        
        await query.message.delete()
        msg = await context.bot.send_message(chat_id=query.message.chat_id, text=get_text(user_id, "wait"))
        
        try:
            unique_name = f"{DOWNLOAD_DIR}/{user_id}_{int(asyncio.get_event_loop().time())}"
            ydl_opts = {
                'outtmpl': f"{unique_name}.%(ext)s",
                'quiet': True,
                'no_warnings': True,
            }
            
            if mode == "video":
                ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                ydl_opts['merge_output_format'] = 'mp4'
            else:
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]

            def download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return ydl.prepare_filename(info), info.get('title', 'video'), info.get('width'), info.get('height'), info.get('duration')

            loop = asyncio.get_event_loop()
            filename, title, w, h, d = await loop.run_in_executor(None, download)
            
            # التأكد من اسم الملف النهائي (خاصة في الصوت)
            final_file = filename
            if mode == "audio" and not filename.endswith(".mp3"):
                final_file = os.path.splitext(filename)[0] + ".mp3"

            with open(final_file, "rb") as f:
                if mode == "audio":
                    await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, caption=f"🎵 {title}")
                else:
                    await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=f"🎬 {title}", width=w, height=h, duration=d, supports_streaming=True)
            
            await msg.delete()
            if os.path.exists(final_file): os.remove(final_file)
            
        except Exception as e:
            logger.error(f"Error: {e}")
            await msg.edit_text(get_text(user_id, "error"))

def main():
    if TOKEN == "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA":
        print("❌ يرجى وضع التوكن في الكود!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    print("🚀 البوت يعمل الآن بنجاح...")
    app.run_polling()

if __name__ == "__main__":
    main()
