import os
import asyncio
import yt_dlp
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

# ====== ضع التوكن هنا ======
TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"

DOWNLOAD_DIR = "downloads"
FREE_LIMIT = 50 * 1024 * 1024      # 50MB
PREMIUM_LIMIT = 200 * 1024 * 1024  # 200MB
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ضع ايدي المستخدمين المدفوعين هنا
PREMIUM_USERS = {123456789}

# ====== خيارات تحميل الفيديو (سريع + HD رسمي) ======
VIDEO_OPTIONS = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'noplaylist': True,
    'merge_output_format': 'mp4',
    'quiet': True
}

# ====== خيارات تحميل الصوت ======
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
    'quiet': True
}


# ================= أوامر البوت =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id in PREMIUM_USERS:
        msg = "💎 أنت مشترك مدفوع — الحد 200MB"
    else:
        msg = "📌 نسخة مجانية — الحد 50MB"

    await update.message.reply_text(
        f"{msg}\n\n"
        "🎬 أرسل رابط من YouTube / TikTok / Instagram / Facebook\n"
        "سيظهر لك خيار تحميل فيديو أو صوت."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 طريقة الاستخدام:\n"
        "1️⃣ أرسل الرابط\n"
        "2️⃣ اختر فيديو أو صوت\n"
        "3️⃣ إذا كان كبير سيتم ضغطه تلقائيًا\n\n"
        "⚡ سريع — بدون زوم — احترافي"
    )


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🔄 تمت إعادة التشغيل. أرسل رابط جديد.")


# ================= أدوات مساعدة =================

def get_video_info(url):
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        return ydl.extract_info(url, download=False)


def compress_video(input_path, output_path):
    command = [
        "ffmpeg", "-y", "-i", input_path,
        "-vcodec", "libx264", "-crf", "28", "-preset", "fast",
        "-acodec", "aac", "-b:a", "128k",
        output_path
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path


# ================= التحميل والإرسال =================

async def download_and_send(chat, url: str, mode: str, limit: int):
    loading_msg = await chat.send_message("⏳ جاري التحميل...")

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: get_video_info(url))
        title = info.get("title", "بدون عنوان")

        if mode == "audio":
            with yt_dlp.YoutubeDL(AUDIO_OPTIONS) as ydl_audio:
                info_audio = await loop.run_in_executor(
                    None, lambda: ydl_audio.extract_info(url, download=True)
                )
                audio_file = ydl_audio.prepare_filename(info_audio).rsplit(".", 1)[0] + ".mp3"

            await loading_msg.delete()

            with open(audio_file, "rb") as f:
                await chat.send_audio(
                    audio=f,
                    caption=f"🎵 تم استخراج الصوت:\n{title}"
                )

            os.remove(audio_file)

        else:
            with yt_dlp.YoutubeDL(VIDEO_OPTIONS) as ydl:
                info_downloaded = await loop.run_in_executor(
                    None, lambda: ydl.extract_info(url, download=True)
                )
                filename = ydl.prepare_filename(info_downloaded)

            if os.path.getsize(filename) > limit:
                compressed_file = filename.rsplit(".", 1)[0] + "_compressed.mp4"
                compress_video(filename, compressed_file)

                if os.path.getsize(compressed_file) <= limit:
                    await loading_msg.delete()

                    with open(compressed_file, "rb") as f:
                        await chat.send_video(
                            video=f,
                            caption=f"🎬 تم تحميل الفيديو بعد الضغط:\n{title}",
                            supports_streaming=True
                        )

                    os.remove(compressed_file)
                else:
                    os.remove(filename)
                    await loading_msg.delete()
                    await chat.send_message("⚠️ الفيديو كبير جدًا — سيتم إرسال الصوت فقط.")
                    await download_and_send(chat, url, "audio", limit)
                    return
            else:
                await loading_msg.delete()

                with open(filename, "rb") as f:
                    await chat.send_video(
                        video=f,
                        caption=f"🎬 تم التحميل:\n{title}",
                        supports_streaming=True
                    )

            os.remove(filename)

    except Exception as e:
        print(e)
        await loading_msg.edit_text("❌ فشل التحميل — تأكد من الرابط.")


# ================= استقبال الرابط =================

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "youtube.com/shorts/" in url:
        url = url.replace("/shorts/", "/watch?v=")

    context.user_data["url"] = url

    keyboard = [
        [InlineKeyboardButton("🎬 تحميل فيديو", callback_data="video")],
        [InlineKeyboardButton("🎵 تحميل صوت", callback_data="audio")],
        [InlineKeyboardButton("🔄 إعادة التشغيل", callback_data="restart")]
    ]

    await update.message.reply_text(
        "اختر نوع التحميل:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ================= أزرار =================

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
        await update.effective_chat.send_message("🔄 أرسل رابط جديد.")


# ================= تشغيل البوت =================

async def set_commands(app):
    commands = [
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

    print("🚀 البوت يعمل الآن...")
    app.run_polling()


if __name__ == "__main__":
    main()
