import os
import logging
from flask import Flask, request
from telegram import Bot, Update
import asyncio

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(), bot)
    asyncio.run(handle_update(update))
    return 'OK', 200

async def handle_update(update):
    if update.message and update.message.text == '/start':
        await update.message.reply_text('✅ البوت يعمل!')

@app.route('/')
def home():
    return 'Bot is running!'

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
