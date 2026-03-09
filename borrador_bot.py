# ~/cm_bot/borrador_bot.py
import os
import re
import json
import uuid
import shutil
import traceback
from pathlib import Path
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from ai_seo import generate_marketplace_seo


# =========================================================
# Configuración
# =========================================================
BASE_DIR = Path.home() / "cm_bot" / "borradores"
BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_PATH = Path.home() / "cm_bot" / ".env"

if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")


TG_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()

if not TG_TOKEN:
    raise RuntimeError("Falta TG_BOT_TOKEN en ~/.env o variables de entorno")


# =========================================================
# Utilidades
# =========================================================
def clean(txt: str) -> str:
    txt = str(txt or "").strip()
    txt = re.sub(r"\s+", " ", txt)
    return txt


def safe_unlink(path: str | Path | None) -> None:
    try:
        if path and Path(path).exists():
            Path(path).unlink()
    except Exception:
        pass


def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def slugify(text: str, max_len: int = 50) -> str:
    text = clean(text).lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[-\s]+", "_", text).strip("_")
    if not text:
        text = "borrador"
    return text[:max_len]


def extract_numeric_price(value: str) -> str:
    value = clean(value)
    digits = re.sub(r"[^\d]", "", value)
    return digits


# =========================================================
# Parseo de datos
# =========================================================
FIELD_ALIASES = {
    "producto": ["producto", "repuesto", "pieza", "nombre"],
    "marca": ["marca"],
    "linea": ["linea", "línea", "modelo"],
    "anio": ["anio", "año", "años", "year"],
    "precio": ["precio", "valor", "costo"],
    "estado": ["estado", "condicion", "condición"],
    "motor": ["motor", "cilindraje"],
    "medida": ["medida", "detalle", "medidas", "observacion", "observación"],
}


def resolve_field(key: str) -> str | None:
    key = clean(key).lower()
    key = key.replace("í", "i").replace("á", "a").replace("é", "e").replace("ó", "o").replace("ú", "u")

    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            alias_n = (
                alias.lower()
                .replace("í", "i")
                .replace("á", "a")
                .replace("é", "e")
                .replace("ó", "o")
                .replace("ú", "u")
            )
            if alias_n == key or alias_n in key:
                return field

    return None


def parse_datos(texto: str) -> dict:
    data: dict[str, str] = {}
    lines = texto.splitlines()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if ":" not in line:
            continue

        k, v = line.split(":", 1)
        field = resolve_field(k)
        value = clean(v)

        if not field or not value:
            continue

        if field == "precio":
            data[field] = extract_numeric_price(value) or value
        else:
            data[field] = value

    return data


def validate_data(data: dict) -> tuple[bool, list[str]]:
    missing = []

    for required in ["producto", "precio", "estado"]:
        if not clean(data.get(required, "")):
            missing.append(required)

    return (len(missing) == 0, missing)


# =========================================================
# Armado del texto final
# =========================================================
def build_text(data: dict, seo: dict) -> str:
    titulo = clean(seo.get("titulo", ""))
    intro = clean(seo.get("intro", ""))
    desc = clean(seo.get("descripcion", ""))
    keywords = seo.get("keywords", []) or []

    marca = clean(data.get("marca", ""))
    linea = clean(data.get("linea", ""))
    anio = clean(data.get("anio", ""))
    precio = clean(data.get("precio", ""))
    estado = clean(data.get("estado", ""))
    motor = clean(data.get("motor", ""))
    medida = clean(data.get("medida", ""))

    vehiculo = " ".join([x for x in [marca, linea, anio] if x]).strip()

    out = []

    if titulo:
        out.append(titulo)

    if intro:
        out.append(intro)

    out.append("✅ Datos del producto")
    out.append(f"Producto: {clean(data.get('producto', ''))}")

    if vehiculo:
        out.append(f"Vehículo: {vehiculo}")

    if motor:
        out.append(f"Motor: {motor}")

    if medida:
        out.append(f"Detalle / medida: {medida}")

    if precio:
        out.append(f"Precio: Q{precio}")

    if estado:
        out.append(f"Estado: {estado}")

    if desc:
        out.append("")
        out.append(desc)

    if keywords:
        out.append("")
        out.append("Palabras clave:")
        for kw in keywords:
            kw = clean(kw)
            if kw:
                out.append(kw)

    return "\n".join(out).strip() + "\n"


