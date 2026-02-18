
import os
import yt_dlp
import asyncio
import json

# تحميل ملف اللغات
with open('languages.json', 'r', encoding='utf-8') as f:
    LANGUAGES = json.load(f)

def get_text(key, lang_code, **kwargs):
    lang = LANGUAGES.get(lang_code, LANGUAGES['en'])
    text = lang.get(key, LANGUAGES['en'].get(key, key))
    if kwargs:
        text = text.format(**kwargs)
    return text

async def download_media(url, format_type, user_id, update, context, lang_code):
    import time
    timestamp = int(time.time())
    out_tmpl = f"downloads/{user_id}_{timestamp}.%(ext)s"
    
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    # إعدادات yt-dlp مبسطة
    ydl_opts = {
        'outtmpl': out_tmpl,
        'noplaylist': True,
        'quiet': True,
        'format': 'best',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
    except Exception as e:
        print(f"Download error: {e}")
        return None
