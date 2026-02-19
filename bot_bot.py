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
# نظام حساب النجوم حسب مدة الفيديو (للمستخدم)
# =========================
def calculate_stars(duration_seconds, is_first_video_today=False):
    """
    حساب عدد النجوم التي سيدفعها المستخدم حسب مدة الفيديو
    
    القواعد:
    - إذا كان أول فيديو لليوم وأقل من دقيقة = مجاني
    - أول فيديو لليوم وأكثر من دقيقة = 2 نجوم فقط (سعر مخفض)
    - باقي الفيديوهات:
        * أقل من دقيقة = 1 نجمة
        * 1-5 دقائق = نجمة لكل دقيقة
        * 5-30 دقيقة = نجمة لكل دقيقتين
        * 30-60 دقيقة = نجمة لكل 3 دقائق
        * أكثر من ساعة = نجمة لكل 5 دقائق
    """
    if is_first_video_today:
        if duration_seconds < 60:
            return 0  # مجاني
        else:
            return 2  # سعر مخفض لأول فيديو طويل
    
    if duration_seconds < 60:
        return 1
    
    minutes = duration_seconds / 60
    
    if minutes <= 5:
        return int(minutes)
    
    if minutes <= 30:
        base = 5
        extra = (minutes - 5) / 2
        return int(base + extra)
    
    if minutes <= 60:
        base = 17
        extra = (minutes - 30) / 3
        return int(base + extra)
    
    base = 27
    extra = (minutes - 60) / 5
    return int(base + extra)

async def get_video_duration(url):
    """الحصول على مدة الفيديو"""
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(yl.extract_info, url, download=False)
            return info.get('duration', 0)
    except:
        return 0

# =========================
# نظام أول فيديو كل يوم (مجاني أو مخفض)
# =========================
user_first_video = {}  # تخزين حالة أول فيديو لكل مستخدم

def check_first_video_status(user_id):
    """التحقق من حالة أول فيديو للمستخدم اليوم"""
    today = date.today()
    
    if user_id not in user_first_video:
        user_first_video[user_id] = today
        return True  # أول فيديو اليوم
    
    last_first = user_first_video[user_id]
    
    if last_first < today:
        user_first_video[user_id] = today
        return True  # يوم جديد -> أول فيديو
    else:
        return False  # ليس أول فيديو

