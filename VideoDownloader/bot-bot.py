import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from utils import get_text, get_video_info, download_media

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# User Queues Storage
user_queues = {}

async def get_user_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return context.user_data.get('lang', 'ar')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update, context)
    reply_keyboard = [['/language', '/help'], ['/restart']]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(get_text('welcome', lang), reply_markup=markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update, context)
    await update.message.reply_text(get_text('help', lang))

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update, context)
    keyboard = [
        [InlineKeyboardButton("العربية 🇸🇦", callback_data='lang_ar'), InlineKeyboardButton("English 🇺🇸", callback_data='lang_en')],
        [InlineKeyboardButton("Русский 🇷🇺", callback_data='lang_ru'), InlineKeyboardButton("Türkçe 🇹🇷", callback_data='lang_tr')],
        [InlineKeyboardButton("Deutsch 🇩🇪", callback_data='lang_de'), InlineKeyboardButton("Français 🇫🇷", callback_data='lang_fr')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(get_text('choose_lang', lang), reply_markup=reply_markup)

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Reset queue for user
    if user_id in user_queues:
        user_queues[user_id] = asyncio.Queue()
    lang = await get_user_lang(update, context)
    await update.message.reply_text(get_text('queue_restarted', lang))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    lang = await get_user_lang(update, context)
    
    if not text.startswith('http'):
        return

    status_msg = await update.message.reply_text("🔍 ...")
    # Fetch info to validate
    info = await asyncio.to_thread(get_video_info, text)
    
    if not info:
        await status_msg.edit_text(get_text('invalid_link', lang))
        return

    context.user_data['current_url'] = text
    
    keyboard = [
        [InlineKeyboardButton(get_text('quality_480p', lang), callback_data='dl_480p'),
         InlineKeyboardButton(get_text('quality_720p', lang), callback_data='dl_720p')],
        [InlineKeyboardButton(get_text('quality_best', lang), callback_data='dl_best')],
        [InlineKeyboardButton(get_text('audio_only', lang), callback_data='dl_audio')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await status_msg.edit_text(get_text('choose_quality', lang), reply_markup=reply_markup)

async def worker(user_id, queue, context):
    while True:
        update, format_type, lang = await queue.get()
        try:
            url = context.user_data.get('current_url')
            if not url:
                continue

            # Initial check for size
            info = await asyncio.to_thread(get_video_info, url)
            filesize = info.get('filesize', 0) or info.get('filesize_approx', 0)
            
            if filesize > 80 * 1024 * 1024:
                await context.bot.send_message(chat_id=user_id, text=get_text('error_large_file', lang))
                continue

            status_msg = await context.bot.send_message(chat_id=user_id, text=get_text('downloading', lang, progress=0))
            context.user_data['status_msg_id'] = status_msg.message_id
            context.user_data['last_progress'] = 0

            file_path = await download_media(url, format_type, user_id, update, context, lang)
            
            if file_path and os.path.exists(file_path):
                if os.path.getsize(file_path) > 80 * 1024 * 1024:
                    await status_msg.edit_text(get_text('error_large_file', lang))
                else:
                    await status_msg.edit_text(get_text('uploading', lang))
                    with open(file_path, 'rb') as f:
                        if format_type == 'audio':
                            await context.bot.send_audio(chat_id=user_id, audio=f)
                        else:
                            await context.bot.send_video(chat_id=user_id, video=f)
                    await status_msg.delete()
                
                if os.path.exists(file_path):
                    os.remove(file_path)
            else:
                await status_msg.edit_text(get_text('error_download', lang))
        except Exception as e:
            logging.error(f"Worker Error: {e}")
            try:
                await context.bot.send_message(chat_id=user_id, text=get_text('error_download', lang))
            except:
                pass
        finally:
            queue.task_done()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context)

    if data.startswith('lang_'):
        new_lang = data.split('_')[1]
        context.user_data['lang'] = new_lang
        await query.edit_message_text(get_text('lang_set', new_lang))
    
    elif data.startswith('dl_'):
        format_type = data.split('_')[1]
        
        if user_id not in user_queues:
            user_queues[user_id] = asyncio.Queue()
            asyncio.create_task(worker(user_id, user_queues[user_id], context))
        
        queue = user_queues[user_id]
        await queue.put((update, format_type, lang))
        pos = queue.qsize()
        await query.edit_message_text(get_text('added_to_queue', lang, pos=pos))

if __name__ == '__main__':
    # Token placeholder
    TOKEN = os.getenv('BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')
    
    if TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN':
        print("Error: Please set your BOT_TOKEN in the environment or replace the placeholder in main.py")
    else:
        app = ApplicationBuilder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("language", language_command))
        app.add_handler(CommandHandler("restart", restart_command))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("Bot is running...")
        app.run_polling()
