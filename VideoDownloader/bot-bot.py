import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from utils import get_text, download_media

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# تخزين لغة المستخدم
user_lang = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_lang:
        user_lang[user_id] = 'ar'
    
    # أزرار القائمة الرئيسية
    keyboard = [
        [KeyboardButton("اللغة 🌐"), KeyboardButton("المساعدة 📖")],
        [KeyboardButton("إعادة التشغيل 🔄")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        get_text('welcome', user_lang[user_id]),
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    await update.message.reply_text(get_text('help', lang))

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🇸🇦 عربي", callback_data='lang_ar'),
         InlineKeyboardButton("🇺🇸 English", callback_data='lang_en')],
        [InlineKeyboardButton("🇹🇷 Türkçe", callback_data='lang_tr'),
         InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        get_text('choose_lang', user_lang.get(user_id, 'ar')),
        reply_markup=reply_markup
    )

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    if user_id in context.user_data:
        context.user_data.clear()
    
    await update.message.reply_text(get_text('queue_restarted', lang))
    await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    # معالجة أزرار القائمة
    if text in ["اللغة 🌐", "Language 🌐"]:
        await language_command(update, context)
        return
    elif text in ["المساعدة 📖", "Help 📖"]:
        await help_command(update, context)
        return
    elif text in ["إعادة التشغيل 🔄", "Restart 🔄"]:
        await restart_command(update, context)
        return
    
    # معالجة الروابط
    if text.startswith('http'):
        status_msg = await update.message.reply_text("🔍 جاري التحميل...")
        
        try:
            # حفظ الرابط في بيانات المستخدم
            context.user_data['url'] = text
            
            # عرض أزرار اختيار الجودة
            keyboard = [
                [InlineKeyboardButton("480p 🎬", callback_data='quality_480p'),
                 InlineKeyboardButton("720p 🎬", callback_data='quality_720p')],
                [InlineKeyboardButton("أفضل جودة ✨", callback_data='quality_best'),
                 InlineKeyboardButton("صوت 🎵", callback_data='quality_audio')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await status_msg.edit_text(
                "🎯 اختر جودة التحميل:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logging.error(f"Error: {e}")
            await status_msg.edit_text("❌ حدث خطأ في التحميل")
    else:
        await update.message.reply_text("❌ رابط غير صالح")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    # معالجة تغيير اللغة
    if data.startswith('lang_'):
        new_lang = data.split('_')[1]
        user_lang[user_id] = new_lang
        await query.edit_message_text("✅ تم تغيير اللغة")
        return
    
    # معالجة اختيار الجودة
    if data.startswith('quality_'):
        url = context.user_data.get('url')
        if not url:
            await query.edit_message_text("❌ حدث خطأ")
            return
        
        quality_type = data.split('_')[1]
        is_audio = (quality_type == 'audio')
        
        await query.edit_message_text("⏳ جاري التحميل...")
        
        try:
            file_path = await download_media(url, quality_type, user_id)
            
            if file_path and os.path.exists(file_path):
                await query.edit_message_text("📤 جاري الإرسال...")
                
                with open(file_path, 'rb') as f:
                    if is_audio:
                        await context.bot.send_audio(chat_id=user_id, audio=f)
                    else:
                        await context.bot.send_video(chat_id=user_id, video=f)
                
                os.remove(file_path)
                await query.delete()
            else:
                await query.edit_message_text("❌ فشل التحميل")
                
        except Exception as e:
            logging.error(f"Download error: {e}")
            await query.edit_message_text("❌ حدث خطأ")

if __name__ == '__main__':
    TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ البوت يعمل الآن...")
    app.run_polling()
