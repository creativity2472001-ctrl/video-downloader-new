import os
import logging
from flask import Flask, request
from telegram import Bot, Update
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """استقبال التحديثات من تيليجرام"""
    try:
        update = Update.de_json(request.get_json(), bot)
        asyncio.run(handle_update(update))
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

async def handle_update(update):
    """معالجة التحديثات"""
    try:
        if update.message and update.message.text:
            text = update.message.text
            user_id = update.message.from_user.id
            
            if text == '/start':
                await update.message.reply_text(
                    f"✅ البوت يعمل!\nمعرفك: {user_id}\nأرسل أي شيء للتجربة"
                )
            else:
                await update.message.reply_text(f"استقبلت: {text}")
                
    except Exception as e:
        logger.error(f"Handle update error: {e}")

@app.route('/')
def home():
    return 'البوت شغال! 🚀'

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🚀 بدء تشغيل البوت على المنفذ {port}")
    app.run(host='0.0.0.0', port=port)
