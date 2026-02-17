import os, asyncio, yt_dlp, logging, json, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8373058261:AAG7_Fo2P_6kv6hHRp5xcl4QghDRpX5TryA"
MAX_SIZE_MB = 80
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Load Languages ---
def load_languages():
    try:
        with open('languages.json','r',encoding='utf-8') as f: return json.load(f)
    except: return {}
LANGS = load_languages()
user_prefs = {}

def get_text(user_id, key, *args):
    lang = user_prefs.get(user_id,{}).get('lang','ar')
    text = LANGS.get(lang,LANGS.get('en',{})).get(key,"")
    return text.format(*args) if args else text

# --- Progress Hook ---
def progress_hook(d, context, chat_id, message_id, user_id):
    if d['status']=='downloading':
        p=d.get('_percent_str','0%').replace('%','')
        try:
            pf=float(p)
            last=context.user_data.get('last_progress',0)
            if pf-last>=25 or pf>=99:
                context.user_data['last_progress']=pf
                asyncio.get_event_loop().create_task(context.bot.edit_message_text(chat_id=chat_id,message_id=message_id,text=get_text(user_id,'progress',p.strip())))
        except: pass

# --- Worker ---
async def worker(user_id, context):
    queue=user_prefs[user_id]['queue']
    while True:
        task=await queue.get()
        try: await download_and_send_task(task, context)
        except Exception as e: logger.error(f"Worker Task Error: {e}")
        finally: queue.task_done()

# --- Download and Send ---
async def download_and_send_task(task, context):
    chat_id,user_id, url, mode, quality = task['chat_id'],task['user_id'],task['url'],task['mode'],task['quality']
    msg = await context.bot.send_message(chat_id=chat_id,text=get_text(user_id,'wait'))
    actual_file = None
    try:
        unique_name = f"{DOWNLOAD_DIR}/{user_id}_{int(time.time())}"
        ydl_opts={'outtmpl':f"{unique_name}.%(ext)s",'quiet':True,'noplaylist':True,'progress_hooks':[lambda d: progress_hook(d,context,chat_id,msg.message_id,user_id)]}

        if mode=="video":
            height=720 if quality=="720" else 480 if quality=="480" else 0
            if height>0: ydl_opts.update({'format':f'bestvideo[height<={height}]+bestaudio/best'})
            else: ydl_opts.update({'format':'bestvideo+bestaudio/best'})
            ydl_opts.update({'merge_output_format':'mp4','postprocessor_args':{'ffmpeg':['-c:v','libx264','-preset','veryfast','-c:a','aac']}})
        else:
            ydl_opts.update({'format':'bestaudio/best','postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}]})

        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info=ydl.extract_info(url,download=True)
                return ydl.prepare_filename(info), info.get('title','video'), info.get('width'), info.get('height'), info.get('duration')
        loop=asyncio.get_event_loop()
        filename, title, w, h, d = await loop.run_in_executor(None, download)
        actual_file=filename if mode=="video" else os.path.splitext(filename)[0]+".mp3"

        size_mb=os.path.getsize(actual_file)/(1024*1024)
        if size_mb>MAX_SIZE_MB:
            await msg.edit_text(get_text(user_id,"too_large",round(size_mb,1)))
        else:
            with open(actual_file,"rb") as f:
                if mode=="audio": await context.bot.send_audio(chat_id=chat_id,audio=f,caption=f"🎵 {title}")
                else: await context.bot.send_video(chat_id=chat_id,video=f,caption=f"🎬 {title}",width=w,height=h,duration=d,supports_streaming=True)
            await msg.delete()
    except Exception as e:
        logger.error(f"Download Error: {e}")
        try: await msg.edit_text(get_text(user_id,'error'))
        except: pass
    finally:
        if actual_file and os.path.exists(actual_file):
            try: os.remove(actual_file)
            except: pass

# --- Start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id=update.effective_user.id
    if user_id not in user_prefs:
        user_prefs[user_id]={'lang':'ar','queue':asyncio.Queue()}
        asyncio.create_task(worker(user_id,context))
    keyboard=[[KeyboardButton("اللغة 🌐"),KeyboardButton("المساعدة 📖")]]
    await update.message.reply_text(get_text(user_id,'start'),reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))

# --- Handle messages ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text,user_id=update.message.text,update.effective_user.id
    if user_id not in user_prefs:
        user_prefs[user_id]={'lang':'ar','queue':asyncio.Queue()}
        asyncio.create_task(worker(user_id,context))
    if text=="المساعدة 📖": await update.message.reply_text(get_text(user_id,'help'))
    elif text=="اللغة 🌐":
        keyboard=[[InlineKeyboardButton("🇸🇦 عربي",callback_data="set_ar"),InlineKeyboardButton("🇺🇸 English",callback_data="set_en")],
                  [InlineKeyboardButton("🇹🇷 Türkçe",callback_data="set_tr"),InlineKeyboardButton("🇷🇺 Русский",callback_data="set_ru")],
                  [InlineKeyboardButton("🇩🇪 Deutsch",callback_data="set_de"),InlineKeyboardButton("🇫🇷 Français",callback_data="set_fr")]]
        await update.message.reply_text("Choose language:",reply_markup=InlineKeyboardMarkup(keyboard))
    elif "http" in text:
        try:
            with yt_dlp.YoutubeDL({'quiet':True,'noplaylist':True}) as ydl:
                info=ydl.extract_info(text,download=False)
                size=info.get('filesize') or info.get('filesize_approx')
                if size and size>MAX_SIZE_MB*1024*1024:
                    await update.message.reply_text(get_text(user_id,'too_large',round(size/(1024*1024),1)))
                    return
        except: pass
        context.user_data["url"]=text
        keyboard=[[InlineKeyboardButton(get_text(user_id,"video_480"),callback_data="dl_video_480"),
                   InlineKeyboardButton(get_text(user_id,"video_720"),callback_data="dl_video_720")],
                  [InlineKeyboardButton(get_text(user_id,"video_auto"),callback_data="dl_video_auto")],
                  [InlineKeyboardButton(get_text(user_id,"audio"),callback_data="dl_audio")]]
        await update.message.reply_text(get_text(user_id,"choose"),reply_markup=InlineKeyboardMarkup(keyboard))

# --- Buttons ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()
    user_id,data=query.from_user.id,query.data
    if data.startswith("set_"):
        user_prefs[user_id]['lang']=data.split("_")[1]
        await query.edit_message_text(get_text(user_id,'lang_done'))
    elif data.startswith("dl_"):
        parts=data.split("_")
        mode=parts[1]
        quality=parts[2] if len(parts)>2 else "auto"
        url=context.user_data.get("url")
        if not url: return
        await query.message.delete()
        await user_prefs[user_id]['queue'].put({'chat_id':query.message.chat_id,'user_id':user_id,'url':url,'mode':mode,'quality':quality})

# --- Main ---
def main():
    if TOKEN=="ضع_التوكن_هنا": return
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    print("🚀 البوت الاحترافي النهائي يعمل الآن...")
    app.run_polling()

if __name__=="__main__":
    main()
