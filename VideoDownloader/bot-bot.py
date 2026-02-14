import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# ضع التوكن الخاص ببوتك هنا
TOKEN = '8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA'

# إعدادات التحميل (yt-dlp)
def get_ytdl_opts(download_type, output_path):
    if download_type == 'video':
        return {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': f'{output_path}.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True,
        }
    else:  # audio
        return {
            'format': 'bestaudio/best',
            'outtmpl': f'{output_path}.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # زر القائمة (Menu) بجانب صندوق الكتابة
    keyboard = [['اللغة 🌐', 'المساعدة 📖', 'إعادة التشغيل 🔄']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "أهلاً بك! أرسل لي رابط الفيديو وسأقوم بتحميله لك فوراً.",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "المساعدة 📖":
        help_text = (
            "📖 Download instructions:\n\n"
            "1. Go to the Instagram/TikTok/Pinterest/Likee/YouTube app\n"
            "2. Choose a video you like\n"
            "3. Tap the ↪️ button or the three dots in the top right corner.\n"
            "4. Tap the \"Copy\" button.\n"
            "5. Send the link to the bot and in a few seconds you'll get the video without a watermark."
        )
        await update.message.reply_text(help_text)
        return

    if text == "اللغة 🌐":
        await update.message.reply_text("اللغة المتاحة حالياً: العربية / English")
        return

    if text == "إعادة التشغيل 🔄":
        await start(update, context)
        return

    # التحقق إذا كان النص رابطاً
    if text.startswith("http"):
        context.user_data['link'] = text
        keyboard = [
            [InlineKeyboardButton("فيديو 🎬", callback_data='video')],
            [InlineKeyboardButton("صوت 🎵", callback_data='audio')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("اختر نوع التحميل:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    choice = query.data
    link = context.user_data.get('link')
    
    await query.answer()
    
    # تعديل الرسالة لتظهر "جاري التحميل" مع الساعة الرملية واختفاء الأزرار
    loading_msg = await query.edit_message_text("جاري التحميل... ⏳")

    file_id = f"file_{query.from_user.id}"
    opts = get_ytdl_opts(choice, file_id)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=True)
            filename = ydl.prepare_filename(info)
            if choice == 'audio':
                filename = filename.rsplit('.', 1)[0] + '.mp3'

        # إرسال الملف
        with open(filename, 'rb') as f:
            if choice == 'video':
                await query.message.reply_video(video=f, caption="تم التحميل بنجاح! ✅")
            else:
                await query.message.reply_audio(audio=f, caption="تم التحميل بنجاح! ✅")
        
        # حذف رسالة "جاري التحميل" بعد الانتهاء
        await loading_msg.delete()
        
        # تنظيف الملفات من السيرفر
        if os.path.exists(filename):
            os.remove(filename)

    except Exception as e:
        await query.edit_message_text(f"عذراً، حدث خطأ: {str(e)}")

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("البوت يعمل الآن...")
    application.run_polling()

if __name__ == '__main__':
    main()
