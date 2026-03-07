# ~/cm_bot/borrador_bot.py
import os
import re
import json
import sys
import logging
import datetime as dt
from pathlib import Path

ENV_PATH = Path.home() / "cm_bot" / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")

sys.path.append(str(Path(__file__).parent))

from PIL import Image
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

from ai_seo import generate_marketplace_seo

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()

BASE_DIR = Path.home() / "CM_Borradores"
BASE_DIR.mkdir(parents=True, exist_ok=True)
INDEX_FILE = BASE_DIR / "index.jsonl"


# -------------------------
# Utilidades
# -------------------------
def ensure_index_file():
    if not INDEX_FILE.exists():
        INDEX_FILE.write_text("", encoding="utf-8")


def append_index(record: dict):
    ensure_index_file()
    with INDEX_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def limpiar_texto(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9áéíóúñü\s-]", "", s)
    s = s.replace(" ", "-")
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:60] or "producto"


def copiar_portapapeles(texto: str) -> bool:
    try:
        import subprocess
        subprocess.run(["xclip", "-selection", "clipboard"], input=texto.encode("utf-8"), check=True)
        return True
    except Exception:
        return False


# -------------------------
# Parser
# -------------------------
FIELD_ALIASES = {
    "producto": {"producto", "prod", "pieza", "articulo", "artículo"},
    "marca": {"marca"},
    "linea": {"linea", "línea", "modelo"},
    "anio": {"anio", "año", "year"},
    "precio": {"precio", "valor", "costo", "coste", "q"},
    "estado": {"estado", "condicion", "condición"},
    "medida": {"medida", "detalle", "size", "rin", "rín"},
}


def norm_key(k: str) -> str:
    k = (k or "").strip().lower()
    k = k.replace(":", "").replace(".", "")
    k = k.replace("línea", "linea").replace("año", "anio").replace("condición", "condicion").replace("rín", "rin")
    return k


def parse_key_value_lines(text: str) -> dict:
    out = {}
    lines = [x.strip() for x in (text or "").splitlines() if x.strip()]

    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            k = norm_key(k)
            v = limpiar_texto(v)
        else:
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            k, v = norm_key(parts[0]), limpiar_texto(parts[1])

        for field, aliases in FIELD_ALIASES.items():
            if k in aliases:
                out[field] = v
                break
    return out


def detect_precio_any(text: str) -> str:
    t = (text or "").replace(",", "")
    m = re.search(r"(?:Q\s*)?(\d{2,7})", t)
    return m.group(1) if m else "-"


def detect_estado_any(text: str) -> str:
    t = (text or "").lower()
    if "nuevo" in t:
        return "Nuevo"
    if "usado" in t or "usada" in t:
        return "Usado"
    if "seminuevo" in t or "semi nuevo" in t:
        return "Seminuevo"
    return "-"


