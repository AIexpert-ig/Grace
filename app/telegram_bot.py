import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")

telegram_app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I'm your Grace Hotel bot. How can I help?")

telegram_app.add_handler(CommandHandler("start", start))

async def set_webhook(webhook_url: str):
    await telegram_app.bot.set_webhook(url=webhook_url)
