import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# ضع التوكن الخاص ببوتك هنا
TOKEN = '8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA'

# دالة إعدادات التحميل لضمان الجودة والتوافق
def get_ytdl_opts(download_type, file_path):
    if download_type == 'video':
        return {
            # اختيار أفضل جودة MP4 مدمجة (صوت وفيديو) لضمان العمل على الآيفون والأندرويد
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'{file_path}.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
    else:  # audio
        return {
            'format': 'bestaudio/best',
            'outtmpl': f'{file_path}.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إنشاء أزرار القائمة الرئيسية (التي تظهر بجانب مربع النص)
    keyboard = [['اللغة 🌐', 'المساعدة 📖', 'إعادة التشغيل 🔄']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "أهلاً بك! أرسل لي رابط الفيديو وسأقوم بتحميله لك فوراً بأعلى جودة.",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # معالجة أزرار القائمة
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
        await update.message.reply_text("اللغة المتاحة حالياً:\nالعربية / English")
        return

    if text == "إعادة التشغيل 🔄":
        await start(update, context)
        return

    # إذا أرسل المستخدم رابطاً
    if text.startswith("http"):
        context.user_data['link'] = text
        # أزرار اختيار النوع (تختفي لاحقاً)
        keyboard = [
            [InlineKeyboardButton("فيديو 🎬", callback_data='video')],
            [InlineKeyboardButton("صوت 🎵", callback_data='audio')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("اختر نوع التحميل فيديو او صوت:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    choice = query.data
    link = context.user_data.get('link')
    
    await query.answer()
    
    # 1. تختفي رسالة "اختر النوع" وتظهر "جاري التحميل ⏳"
    loading_msg = await query.edit_message_text("جاري التحميل... ⏳")

    # اسم ملف مؤقت فريد لكل مستخدم
    file_prefix = f"dl_{query.from_user.id}"
    opts = get_ytdl_opts(choice, file_prefix)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            # استخراج المعلومات والتحميل
            info = ydl.extract_info(link, download=True)
            filename = ydl.prepare_filename(info)
            
            # في حالة الصوت، yt-dlp يغير الامتداد لـ mp3 بعد المعالجة
            if choice == 'audio':
                filename = os.path.splitext(filename)[0] + '.mp3'

        # 2. إرسال الفيديو/الصوت للمستخدم
        with open(filename, 'rb') as f:
            if choice == 'video':
                await query.message.reply_video(video=f, caption="تم التحميل بنجاح! ✅")
            else:
                await query.message.reply_audio(audio=f, caption="تم التحميل بنجاح! ✅")
        
        # 3. حذف رسالة "جاري التحميل" بعد ظهور الفيديو
        await loading_msg.delete()
        
        # تنظيف الملفات من السيرفر فوراً لزيادة السرعة وتوفير المساحة
        if os.path.exists(filename):
            os.remove(filename)

    except Exception as e:
        await query.edit_message_text(f"حدث خطأ أثناء التحميل: {str(e)}")

def main():
    # بناء التطبيق باستخدام التوكن
    application = Application.builder().token(TOKEN).build()

    # الروابط والمستقبلات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("البوت يعمل الآن... اضغط Ctrl+C للإيقاف")
    application.run_polling()

if __name__ == '__main__':
    main()
