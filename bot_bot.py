import os
import json
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from typing import Optional
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
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
    """
    حساب عدد النجوم المطلوبة حسب مدة الفيديو
    
    القواعد:
    - إذا كان أول فيديو لليوم:
        * أقل من دقيقة = مجاني (0 نجوم)
        * أكثر من دقيقة = سعر مخفض (نجمتين فقط مهما كانت المدة)
    - للفيديوهات التالية:
        * أقل من دقيقة = نجمة واحدة
        * 1-5 دقائق = نجمة لكل دقيقة
        * 5-30 دقيقة = نجمة لكل دقيقتين
        * 30-60 دقيقة = نجمة لكل 3 دقائق
        * أكثر من ساعة = نجمة لكل 5 دقائق
    """
    if is_first_video_today:
        if duration_seconds < 60:  # أقل من دقيقة
            return 0  # مجاني
        else:
            return 2  # سعر ثابت مخفض (نجمتين فقط) لأول فيديو مهما كان طويلاً
    
    # للفيديوهات التالية في نفس اليوم
    if duration_seconds < 60:  # أقل من دقيقة
        return 1
    
    minutes = duration_seconds / 60
    
    if minutes <= 5:  # 1-5 دقائق
        return int(minutes)  # نجمة لكل دقيقة
    
    if minutes <= 30:  # 5-30 دقيقة
        base = 5  # أول 5 دقائق ب 5 نجوم
        extra = (minutes - 5) / 2  # كل دقيقتين بعد الـ 5 = نجمة
        return int(base + extra)
    
    if minutes <= 60:  # 30-60 دقيقة
        base = 17  # 5 + (25/2) = 17.5
        extra = (minutes - 30) / 3  # كل 3 دقائق = نجمة
        return int(base + extra)
    
    # أكثر من ساعة
    base = 27  # 17 + (30/3) = 27
    extra = (minutes - 60) / 5  # كل 5 دقائق = نجمة
    return int(base + extra)

