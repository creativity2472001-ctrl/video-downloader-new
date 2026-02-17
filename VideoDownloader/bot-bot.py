import os
import asyncio
import yt_dlp
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

# ======================== الإعدادات الأساسية ========================
# ضع التوكن الخاص بك هنا مباشرة أو استخدم متغيرات البيئة
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

if TOKEN == "YOUR_BOT_TOKEN_HERE":
    print("❌ خطأ: لم يتم العثور على التوكن!")
    print("📝 يرجى وضع التوكن في الكود أو في متغير البيئة TELEGRAM_BOT_TOKEN")
    exit(1)

MAX_SIZE_MB = 80
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ======================== ملف اللغات (موسع) ========================
LANGS = {
    "ar": {
        "start": "🎬 أهلاً بك! أرسل رابط فيديو لتحميله.",
        "help": "📖 **تعليمات التحميل:**\n\n1. اذهب إلى تطبيق انستغرام/تيك توك/يوتيوب.\n2. اختر الفيديو الذي تريده.\n3. اضغط على زر المشاركة ↪️ أو النقاط الثلاث.\n4. اضغط على \"نسخ الرابط\".\n5. أرسل الرابط إلى البوت وستحصل على الفيديو خلال ثوانٍ.",
        "choose": "🎯 اختر الجودة:",
        "video_auto": "أفضل جودة ✨",
        "audio": "صوت فقط 🎵",
        "wait": "⏳ جاري التحميل، يرجى الانتظار...",
        "error": "❌ حدث خطأ. يرجى التأكد من أن الرابط صحيح والمحاولة مرة أخرى.",
        "too_large": "⚠️ الملف كبير جداً ({0}MB). لا يمكن إرساله.",
        "language": "🌐 اللغة",
        "help_btn": "📖 المساعدة",
        "restart_btn": "🔄 إعادة التشغيل",
        "lang_choose": "🌐 اختر لغتك:",
        "lang_done": "✅ تم تغيير اللغة بنجاح."
    },
    "en": {
        "start": "🎬 Welcome! Send a video link to download.",
        "help": "📖 **Download instructions:**\n\n1. Go to the Instagram/TikTok/YouTube app.\n2. Choose a video you like.\n3. Tap the ↪️ button or the three dots.\n4. Tap the \"Copy\" button.\n5. Send the link to the bot and in a few seconds you'll get the video.",
        "choose": "🎯 Choose quality:",
        "video_auto": "Best Quality ✨",
        "audio": "Audio Only 🎵",
        "wait": "⏳ Downloading, please wait...",
        "error": "❌ An error occurred. Please ensure the link is correct and try again.",
        "too_large": "⚠️ File is too large ({0}MB). Cannot send.",
        "language": "🌐 Language",
        "help_btn": "📖 Help",
        "restart_btn": "🔄 Restart",
        "lang_choose": "🌐 Choose your language:",
        "lang_done": "✅ Language changed successfully."
    },
    "de": {
        "start": "🎬 Willkommen! Senden Sie einen Video-Link zum Herunterladen.",
        "help": "📖 **Anleitung zum Herunterladen:**\n\n1. Gehen Sie zur Instagram/TikTok/YouTube-App.\n2. Wählen Sie ein Video, das Ihnen gefällt.\n3. Tippen Sie auf die ↪️-Schaltfläche oder die drei Punkte.\n4. Tippen Sie auf die „Kopieren“-Schaltfläche.\n5. Senden Sie den Link an den Bot und in wenigen Sekunden erhalten Sie das Video.",
        "choose": "🎯 Qualität wählen:",
        "video_auto": "Beste Qualität ✨",
        "audio": "Nur Audio 🎵",
        "wait": "⏳ Wird heruntergeladen, bitte warten...",
        "error": "❌ Ein Fehler ist aufgetreten. Bitte stellen Sie sicher, dass der Link korrekt ist und versuchen Sie es erneut.",
        "too_large": "⚠️ Datei ist zu groß ({0}MB). Senden nicht möglich.",
        "language": "🌐 Sprache",
        "help_btn": "📖 Hilfe",
        "restart_btn": "🔄 Neustart",
        "lang_choose": "🌐 Wählen Sie Ihre Sprache:",
        "lang_done": "✅ Sprache erfolgreich geändert."
    },
    "fr": {
        "start": "🎬 Bienvenue ! Envoyez un lien vidéo pour le télécharger.",
        "help": "📖 **Instructions de téléchargement :**\n\n1. Allez sur l'application Instagram/TikTok/YouTube.\n2. Choisissez une vidéo que vous aimez.\n3. Appuyez sur le bouton ↪️ ou les trois points.\n4. Appuyez sur le bouton « Copier ».\n5. Envoyez le lien au bot et en quelques secondes, vous obtiendrez la vidéo.",
        "choose": "🎯 Choisissez la qualité :",
        "video_auto": "Meilleure qualité ✨",
        "audio": "Audio seulement 🎵",
        "wait": "⏳ Téléchargement en cours, veuillez patienter...",
        "error": "❌ Une erreur s'est produite. Veuillez vous assurer que le lien est correct et réessayez.",
        "too_large": "⚠️ Le fichier est trop volumineux ({0}MB). Envoi impossible.",
        "language": "🌐 Langue",
        "help_btn": "📖 Aide",
        "restart_btn": "🔄 Redémarrer",
        "lang_choose": "🌐 Choisissez votre langue :",
        "lang_done": "✅ Langue changée avec succès."
    },
    "tr": {
        "start": "🎬 Hoş geldiniz! İndirmek için bir video bağlantısı gönderin.",
        "help": "📖 **İndirme talimatları:**\n\n1. Instagram/TikTok/YouTube uygulamasına gidin.\n2. Beğendiğiniz bir video seçin.\n3. ↪️ düğmesine veya üç noktaya dokunun.\n4. \"Kopyala\" düğmesine dokunun.\n5. Bağlantıyı bota gönderin ve birkaç saniye içinde videoyu alacaksınız.",
        "choose": "🎯 Kaliteyi seçin:",
        "video_auto": "En İyi Kalite ✨",
        "audio": "Sadece Ses 🎵",
        "wait": "⏳ İndiriliyor, lütfen bekleyin...",
        "error": "❌ Bir hata oluştu. Lütfen bağlantının doğru olduğundan emin olun ve tekrar deneyin.",
        "too_large": "⚠️ Dosya çok büyük ({0}MB). Gönderilemiyor.",
        "language": "🌐 Dil",
        "help_btn": "📖 Yardım",
        "restart_btn": "🔄 Yeniden Başlat",
        "lang_choose": "🌐 Dilinizi seçin:",
        "lang_done": "✅ Dil başarıyla değiştirildi."
    }
}

