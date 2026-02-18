import json
import os
import asyncio
import yt_dlp
from telegram import Update
from telegram.ext import ContextTypes

# تحميل ملف اللغات
def load_languages():
    with open('languages.json', 'r', encoding='utf-8') as f:
        return json.load(f)

LANGUAGES = load_languages()

def get_text(key, lang_code, **kwargs):
    # Default to English if language or key not found
    lang = LANGUAGES.get(lang_code, LANGUAGES['en'])
    text = lang.get(key, LANGUAGES['en'].get(key, key))
    return text.format(**kwargs)

async def download_progress_hook(d, update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code):
    if d['status'] == 'downloading':
        p = d.get('_percent_str', '0%').replace('%', '').strip()
        try:
            # Remove ANSI escape codes if any
            import re
            p = re.sub(r'\x1b\[[0-9;]*m', '', p)
            progress = float(p)
            
            last_p = context.user_data.get('last_progress', 0)
            # Update every 25% or at 99%
            if progress >= last_p + 25 or progress >= 99:
                context.user_data['last_progress'] = progress
                msg_text = get_text('downloading', lang_code, progress=int(progress))
                try:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=context.user_data['status_msg_id'],
                        text=msg_text
                    )
                except:
                    pass
        except Exception as e:
            pass

def get_video_info(url):
    ydl_opts = {'quiet': True, 'noplaylist': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return info
        except:
            return None

async def download_media(url, format_type, user_id, update, context, lang_code):
    import time
    timestamp = int(time.time())
    out_tmpl = f"downloads/{user_id}_{timestamp}.%(ext)s"
    
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    # Hook for progress
    def hook(d):
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(download_progress_hook(d, update, context, lang_code))

    ydl_opts = {
        'outtmpl': out_tmpl,
        'noplaylist': True,
        'quiet': True,
        'progress_hooks': [hook],
    }

    if format_type == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    elif format_type == '480p':
        ydl_opts['format'] = 'bestvideo[height<=480]+bestaudio/best[height<=480]/best[height<=480]'
    elif format_type == '720p':
        ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]/best[height<=720]'
    else:  # auto/best
        ydl_opts['format'] = 'bestvideo+bestaudio/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Using to_thread for blocking call
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            filename = ydl.prepare_filename(info)
            if format_type == 'audio':
                filename = os.path.splitext(filename)[0] + ".mp3"
            return filename
    except Exception as e:
        print(f"Download Error: {e}")
        return None
