import os
import json
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

import yt_dlp
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تحميل ملف اللغات
with open('languages.json', 'r', encoding='utf-8') as f:
    LANGUAGES = json.load(f)

# متغيرات البيئة
TOKEN = os.getenv('BOT_TOKEN')
DEFAULT_LANG = os.getenv('BOT_LANG', 'ar')

# تخزين لغة كل مستخدم
user_languages = {}

class DownloadBot:
    def __init__(self):
        self.active_downloads = {}
        
    def get_text(self, user_id: int, key: str, **kwargs) -> str:
        """الحصول على نص مترجم حسب لغة المستخدم"""
        lang = user_languages.get(user_id, DEFAULT_LANG)
        text = LANGUAGES.get(lang, LANGUAGES['ar']).get(key, key)
        return text.format(**kwargs)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج أمر /start - يعرض القائمة الرئيسية"""
        user_id = update.effective_user.id
        
        # تعيين اللغة الافتراضية للمستخدم الجديد
        if user_id not in user_languages:
            user_languages[user_id] = DEFAULT_LANG
        
        # قائمة الأزرار الرئيسية
        keyboard = [
            [InlineKeyboardButton(self.get_text(user_id, 'language_btn'), callback_data='menu_language')],
            [InlineKeyboardButton(self.get_text(user_id, 'help_btn'), callback_data='menu_help')],
            [InlineKeyboardButton(self.get_text(user_id, 'restart_btn'), callback_data='menu_restart')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            self.get_text(user_id, 'welcome'),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def handle_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج أزرار القائمة"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        if data == 'menu_language':
            # عرض أزرار اللغات
            keyboard = [
                [
                    InlineKeyboardButton("🇸🇦 العربية", callback_data='lang_ar'),
                    InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')
                ],
                [
                    InlineKeyboardButton("🇹🇷 Türkçe", callback_data='lang_tr'),
                    InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru')
                ],
                [InlineKeyboardButton("🔙 رجوع", callback_data='menu_back')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                self.get_text(user_id, 'choose_lang'),
                reply_markup=reply_markup
            )
            
        elif data == 'menu_help':
            # عرض تعليمات التحميل حسب اللغة
            help_text = LANGUAGES.get(user_languages.get(user_id, 'ar'), {}).get('help_full', '')
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_back')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                help_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        elif data == 'menu_restart':
            # إعادة التشغيل (مسح البيانات)
            context.user_data.clear()
            await query.edit_message_text(
                self.get_text(user_id, 'queue_restarted')
            )
            # إظهار القائمة الرئيسية مرة أخرى
            await self.start(update, context)
            
        elif data == 'menu_back':
            # الرجوع للقائمة الرئيسية
            await self.start(update, context)
            
        elif data.startswith('lang_'):
            # تغيير اللغة
            new_lang = data.replace('lang_', '')
            user_languages[user_id] = new_lang
            await query.edit_message_text(self.get_text(user_id, 'lang_set'))
            # إظهار القائمة الرئيسية باللغة الجديدة
            await self.start(update, context)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الروابط - يعرض خيارات فيديو/صوت"""
        url = update.message.text.strip()
        user_id = update.effective_user.id
        
        # التحقق من الرابط
        if not (url.startswith('http://') or url.startswith('https://')):
            await update.message.reply_text(self.get_text(user_id, 'invalid_link'))
            return
        
        # حفظ الرابط في context
        context.user_data['url'] = url
        
        # استخراج معلومات الفيديو
        try:
            ydl_opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )
                duration = info.get('duration', 0)
                context.user_data['duration'] = duration
                context.user_data['title'] = info.get('title', 'Video')
        except Exception as e:
            logger.error(f"Error extracting info: {e}")
            duration = 0
        
        # أزرار الجودات
        keyboard = [
            [
                InlineKeyboardButton(self.get_text(user_id, 'quality_480p'), callback_data='video_480'),
                InlineKeyboardButton(self.get_text(user_id, 'quality_720p'), callback_data='video_720')
            ],
            [
                InlineKeyboardButton(self.get_text(user_id, 'quality_best'), callback_data='video_best'),
                InlineKeyboardButton(self.get_text(user_id, 'audio_only'), callback_data='audio')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"{self.get_text(user_id, 'choose_quality')}\n{self.get_text(user_id, 'duration')}: {duration//60}:{duration%60:02d}"
        await update.message.reply_text(message, reply_markup=reply_markup)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج أزرار التحميل"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        url = context.user_data.get('url')
        
        # إذا كان من القائمة، نمرره للمعالج المناسب
        if data.startswith('menu_') or data.startswith('lang_'):
            await self.handle_menu(update, context)
            return
        
        # معالجة التحميل
        if not url:
            await query.edit_message_text(self.get_text(user_id, 'invalid_link'))
            return
        
        # حذف الأزرار وإظهار رسالة التحميل
        await query.edit_message_text(self.get_text(user_id, 'downloading'))
        
        # بدء التحميل
        if data == 'audio':
            await self.download_and_send(query, context, url, 'audio')
        elif data.startswith('video_'):
            quality = data.replace('video_', '')
            await self.download_and_send(query, context, url, 'video', quality)
    
    async def download_and_send(self, query, context: ContextTypes.DEFAULT_TYPE, url: str, media_type: str, quality: str = 'best'):
        """تحميل وإرسال الملف"""
        user_id = query.from_user.id
        
        try:
            # إعدادات yt-dlp
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'outtmpl': '/tmp/%(title)s.%(ext)s',
            }
            
            if media_type == 'audio':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:
                if quality == 'best':
                    ydl_opts['format'] = 'best'
                elif quality == '480':
                    ydl_opts['format'] = 'best[height<=480]'
                elif quality == '720':
                    ydl_opts['format'] = 'best[height<=720]'
            
            # تحميل الملف
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info)
                
                if media_type == 'audio':
                    filename = filename.rsplit('.', 1)[0] + '.mp3'
            
            # إرسال الملف
            with open(filename, 'rb') as f:
                if media_type == 'audio':
                    await query.message.reply_audio(
                        audio=f,
                        title=info.get('title', 'Audio'),
                        performer=info.get('uploader', 'Unknown'),
                        duration=info.get('duration')
                    )
                else:
                    await query.message.reply_video(
                        video=f,
                        supports_streaming=True
                    )
            
            # حذف الملف المؤقت
            os.remove(filename)
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            await query.message.reply_text(
                self.get_text(user_id, 'error', error=str(e)[:100])
            )

