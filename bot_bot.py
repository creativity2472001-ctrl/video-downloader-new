import os
import json
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
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
# نظام الإعلانات الإجبارية (معدل لمتغيرات البيئة)
# =========================

@dataclass
class AdConfig:
    """إعدادات الإعلانات - تقرأ من متغيرات البيئة"""
    # قراءة الروابط من متغيرات البيئة مع قيم افتراضية مؤقتة
    CLICK_URL: str = os.getenv('CLICK_URL', "https://adsgram.ai/c/temp_click_url")
    REWARD_URL: str = os.getenv('REWARD_URL', "https://temp-domain.com/reward")
    
    # قراءة الإعدادات من متغيرات البيئة
    MAX_ADS_PER_DAY: int = int(os.getenv('MAX_ADS_PER_DAY', '30'))
    AD_COOLDOWN: int = int(os.getenv('AD_COOLDOWN', '300'))
    MIN_WITHDRAWAL: float = float(os.getenv('MIN_WITHDRAWAL', '10.0'))
    
    # رابط السيرفر الأساسي (سيتم تعيينه تلقائياً)
    BASE_URL: str = os.getenv('RAILWAY_STATIC_URL', '')

# =========================
# قاعدة بيانات الإعلانات
# =========================
ads_db = sqlite3.connect('ads_data.db', check_same_thread=False)
ads_cursor = ads_db.cursor()

# إنشاء الجداول المطلوبة
ads_cursor.executescript('''
-- جدول إعلانات المستخدمين
CREATE TABLE IF NOT EXISTS user_ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    ad_id TEXT,
    watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed BOOLEAN DEFAULT 0,
    earned REAL DEFAULT 0
);

-- جدول التحميلات المعلقة
CREATE TABLE IF NOT EXISTS pending_downloads (
    user_id INTEGER PRIMARY KEY,
    video_url TEXT NOT NULL,
    quality TEXT DEFAULT 'best',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- جدول إحصائيات الإعلانات اليومية
CREATE TABLE IF NOT EXISTS ads_stats (
    user_id INTEGER,
    date TEXT,
    count INTEGER DEFAULT 0,
    earned_today REAL DEFAULT 0,
    PRIMARY KEY (user_id, date)
);

-- جدول أرباح المستخدمين
CREATE TABLE IF NOT EXISTS user_earnings (
    user_id INTEGER PRIMARY KEY,
    total_earned REAL DEFAULT 0,
    pending_earned REAL DEFAULT 0,
    withdrawn REAL DEFAULT 0,
    last_withdrawal TIMESTAMP,
    wallet_address TEXT
);

-- جدول طلبات السحب
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

-- إنشاء الفهارس لتحسين الأداء
CREATE INDEX IF NOT EXISTS idx_user_ads_user_id ON user_ads(user_id);
CREATE INDEX IF NOT EXISTS idx_user_ads_watched_at ON user_ads(watched_at);
CREATE INDEX IF NOT EXISTS idx_ads_stats_date ON ads_stats(date);
''')
ads_db.commit()

# =========================
# دوال الإعلانات المساعدة
# =========================

def get_user_ads_today(user_id: int) -> int:
    """عدد الإعلانات التي شاهدها المستخدم اليوم"""
    today = datetime.now().strftime('%Y-%m-%d')
    ads_cursor.execute(
        "SELECT count FROM ads_stats WHERE user_id=? AND date=?",
        (user_id, today)
    )
    row = ads_cursor.fetchone()
    return row[0] if row else 0

def increment_user_ads(user_id: int, earned: float = 0.01):
    """زيادة عدد إعلانات المستخدم لليوم وإضافة الأرباح"""
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
    """تحديث أرباح المستخدم"""
    ads_cursor.execute('''
    INSERT INTO user_earnings (user_id, total_earned, pending_earned)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        total_earned = total_earned + ?,
        pending_earned = pending_earned + ?
    ''', (user_id, amount, amount, amount, amount))
    ads_db.commit()

def save_pending_download(user_id: int, url: str, quality: str = 'best'):
    """حفظ رابط التحميل مؤقتاً"""
    ads_cursor.execute('''
    INSERT OR REPLACE INTO pending_downloads (user_id, video_url, quality)
    VALUES (?, ?, ?)
    ''', (user_id, url, quality))
    ads_db.commit()
    logger.info(f"Saved pending download for user {user_id}")

def get_pending_download(user_id: int) -> tuple:
    """استرجاع رابط التحميل المحفوظ"""
    ads_cursor.execute(
        "SELECT video_url, quality FROM pending_downloads WHERE user_id=?",
        (user_id,)
    )
    row = ads_cursor.fetchone()
    return row if row else (None, None)

