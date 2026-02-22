import os
import yt_dlp
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def download_media(url: str, quality: str, user_id: int) -> Optional[str]:
    """تحميل الوسائط باستخدام yt-dlp"""
    try:
        # إنشاء مجلد التحميلات إذا لم يكن موجوداً
        download_dir = "downloads"
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        
        # تحديد جودة التحميل
        format_spec = 'best'
        if quality == '480p':
            format_spec = 'best[height<=480]'
        elif quality == '720p':
            format_spec = 'best[height<=720]'
        elif quality == 'audio':
            format_spec = 'bestaudio/best'
        
        # خيارات التحميل
        ydl_opts = {
            'format': format_spec,
            'outtmpl': f'{download_dir}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        
        # تنفيذ التحميل في thread منفصل
        loop = asyncio.get_event_loop()
        
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return filename
        
        file_path = await loop.run_in_executor(None, download)
        logger.info(f"تم التحميل للمستخدم {user_id}: {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"خطأ في التحميل للمستخدم {user_id}: {e}")
        return None

def get_text(key: str, lang: str = 'ar', **kwargs) -> str:
    """الحصول على النصوص حسب اللغة - نسخة مبسطة"""
    texts = {
        'ar': {
            'language_btn': '🌐 اللغة',
            'help_btn': '📖 المساعدة',
            'restart_btn': '🔄 إعادة التشغيل',
            'choose_lang': '🌐 اختر لغتك المفضلة:',
            'lang_set': '✅ تم تغيير اللغة بنجاح!',
            'help_full': '📖 **تعليمات التحميل:**\n\n1. أرسل رابط فيديو\n2. اختر الجودة\n3. ادفع النجوم المطلوبة\n4. استلم الفيديو',
            'choose_quality': '🎯 اختر جودة التحميل',
            'duration': '⏱️ المدة',
            'free_label': 'مجاني ✅',
            'quality_best': 'أفضل جودة',
            'audio_only': 'صوت فقط',
            'invalid_link': '❌ رابط غير صالح',
            'downloading': '⏳ جاري التحميل...',
            'download_title': 'تحميل فيديو',
            'audio_title': 'تحميل صوت',
            'payment_desc': 'ادفع ⭐{stars} للتحميل',
            'download_price': 'سعر التحميل',
            'queue_restarted': '🔄 تم إعادة التشغيل',
            'first_video_free': '🎁 أول فيديو اليوم مجاني!',
            'first_video_special': '🎁 أول فيديو اليوم بسعر خاص',
        },
        'en': {
            'language_btn': '🌐 Language',
            'help_btn': '📖 Help',
            'restart_btn': '🔄 Restart',
            'choose_lang': '🌐 Choose your language:',
            'lang_set': '✅ Language changed!',
            'help_full': '📖 **Instructions:**\n\n1. Send video link\n2. Choose quality\n3. Pay required stars\n4. Get video',
            'choose_quality': '🎯 Choose quality',
            'duration': '⏱️ Duration',
            'free_label': 'Free ✅',
            'quality_best': 'Best Quality',
            'audio_only': 'Audio Only',
            'invalid_link': '❌ Invalid link',
            'downloading': '⏳ Downloading...',
            'download_title': 'Download Video',
            'audio_title': 'Download Audio',
            'payment_desc': 'Pay ⭐{stars} to download',
            'download_price': 'Download price',
            'queue_restarted': '🔄 Restarted',
            'first_video_free': '🎁 First video today free!',
            'first_video_special': '🎁 First video today special price',
        }
    }
    
    # إذا كانت اللغة غير موجودة، استخدم العربية
    if lang not in texts:
        lang = 'ar'
    
    # الحصول على النص
    text = texts[lang].get(key, key)
    
    # تنسيق النص بالمتغيرات
    if kwargs and '{' in text:
        try:
            text = text.format(**kwargs)
        except:
            pass
    
    return text
