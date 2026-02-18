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
    
    if quality_type == 'audio':
        ydl_opts = {
            'outtmpl': f'downloads/{user_id}_{timestamp}.%(ext)s',
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }
    else:
        ydl_opts = {
            'outtmpl': f'downloads/{user_id}_{timestamp}.%(ext)s',
            'format': 'best[ext=mp4]/best',
            'quiet': True,
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