# =========================================================
# Guardado
# =========================================================
def save_borrador(data: dict, seo: dict, foto_path: str | None) -> Path:
    ts = now_ts()
    folder_name = f"{ts}_{slugify(data.get('producto', 'borrador'))}"
    folder = BASE_DIR / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    text = build_text(data, seo)
    (folder / "borrador.txt").write_text(text, encoding="utf-8")

    meta = {
        "producto": clean(data.get("producto", "")),
        "marca": clean(data.get("marca", "")),
        "linea": clean(data.get("linea", "")),
        "anio": clean(data.get("anio", "")),
        "precio": clean(data.get("precio", "")),
        "estado": clean(data.get("estado", "")),
        "motor": clean(data.get("motor", "")),
        "medida": clean(data.get("medida", "")),
        "perfil": "",
        "publicado": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "folder": folder.name,
    }

    (folder / "datos.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if foto_path and Path(foto_path).exists():
        destino = folder / "foto.jpg"
        shutil.move(str(foto_path), str(destino))

    return folder


# =========================================================
# Mensajes al usuario
# =========================================================
START_TEXT = """
Bot de borradores Crazy Motors.

Flujo:
1. Enviá primero la foto del repuesto
2. Luego mandá los datos en este formato:

Producto: Ventilador de Radiador y AC
Marca: Toyota
Linea: Rav4
Anio: 2006-2011
Motor: 2.4
Medida: 2 pines
Precio: 850
Estado: Usado

Mínimo requerido:
- Producto
- Precio
- Estado
""".strip()


def format_missing_fields(missing: list[str]) -> str:
    names = {
        "producto": "Producto",
        "precio": "Precio",
        "estado": "Estado",
    }
    return "\n".join(f"- {names.get(x, x)}" for x in missing)


# =========================================================
# Handlers
# =========================================================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.setdefault("foto", None)
    await update.message.reply_text(START_TEXT)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.photo:
        return

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)

        tmp = BASE_DIR / f"tmp_{uuid.uuid4().hex}.jpg"
        await file.download_to_drive(tmp)

        # borrar foto anterior temporal si existía
        old_tmp = context.user_data.get("foto")
        if old_tmp and old_tmp != str(tmp):
            safe_unlink(old_tmp)

        context.user_data["foto"] = str(tmp)

        await update.message.reply_text(
            "✅ Foto guardada.\n\nAhora enviame los datos del repuesto.\n\n"
            "Formato sugerido:\n"
            "Producto: ...\n"
            "Marca: ...\n"
            "Linea: ...\n"
            "Anio: ...\n"
            "Motor: ...\n"
            "Medida: ...\n"
            "Precio: ...\n"
            "Estado: ..."
        )

    except Exception:
        traceback.print_exc()
        await update.message.reply_text("⚠️ No pude guardar la foto. Intentá nuevamente.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    # ignorar comandos
    if text.startswith("/"):
        return

    data = parse_datos(text)
    valid, missing = validate_data(data)

    if not valid:
        await update.message.reply_text(
            "❌ Datos insuficientes.\n\nNecesito mínimo:\n"
            f"{format_missing_fields(missing)}"
        )
        return

    foto = context.user_data.get("foto")

    try:
        await update.message.reply_text("⏳ Generando borrador SEO...")
        seo = generate_marketplace_seo(data)

        folder = save_borrador(data, seo, foto)

        # limpiar referencia temporal ya movida
        context.user_data["foto"] = None

        await update.message.reply_text(
            "✅ Borrador creado correctamente.\n\n"
            f"Carpeta: {folder.name}"
        )

    except Exception as e:
        traceback.print_exc()

        await update.message.reply_text(
            f"⚠️ No pude crear el borrador.\nDetalle: {str(e)}"
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("ERROR GLOBAL:")
    traceback.print_exception(context.error)

    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Ocurrió un error inesperado procesando tu solicitud."
            )
    except Exception:
        pass


# =========================================================
# Main
# =========================================================
def main() -> None:
    app = ApplicationBuilder().token(TG_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    print("Bot iniciado")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
