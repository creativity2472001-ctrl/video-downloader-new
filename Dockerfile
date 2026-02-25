FROM python:3.11-slim

# تثبيت FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# تشغيل Gunicorn (خادم ويب)
CMD gunicorn bot-bot:app --bind 0.0.0.0:$PORT
