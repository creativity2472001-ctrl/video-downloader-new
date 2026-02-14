import os
import asyncio
import yt_dlp
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"
DOWNLOAD_DIR = "downloads"
FREE_LIMIT = 50 * 1024 * 1024   # 50MB للمجاني
PREMIUM_LIMIT = 200 * 1024 * 1024  # 200MB للمدفوع
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

PREMIUM_USERS = {123456789, 987654321}

VIDEO_OPTIONS = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
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

async def download_and_send(message, url: str, mode: str, limit: int):
    status = await message.reply_text("🔍 جاري التحليل...")

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: get_video_info(url))

        title = info.get("title", "بدون عنوان")
        duration = info.get("duration", 0)

        await status.edit_text(f"📌 {title}\n⏱ المدة: {duration} ثانية\n⬇️ جاري التحميل...")

        if mode == "audio":
            with yt_dlp.YoutubeDL(AUDIO_OPTIONS) as ydl_audio:
                info_audio = await loop.run_in_executor(None, lambda: ydl_audio.extract_info(url, download=True))
                audio_file = ydl_audio.prepare_filename(info_audio).rsplit(".", 1)[0] + ".mp3"
                try:
                    with open(audio_file, "rb") as f:
                        await message.reply_audio(audio=f, caption=f"🎵 تم استخراج الصوت من: {title}")
                finally:
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
        else:  # video
            with yt_dlp.YoutubeDL(VIDEO_OPTIONS) as ydl:
                info_downloaded = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info_downloaded)

            try:
                if limit and os.path.getsize(filename) > limit:
                    await status.edit_text("⚠️ الفيديو أكبر من الحد المسموح به، سيتم ضغطه...")
                    compressed_file = filename.rsplit(".",1)[0] + "_compressed.mp4"
                    compress_video(filename, compressed_file, limit)
                    if os.path.getsize(compressed_file) <= limit:
                        with open(compressed_file, "rb") as f:
                            await message.reply_video(video=f, caption=f"🎬 تم تحميل الفيديو بعد الضغط: {title}")
                        os.remove(compressed_file)
                    else:
                        os.remove(filename)
                        await status.edit_text("⚠️ لا يمكن ضغط الفيديو بما يكفي، سيتم إرسال الصوت فقط.")
                        await download_and_send(message, url, "audio", limit)
                        return
                else:
                    with open(filename, "rb") as f:
                        await message.reply_video(video=f, caption=f"🎬 تم التحميل: {title}")
            finally:
                if os.path.exists(filename):
                    os.remove(filename)

        await status.delete()

    except Exception as e:
        print(f"Error: {e}")
        await status.edit_text("❌ فشل التحميل، تحقق من الرابط أو أعد المحاولة.")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if "youtube.com/shorts/" in url:
        url = url.replace("/shorts/", "/watch?v=")

    context.user_data["url"] = url

    keyboard = [
        [InlineKeyboardButton("🎬 فيديو", callback_data="video")],
        [InlineKeyboardButton("🎵 صوت", callback_data="audio")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر ما تريد تحميله:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    url = context.user_data.get("url")
    user_id = query.from_user.id
    limit = PREMIUM_LIMIT if user_id in PREMIUM_USERS else FREE_LIMIT

    if query.data == "video":
        await download_and_send(query.message, url, "video", limit)
    elif query.data == "audio":
        await download_and_send(query.message, url, "audio", limit)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 البوت يعمل الآن!")
    app.run_polling()

if __name__ == "__main__":
    main()
