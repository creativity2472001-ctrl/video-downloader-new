import os
import yt_dlp
import json
import asyncio

with open('languages.json', 'r', encoding='utf-8') as f:
    LANGUAGES = json.load(f)

def get_text(key, lang_code, **kwargs):
    lang = LANGUAGES.get(lang_code, LANGUAGES['en'])
    text = lang.get(key, LANGUAGES['en'].get(key, key))
    if kwargs:
        text = text.format(**kwargs)
    return text

async def download_media(url, quality_type, user_id):
    import time
    timestamp = int(time.time())
    
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    # إعدادات محسنة ليوتيوب وجميع المواقع
    base_opts = {
        'outtmpl': f'downloads/{user_id}_{timestamp}.%(ext)s',
        'quiet': True,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'no_warnings': True,
        'extract_flat': False,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    if quality_type == 'audio':
        ydl_opts = {
            **base_opts,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    elif quality_type == '480p':
        ydl_opts = {
            **base_opts,
            'format': 'best[height<=480]',
        }
    elif quality_type == '720p':
        ydl_opts = {
            **base_opts,
            'format': 'best[height<=720]',
        }
    else:  # best quality
        ydl_opts = {
            **base_opts,
            'format': 'best',
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            filename = ydl.prepare_filename(info)
            
            if quality_type == 'audio':
                filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
            
            return filename
    except Exception as e:
        print(f"Download error: {e}")
        return None
