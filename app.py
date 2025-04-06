import logging
import requests
import base64
from datetime import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler,
    PicklePersistence
)
from telegram.ext.webhookhandler import WebhookHandler

# --- CONFIG ---
BOT_TOKEN = "8034760491:AAEIqcV0xvX6ugpHr05-bVZY6bUM-aGNfjg"
API_KEY = "SG_b5f8f712e9924783"
API_ENDPOINT = "https://api.segmind.com/v1/sd2.1-faceswapper"
WEBHOOK_URL = "https://your-koyeb-subdomain.koyeb.app/webhook"  # Replace this

COOLDOWN_SECONDS = 120
user_last_time = {}
user_images = {}

GET_FACE, GET_TARGET = range(2)

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- FLASK APP ---
flask_app = Flask(__name__)

# --- UTIL FUNCTIONS ---
def img_url_to_base64(url):
    img_data = requests.get(url).content
    return base64.b64encode(img_data).decode()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("☂️SWAP FACE☂️", callback_data="swap")],
        [InlineKeyboardButton("☂️DEVELOPER☂️", url="https://t.me/+cc6Lt64HKXtmYmNl")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "**👾Welcome to Face Swapper Bot!**\nSend two images and get a swapped face output💮.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "swap":
        await query.message.reply_text("⚡PLEASE SEND THE FACE IMAGE.🛑")
        return GET_FACE

async def get_face_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not update.message.photo:
        await update.message.reply_text("🙄PLEASE SEND AN IMAGE.🔥")
        return GET_FACE

    photo_file = await update.message.photo[-1].get_file()
    user_images[user_id] = {"face": photo_file.file_path}
    await update.message.reply_text("☂️NOW SEND THE TARGET IMAGE.☂️")
    return GET_TARGET

async def get_target_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    now = datetime.now()

    if user_id in user_last_time:
        diff = (now - user_last_time[user_id]).total_seconds()
        if diff < COOLDOWN_SECONDS:
            wait = int(COOLDOWN_SECONDS - diff)
            await update.message.reply_text(f"☂️Please wait {wait} seconds before using this again.☂️")
            return ConversationHandler.END

    user_last_time[user_id] = now

    if not update.message.photo:
        await update.message.reply_text("☂️PLEASE SEND AN IMAGE.☂️")
        return GET_TARGET

    photo_file = await update.message.photo[-1].get_file()
    target_img_url = photo_file.file_path

    user_images[user_id]["target"] = target_img_url
    face_b64 = img_url_to_base64(user_images[user_id]["face"])
    target_b64 = img_url_to_base64(target_img_url)

    payload = {
        "input_face_image": face_b64,
        "target_face_image": target_b64,
        "file_type": "png",
        "face_restore": True
    }

    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }

    await update.message.reply_text("💮PROCESSING IMAGE... PLEASE WAIT.⚡")
    res = requests.post(API_ENDPOINT, json=payload, headers=headers)

    if res.status_code == 200:
        with open(f"output_{user_id}.png", "wb") as f:
            f.write(res.content)
        await update.message.reply_photo(photo=open(f"output_{user_id}.png", "rb"))
    else:
        await update.message.reply_text("Failed to process image.")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

# --- MAIN BOT SETUP ---
persistence = PicklePersistence(filepath="bot_data")
application = Application.builder().token(BOT_TOKEN).persistence(persistence).build()

conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(button_handler)],
    states={
        GET_FACE: [MessageHandler(filters.PHOTO, get_face_image)],
        GET_TARGET: [MessageHandler(filters.PHOTO, get_target_image)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

application.add_handler(CommandHandler("start", start))
application.add_handler(conv_handler)

# --- FLASK WEBHOOK ROUTE ---
@flask_app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "ok"

# --- START WEBHOOK ---
if __name__ == '__main__':
    application.run_webhook(
        listen="0.0.0.0",
        port=8080,
        webhook_url=WEBHOOK_URL
    )
    flask_app.run(host="0.0.0.0", port=8080)
