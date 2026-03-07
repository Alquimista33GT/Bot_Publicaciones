#!/usr/bin/env python3
import os
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from odf.opendocument import OpenDocumentText
from odf.text import P
from odf.style import Style, TextProperties

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # export BOT_TOKEN="..."
BASE_DIR = Path("./telegram_inbox")
PDF_DIR = BASE_DIR / "pdf"
AUDIO_DIR = BASE_DIR / "audio"
ODT_DIR = BASE_DIR / "odt"

PDF_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
ODT_DIR.mkdir(parents=True, exist_ok=True)

# Flags (cambia a False si no quieres)
ENABLE_PDF_TEXT_EXTRACT = True   # requiere pypdf
ENABLE_AUDIO_TRANSCRIBE = True   # requiere whisper + ffmpeg

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def stamp_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def safe_name(name: str) -> str:
    keep = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- "
    cleaned = "".join(c for c in name if c in keep).strip()
    return cleaned or "archivo"

def user_tag(update: Update) -> str:
    u = update.effective_user
    if not u:
        return "unknown"
    uname = f"@{u.username}" if u.username else ""
    return f"{u.id} {u.first_name or ''} {u.last_name or ''} {uname}".strip()

def odt_write_report(out_path: Path, lines: list[str], body_text: str | None = None):
    """
    Crea un .odt simple con encabezado + contenido.
    """
    doc = OpenDocumentText()

    # Estilo para título
    title_style = Style(name="TitleStyle", family="paragraph")
    title_style.addElement(TextProperties(attributes={"fontsize": "16pt", "fontweight": "bold"}))
    doc.styles.addElement(title_style)

    # Título
    doc.text.addElement(P(text="Registro de archivo (Telegram)", stylename=title_style))

    # Lineas de metadata
    for ln in lines:
        doc.text.addElement(P(text=ln))

    doc.text.addElement(P(text=""))  # salto

    # Contenido (texto extraído / transcripción)
    if body_text:
        doc.text.addElement(P(text="Contenido:"))
        doc.text.addElement(P(text=""))
        # dividir por líneas para que no quede un párrafo gigante
        for part in body_text.splitlines():
            doc.text.addElement(P(text=part))

    doc.save(str(out_path))

def extract_text_from_pdf(pdf_path: Path) -> str | None:
    if not ENABLE_PDF_TEXT_EXTRACT:
        return None
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        chunks = []
        for page in reader.pages:
            t = page.extract_text() or ""
            t = t.strip()
            if t:
                chunks.append(t)
        text = "\n\n".join(chunks).strip()
        return text if text else None
    except Exception as e:
        return f"[No se pudo extraer texto del PDF: {e}]"

def transcribe_audio(audio_path: Path) -> str | None:
    if not ENABLE_AUDIO_TRANSCRIBE:
        return None
    try:
        import whisper
        model = whisper.load_model("base")  # base = balance calidad/velocidad
        result = model.transcribe(str(audio_path), language="es")
        text = (result.get("text") or "").strip()
        return text if text else None
    except Exception as e:
        return f"[No se pudo transcribir el audio: {e}]"

# =========================
# HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Envíame un PDF o un audio/nota de voz. Guardaré el archivo y generaré un reporte en .ODT."
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    doc = msg.document

    original_name = safe_name(doc.file_name or "documento.pdf")
    file_stamp = stamp_str()

    saved_name = f"{file_stamp}_{original_name}"
    saved_path = PDF_DIR / saved_name

    tg_file = await context.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(custom_path=str(saved_path))

    # ODT
    odt_name = f"{file_stamp}_PDF_{Path(original_name).stem}.odt"
    odt_path = ODT_DIR / safe_name(odt_name)

    pdf_text = extract_text_from_pdf(saved_path)

    meta_lines = [
        f"Fecha/Hora: {now_str()}",
        f"Usuario: {user_tag(update)}",
        "Tipo: PDF",
        f"Nombre original: {original_name}",
        f"Guardado en: {saved_path.resolve()}",
    ]

    odt_write_report(odt_path, meta_lines, body_text=pdf_text)

    await msg.reply_text(f"PDF guardado: {saved_name}\nODT generado: {odt_path.name}")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    audio = msg.audio
    voice = msg.voice

    if not (audio or voice):
        return

    file_stamp = stamp_str()
    duration = None

    if audio:
        file_id = audio.file_id
        original_name = safe_name(audio.file_name or "audio.mp3")
        duration = audio.duration
    else:
        file_id = voice.file_id
        original_name = "voice.ogg"
        duration = voice.duration

    saved_name = f"{file_stamp}_{original_name}"
    saved_path = AUDIO_DIR / saved_name

    tg_file = await context.bot.get_file(file_id)
    await tg_file.download_to_drive(custom_path=str(saved_path))

    # ODT
    odt_name = f"{file_stamp}_AUDIO_{Path(original_name).stem}.odt"
    odt_path = ODT_DIR / safe_name(odt_name)

    transcript = transcribe_audio(saved_path)

    meta_lines = [
        f"Fecha/Hora: {now_str()}",
        f"Usuario: {user_tag(update)}",
        "Tipo: AUDIO",
        f"Nombre: {original_name}",
        f"Duración: {duration}s",
        f"Guardado en: {saved_path.resolve()}",
    ]

    odt_write_report(odt_path, meta_lines, body_text=transcript)

    await msg.reply_text(f"Audio guardado: {saved_name}\nODT generado: {odt_path.name}")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Solo acepto PDF o audio/nota de voz por ahora.")

def main():
    if not BOT_TOKEN:
        raise SystemExit('Falta BOT_TOKEN. Ejemplo: export BOT_TOKEN="123:ABC"')

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
    app.add_handler(MessageHandler(filters.ALL, unknown))

    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
