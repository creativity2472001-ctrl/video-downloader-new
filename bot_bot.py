import os
import json
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from typing import Optional
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, PreCheckoutQueryHandler, filters, ContextTypes
from utils import get_text, download_media

# =========================
# إعداد التسجيل
# =========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =========================
# نظام حساب النجوم حسب مدة الفيديو
# =========================
def calculate_stars(duration_seconds, is_first_video_today=False):
    if is_first_video_today:
        if duration_seconds < 60:
            return 0
        else:
            return 2
    
    if duration_seconds < 60:
        return 0
    
    minutes = (duration_seconds + 59) // 60
    return minutes

async def get_video_duration(url):
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            return info.get('duration', 0)
    except:
        return 0

# =========================
# نظام أول فيديو كل يوم
# =========================
def init_first_video_db():
    conn = sqlite3.connect('first_video.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS first_video (
            user_id INTEGER PRIMARY KEY,
            last_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_first_video_db()

def check_first_video_status(user_id):
    today = date.today().isoformat()
    
    conn = sqlite3.connect('first_video.db')
    c = conn.cursor()
    
    c.execute("SELECT last_date FROM first_video WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    
    if not row:
        c.execute("INSERT INTO first_video (user_id, last_date) VALUES (?, ?)", 
                 (user_id, today))
        conn.commit()
        conn.close()
        return True
    
    last_date = row[0]
    
    if last_date < today:
        c.execute("UPDATE first_video SET last_date = ? WHERE user_id = ?", 
                 (today, user_id))
        conn.commit()
        conn.close()
        return True
    else:
        conn.close()
        return False

# =========================
# قاعدة بيانات الإحصائيات
# =========================
stats_db = sqlite3.connect('bot_stats.db', check_same_thread=False)
stats_cursor = stats_db.cursor()

stats_cursor.execute('''
CREATE TABLE IF NOT EXISTS bot_earnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    total_stars INTEGER DEFAULT 0,
    total_downloads INTEGER DEFAULT 0
)
''')
stats_db.commit()

def add_earnings(stars: int):
    today = datetime.now().strftime('%Y-%m-%d')
    stats_cursor.execute('''
    INSERT INTO bot_earnings (date, total_stars, total_downloads)
    VALUES (?, ?, 1)
    ON CONFLICT(date) DO UPDATE SET
        total_stars = total_stars + ?,
        total_downloads = total_downloads + 1
    ''', (today, stars, stars))
    stats_db.commit()

# =========================
# تخزين لغة المستخدم
# =========================
user_lang = {}

# =========================
# معالج /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_lang:
        user_lang[user_id] = 'ar'
    
    is_first = check_first_video_status(user_id)
    
    first_video_text = ""
    if is_first:
        first_video_text = "\n🎁 أول فيديو اليوم: أقل من دقيقة مجاني، أكثر من دقيقة نجمتين فقط!"
    
    keyboard = [
        [KeyboardButton(get_text('language_btn', user_lang[user_id])), 
         KeyboardButton(get_text('help_btn', user_lang[user_id]))],
        [KeyboardButton(get_text('restart_btn', user_lang[user_id]))]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = (
        f"🎬 أهلاً بك في بوت التحميل!{first_video_text}\n\n"
        "💰 **نظام الأسعار:**\n"
        "• أقل من دقيقة = مجاني ✅\n"
        "• أول فيديو باليوم (أكثر من دقيقة) = ⭐2\n"
        "• باقي الفيديوهات = كل دقيقة = نجمة ⭐\n\n"
        "أرسل رابط فيديو للبدء"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup
    )

# =========================
# معالج المساعدة
# =========================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    await update.message.reply_text(get_text('help_full', lang))

# =========================
# معالج اللغة
# =========================
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🇸🇦 عربي", callback_data='lang_ar'),
         InlineKeyboardButton("🇺🇸 English", callback_data='lang_en')],
        [InlineKeyboardButton("🇹🇷 Türkçe", callback_data='lang_tr'),
         InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        get_text('choose_lang', user_lang.get(user_id, 'ar')),
        reply_markup=reply_markup
    )

# =========================
# معالج إعادة التشغيل
# =========================
async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    if user_id in context.user_data:
        context.user_data.clear()
    
    await update.message.reply_text(get_text('queue_restarted', lang))
    await start(update, context)

# =========================
# معالج الروابط
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    # معالجة أزرار القائمة
    if text in [get_text('language_btn', 'ar'), get_text('language_btn', 'en'),
                get_text('language_btn', 'tr'), get_text('language_btn', 'ru')]:
        await language_command(update, context)
        return
    elif text in [get_text('help_btn', 'ar'), get_text('help_btn', 'en'),
                  get_text('help_btn', 'tr'), get_text('help_btn', 'ru')]:
        await help_command(update, context)
        return
    elif text in [get_text('restart_btn', 'ar'), get_text('restart_btn', 'en'),
                  get_text('restart_btn', 'tr'), get_text('restart_btn', 'ru')]:
        await restart_command(update, context)
        return
    
    # معالجة الروابط
    if text.startswith(('http://', 'https://')):
        context.user_data['download_url'] = text
        
        is_first = check_first_video_status(user_id)
        duration = await get_video_duration(text)
        stars_needed = calculate_stars(duration, is_first)
        
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        
        stars_display = get_text('free_label', lang) if stars_needed == 0 else f"⭐{stars_needed}"
        duration_text = f"\n⏱️ {get_text('duration', lang)}: {minutes}:{seconds:02d}"
        
        keyboard = [
            [
                InlineKeyboardButton(f"480p 🎬 {stars_display}", callback_data=f'quality_480p_{stars_needed}'),
                InlineKeyboardButton(f"720p 🎬 {stars_display}", callback_data=f'quality_720p_{stars_needed}')
            ],
            [
                InlineKeyboardButton(f"{get_text('quality_best', lang)} ✨ {stars_display}", callback_data=f'quality_best_{stars_needed}'),
                InlineKeyboardButton(f"{get_text('audio_only', lang)} 🎵 {stars_display}", callback_data=f'quality_audio_{stars_needed}')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"{get_text('choose_quality', lang)}:{duration_text}",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(get_text('invalid_link', lang))

# =========================
# معالج الأزرار
# =========================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    if data.startswith('lang_'):
        new_lang = data.split('_')[1]
        user_lang[user_id] = new_lang
        await query.edit_message_text(get_text('lang_set', new_lang))
        return
    
    if data.startswith('quality_'):
        parts = data.split('_')
        quality = parts[1]
        stars_needed = int(parts[2])
        
        url = context.user_data.get('download_url')
        if not url:
            await query.delete()
            return
        
        if stars_needed == 0:
            await query.edit_message_text(get_text('downloading', lang))
            
            try:
                file_path = await download_media(url, quality, user_id)
                
                if file_path and os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        if quality == 'audio':
                            await context.bot.send_audio(chat_id=user_id, audio=f)
                        else:
                            await context.bot.send_video(chat_id=user_id, video=f)
                    
                    os.remove(file_path)
                    await query.delete()
            except Exception as e:
                logger.error(f"Download error: {e}")
        else:
            title = get_text('download_title', lang) if quality != 'audio' else get_text('audio_title', lang)
            description = get_text('payment_desc', lang, stars=stars_needed)
            payload = f"{quality}_{stars_needed}_{user_id}"
            prices = [LabeledPrice(get_text('download_price', lang), stars_needed)]
            
            await context.bot.send_invoice(
                chat_id=user_id,
                title=title,
                description=description,
                payload=payload,
                provider_token="",
                currency="XTR",
                prices=prices
            )
            
            await query.message.delete()

# =========================
# معالج الدفع الناجح
# =========================
async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    payload = update.message.successful_payment.invoice_payload
    parts = payload.split('_')
    quality = parts[0]
    stars_paid = int(parts[1])
    
    add_earnings(stars_paid)
    
    url = context.user_data.get('download_url')
    if not url:
        return
    
    status_msg = await update.message.reply_text(get_text('downloading', lang))
    
    try:
        file_path = await download_media(url, quality, user_id)
        
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                if quality == 'audio':
                    await context.bot.send_audio(chat_id=user_id, audio=f)
                else:
                    await context.bot.send_video(chat_id=user_id, video=f)
            
            os.remove(file_path)
            await status_msg.delete()
    except Exception as e:
        logger.error(f"Download error: {e}")

# =========================
# معالج التحقق قبل الدفع
# =========================
async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

# =========================
# أمر إحصائيات للمطور
# =========================
async def owner_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    OWNER_ID = 8373058261
    
    if user_id != OWNER_ID:
        return
    
    stats_cursor.execute("SELECT date, total_stars FROM bot_earnings ORDER BY date DESC LIMIT 7")
    rows = stats_cursor.fetchall()
    
    text = "📊 **إحصائيات الأرباح (آخر 7 أيام):**\n\n"
    total = 0
    
    for date_str, stars in rows:
        text += f"• {date_str}: ⭐{stars}\n"
        total += stars
    
    text += f"\n💰 **الإجمالي: ⭐{total}**"
    
    await update.message.reply_text(text)

# =========================
# التشغيل الرئيسي
# =========================
if __name__ == '__main__':
    TOKEN = os.getenv('BOT_TOKEN', '8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA')
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("stats", owner_stats))
    
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # تشغيل Polling (لأننا على Railway)
    print("✅ البوت يعمل...")
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv('PORT', 8080)),
        url_path="webhook",
        webhook_url=f"https://{os.getenv('RAILWAY_STATIC_URL')}/webhook"
    )
