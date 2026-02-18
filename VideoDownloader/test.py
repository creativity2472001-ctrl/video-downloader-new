import yt_dlp
import os

url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # رابط تجريبي

ydl_opts = {
    'outtmpl': 'downloads/test.%(ext)s',
    'format': 'best',
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        print("🔄 جاري التحميل...")
        ydl.download([url])
        print("✅ تم التحميل!")
except Exception as e:
    print(f"❌ خطأ: {e}")
