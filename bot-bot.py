ync def download_and_send(message, url, mode):
    user_id = message.from_user.id
    lang = user_language.get(user_id, "ar")
    hourglass_frames = LANGUAGE_DATA[lang]["hourglass"]

    # ⏳ رسالة الساعة الرمليه المتحركة
    status = await message.reply_text(hourglass_frames[0])
    try:
        loop = asyncio.get_event_loop()

        if mode == "audio":
            with yt_dlp.YoutubeDL(AUDIO_OPTIONS) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"
            await message.reply_audio(open(filename, "rb"))
            os.remove(filename)

        else:
            with yt_dlp.YoutubeDL(BASE_YDL_OPTS) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info)

            # الفيديو يرسل بالحجم الأصلي بدون زوم
            await message.reply_video(open(filename, "rb"))
            os.remove(filename)

        # إزالة رسالة الساعة بعد إرسال الفيديو
        await status.delete()

    except Exception as e:
        print(e)
        # تجاهل أي خطأ ولا توقف إرسال الفيديو
        await status.delete()

# ----------------- HANDLE LINK -----------------
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    lang = user_language.get(user_id, "ar")

    if not url.startswith("http"):
        await update.message.reply_text(LANGUAGE_DATA[lang]["invalid"])
        return

    context.user_data["url"] = url

    keyboard = [
        [InlineKeyboardButton("🎬 Video", callback_data="video")],
        [InlineKeyboardButton("🎵 Audio", callback_data="audio")]
    ]

    await update.message.reply_text(
        LANGUAGE_DATA[lang]["choose_mode"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ----------------- BUTTON -----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "help":
        await help_command(update, context)
    elif data == "select_lang":
        await select_language(update, context)
    elif data == "restart":
        await restart(update, context)
    elif data in ["lang_ar", "lang_en"]:
        await set_language(update, context, data.split("_")[1])
    elif data in ["video", "audio"]:
        url = context.user_data.get("url")
        if url:
            await download_and_send(query.message, url, data)

# ----------------- MAIN -----------------
def main():
    app = Application.builder().token(TOKEN).build()

    commands = [
        BotCommand("start", "Start bot"),
        BotCommand("help", "Help"),
    ]

    async def set_commands(app):
        await app.bot.set_my_commands(commands)

    app.post_init = set_commands

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 Bot running...")
    app.run_polling()

if name == "main":
    main()
