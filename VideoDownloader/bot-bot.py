import os
import asyncio
import yt_dlp
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 🛠️ إعدادات الفيديو المحسنة (جودة عالية + سرعة + توافق)
VIDEO_OPTIONS = {
    # السطر القادم يجبر على تحميل أفضل فيديو MP4 مدمج مع الصوت لضمان عدم ظهور صورة ثابتة
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'merge_output_format': 'mp4',
    'outtmpl': f'{DOWNLOAD_DIR}/%(id)s.%(ext)s',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'nocheckcertificate': True,
    'geo_bypass': True,
    # معالجة إضافية لضمان عمل الفيديو في استوديو الآيفون والأندرويد
    'postprocessor_args': [
        '-vcodec', 'libx264',  # الترميز الأسرع والأفضل توافقاً
        '-pix_fmt', 'yuv420p', # ضروري لظهور الفيديو في معرض الصور
        '-acodec', 'aac'
    ],
    'concurrent_fragment_downloads': 10, # زيادة سرعة التحميل عبر تعدد الخيوط
}

AUDIO_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(id)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'noplaylist': True,
}

TEXTS = {
    "choose": {"AR": "اختر نوع التحميل:", "EN": "Choose download type:"},
    "loading": {"AR": "⏳ جاري المعالجة والتحميل بأقصى جودة...", "EN": "⏳ Processing and downloading in HD..."},
    "error": {"AR": "❌ عذراً، تعذر تحميل هذا الرابط.", "EN": "❌ Sorry, failed to download this link."},
}

# ================= Functions =================

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "🚀 البدء"),
        BotCommand("language", "🌐 اللغة / Language"),
        BotCommand("help", "📖 المساعدة"),
        BotCommand("restart", "🔄 إعادة التشغيل")
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lang"] = context.user_data.get("lang", "AR")
    await update.message.reply_text("🚀 أرسل الرابط لتحميل الفيديو أو الصوت بجودة عالية")

async def download_and_send(chat, url, mode, lang):
    loading_msg = await chat.send_message(TEXTS["loading"][lang])
    loop = asyncio.get_event_loop()

    try:
        options = VIDEO_OPTIONS.copy() if mode == "video" else AUDIO_OPTIONS.copy()

        def download():
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info), info.get("title", "Video")

        filename, title = await loop.run_in_executor(None, download)

        # تعديل الامتداد في حالة الصوت
        if mode == "audio":
            filename = filename.rsplit(".", 1)[0] + ".mp3"

        if not os.path.exists(filename):
             raise Exception("File not found")

        with open(filename, "rb") as f:
            if mode == "audio":
                await chat.send_audio(f, caption=f"🎵 {title}")
            else:
                # تدعم ميزة البث أثناء التحميل لجعل الفيديو يبدأ فوراً
                await chat.send_video(f, caption=f"🎬 {title}", supports_streaming=True)

        await loading_msg.delete()
        os.remove(filename)

    except Exception as e:
        print("Error:", e)
        await loading_msg.edit_text(TEXTS["error"][lang])
        if 'filename' in locals() and os.path.exists(filename):
            os.remove(filename)

# ================= Handlers =================

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"): return
    
    context.user_data["url"] = url
    lang = context.user_data.get("lang", "AR")

    keyboard = [[
        InlineKeyboardButton("🎬 فيديو HD", callback_data="video"),
        InlineKeyboardButton("🎵 صوت MP3", callback_data="audio")
    ]]
    await update.message.reply_text(TEXTS["choose"][lang], reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    lang = context.user_data.get("lang", "AR")
    url = context.user_data.get("url")

    if query.data in ["video", "audio"]:
        await query.message.delete()
        await download_and_send(update.effective_chat, url, query.data, lang)
    
    elif "lang_" in query.data:
        context.user_data["lang"] = "AR" if "ar" in query.data else "EN"
        msg = "✅ تم اختيار اللغة العربية" if "ar" in query.data else "✅ English Selected"
        await query.message.edit_text(msg)

# ================= Main =================

def main():
    app = Application.builder().token(TOKEN).post_init(set_commands).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", lambda u, c: update.message.reply_text("اختر:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("العربية", callback_data="lang_ar"), InlineKeyboardButton("English", callback_data="lang_en")]]))))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🚀 البوت يعمل الآن بجودة عالية...")
    app.run_polling()

if __name__ == "__main__":
    main()