def clear_pending_download(user_id: int):
    """مسح الرابط المحفوظ بعد التحميل"""
    ads_cursor.execute("DELETE FROM pending_downloads WHERE user_id=?", (user_id,))
    ads_db.commit()

def get_user_earnings(user_id: int) -> dict:
    """استرجاع أرباح المستخدم"""
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
    
    # أزرار القائمة الرئيسية (مع إضافة زر الأرباح)
    keyboard = [
        [KeyboardButton("اللغة 🌐"), KeyboardButton("المساعدة 📖")],
        [KeyboardButton("أرباحي 💰"), KeyboardButton("إعادة التشغيل 🔄")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # رسالة ترحيب مع شرح نظام الإعلانات
    welcome_text = (
        "🎬 أهلاً بك في بوت التحميل!\n\n"
        "📺 نظام الإعلانات:\n"
        f"• {AdConfig.MAX_ADS_PER_DAY} إعلان مجاني يومياً\n"
        "• كل إعلان تشاهده = ربح 0.01 دولار\n"
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
        help_text += "💰 **Earnings System:**\n"
        help_text += "• Each ad you watch = $0.01\n"
        help_text += f"• Minimum withdrawal: ${AdConfig.MIN_WITHDRAWAL}\n"
        help_text += "• Withdraw via USDT (TRC20)\n\n"
        help_text += "🌐 You can change language from the **Language** button"
    
    await update.message.reply_text(help_text)

async def earnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض أرباح المستخدم"""
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
    """طلب سحب الأرباح"""
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    earnings = get_user_earnings(user_id)
    
    # التحقق من وجود عنوان محفظة
    if len(context.args) == 0:
        await update.message.reply_text(
            "❌ يرجى إرسال عنوان USDT الخاص بك\nمثال: /withdraw TVd2P6p8hR7Xq..." if lang == 'ar' else
            "❌ Please send your USDT address\nExample: /withdraw TVd2P6p8hR7Xq..."
        )
        return
    
    wallet = context.args[0]
    
    # التحقق من الحد الأدنى
    if earnings['pending'] < AdConfig.MIN_WITHDRAWAL:
        await update.message.reply_text(
            f"❌ الحد الأدنى للسحب {AdConfig.MIN_WITHDRAWAL} USDT\n"
            f"رصيدك الحالي: {earnings['pending']:.3f} USDT" if lang == 'ar' else
            f"❌ Minimum withdrawal is {AdConfig.MIN_WITHDRAWAL} USDT\n"
            f"Your balance: {earnings['pending']:.3f} USDT"
        )
        return
    
    # إنشاء طلب سحب
    ads_cursor.execute('''
    INSERT INTO withdrawal_requests (user_id, amount, wallet_address)
    VALUES (?, ?, ?)
    ''', (user_id, earnings['pending'], wallet))
    ads_db.commit()
    
    # تحديث الرصيد المعلق
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
    
    if user_id in context.user_data:
        context.user_data.clear()
    
    await update.message.reply_text(
        "🔄 تم إعادة التشغيل" if user_lang.get(user_id, 'ar') == 'ar' else "🔄 Restarted"
    )
    await start(update, context)

async def show_quality_options(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """عرض خيارات الجودة"""
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    # حفظ الرابط مؤقتاً
    context.user_data['download_url'] = url
    
    keyboard = [
        [
            InlineKeyboardButton("480p 🎬", callback_data='quality_480p'),
            InlineKeyboardButton("720p 🎬", callback_data='quality_720p')
        ],
        [
            InlineKeyboardButton("أفضل جودة ✨" if lang == 'ar' else "Best Quality ✨", 
                               callback_data='quality_best'),
            InlineKeyboardButton("صوت 🎵" if lang == 'ar' else "Audio 🎵", 
                               callback_data='quality_audio')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎯 اختر جودة التحميل:" if lang == 'ar' else "🎯 Choose download quality:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الرسائل النصية"""
    text = update.message.text
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, 'ar')
    
    # معالجة أزرار القائمة
    if text in ["اللغة 🌐", "Language 🌐"]:
        await language_command(update, context)
        return
    elif text in ["المساعدة 📖", "Help 📖"]:
        await help_command(update, context)
        return
    elif text in ["أرباحي 💰", "Earnings 💰"]:
        await earnings_command(update, context)
        return
    elif text in ["إعادة التشغيل 🔄", "Restart 🔄"]:
        await restart_command(update, context)
        return
    
    # معالجة الروابط
    if text.startswith(('http://', 'https://')):
        # التحقق من عدد الإعلانات اليومية
        ads_today = get_user_ads_today(user_id)
        
        if ads_today >= AdConfig.MAX_ADS_PER_DAY:
            # إذا وصل للحد الأقصى، تحميل مباشر
            await update.message.reply_text(
                "⏳ وصلت للحد الأقصى للإعلانات اليومية، جاري التحميل المباشر..." 
                if lang == 'ar' else "⏳ You've reached daily ad limit, downloading directly..."
            )
            await show_quality_options(update, context, text)
        else:
            # حفظ الرابط مؤقتاً وعرض الإعلان الإجباري
            save_pending_download(user_id, text)
            
            # رسالة الإعلان الإجباري
            remaining = AdConfig.MAX_ADS_PER_DAY - ads_today
            keyboard = [[
                InlineKeyboardButton(
                    "🎬 مشاهدة الإعلان (إجباري)" if lang == 'ar' else "🎬 Watch Ad (Required)",
                    url=AdConfig.CLICK_URL
                )
            ]]
            
            await update.message.reply_text(
                f"⚠️ يجب مشاهدة إعلان واحد أولاً\n"
                f"📊 متبقي لك اليوم: {remaining} إعلان\n"
                f"💰 ربح الإعلان: 0.01 USDT\n\n"
                f"بعد المشاهدة، سيتم تفعيل التحميل تلقائياً!" 
                if lang == 'ar' else
                f"⚠️ You must watch one ad first\n"
                f"📊 Remaining today: {remaining} ads\n"
                f"💰 Ad reward: $0.01\n\n"
                f"After watching, download will be activated automatically!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await update.message.reply_text(
            "❌ رابط غير صالح" if lang == 'ar' else "❌ Invalid link"
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار"""
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
        quality = data.split('_')[1]
        
        # هل هناك رابط معلق من الإعلان؟
        pending_url, pending_quality = get_pending_download(user_id)
        
        if pending_url:
            # استخدام الرابط من الإعلان
            url = pending_url
            clear_pending_download(user_id)
            
            # تسجيل مشاهدة الإعلان وإضافة الأرباح
            increment_user_ads(user_id, 0.01)
            update_user_earnings(user_id, 0.01)
            
            await query.edit_message_text(
                "✅ تم مشاهدة الإعلان! جاري التحميل..." 
                if lang == 'ar' else "✅ Ad watched! Downloading..."
            )
        else:
            # تحميل مباشر
            url = context.user_data.get('download_url')
            if not url:
                await query.edit_message_text(
                    "❌ حدث خطأ، أعد إرسال الرابط" 
                    if lang == 'ar' else "❌ Error, resend the link"
                )
                return
            
            await query.edit_message_text(
                "⏳ جاري التحميل..." if lang == 'ar' else "⏳ Downloading..."
            )
        
        try:
            # تحميل الملف
            file_path = await download_media(url, quality, user_id)
            
            if file_path and os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    if quality == 'audio':
                        await context.bot.send_audio(chat_id=user_id, audio=f)
                    else:
                        await context.bot.send_video(chat_id=user_id, video=f)
                
                os.remove(file_path)
                
                # رسالة تأكيد مع الإحصائيات
                if pending_url:
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
    
    # معالجة طلب السحب
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

# =========================
# نقطة الدخول الرئيسية (معدلة للسيرفر)
# =========================
if __name__ == '__main__':
    # توكن البوت من متغير البيئة
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        logger.error("❌ BOT_TOKEN not found in environment variables!")
        TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"  # للاختبار المحلي فقط
        logger.warning("⚠️ Using default token for local testing")
    
    # إنشاء التطبيق
    app = ApplicationBuilder().token(TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("earnings", earnings_command))
    app.add_handler(CommandHandler("withdraw", withdraw_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # التحقق من وجود متغيرات البيئة للسيرفر
    RAILWAY_ENV = os.getenv('RAILWAY_ENVIRONMENT')
    
    if RAILWAY_ENV:
        # تشغيل على Railway
        PORT = int(os.getenv('PORT', 8080))
        RAILWAY_URL = os.getenv('RAILWAY_STATIC_URL')
        
        logger.info(f"🚀 Starting bot on Railway - Port: {PORT}")
        
        if RAILWAY_URL:
            WEBHOOK_URL = f"https://{RAILWAY_URL}/{TOKEN}"
            logger.info(f"🌐 Webhook URL: {WEBHOOK_URL}")
            
            # تشغيل webhook
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=TOKEN,
                webhook_url=WEBHOOK_URL
            )
        else:
            logger.error("❌ RAILWAY_STATIC_URL not set!")
    else:
        # تشغيل محلي
        logger.info("💻 Starting bot locally...")
        app.run_polling()
