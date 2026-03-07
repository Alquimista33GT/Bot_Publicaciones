import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(">>> LLEGO /start", update.effective_chat.id)
    await update.message.reply_text("✅ Estoy vivo. Mandame 'hola' o una foto.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text if update.message else ""
    print(">>> LLEGO TEXTO:", txt)
    await update.message.reply_text(f"📩 Recibido: {txt}")

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(">>> LLEGO FOTO")
    await update.message.reply_text("📸 Foto recibida ✅")

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("ERROR:", context.error)

def main():
    if not TOKEN:
        raise SystemExit("Falta TG_BOT_TOKEN")

    app = Application.builder().token(TOKEN).build()
    app.add_error_handler(on_error)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.add_handler(MessageHandler(filters.PHOTO, photo))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
