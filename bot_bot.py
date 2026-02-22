import os
import logging
from flask import Flask, request
from telegram import Bot, Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('BOT_TOKEN')
PORT = int(os.getenv('PORT', 8080))

bot = Bot(token=TOKEN)
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """استقبال التحديثات من تيليجرام"""
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        if update.message and update.message.text:
            text = update.message.text
            chat_id = update.message.chat_id
            
            if text == '/start':
                bot.send_message(chat_id=chat_id, text="✅ البوت يعمل!")
            else:
                bot.send_message(chat_id=chat_id, text=f"استقبلت: {text}")
        return 'OK', 200
    except Exception as e:
        logger.error(f"خطأ: {e}")
        return 'Error', 500

@app.route('/')
def home():
    return "البوت شغال! 🚀"

if __name__ == '__main__':
    logger.info(f"🚀 تشغيل البوت على المنفذ {PORT}")
    app.run(host='0.0.0.0', port=PORT)