# =========================
# قاعدة بيانات بسيطة لتخزين إحصائياتك (اختياري)
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
    """تسجيل الأرباح (لمعرفتك أنت فقط)"""
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
# معالج أمر /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_lang:
        user_lang[user_id] = 'ar'
    
    # التحقق من حالة أول فيديو لليوم
    is_first = check_first_video_status(user_id)
    
    first_video_text = ""
    if is_first:
        first_video_text = "\n🎁 أول فيديو اليوم: أقل من دقيقة مجاني، أكثر من دقيقة نجمتين فقط!"
    
    keyboard = [
        [KeyboardButton("اللغة 🌐"), KeyboardButton(get_text('help_btn', user_lang[user_id]))],
        [KeyboardButton("إعادة التشغيل 🔄")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = (
        f"🎬 أهلاً بك في بوت التحميل!{first_video_text}\n\n"
        "💰 **نظام الأسعار:**\n"
        "• فيديو أقل من دقيقة = ⭐1\n"
        "• 1-5 دقائق = ⭐ لكل دقيقة\n"
        "• 5-30 دقيقة = ⭐ لكل دقيقتين\n"
        "• 30-60 دقيقة = ⭐ لكل 3 دقائق\n"
        "• أكثر من ساعة = ⭐ لكل 5 دقائق\n\n"
        "🎁 **عرض خاص:** أول فيديو كل يوم:\n"
        "• أقل من دقيقة = مجاني!\n"
        "• أكثر من دقيقة = نجمتين فقط!\n\n"
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
    
    help_text = get_text('help', lang)
    
    if lang == 'ar':
        help_text += "\n\n📖 **تعليمات التحميل:**\n\n"
        help_text += "1️⃣ أرسل رابط الفيديو\n"
        help_text += "2️⃣ اختر الجودة المطلوبة\n"
        help_text += "3️⃣ ادفع النجوم المطلوبة\n"
        help_text += "4️⃣ استلم الفيديو\n\n"
        help_text += "💰 **نظام الأسعار:**\n"
        help_text += "• أول فيديو باليوم (أقل من دقيقة) = مجاني!\n"
        help_text += "• أول فيديو باليوم (أكثر من دقيقة) = ⭐2\n"
        help_text += "• باقي الفيديوهات حسب المدة\n\n"
        help_text += "⭐ **النجوم:** تشتريها من تيليجرام عبر @wallet"
    else:
        help_text += "\n\n📖 **Instructions:**\n\n"
        help_text += "1️⃣ Send video link\n"
        help_text += "2️⃣ Choose quality\n"
        help_text += "3️⃣ Pay required stars\n"
        help_text += "4️⃣ Get video\n\n"
        help_text += "💰 **Pricing:**\n"
        help_text += "• First video (less than 1 min) = FREE!\n"
        help_text += "• First video (more than 1 min) = ⭐2\n"
        help_text += "• Other videos based on duration"
    
    await update.message.reply_text(help_text)

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
        "اختر اللغة:" if user_lang.get(user_id, 'ar') == 'ar' else "Choose language:",
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
    
    await update.message.reply_text(
        "🔄 تم إعادة التشغيل" if lang == 'ar' else "🔄 Restarted"
    )
    await start(update, context)

# =========================
# معالج الروابط وعرض خيارات الجودة
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    # معالجة أزرار القائمة
    if text in ["اللغة 🌐", "Language 🌐"]:
        await language_command(update, context)
        return
    elif text in ["المساعدة 📖", get_text('help_btn', 'en')]:
        await help_command(update, context)
        return
    elif text in ["إعادة التشغيل 🔄", get_text('restart_btn', 'en')]:
        await restart_command(update, context)
        return
    
    # معالجة الروابط
    if text.startswith(('http://', 'https://')):
        # حفظ الرابط مؤقتاً
        context.user_data['download_url'] = text
        
        # التحقق من حالة أول فيديو لليوم
        is_first = check_first_video_status(user_id)
        
        # حساب مدة الفيديو والنجوم المطلوبة
        duration = await get_video_duration(text)
        stars_needed = calculate_stars(duration, is_first)
        
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        
        stars_display = "مجاني" if stars_needed == 0 else f"⭐{stars_needed}"
        
        # رسالة المدة
        duration_text = f"\n⏱️ المدة: {minutes}:{seconds:02d}"
        
        if is_first:
            if stars_needed == 0:
                duration_text += "\n🎁 أول فيديو اليوم وأقل من دقيقة → مجاني!"
            else:
                duration_text += f"\n🎁 أول فيديو اليوم → سعر خاص: {stars_display}"
        
        keyboard = [
            [
                InlineKeyboardButton(f"480p 🎬 {stars_display}", callback_data=f'quality_480p_{stars_needed}'),
                InlineKeyboardButton(f"720p 🎬 {stars_display}", callback_data=f'quality_720p_{stars_needed}')
            ],
            [
                InlineKeyboardButton(f"أفضل جودة ✨ {stars_display}", callback_data=f'quality_best_{stars_needed}'),
                InlineKeyboardButton(f"صوت 🎵 {stars_display}", callback_data=f'quality_audio_{stars_needed}')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎯 اختر جودة التحميل:{duration_text}",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "❌ رابط غير صالح" if lang == 'ar' else "❌ Invalid link"
        )

# =========================
# معالج الأزرار (اختيار الجودة وطلب الدفع)
# =========================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    # معالجة تغيير اللغة
    if data.startswith('lang_'):
        new_lang = data.split('_')[1]
        user_lang[user_id] = new_lang
        await query.edit_message_text("✅ تم تغيير اللغة" if new_lang == 'ar' else "✅ Language changed")
        return
    
    # معالجة اختيار الجودة وطلب الدفع
    if data.startswith('quality_'):
        parts = data.split('_')
        quality = parts[1]
        stars_needed = int(parts[2])
        
        url = context.user_data.get('download_url')
        if not url:
            await query.edit_message_text("❌ حدث خطأ، أعد إرسال الرابط")
            return
        
        if stars_needed == 0:
            # تحميل مجاني
            await query.edit_message_text("⏳ جاري التحميل المجاني...")
            
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
                else:
                    await query.edit_message_text("❌ فشل التحميل")
            except Exception as e:
                logger.error(f"Download error: {e}")
                await query.edit_message_text("❌ حدث خطأ في التحميل")
        else:
            # طلب دفع بالنجوم
            title = "تحميل فيديو" if quality != 'audio' else "تحميل صوت"
            description = f"تحميل بجودة {quality} ⭐{stars_needed}"
            payload = f"{quality}_{stars_needed}_{user_id}"
            prices = [LabeledPrice("سعر التحميل", stars_needed)]
            
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
    
    # استخراج معلومات الدفع
    payload = update.message.successful_payment.invoice_payload
    parts = payload.split('_')
    quality = parts[0]
    stars_paid = int(parts[1])
    
    # تسجيل الأرباح (لمعرفتك أنت فقط)
    add_earnings(stars_paid)
    
    url = context.user_data.get('download_url')
    if not url:
        await update.message.reply_text("❌ حدث خطأ")
        return
    
    status_msg = await update.message.reply_text("⏳ جاري التحميل بعد الدفع...")
    
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
        else:
            await status_msg.edit_text("❌ فشل التحميل")
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status_msg.edit_text("❌ حدث خطأ في التحميل")

# =========================
# معالج التحقق قبل الدفع
# =========================
async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

# =========================
# أمر إحصائيات (للمطور فقط) - لمعرفة أرباحك
# =========================
async def owner_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    OWNER_ID = 123456789  # ضع معرفك هنا
    
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
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("stats", owner_stats))  # للمطور فقط
    
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ البوت يعمل الآن (المستخدم يدفع وأنت تربح)")
    app.run_polling()
