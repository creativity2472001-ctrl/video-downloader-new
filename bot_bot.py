import os
import logging
import asyncio
from flask import Flask, request
from telegram import Bot, Update

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# المتغيرات
TOKEN = os.getenv('BOT_TOKEN')
PORT = int(os.getenv('PORT', 8080))

# إنشاء البوت وتطبيق Flask
bot = Bot(token=TOKEN)
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """استقبال التحديثات من تيليجرام"""
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        
        # معالجة الرسائل
        if update.message and update.message.text:
            text = update.message.text
            chat_id = update.message.chat_id
            logger.info(f"رسالة من {chat_id}: {text}")
            
            if text == '/start':
                bot.send_message(chat_id=chat_id, text="✅ البوت يعمل!")
            else:
                bot.send_message(chat_id=chat_id, text=f"استقبلت: {text}")
        
        return 'OK', 200
    except Exception as e:
        logger.error(f"خطأ في webhook: {e}")
        return 'Error', 500

@app.route('/')
def home():
    return "البوت شغال! 🚀"

@app.route('/test')
def test():
    return "Test page works!"

if __name__ == '__main__':
    # تعيين Webhook عند التشغيل (بشكل صحيح مع await)
    webhook_url = f"https://video-downloader-new-production.up.railway.app/webhook"
    
    # استخدام asyncio لتشغيل الدالة غير المتزامنة
    try:
        asyncio.run(bot.set_webhook(url=webhook_url))
        logger.info(f"✅ Webhook مضبوط على: {webhook_url}")
    except Exception as e:
        logger.error(f"خطأ في تعيين Webhook: {e}")
    
    # تشغيل السيرفر
    logger.info(f"🚀 تشغيل البوت على المنفذ {PORT}")
    app.run(host='0.0.0.0', port=PORT)