def detect_anio_any(text: str) -> str:
    t = (text or "").lower().replace("–", "-")
    t = t.replace(" al ", "-").replace(" a ", "-")
    m = re.search(r"(19\d{2}|20\d{2})\s*-\s*(19\d{2}|20\d{2})", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m2 = re.search(r"(19\d{2}|20\d{2})", t)
    return m2.group(1) if m2 else "-"


def parse_pipe(text: str) -> dict | None:
    if "|" not in (text or ""):
        return None
    parts = [limpiar_texto(p) for p in text.split("|")]
    while len(parts) < 6:
        parts.append("-")
    producto, marca, linea, anio, precio, estado = parts[:6]
    return {
        "producto": producto,
        "marca": marca,
        "linea": linea,
        "anio": anio,
        "precio": re.sub(r"[^\d]", "", precio) or precio,
        "estado": estado,
        "medida": "-",
    }


def parse_free_text_blob(text: str) -> dict:
    t = limpiar_texto(text)
    return {
        "producto": t,
        "marca": "-",
        "linea": "-",
        "anio": detect_anio_any(t),
        "precio": detect_precio_any(t),
        "estado": detect_estado_any(t),
        "medida": "-",
    }


def parse_any(text: str) -> dict | None:
    if not text:
        return None

    d = parse_pipe(text)
    if d:
        return d

    d = parse_key_value_lines(text)

    if not d:
        d = parse_free_text_blob(text)

    d.setdefault("producto", "-")
    d.setdefault("marca", "-")
    d.setdefault("linea", "-")
    d.setdefault("anio", detect_anio_any(text))
    d.setdefault("precio", detect_precio_any(text))
    d.setdefault("estado", detect_estado_any(text))
    d.setdefault("medida", "-")

    if d.get("precio"):
        d["precio"] = re.sub(r"[^\d]", "", d["precio"]) or d["precio"]

    return d


def needs_more_data(data: dict | None) -> bool:
    if not data:
        return True
    for k in ("producto", "precio", "estado"):
        if not data.get(k) or data.get(k) == "-":
            return True
    return False


# -------------------------
# Guardado
# -------------------------
def make_folder(ts: str, data: dict | None) -> Path:
    producto_slug = slug((data or {}).get("producto", "") if data else "producto")
    folder = BASE_DIR / f"{ts}_{producto_slug}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_all(folder: Path, ts: str, data: dict, borrador: str):
    (folder / "borrador.txt").write_text(borrador, encoding="utf-8")
    (folder / "datos.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    record = {
        "ts": ts,
        "folder": str(folder),
        "foto": str(folder / "foto.jpg"),
        "thumb": str(folder / "thumb.jpg"),
        "borrador": str(folder / "borrador.txt"),
        "datos": data,
    }
    append_index(record)


# -------------------------
# SEO / Borrador
# -------------------------
def local_seo_fallback(data: dict) -> dict:
    producto = data.get("producto", "-").lower()
    marca = data.get("marca", "-").lower()
    linea = data.get("linea", "-").lower()
    anio = data.get("anio", "-")
    estado = data.get("estado", "-").lower()

    titulo = " ".join(
        [
            x for x in [
                data.get("producto", "-"),
                data.get("marca", "-"),
                data.get("linea", "-"),
                data.get("anio", "-"),
            ]
            if x and x != "-"
        ]
    ).strip() or "Publicación"

    intro = f"{data.get('producto', '-')} para {data.get('marca', '-')} {data.get('linea', '-')} {data.get('anio', '-')} disponible.".strip()

    descripcion = (
        f"{data.get('producto', '-')} en estado {estado} disponible para entrega. "
        f"Envíos a Guatemala. Paga al recibir según cobertura."
    )

    keywords = [
        f"{producto} {marca} {linea}".strip(),
        f"{producto} {linea} {anio}".strip(),
        f"{producto} usado original".strip(),
        f"repuestos {marca} guatemala".strip(),
        f"repuestos {linea} guatemala".strip(),
        f"pieza {producto} {marca}".strip(),
        f"{producto} para carro".strip(),
        f"autopartes {marca} guatemala".strip(),
        f"repuesto automotriz {linea}".strip(),
        f"{producto} {anio} guatemala".strip(),
        f"{producto} {marca} usado".strip(),
        f"parachoques {linea} {anio}".strip() if "bumper" in producto else f"{producto} {marca} repuesto".strip(),
    ]

    seen = set()
    clean = []
    for k in keywords:
        k = limpiar_texto(k)
        if not k:
            continue
        if len(k.split()) < 2:
            continue
        if k in seen:
            continue
        seen.add(k)
        clean.append(k)

    return {
        "titulo": titulo,
        "intro": intro,
        "descripcion": descripcion,
        "keywords": clean[:16],
    }


def keywords_to_lines(keywords: list[str]) -> str:
    """
    Mantiene frases completas.
    Si llegan palabras sueltas, las agrupa en frases de 2 a 4 palabras.
    """
    normalized = []
    for kw in (keywords or []):
        s = (kw or "").strip()
        s = s.replace("#", "")
        s = s.replace("•", " ").replace("—", " ").replace("|", " ")
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            normalized.append(s)

    clean = []
    seen = set()
    i = 0

    while i < len(normalized):
        s = normalized[i]

        if len(s.split()) >= 2:
            phrase = s
            i += 1
        else:
            chunk = [s]
            j = i + 1
            while j < len(normalized) and len(chunk) < 4 and len(normalized[j].split()) == 1:
                chunk.append(normalized[j])
                j += 1
            phrase = " ".join(chunk)
            i = j

        phrase = limpiar_texto(phrase)

        if len(phrase.split()) < 2:
            continue

        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        clean.append(phrase)

        if len(clean) >= 16:
            break

    return "\n".join(clean)


def build_borrador_final(data: dict) -> str:
    try:
        seo = generate_marketplace_seo(data)
    except Exception as e:
        print("AI FALLÓ, uso fallback local:", e)
        seo = local_seo_fallback(data)

    titulo = limpiar_texto(seo.get("titulo", "Publicación"))
    intro = limpiar_texto(seo.get("intro", ""))
    descripcion = (seo.get("descripcion", "") or "").strip()

    raw_keywords = seo.get("keywords", []) or []
    raw_keywords = [re.sub(r"#", "", (k or "")) for k in raw_keywords]
    keywords_block = keywords_to_lines(raw_keywords)

    producto = data.get("producto", "-")
    marca = data.get("marca", "-")
    linea = data.get("linea", "-")
    anio = data.get("anio", "-")
    precio = data.get("precio", "-")
    estado = data.get("estado", "-")

    return f"""{titulo}

{intro}

✅ Producto: {producto}
🚗 Vehículo: {marca} {linea} {anio}
💰 Precio: Q{precio}
📦 Estado: {estado}

{descripcion}

Palabras clave:
{keywords_block}
""".strip() + "\n"


# -------------------------
# Lógica principal
# -------------------------
async def build_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE, folder: Path, ts: str, text_data: str):
    data = parse_any(text_data)
    print("PARSED:", data)

    if needs_more_data(data):
        await update.message.reply_text(
            "Me faltan datos mínimos.\n"
            "Necesito al menos: Producto + Precio + Estado."
        )
        return

    borrador = build_borrador_final(data)
    save_all(folder, ts, data, borrador)
    copiado = copiar_portapapeles(borrador)

    context.user_data.pop("pending_folder", None)
    context.user_data.pop("pending_ts", None)
    context.user_data.pop("pending_text", None)

    await update.message.reply_text(
        "✅ Publicación lista.\n"
        f"📁 {folder}\n"
        + ("📋 Copiado al portapapeles." if copiado else "ℹ️ Guardado en borrador.txt.")
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Bot activo.\n\n"
        "Podés usarlo de 3 formas:\n"
        "1) Foto primero y luego datos\n"
        "2) Datos primero y luego foto\n"
        "3) Foto con caption\n\n"
        "Ejemplo:\n"
        "Producto: Bumper trasero\n"
        "Marca: Toyota\n"
        "Linea: Tacoma\n"
        "Año: 1996-2004\n"
        "Precio: 1300\n"
        "Estado: Usado Original"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg = update.message
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = make_folder(ts, {"producto": "foto"})

        photo = msg.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        img_path = folder / "foto.jpg"
        await file.download_to_drive(str(img_path))

        try:
            im = Image.open(img_path)
            im.thumbnail((900, 900))
            im.save(folder / "thumb.jpg", quality=85)
        except Exception as e:
            print("WARN thumb:", e)

        context.user_data["pending_folder"] = str(folder)
        context.user_data["pending_ts"] = ts

        caption = (msg.caption or "").strip()
        pending_text = (context.user_data.get("pending_text") or "").strip()

        print("FOTO OK ->", folder)
        print("CAPTION:", repr(caption))
        print("PENDING_TEXT:", repr(pending_text))

        text_data = caption or pending_text
        if text_data:
            await build_and_save(update, context, folder, ts, text_data)
            return

        await msg.reply_text(
            "✅ Foto guardada.\n\n"
            "Ahora mandame los datos.\n"
            "Mínimo: Producto + Precio + Estado."
        )
    except Exception as e:
        print("ERROR FOTO:", e)
        await update.message.reply_text(f"⚠️ Error guardando foto: {e}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        txt = (update.message.text or "").strip()
        print("TEXTO RECIBIDO:", repr(txt))

        folder_str = context.user_data.get("pending_folder")
        ts = context.user_data.get("pending_ts")

        print("PENDING:", folder_str, ts)

        if not folder_str or not ts:
            context.user_data["pending_text"] = txt
            await update.message.reply_text(
                "✅ Datos recibidos.\n"
                "Ahora mandame la foto para generar el borrador."
            )
            return

        folder = Path(folder_str)
        await build_and_save(update, context, folder, ts, txt)

    except Exception as e:
        print("ERROR TEXTO:", e)
        await update.message.reply_text(f"⚠️ Error procesando datos: {e}")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("ERROR GENERAL:", context.error)


def main():
    if not TOKEN:
        raise SystemExit("Falta TG_BOT_TOKEN")

    ensure_index_file()

    app = Application.builder().token(TOKEN).build()
    app.add_error_handler(on_error)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
