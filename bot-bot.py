import os
import asyncio
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"
DOWNLOAD_DIR = "downloads"
FREE_LIMIT = 50 * 1024 * 1024   # 50MB للمجاني
PREMIUM_LIMIT = 200 * 1024 * 1024  # 200MB للمدفوع
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# قائمة المستخدمين المدفوعين (ضع الـ user_id هنا)
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
        "يمكنك استخدام الأوامر:\n"
        "▶️ /video <link> لتحميل الفيديو\n"
        "🎵 /audio <link> لتحميل الصوت فقط\n"
        "أو أرسل الرابط مباشرة وسأختار لك حسب الحجم."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 استخدام البوت:\n"
        "1️⃣ أرسل رابط الفيديو مباشرة\n"
        "2️⃣ إذا كان أصغر من الحد المسموح به سيتم إرساله مباشرة\n"
        "3️⃣ إذا أكبر، سيتم إرسال الصوت فقط\n\n"
        "أوامر إضافية:\n"
        "▶️ /video <link> لتحميل الفيديو\n"
        "🎵 /audio <link> لتحميل الصوت فقط"
    )

def get_video_info(url):
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        return ydl.extract_info(url, download=False)

async def download_and_send(update: Update, url: str, mode: str, limit: int):
    status = await update.message.reply_text("🔍 جاري التحليل...")

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
                        await update.message.reply_audio(audio=f, caption=f"🎵 تم استخراج الصوت من: {title}")
                finally:
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
        else:  # video
            with yt_dlp.YoutubeDL(VIDEO_OPTIONS) as ydl:
                info_downloaded = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info_downloaded)

            try:
                # تحقق من الحجم الفعلي
                if limit and os.path.getsize(filename) > limit:
                    await status.edit_text("⚠️ الفيديو أكبر من الحد المسموح به، سيتم إرسال الصوت فقط.")
                    os.remove(filename)
                    return await download_and_send(update, url, "audio", limit)

                with open(filename, "rb") as f:
                    await update.message.reply_video(video=f, caption=f"🎬 تم التحميل: {title}")
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

    user_id = update.message.from_user.id
    limit = PREMIUM_LIMIT if user_id in PREMIUM_USERS else FREE_LIMIT
    await download_and_send(update, url, "video", limit)

async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ يرجى إدخال الرابط بعد الأمر /video")
        return
    url = context.args[0]
    user_id = update.message.from_user.id
    limit = PREMIUM_LIMIT if user_id in PREMIUM_USERS else FREE_LIMIT
    await download_and_send(update, url, "video", limit)

async def audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ يرجى إدخال الرابط بعد الأمر /audio")
        return
    url = context.args[0]
    user_id = update.message.from_user.id
    limit = PREMIUM_LIMIT if user_id in PREMIUM_USERS else FREE_LIMIT
    await download_and_send(update, url, "audio", limit)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start ))
