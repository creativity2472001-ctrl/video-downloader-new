import os
import logging
from flask import Flask, request
from telegram import Bot, Update
import asyncio

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# متغيرات البيئة
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    logger.error("BOT_TOKEN غير موجود!")
    exit(1)

bot = Bot(token=TOKEN)
app = Flask(__name__)

# نقطة النهاية الخاصة بـ Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    """استقبال التحديثات من تيليجرام"""
    try:
        logger.info("تم استقبال تحديث من تيليجرام")
        update = Update.de_json(request.get_json(), bot)
        asyncio.run(handle_update(update))
        return 'OK', 200
    except Exception as e:
        logger.error(f"خطأ في webhook: {e}")
        return 'Error', 500

# دالة معالجة التحديثات
async def handle_update(update):
    try:
        if update.message and update.message.text:
            text = update.message.text
            user_id = update.message.from_user.id
            logger.info(f"رسالة من {user_id}: {text}")
            
            if text == '/start':
                await update.message.reply_text(
                    f"✅ البوت يعمل! مرحباً بك.\nمعرفك: {user_id}"
                )
            else:
                await update.message.reply_text(f"استقبلت: {text}")
    except Exception as e:
        logger.error(f"خطأ في معالجة التحديث: {e}")

# نقطة نهاية للتحقق من أن السيرفر يعمل
@app.route('/')
def home():
    return 'البوت شغال! 🚀'

# نقطة نهاية لفحص الصحة (health check)
@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🚀 بدء تشغيل البوت على المنفذ {port}")
    app.run(host='0.0.0.0', port=port)