async def get_video_duration(url):
    """الحصول على مدة الفيديو قبل التحميل"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            duration = info.get('duration', 0)
            return duration
    except Exception as e:
        logger.error(f"Error getting video duration: {e}")
        return 0  # إذا فشل، نعتبره فيديو قصير

# =========================
# نظام أول فيديو كل يوم
# =========================
user_free_downloads = {}  # تخزين آخر تحميل مجاني لكل مستخدم
user_first_video_done = {}  # تخزين إذا المستخدم استخدم أول فيديو اليوم

def check_first_video_status(user_id):
    """التحقق من حالة أول فيديو للمستخدم اليوم"""
    today = date.today()
    
    # التحقق من استخدام أول فيديو
    if user_id in user_first_video_done:
        last_first = user_first_video_done.get(user_id)
        if last_first == today:
            return False  # استخدم أول فيديو اليوم بالفعل
        else:
            # يوم جديد
            user_first_video_done[user_id] = today
            return True
    else:
        # أول مرة
        user_first_video_done[user_id] = today
        return True

def check_free_download(user_id):
    """التحقق من توفر تحميل مجاني للمستخدم اليوم (أقل من دقيقة)"""
    today = date.today()
    
    if user_id not in user_free_downloads:
        user_free_downloads[user_id] = today
        return True
    
    last_free = user_free_downloads[user_id]
    
    if last_free < today:
        user_free_downloads[user_id] = today
        return True
    else:
        return False

# =========================
# نظام الإعلانات الإجبارية
# =========================
@dataclass
class AdConfig:
    CLICK_URL: str = os.getenv('CLICK_URL', "https://adsgram.ai/c/temp_click_url")
    REWARD_URL: str = os.getenv('REWARD_URL', "https://temp-domain.com/reward")
    MAX_ADS_PER_DAY: int = int(os.getenv('MAX_ADS_PER_DAY', '30'))
    AD_COOLDOWN: int = int(os.getenv('AD_COOLDOWN', '300'))
    MIN_WITHDRAWAL: float = float(os.getenv('MIN_WITHDRAWAL', '10.0'))
    BASE_URL: str = os.getenv('RAILWAY_STATIC_URL', '')

# =========================
# قاعدة بيانات الإعلانات
# =========================
ads_db = sqlite3.connect('ads_data.db', check_same_thread=False)
ads_cursor = ads_db.cursor()

ads_cursor.executescript('''
CREATE TABLE IF NOT EXISTS user_ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    ad_id TEXT,
    watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed BOOLEAN DEFAULT 0,
    earned REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pending_downloads (
    user_id INTEGER PRIMARY KEY,
    video_url TEXT NOT NULL,
    quality TEXT DEFAULT 'best',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ads_stats (
    user_id INTEGER,
    date TEXT,
    count INTEGER DEFAULT 0,
    earned_today REAL DEFAULT 0,
    PRIMARY KEY (user_id, date)
);

CREATE TABLE IF NOT EXISTS user_earnings (
    user_id INTEGER PRIMARY KEY,
    total_earned REAL DEFAULT 0,
    pending_earned REAL DEFAULT 0,
    withdrawn REAL DEFAULT 0,
    last_withdrawal TIMESTAMP,
    wallet_address TEXT
);

CREATE TABLE IF NOT EXISTS withdrawal_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    wallet_address TEXT,
    status TEXT DEFAULT 'pending',
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_earnings(user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_ads_user_id ON user_ads(user_id);
CREATE INDEX IF NOT EXISTS idx_user_ads_watched_at ON user_ads(watched_at);
CREATE INDEX IF NOT EXISTS idx_ads_stats_date ON ads_stats(date);
''')
ads_db.commit()

# =========================
# دوال الإعلانات المساعدة
# =========================
def get_user_ads_today(user_id: int) -> int:
    today = datetime.now().strftime('%Y-%m-%d')
    ads_cursor.execute(
        "SELECT count FROM ads_stats WHERE user_id=? AND date=?",
        (user_id, today)
    )
    row = ads_cursor.fetchone()
    return row[0] if row else 0

def increment_user_ads(user_id: int, earned: float = 0.01):
    today = datetime.now().strftime('%Y-%m-%d')
    ads_cursor.execute('''
    INSERT INTO ads_stats (user_id, date, count, earned_today) 
    VALUES (?, ?, 1, ?)
    ON CONFLICT(user_id, date) DO UPDATE SET 
        count = count + 1,
        earned_today = earned_today + ?
    ''', (user_id, today, earned, earned))
    ads_db.commit()

def update_user_earnings(user_id: int, amount: float):
    ads_cursor.execute('''
    INSERT INTO user_earnings (user_id, total_earned, pending_earned)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        total_earned = total_earned + ?,
        pending_earned = pending_earned + ?
    ''', (user_id, amount, amount, amount, amount))
    ads_db.commit()

def save_pending_download(user_id: int, url: str, quality: str = 'best'):
    ads_cursor.execute('''
    INSERT OR REPLACE INTO pending_downloads (user_id, video_url, quality)
    VALUES (?, ?, ?)
    ''', (user_id, url, quality))
    ads_db.commit()
    logger.info(f"Saved pending download for user {user_id}")

def get_pending_download(user_id: int) -> tuple:
    ads_cursor.execute(
        "SELECT video_url, quality FROM pending_downloads WHERE user_id=?",
        (user_id,)
    )
    row = ads_cursor.fetchone()
    return row if row else (None, None)

def clear_pending_download(user_id: int):
    ads_cursor.execute("DELETE FROM pending_downloads WHERE user_id=?", (user_id,))
    ads_db.commit()

def get_user_earnings(user_id: int) -> dict:
    ads_cursor.execute(
        "SELECT total_earned, pending_earned, withdrawn FROM user_earnings WHERE user_id=?",
        (user_id,)
    )
    row = ads_cursor.fetchone()
    if row:
        return {
            'total': row[0],
            'pending': row[1],
            'withdrawn': row[2]
        }
    return {'total': 0, 'pending': 0, 'withdrawn': 0}

# =========================
# تخزين لغة المستخدم
# =========================
user_lang = {}

# =========================
# معالجات الأوامر الرئيسية
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_lang:
        user_lang[user_id] = 'ar'
    
    # التحقق من حالة أول فيديو لليوم
    is_first = check_first_video_status(user_id)
    free_available = check_free_download(user_id)
    
    first_video_text = ""
    if is_first:
        if free_available:
            first_video_text = " (أول فيديو اليوم مجاني إذا كان أقل من دقيقة!)"
        else:
            first_video_text = " (أول فيديو اليوم بسعر مخفض: نجمتين فقط مهما كانت مدته!)"
    
    keyboard = [
        [KeyboardButton("اللغة 🌐"), KeyboardButton(get_text('help_btn', user_lang[user_id]))],
        [KeyboardButton("أرباحي 💰"), KeyboardButton(get_text('restart_btn', user_lang[user_id]))]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = (
        f"🎬 أهلاً بك في بوت التحميل!{first_video_text}\n\n"
        "📺 نظام الأسعار:\n"
        "• فيديو أقل من دقيقة = ⭐1\n"
        "• 1-5 دقائق = ⭐ لكل دقيقة\n"
        "• 5-30 دقائق = ⭐ لكل دقيقتين\n"
        "• 30-60 دقيقة = ⭐ لكل 3 دقائق\n"
        "• أكثر من ساعة = ⭐ لكل 5 دقائق\n\n"
        "🎁 أول فيديو كل يوم:\n"
        "• أقل من دقيقة = مجاني!\n"
        "• أكثر من دقيقة = نجمتين فقط!\n\n"
        f"💰 كل إعلان تشاهده = ربح 0.01 دولار\n"
        f"• الحد الأدنى للسحب: {AdConfig.MIN_WITHDRAWAL} دولار\n\n"
        "أرسل رابط فيديو للبدء"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    help_text = get_text('help', lang)
    
    if lang == 'ar':
        help_text += "\n\n📖 **تعليمات التحميل:**\n\n"
        help_text += "1️⃣ اذهب إلى تطبيق Instagram/TikTok/Pinterest/Likee/YouTube\n"
        help_text += "2️⃣ اختر الفيديو الذي تريده\n"
        help_text += "3️⃣ اضغط على زر ↪️ أو الثلاث نقاط في الأعلى\n"
        help_text += "4️⃣ اضغط على زر **نسخ الرابط**\n"
        help_text += "5️⃣ أرسل الرابط هنا\n\n"
        help_text += "💰 **نظام الأسعار:**\n"
        help_text += "• فيديو أقل من دقيقة = ⭐1\n"
        help_text += "• 1-5 دقائق = ⭐ لكل دقيقة\n"
        help_text += "• 5-30 دقائق = ⭐ لكل دقيقتين\n"
        help_text += "• 30-60 دقيقة = ⭐ لكل 3 دقائق\n"
        help_text += "• أكثر من ساعة = ⭐ لكل 5 دقائق\n\n"
        help_text += "🎁 **أول فيديو كل يوم:**\n"
        help_text += "• أقل من دقيقة = مجاني!\n"
        help_text += "• أكثر من دقيقة = نجمتين فقط!\n\n"
        help_text += "💰 **نظام الأرباح:**\n"
        help_text += "• كل إعلان تشاهده = 0.01 دولار\n"
        help_text += f"• الحد الأدنى للسحب: {AdConfig.MIN_WITHDRAWAL} دولار\n"
        help_text += "• اسحب أرباحك عبر USDT (TRC20)\n\n"
        help_text += "🌐 يمكنك تغيير اللغة من زر **اللغة** في القائمة"
    else:
        help_text += "\n\n📖 **Download Instructions:**\n\n"
        help_text += "1️⃣ Go to Instagram/TikTok/Pinterest/Likee/YouTube app\n"
        help_text += "2️⃣ Choose a video you like\n"
        help_text += "3️⃣ Tap the ↪️ button or the three dots\n"
        help_text += "4️⃣ Tap the **Copy** button\n"
        help_text += "5️⃣ Send the link here\n\n"
        help_text += "💰 **Pricing System:**\n"
        help_text += "• Video less than 1 minute = ⭐1\n"
        help_text += "• 1-5 minutes = ⭐ per minute\n"
        help_text += "• 5-30 minutes = ⭐ per 2 minutes\n"
        help_text += "• 30-60 minutes = ⭐ per 3 minutes\n"
        help_text += "• More than 1 hour = ⭐ per 5 minutes\n\n"
        help_text += "🎁 **First video every day:**\n"
        help_text += "• Less than 1 minute = FREE!\n"
        help_text += "• More than 1 minute = only 2 stars!\n\n"
        help_text += "💰 **Earnings System:**\n"
        help_text += "• Each ad you watch = $0.01\n"
        help_text += f"• Minimum withdrawal: ${AdConfig.MIN_WITHDRAWAL}\n"
        help_text += "• Withdraw via USDT (TRC20)\n\n"
        help_text += "🌐 You can change language from the **Language** button"
    
    await update.message.reply_text(help_text)

async def earnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    earnings = get_user_earnings(user_id)
    ads_today = get_user_ads_today(user_id)
    
    if lang == 'ar':
        text = (
            f"💰 **أرباحك الحالية:**\n\n"
            f"• الإجمالي: {earnings['total']:.3f} USDT\n"
            f"• معلق: {earnings['pending']:.3f} USDT\n"
            f"• تم السحب: {earnings['withdrawn']:.3f} USDT\n\n"
            f"📊 **إحصائيات اليوم:**\n"
            f"• إعلانات اليوم: {ads_today}/{AdConfig.MAX_ADS_PER_DAY}\n"
            f"• أرباح اليوم: {ads_today * 0.01:.3f} USDT\n\n"
            f"💳 **للسحب:** أرسل /withdraw [عنوان USDT]"
        )
    else:
        text = (
            f"💰 **Your Earnings:**\n\n"
            f"• Total: {earnings['total']:.3f} USDT\n"
            f"• Pending: {earnings['pending']:.3f} USDT\n"
            f"• Withdrawn: {earnings['withdrawn']:.3f} USDT\n\n"
            f"📊 **Today's Stats:**\n"
            f"• Ads today: {ads_today}/{AdConfig.MAX_ADS_PER_DAY}\n"
            f"• Today's earnings: {ads_today * 0.01:.3f} USDT\n\n"
            f"💳 **To withdraw:** Send /withdraw [USDT address]"
        )
    
    keyboard = [[InlineKeyboardButton(
        "💸 طلب سحب" if lang == 'ar' else "💸 Request Withdrawal",
        callback_data="request_withdrawal"
    )]]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    earnings = get_user_earnings(user_id)
    
    if len(context.args) == 0:
        await update.message.reply_text(
            "❌ يرجى إرسال عنوان USDT الخاص بك\nمثال: /withdraw TVd2P6p8hR7Xq..." if lang == 'ar' else
            "❌ Please send your USDT address\nExample: /withdraw TVd2P6p8hR7Xq..."
        )
        return
    
    wallet = context.args[0]
    
    if earnings['pending'] < AdConfig.MIN_WITHDRAWAL:
        await update.message.reply_text(
            f"❌ الحد الأدنى للسحب {AdConfig.MIN_WITHDRAWAL} USDT\n"
            f"رصيدك الحالي: {earnings['pending']:.3f} USDT" if lang == 'ar' else
            f"❌ Minimum withdrawal is {AdConfig.MIN_WITHDRAWAL} USDT\n"
            f"Your balance: {earnings['pending']:.3f} USDT"
        )
        return
    
    ads_cursor.execute('''
    INSERT INTO withdrawal_requests (user_id, amount, wallet_address)
    VALUES (?, ?, ?)
    ''', (user_id, earnings['pending'], wallet))
    ads_db.commit()
    
    ads_cursor.execute('''
    UPDATE user_earnings 
    SET pending_earned = 0 
    WHERE user_id = ?
    ''', (user_id,))
    ads_db.commit()
    
    await update.message.reply_text(
        "✅ تم إرسال طلب السحب بنجاح!\n"
        "سيتم مراجعته وصرفه خلال 24-48 ساعة." if lang == 'ar' else
        "✅ Withdrawal request sent successfully!\n"
        "It will be processed within 24-48 hours."
    )

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

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    if user_id in context.user_data:
        context.user_data.clear()
    
    await update.message.reply_text(
        "🔄 تم إعادة التشغيل" if lang == 'ar' else "🔄 Restarted"
    )
    await start(update, context)

async def show_quality_options(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """عرض خيارات الجودة مع حساب النجوم حسب المدة"""
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    # حفظ الرابط مؤقتاً
    context.user_data['download_url'] = url
    
    # التحقق من حالة أول فيديو لليوم
    is_first_video = check_first_video_status(user_id)
    
    # حساب مدة الفيديو والنجوم المطلوبة
    duration = await get_video_duration(url)
    stars_needed = calculate_stars(duration, is_first_video)
    
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    
    # تحديد عرض النجوم
    if stars_needed == 0:
        stars_display = "مجاني"
        payment_type = "free"
    else:
        stars_display = f"⭐{stars_needed}"
        payment_type = "paid"
    
    # رسالة المدة
    duration_text = f"\n⏱️ المدة: {minutes}:{seconds:02d}"
    
    if is_first_video:
        if stars_needed == 0:
            duration_text += "\n🎁 هذا أول فيديو لك اليوم وأقل من دقيقة → مجاني!"
        else:
            duration_text += f"\n🎁 هذا أول فيديو لك اليوم → سعر خاص: {stars_display}"
    
    keyboard = [
        [
            InlineKeyboardButton(f"480p 🎬 {stars_display}", 
                               callback_data=f'quality_480p_{payment_type}'),
            InlineKeyboardButton(f"720p 🎬 {stars_display}", 
                               callback_data=f'quality_720p_{payment_type}')
        ],
        [
            InlineKeyboardButton(f"أفضل جودة ✨ {stars_display}", 
                               callback_data=f'quality_best_{payment_type}'),
            InlineKeyboardButton(f"صوت 🎵 {stars_display}", 
                               callback_data=f'quality_audio_{payment_type}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎯 اختر جودة التحميل:{duration_text}",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    # معالجة أزرار القائمة
    if text in ["اللغة 🌐", "Language 🌐"]:
        await language_command(update, context)
        return
    elif text in ["المساعدة 📖", get_text('help_btn', 'en'), get_text('help_btn', 'tr'), get_text('help_btn', 'ru')]:
        await help_command(update, context)
        return
    elif text in ["أرباحي 💰", "Earnings 💰"]:
        await earnings_command(update, context)
        return
    elif text in ["إعادة التشغيل 🔄", get_text('restart_btn', 'en'), get_text('restart_btn', 'tr'), get_text('restart_btn', 'ru')]:
        await restart_command(update, context)
        return
    
    # معالجة الروابط
    if text.startswith(('http://', 'https://')):
        # عرض خيارات الجودة مع حساب النجوم
        await show_quality_options(update, context, text)
    else:
        await update.message.reply_text(
            "❌ رابط غير صالح" if lang == 'ar' else "❌ Invalid link"
        )

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
        
        messages = {
            'ar': "✅ تم تغيير اللغة إلى العربية",
            'en': "✅ Language changed to English",
            'tr': "✅ Dil Türkçe olarak değiştirildi",
            'ru': "✅ Язык изменен на русский"
        }
        await query.edit_message_text(messages.get(new_lang, "✅ Language changed"))
        return
    
    # معالجة اختيار الجودة
    if data.startswith('quality_'):
        parts = data.split('_')
        quality = parts[1]
        payment_type = parts[2]  # free أو paid
        
        url = context.user_data.get('download_url')
        pending_url, pending_quality = get_pending_download(user_id)
        
        if pending_url:
            url = pending_url
            clear_pending_download(user_id)
        
        if not url:
            await query.edit_message_text(
                "❌ حدث خطأ، أعد إرسال الرابط" 
                if lang == 'ar' else "❌ Error, resend the link"
            )
            return
        
        # إذا كان مدفوع، نطلب دفع بالنجوم (سيتم إضافة هذا لاحقاً)
        if payment_type == "paid":
            # مؤقتاً: رسالة مؤقتة
            await query.edit_message_text(
                "⏳ جاري التحميل..." if lang == 'ar' else "⏳ Downloading..."
            )
        else:
            # مجاني
            await query.edit_message_text(
                "⏳ جاري التحميل..." if lang == 'ar' else "⏳ Downloading..."
            )
        
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
                
                # إذا كان مدفوع، نضيف الأرباح
                if payment_type == "paid" and not pending_url:
                    increment_user_ads(user_id, 0.01)
                    update_user_earnings(user_id, 0.01)
                    
                    ads_today = get_user_ads_today(user_id)
                    earnings = get_user_earnings(user_id)
                    
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"✅ تم التحميل بنجاح!\n"
                            f"📊 إعلانات اليوم: {ads_today}/{AdConfig.MAX_ADS_PER_DAY}\n"
                            f"💰 رصيدك: {earnings['total']:.3f} USDT"
                        ) if lang == 'ar' else (
                            f"✅ Downloaded successfully!\n"
                            f"📊 Today's ads: {ads_today}/{AdConfig.MAX_ADS_PER_DAY}\n"
                            f"💰 Your balance: {earnings['total']:.3f} USDT"
                        )
                    )
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ فشل التحميل" if lang == 'ar' else "❌ Download failed"
                )
                
        except Exception as e:
            logger.error(f"Download error for user {user_id}: {e}")
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ حدث خطأ في التحميل" if lang == 'ar' else "❌ Download error"
            )
    
    elif data == "request_withdrawal":
        earnings = get_user_earnings(user_id)
        
        if earnings['pending'] < AdConfig.MIN_WITHDRAWAL:
            await query.edit_message_text(
                f"❌ رصيدك غير كافٍ للسحب\n"
                f"الحد الأدنى: {AdConfig.MIN_WITHDRAWAL} USDT\n"
                f"رصيدك: {earnings['pending']:.3f} USDT" if lang == 'ar' else
                f"❌ Insufficient balance\n"
                f"Minimum: {AdConfig.MIN_WITHDRAWAL} USDT\n"
                f"Your balance: {earnings['pending']:.3f} USDT"
            )
        else:
            await query.edit_message_text(
                "💳 أرسل عنوان USDT الخاص بك:\n"
                "/withdraw [عنوان USDT]" 
                if lang == 'ar' else
                "💳 Send your USDT address:\n"
                "/withdraw [USDT address]"
            )

if __name__ == '__main__':
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        logger.error("❌ BOT_TOKEN not found in environment variables!")
        TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"
        logger.warning("⚠️ Using default token for local testing")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("earnings", earnings_command))
    app.add_handler(CommandHandler("withdraw", withdraw_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    RAILWAY_ENV = os.getenv('RAILWAY_ENVIRONMENT')
    
    if RAILWAY_ENV:
        PORT = int(os.getenv('PORT', 8080))
        RAILWAY_URL = os.getenv('RAILWAY_STATIC_URL')
        
        logger.info(f"🚀 Starting bot on Railway - Port: {PORT}")
        
        if RAILWAY_URL:
            WEBHOOK_URL = f"https://{RAILWAY_URL}/{TOKEN}"
            logger.info(f"🌐 Webhook URL: {WEBHOOK_URL}")
            
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=TOKEN,
                webhook_url=WEBHOOK_URL
            )
        else:
            logger.error("❌ RAILWAY_STATIC_URL not set!")
    else:
        logger.info("💻 Starting bot locally...")
        app.run_polling()
