import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ضع التوكن الخاص ببوتك هنا
TOKEN = '8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA'

# إعدادات متقدمة للسرعة والجودة
def download_process(link, choice, file_path):
    if choice == 'video':
        ydl_opts = {
            'format': 'best[ext=mp4]/best', # أسرع صيغة مدمجة
            'outtmpl': f'{file_path}.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
    else:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{file_path}.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=True)
        return ydl.prepare_filename(info)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['اللغة 🌐', 'المساعدة 📖', 'إعادة التشغيل 🔄']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("أهلاً بك! أرسل الرابط وسأقوم بالتحميل فوراً ⚡", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith("http"):
        context.user_data['link'] = text
        keyboard = [[InlineKeyboardButton("فيديو 🎬", callback_data='video'), 
                     InlineKeyboardButton("صوت 🎵", callback_data='audio')]]
        await update.message.reply_text("اختر نوع التحميل:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif "المساعدة" in text:
        await update.message.reply_text("📖 أرسل الرابط مباشرة، وسأقوم بجلب الفيديو لك بدون علامة مائية.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # منع التكرار: نقوم بالإجابة على الطلب فوراً لإبلاغ تيليجرام أننا استلمناه
    await query.answer()
    
    choice = query.data
    link = context.user_data.get('link')
    if not link: return

    # تغيير الرسالة واختفاء الأزرار
    loading_msg = await query.edit_message_text("جاري التحميل... ⏳")
    
    file_id = f"dl_{query.from_user.id}_{context.update_id}"
    loop = asyncio.get_event_loop()

    try:
        # تشغيل التحميل في "خيط" منفصل لمنع تجميد البوت (حل مشكلة البطء والخطأ)
        filename = await loop.run_in_executor(None, download_process, link, choice, file_id)
        
        if choice == 'audio' and not filename.endswith('.mp3'):
            filename = os.path.splitext(filename)[0] + '.mp3'

        # إرسال الملف
        with open(filename, 'rb') as f:
            if choice == 'video':
                await query.message.reply_video(video=f, caption="✅ تم التحميل بنجاح!")
            else:
                await query.message.reply_audio(audio=f, caption="✅ تم التحميل بنجاح!")
        
        # حذف رسالة "جاري التحميل" بعد النجاح
        await loading_msg.delete()

    except Exception as e:
        await query.message.reply_text(f"❌ حدث خطأ: {str(e)}")
    finally:
        # تنظيف الملفات
        if 'filename' in locals() and os.path.exists(filename):
            os.remove(filename)

def main():
    # منع إعادة المحاولة التلقائية من تيليجرام (حل مشكلة تكرار الفيديو)
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("البوت يعمل بكفاءة عالية الآن...")
    application.run_polling(drop_pending_updates=True) # يتجاهل الرسائل القديمة عند التشغيل

if __name__ == '__main__':
    main()
