import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

API_TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# لوحة اختيار نوع التحميل
def get_download_type_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🎥 فيديو", callback_data="download_video"),
        InlineKeyboardButton("🎵 صوت", callback_data="download_audio")
    )
    return keyboard

# لوحة القائمة الجانبية
def get_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🌐 اللغة", callback_data="menu_language"),
        InlineKeyboardButton("📖 المساعدة", callback_data="menu_help"),
        InlineKeyboardButton("🔄 Restart", callback_data="menu_restart")
    )
    return keyboard

# لوحة اختيار اللغة
def get_language_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    return keyboard

# استقبال الرابط
@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    await message.reply("أرسل رابط الفيديو من أي موقع عالمي 🌍", reply_markup=get_menu_keyboard())

@dp.message_handler(lambda message: message.text.startswith("http"))
async def handle_link(message: types.Message):
    await message.reply("اختر نوع التحميل:", reply_markup=get_download_type_keyboard())

# معالجة اختيار فيديو/صوت
@dp.callback_query_handler(lambda c: c.data in ["download_video", "download_audio"])
async def process_download(callback_query: types.CallbackQuery):
    url = callback_query.message.reply_to_message.text
    choice = callback_query.data

    # حذف رسالة الاختيار
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)

    # إرسال رسالة جاري التحميل
    loading_msg = await bot.send_message(callback_query.message.chat.id, "⏳ جاري التحميل...")

    # إعدادات yt-dlp
    if choice == "download_video":
        ydl_opts = {
            "outtmpl": "%(title)s.%(ext)s",
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4"
        }
    else:
        ydl_opts = {
            "outtmpl": "%(title)s.%(ext)s",
            "format": "bestaudio",
            "merge_output_format": "mp3"
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # إرسال الملف
        if choice == "download_video":
            await bot.send_video(callback_query.message.chat.id, open(filename, "rb"))
        else:
            await bot.send_audio(callback_query.message.chat.id, open(filename, "rb"))

    except Exception as e:
        await bot.send_message(callback_query.message.chat.id, f"❌ خطأ: {e}")

    # حذف رسالة التحميل
    await bot.delete_message(callback_query.message.chat.id, loading_msg.message_id)

# القائمة الجانبية
@dp.callback_query_handler(lambda c: c.data.startswith("menu_"))
async def process_menu(callback_query: types.CallbackQuery):
    if callback_query.data == "menu_language":
        await bot.send_message(callback_query.message.chat.id, "اختر اللغة:", reply_markup=get_language_keyboard())
    elif callback_query.data == "menu_help":
        help_text = """📖 تعليمات التحميل:

1. افتح تطبيق Instagram/TikTok/Pinterest/Likee/YouTube
2. اختر الفيديو الذي يعجبك
3. اضغط زر ↪️ أو الثلاث نقاط
4. اضغط "Copy"
5. أرسل الرابط للبوت وسيصلك الفيديو بدون علامة مائية"""
        await bot.send_message(callback_query.message.chat.id, help_text)
    elif callback_query.data == "menu_restart":
        await bot.send_message(callback_query.message.chat.id, "🔄 تمت إعادة التشغيل. أرسل رابط جديد.", reply_markup=get_menu_keyboard())

# اختيار اللغة
@dp.callback_query_handler(lambda c: c.data.startswith("lang_"))
async def process_language(callback_query: types.CallbackQuery):
    if callback_query.data == "lang_ar":
        await bot.send_message(callback_query.message.chat.id, "✅ اللغة: عربي")
    elif callback_query.data == "lang_en":
        await bot.send_message(callback_query.message.chat.id, "✅ Language: English")

# تشغيل البوت
async def main():
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
