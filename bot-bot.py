import os
import asyncio
import yt_dlp
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"  # ضع التوكن هنا
DOWNLOAD_DIR = "downloads"
FREE_LIMIT = 50 * 1024 * 1024   # 50MB للمجاني
PREMIUM_LIMIT = 200 * 1024 * 1024  # 200MB للمدفوع
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

PREMIUM_USERS = {123456789, 987654321}

VIDEO_OPTIONS = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'merge_output_format': 'mp4'
}

AUDIO_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'restrictfilenames': True,
    'noplaylist': True,
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in PREMIUM_USERS:
        msg = "💎 مرحباً مستخدم النسخة المدفوعة! لديك حد 200MB."
    else:
        msg = "📌 مرحباً! لديك حد 50MB في النسخة المجانية."
    await update.message.reply_text(
        f"{msg}\n\n"
        "🎬 أرسل رابط الفيديو من YouTube, TikTok, Instagram أو Facebook.\n"
        "سيظهر لك خيار: فيديو أو صوت."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 استخدام البوت:\n"
        "1️⃣ أرسل رابط الفيديو مباشرة\n"
        "2️⃣ سيظهر لك خيار: فيديو أو صوت\n"
        "3️⃣ إذا كان الفيديو أكبر من الحد سيتم ضغطه أو تحويله لصوت\n\n"
        "⚡ سريع، بسيط، واحترافي!"
    )

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🔄 تمت إعادة التشغيل. ابدأ من جديد بإرسال رابط الفيديو.")
    await start(update, context)

def get_video_info(url):
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        return ydl.extract_info(url, download=False)

def compress_video(input_path, output_path, target_size):
    command = [
        "ffmpeg", "-y", "-i", input_path,
        "-vcodec", "libx264", "-crf", "28", "-preset", "fast",
        "-acodec", "aac", "-b:a", "128k",
        output_path
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

async def show_loading(chat):
    # نرسل الساعة الرملية فقط بدون نص
    msg = await chat.send_message("⏳⏳⏳")
    frames = ["⏳⏳⏳", "⌛⌛⌛"]

    # نستمر بالتبديل حتى ينتهي التحميل
    async def animate():
        i = 0
        while True:
            await asyncio.sleep(1)
            await msg.edit_text(frames[i % 2])
            i += 1

    task = asyncio.create_task(animate())
    return msg, task

async def download_and_send(chat, url: str, mode: str, limit: int):
    loading_msg, anim_task = await show_loading(chat)
    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: get_video_info(url))
        title = info.get("title", "بدون عنوان")

        if mode == "audio":
            with yt_dlp.YoutubeDL(AUDIO_OPTIONS) as ydl_audio:
                info_audio = await loop.run_in_executor(None, lambda: ydl_audio.extract_info(url, download=True))
                audio_file = ydl_audio.prepare_filename(info_audio).rsplit(".", 1)[0] + ".mp3"
                with open(audio_file, "rb") as f:
                    await chat.send_audio(audio=f, caption=f"🎵 تم استخراج الصوت من: {title}")
                os.remove(audio_file)
        else:
            with yt_dlp.YoutubeDL(VIDEO_OPTIONS) as ydl:
                info_downloaded = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info_downloaded)
            if limit and os.path.getsize(filename) > limit:
                compressed_file = filename.rsplit(".",1)[0] + "_compressed.mp4"
                compress_video(filename, compressed_file, limit)
                if os.path.getsize(compressed_file) <= limit:
                    with open(compressed_file, "rb") as f:
                        await chat.send_video(video=f, caption=f"🎬 تم تحميل الفيديو بعد الضغط: {title}")
                    os.remove(compressed_file)
                else:
                    os.remove(filename)
                    await chat.send_message("⚠️ لا يمكن ضغط الفيديو بما يكفي، سيتم إرسال الصوت فقط.")
                    await download_and_send(chat, url, "audio", limit)
                    return
            else:
                with open(filename, "rb") as f:
                    await chat.send_video(video=f, caption=f"🎬 تم التحميل: {title}")
            os.remove(filename)

        # إيقاف حركة الساعة الرملية وحذفها
        anim_task.cancel()
        await loading_msg.delete()

    except Exception as e:
        print(f"Error: {e}")
        anim_task.cancel()
        await loading_msg.edit_text("❌ فشل التحميل، تحقق من الرابط أو أعد المحاولة.")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if "youtube.com/shorts/" in url:
        url = url.replace("/shorts/", "/watch?v=")

    context.user_data["url"] = url

    keyboard = [
        [InlineKeyboardButton("🎬 فيديو", callback_data="video")],
        [InlineKeyboardButton("🎵 صوت", callback_data="audio")],
        [InlineKeyboardButton("🔄 إعادة التشغيل", callback_data="restart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر ما تريد تحميله:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()

    url = context.user_data.get("url")
    user_id = query.from_user.id
    limit = PREMIUM_LIMIT if user_id in PREMIUM_USERS else FREE_LIMIT

    if query.data == "video":
        await download_and_send(update.effective_chat, url, "video", limit)
    elif query.data == "audio":
        await download_and_send(update.effective_chat, url, "audio", limit)
    elif query.data == "restart":
        context.user_data.clear()
        await update.effective_chat.send_message("🔄 تمت إعادة التشغيل. أرسل رابط جديد.")

async def set_commands(app):
    commands = [
        BotCommand("language", "🌐 اللغة"),
        BotCommand("help", "📖 المساعدة"),
        BotCommand("restart", "🔄 إعادة التشغيل")
    ]
    await app.bot.set_my_commands(commands)

def main():
    app = Application.builder().token(TOKEN).post_init(set_commands).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 البوت يعمل الآن!")
    app.run_polling()

if __name__ == "__main__":
    main()
