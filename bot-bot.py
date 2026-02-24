import os
import logging
from flask import Flask, request
from telegram import Bot, Update
import asyncio
from utils import get_text, download_media

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# متغيرات البيئة
TOKEN = os.getenv('BOT_TOKEN')
PORT = int(os.getenv('PORT', 10000))

# إنشاء البوت
bot = Bot(token=TOKEN)

# إنشاء تطبيق Flask
app = Flask(__name__)

# تخزين لغة المستخدم
user_lang = {}

# نقطة نهاية Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    """استقبال التحديثات من تيليجرام"""
    try:
        logger.info("📩 تم استقبال تحديث من تيليجرام")
        update = Update.de_json(request.get_json(force=True), bot)
        asyncio.run(handle_update(update))
        return 'OK', 200
    except Exception as e:
        logger.error(f"خطأ في webhook: {e}")
        return 'Error', 500

# معالجة التحديثات
async def handle_update(update):
    try:
        if update.message and update.message.text:
            text = update.message.text
            chat_id = update.message.chat_id
            user_id = update.message.from_user.id
            
            logger.info(f"رسالة من {user_id}: {text}")
            
            # رد بسيط للتجربة
            await update.message.reply_text(f"✅ استقبلت رسالتك: {text}")
            
    except Exception as e:
        logger.error(f"خطأ في معالجة التحديث: {e}")

# نقطة نهاية للتحقق من أن السيرفر يعمل
@app.route('/')
def home():
    return 'البوت شغال! 🚀'

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    logger.info(f"🚀 تشغيل البوت على المنفذ {PORT}")
    
    # تعيين Webhook
    webhook_url = f"https://video-downloader-bot.onrender.com/webhook"
    asyncio.run(bot.set_webhook(url=webhook_url))
    logger.info(f"✅ Webhook مضبوط على: {webhook_url}")
    
    # تشغيل Flask
    app.run(host='0.0.0.0', port=PORT)
