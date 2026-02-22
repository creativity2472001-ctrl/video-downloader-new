import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت يعمل! 🎉")

if __name__ == '__main__':
    TOKEN = os.getenv('BOT_TOKEN', '8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA')
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    PORT = int(os.getenv('PORT', 8080))
    RAILWAY_URL = os.getenv('RAILWAY_STATIC_URL')
    
    if RAILWAY_URL:
        print(f"🚀 تشغيل على Railway مع Webhook")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="webhook",
            webhook_url=f"https://{RAILWAY_URL}/webhook"
        )
    else:
        print("💻 تشغيل محلي")
        app.run_polling()
