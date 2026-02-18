import os
import asyncio
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
    
    # أزرار القائمة
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
    await update.message.reply_text(get_text('help', user_lang.get(user_id, 'ar')))

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
            file_path = await download_media(text, 'best', user_id, update, context, lang)
            
            if file_path and os.path.exists(file_path):
                await status_msg.edit_text("✅ تم التحميل! جاري الإرسال...")
                
                with open(file_path, 'rb') as f:
                    await context.bot.send_video(chat_id=user_id, video=f)
                
                os.remove(file_path)
                await status_msg.delete()
            else:
                await status_msg.edit_text(get_text('error_download', lang))
                
        except Exception as e:
            logging.error(f"Error: {e}")
            await status_msg.edit_text(get_text('error_download', lang))
    else:
        await update.message.reply_text(get_text('invalid_link', lang))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    if data.startswith('lang_'):
        new_lang = data.split('_')[1]
        user_lang[user_id] = new_lang
        await query.edit_message_text(get_text('lang_set', new_lang))

if __name__ == '__main__':
    # التوكن من متغير البيئة (آمن لـ GitHub)
    TOKEN = os.environ.get('BOT_TOKEN')
    
    if not TOKEN:
        print("❌ خطأ: لم يتم العثور على التوكن!")
        print("📝 يرجى وضع التوكن في متغير البيئة BOT_TOKEN")
        print("👉 على GitHub: Settings → Secrets and variables → Actions → New repository secret")
        print("👉 Name: BOT_TOKEN, Value: 8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA")
        exit(1)
    
    app = ApplicationBuilder().token(TOKEN.strip()).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ البوت يعمل الآن...")
    app.run_polling()