# ======================== بيانات المستخدمين ========================
users_lang = {}

def get_text(uid, key, *args):
    lang = users_lang.get(uid, "ar")
    text = LANGS.get(lang, LANGS["en"]).get(key, "")
    return text.format(*args) if args else text

def main_keyboard(uid):
    keyboard = [[
        KeyboardButton(get_text(uid, "language")),
        KeyboardButton(get_text(uid, "help_btn")),
        KeyboardButton(get_text(uid, "restart_btn"))
    ]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ======================== معالجات الأوامر والرسائل ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in users_lang:
        users_lang[uid] = "ar"
    await update.message.reply_text(
        get_text(uid, "start"),
        reply_markup=main_keyboard(uid)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        get_text(uid, "help"),
        reply_markup=main_keyboard(uid)
    )

async def show_languages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🇸🇦 عربي", callback_data="lang_ar"), InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"), InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")],
        [InlineKeyboardButton("🇹🇷 Türkçe", callback_data="lang_tr")]
    ]
    await update.message.reply_text(
        get_text(uid, "lang_choose"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang_code = query.data.split('_')[1]
    users_lang[uid] = lang_code
    
    await query.edit_message_text(get_text(uid, "lang_done"))
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=get_text(uid, "start"),
        reply_markup=main_keyboard(uid)
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    url = update.message.text.strip()
    context.user_data['url'] = url
    
    keyboard = [
        [InlineKeyboardButton(get_text(uid, "video_auto"), callback_data="quality_best")],
        [InlineKeyboardButton(get_text(uid, "audio"), callback_data="quality_audio")]
    ]
    await update.message.reply_text(
        get_text(uid, "choose"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def quality_handler_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = query.from_user.id
    url = context.user_data.get('url')
    
    if not url:
        await query.edit_message_text(get_text(uid, "error"))
        return
    
    choice = query.data.split('_')[1]
    is_audio = choice == "audio"
    
    await query.message.delete()
    msg = await context.bot.send_message(query.message.chat_id, get_text(uid, "wait"))
    
    try:
        file_path = await download_media(url, is_audio)
        
        if not file_path:
             await msg.edit_text(get_text(uid, "error"))
             return

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > MAX_SIZE_MB:
            await msg.edit_text(get_text(uid, "too_large", round(size_mb, 1)))
            os.remove(file_path)
            return
        
        await msg.delete()
        caption_text = f"Downloaded via @{context.bot.username}"
        with open(file_path, 'rb') as f:
            if is_audio:
                await context.bot.send_audio(query.message.chat_id, audio=f, caption=caption_text)
            else:
                await context.bot.send_video(query.message.chat_id, video=f, caption=caption_text)
        
        os.remove(file_path)
        
    except Exception as e:
        logger.error(f"Error during download/upload: {e}")
        await msg.edit_text(get_text(uid, "error"))

async def download_media(url, is_audio):
    format_string = 'bestaudio/best' if is_audio else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    output_template = os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s')
    
    ydl_opts = {
        'format': format_string,
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [],
        'merge_output_format': 'mp4',
    }

    if is_audio:
        ydl_opts['postprocessors'].append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if is_audio:
                base, _ = os.path.splitext(filename)
                final_filename = base + '.mp3'
                # التأكد من وجود الملف قبل إعادته
                return final_filename if os.path.exists(final_filename) else None
            return filename
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        return None

# ======================== التشغيل ========================
def main():
    print("🚀 بدء تشغيل البوت...")
    
    app = Application.builder().token(TOKEN).build()
    
    # معالج أمر البدء
    app.add_handler(CommandHandler("start", start_command))
    
    # معالجات الأزرار النصية السفلية
    # يتم استخدام فلاتر نصية دقيقة بدلاً من Regex لتجنب التعقيد
    app.add_handler(MessageHandler(filters.Text([LANGS[lang]['language'] for lang in LANGS]), show_languages_command))
    app.add_handler(MessageHandler(filters.Text([LANGS[lang]['help_btn'] for lang in LANGS]), help_command))
    app.add_handler(MessageHandler(filters.Text([LANGS[lang]['restart_btn'] for lang in LANGS]), start_command))

    # معالج الروابط
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & (filters.Entity("url") | filters.Entity("text_link")), handle_link))
    
    # معالجات الأزرار المضمنة (Callbacks)
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(quality_handler_callback, pattern="^quality_"))
    
    print("✅ البوت يعمل الآن!")
    app.run_polling()

if __name__ == "__main__":
    main()
