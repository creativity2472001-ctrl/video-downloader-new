import os
import asyncio
import yt_dlp
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- الإعدادات ---
TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# خيارات السرعة القصوى وتخطي حماية يوتيوب
YDL_OPTIONS = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'merge_output_format': 'mp4',
    'outtmpl': f'{DOWNLOAD_DIR}/%(id)s.%(ext)s',
    'concurrent_fragment_downloads': 15, # سرعة تحميل مضاعفة
    'nocheckcertificate': True,
    'geo_bypass': True,
    'quiet': True,
    'no_warnings': True,
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    },
    'postprocessor_args': ['-vcodec', 'libx264', '-pix_fmt', 'yuv420p', '-acodec', 'aac'],
}

# نصوص البوت
TEXTS = {
    "AR": {
        "start": "🚀 أرسل رابط الفيديو للتحميل السريع.",
        "choose": "اختر نوع الملف:",
        "loading": "⚡ جاري التحميل بأقصى سرعة...",
        "help": "📖 **دليل المساعدة:**\n- أرسل الرابط مباشرة للبوت.\n- اختر فيديو أو صوت.\n- سيتم الحفظ في الاستوديو.",
        "lang_msg": "🌐 اختر اللغة المطلوبة:",
        "error": "❌ فشل التحميل. تأكد من تحديث yt-dlp.",
        "restart": "🔄 تم إعادة تشغيل البوت بنجاح."
    },
    "EN": {
        "start": "🚀 Send a video link for fast download.",
        "choose": "Choose file type:",
        "loading": "⚡ Fast downloading in progress...",
        "help": "📖 **Help Guide:**\n- Send the link directly.\n- Choose Video or Audio.\n- Files will be saved to gallery.",
        "lang_msg": "🌐 Choose your language:",
        "error": "❌ Download failed. Update yt-dlp.",
        "restart": "🔄 Bot restarted successfully."
    }
}

# ================= الدوال الأساسية =================

async def set_commands(app):
    # تعيين الأزرار التي تظهر بجانب مربع الكتابة
    await app.bot.set_my_commands([
        BotCommand("start", "🚀 البدء / Start"),
        BotCommand("language", "🌐 اللغة / Language"),
        BotCommand("help", "📖 المساعدة / Help"),
        BotCommand("restart", "🔄 إعادة تشغيل / Restart")
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "AR")
    await update.effective_message.reply_text(TEXTS[lang]["start"])

async def show_language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # هذه الدالة تظهر خيارات اللغة (عربي / انجليزي)
    keyboard = [[
        InlineKeyboardButton("🇸🇦 العربية", callback_data="btn_lang_ar"),
        InlineKeyboardButton("🇺🇸 English", callback_data="btn_lang_en")
    ]]
    await update.effective_message.reply_text("اختر اللغة / Choose Language:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "AR")
    await update.effective_message.reply_text(TEXTS[lang]["help"], parse_mode="Markdown")

# ================= معالج الأزرار (الحل الجذري) =================

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    lang = context.user_data.get("lang", "AR")

    # 1. معالجة أزرار اللغة
    if data == "btn_lang_ar":
        context.user_data["lang"] = "AR"
        await query.message.edit_text("✅ تم ضبط اللغة على العربية")
    
    elif data == "btn_lang_en":
        context.user_data["lang"] = "EN"
        await query.message.edit_text("✅ Language set to English")

    # 2. معالجة أزرار التحميل
    elif data.startswith("dl_"):
        mode = data.split("_")[1]
        url = context.user_data.get("current_url")
        if url:
            await query.message.delete()
            await start_download(update.effective_chat, url, mode, lang)

# ================= التحميل والإرسال =================

async def start_download(chat, url, mode, lang):
    status_msg = await chat.send_message(TEXTS[lang]["loading"])
    loop = asyncio.get_event_loop()
    
    try:
        # إعدادات مخصصة للصوت إذا تم اختياره
        opts = YDL_OPTIONS.copy()
        if mode == "audio":
            opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]

        def run():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info), info.get('title', 'file')

        file_path, title = await loop.run_in_executor(None, run)
        if mode == "audio": file_path = file_path.rsplit(".", 1)[0] + ".mp3"

        with open(file_path, "rb") as f:
            if mode == "audio": await chat.send_audio(f, title=title)
            else: await chat.send_video(f, caption=f"🎬 {title}", supports_streaming=True)
        
        os.remove(file_path)
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(TEXTS[lang]["error"])

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"): return
    context.user_data["current_url"] = url
    lang = context.user_data.get("lang", "AR")
    
    keyboard = [[
        InlineKeyboardButton("🎬 Video HD", callback_data="dl_video"),
        InlineKeyboardButton("🎵 Audio MP3", callback_data="dl_audio")
    ]]
    await update.message.reply_text(TEXTS[lang]["choose"], reply_markup=InlineKeyboardMarkup(keyboard))

# ================= التشغيل الرئيسي =================

def main():
    app = Application.builder().token(TOKEN).post_init(set_commands).build()
    
    # ربط الأوامر بالدوال
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", show_language_menu))
    app.add_handler(CommandHandler("help", show_help))
    app.add_handler(CommandHandler("restart", start))
    
    # ربط الرسائل والأزرار
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    
    print("🚀 البوت جاهز والسرعة فائقة والأزرار تعمل!")
    app.run_polling()

if __name__ == "__main__":
    main()
