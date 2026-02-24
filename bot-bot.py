import os
import logging
import asyncio
from flask import Flask, request
from telegram import Bot, Update

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

# حلقة تشغيل asyncio عالمية
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# نقطة نهاية Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    """استقبال التحديثات من تيليجرام"""
    try:
        logger.info("📩 تم استقبال تحديث من تيليجرام")
        update = Update.de_json(request.get_json(force=True), bot)
        
        # إضافة المهمة إلى الحلقة بدلاً من إنشاء حلقة جديدة
        asyncio.run_coroutine_threadsafe(handle_update(update), loop)
        
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
            await update.message.reply_text(f"✅ البوت يعلم! استقبلت رسالتك: {text}")
            
    except Exception as e:
        logger.error(f"خطأ في معالجة التحديث: {e}")

# نقطة نهاية للتحقق من أن السيرفر يعمل
@app.route('/')
def home():
    return 'البوت شغال! 🚀'

@app.route('/health')
def health():
    return 'OK', 200

@app.route('/set_webhook')
def set_webhook():
    """تعيين Webhook (اتصل به مرة واحدة فقط)"""
    try:
        webhook_url = f"https://video-downloader-bot.onrender.com/webhook"
        asyncio.run(bot.set_webhook(url=webhook_url))
        return f"✅ Webhook مضبوط على: {webhook_url}", 200
    except Exception as e:
        return f"❌ خطأ: {e}", 500

def start_background_loop():
    """تشغيل حلقة asyncio في الخلفية"""
    loop.run_forever()

if __name__ == '__main__':
    logger.info(f"🚀 تشغيل البوت على المنفذ {PORT}")
    
    # تعيين Webhook عند بدء التشغيل
    webhook_url = f"https://video-downloader-bot.onrender.com/webhook"
    try:
        # استخدام run_coroutine_threadsafe بدلاً من asyncio.run
        future = asyncio.run_coroutine_threadsafe(
            bot.set_webhook(url=webhook_url), loop
        )
        future.result(timeout=10)  # انتظر حتى يكتمل
        logger.info(f"✅ Webhook مضبوط على: {webhook_url}")
    except Exception as e:
        logger.error(f"❌ فشل تعيين Webhook: {e}")
    
    # تشغيل حلقة asyncio في الخلفية
    import threading
    threading.Thread(target=start_background_loop, daemon=True).start()
    
    # تشغيل Flask
    app.run(host='0.0.0.0', port=PORT)