# إنشاء تطبيق Flask
app = Flask(__name__)

# إنشاء البوت
bot_app = Application.builder().token(TOKEN).build()
download_bot = DownloadBot()

# إضافة المعالجات
bot_app.add_handler(CommandHandler("start", download_bot.start))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_bot.handle_url))
bot_app.add_handler(CallbackQueryHandler(download_bot.handle_callback))

# ========== التعديلات النهائية مع سطور التشخيص ==========
@app.route('/webhook', methods=['POST'])
def webhook():
    """نقطة نهاية Webhook مع تشخيص"""
    try:
        # ✅ سجل أن الطلب وصل
        logger.info("📩 Received webhook request")
        
        # ✅ سجل البيانات الخام
        data = request.get_json(force=True)
        logger.info(f"📦 Raw data: {data}")
        
        # ✅ إنشاء Update
        update = Update.de_json(data, bot_app.bot)
        logger.info(f"🔄 Update created: {update.update_id}")
        
        # ✅ معالجة التحديث
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.process_update(update))
        loop.close()
        
        logger.info("✅ Update processed successfully")
        return 'OK', 200
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return 'Error', 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """تعيين Webhook"""
    try:
        webhook_url = "https://video-downloader-new-npmd.onrender.com/webhook"
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.bot.set_webhook(url=webhook_url))
        loop.close()
        return f"✅ Webhook set to {webhook_url}", 200
    except Exception as e:
        return f"❌ Error: {e}", 500

@app.route('/')
def home():
    return '🤖 Bot is running!'

@app.route('/ping')
def ping():
    return 'pong', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    
    # تعيين Webhook عند بدء التشغيل
    webhook_url = "https://video-downloader-new-npmd.onrender.com/webhook"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.bot.set_webhook(url=webhook_url))
        loop.close()
        logger.info(f"✅ Webhook set to {webhook_url}")
    except Exception as e:
        logger.error(f"❌ Failed to set webhook: {e}")
    
    # تشغيل Flask
    app.run(host='0.0.0.0', port=port)
