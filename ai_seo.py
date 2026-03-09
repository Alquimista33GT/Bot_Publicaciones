# ~/cm_bot/ai_seo.py
import os
import json
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

# =========================================================
# Cargar variables desde ~/.env si existe
# =========================================================
ENV_PATH = Path.home() / "cm_bot" / ".env"

if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")


API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini").strip()

if not API_KEY:
    raise RuntimeError("Falta OPENAI_API_KEY en ~/.env o variables de entorno")

client = OpenAI(api_key=API_KEY)


# =========================================================
# Utilidades generales
# =========================================================
def clean(x: Any) -> str:
    x = str(x or "").strip()
    x = re.sub(r"\s+", " ", x)
    return x


def normalize_text_for_kw(x: str) -> str:
    x = clean(x).lower()
    x = x.replace("#", "")
    x = re.sub(r"[|•;,:]+", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x


def unique_keep_order(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        normalized = normalize_text_for_kw(item)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(clean(item))
    return out


def join_non_empty(parts: list[str], sep: str = " ") -> str:
    return sep.join([clean(p) for p in parts if clean(p)]).strip()


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", clean(text))


# =========================================================
# Manejo de años
# =========================================================
def expand_years(anio: str) -> list[str]:
    raw = clean(anio)
    if not raw:
        return []

    txt = raw.replace("–", "-").replace("—", "-")
    txt = re.sub(r"\bal\b", "-", txt, flags=re.I)
    txt = re.sub(r"\ba\b", "-", txt, flags=re.I)
    txt = re.sub(r"\s+", " ", txt).strip()

    m = re.search(r"(19\d{2}|20\d{2})\s*-\s*(19\d{2}|20\d{2})", txt)
    if m:
        start = int(m.group(1))
        end = int(m.group(2))
        if end >= start and (end - start) <= 20:
            return [str(y) for y in range(start, end + 1)]

    singles = re.findall(r"(19\d{2}|20\d{2})", txt)
    singles = list(dict.fromkeys(singles))
    if singles:
        return singles

    return [raw]


# =========================================================
# Familias y sinónimos de repuestos
# =========================================================
PRODUCT_SYNONYMS = {
    "condensador": [
        "condensador",
        "condensador de aire",
        "condensador de aire acondicionado",
        "condensador ac",
        "radiador de aire acondicionado",
    ],
    "radiador": [
        "radiador",
        "radiador de agua",
        "radiador de motor",
        "enfriador de motor",
    ],
    "ventilador": [
        "ventilador",
        "ventilador de radiador",
        "ventilador de ac",
        "electroventilador",
        "fan de radiador",
    ],
    "bumper": [
        "bumper",
        "bumper delantero",
        "bumper trasero",
        "parachoques",
        "defensa",
    ],
    "faro": [
        "faro",
        "faro delantero",
        "silvin",
        "foco delantero",
        "lampara delantera",
    ],
    "retrovisor": [
        "retrovisor",
        "espejo lateral",
        "espejo retrovisor",
    ],
    "tablero": [
        "tablero",
        "dashboard",
        "panel frontal",
        "tablero interior",
    ],
    "parrilla": [
        "parrilla",
        "rejilla",
        "grilla frontal",
    ],
    "compresor": [
        "compresor",
        "compresor de aire",
        "compresor de ac",
        "compresor de aire acondicionado",
    ],
    "turbo": [
        "turbo",
        "turbocargador",
        "turbo cargador",
    ],
    "llanta": [
        "llanta",
        "neumatico",
        "llanta de carro",
        "juego de llantas",
    ],
    "aro": [
        "aro",
        "aros",
        "rin",
        "rines",
        "juego de aros",
    ],
}


def detect_product_family(producto: str) -> str:
    p = normalize_text_for_kw(producto)

    if "condensador" in p:
        return "condensador"
    if "radiador" in p:
        return "radiador"
    if "ventilador" in p or "electroventilador" in p or "fan" in p:
        return "ventilador"
    if "bumper" in p or "parachoques" in p or "defensa" in p:
        return "bumper"
    if "faro" in p or "silvin" in p or "foco delantero" in p:
        return "faro"
    if "retrovisor" in p or "espejo lateral" in p:
        return "retrovisor"
    if "tablero" in p or "dashboard" in p:
        return "tablero"
    if "parrilla" in p or "rejilla" in p:
        return "parrilla"
    if "compresor" in p:
        return "compresor"
    if "turbo" in p:
        return "turbo"
    if "llanta" in p or "neumatico" in p:
        return "llanta"
    if "aro" in p or "rin" in p or "rines" in p:
        return "aro"

    return ""


def get_product_variations(producto: str) -> list[str]:
    producto = clean(producto)
    fam = detect_product_family(producto)

    out = [producto] if producto else []

    if fam and fam in PRODUCT_SYNONYMS:
        out.extend(PRODUCT_SYNONYMS[fam])

    return unique_keep_order(out)


# =========================================================
# Parseo robusto de JSON
# =========================================================
def parse_json_from_text(txt: str) -> dict:
    txt = (txt or "").strip()
    if not txt:
        raise RuntimeError("IA devolvió respuesta vacía")

    try:
        return json.loads(txt)
    except Exception:
        pass

    match = re.search(r"\{.*\}", txt, re.S)
    if match:
        possible = match.group(0).strip()
        try:
            return json.loads(possible)
        except Exception:
            pass

    raise RuntimeError("IA no devolvió JSON válido")


def extract_response_text(response) -> str:
    txt = ""

    try:
        txt = response.output_text
    except Exception:
        pass

    if txt:
        return txt.strip()

    try:
        outputs = getattr(response, "output", []) or []
        pieces = []

        for item in outputs:
            contents = getattr(item, "content", []) or []
            for c in contents:
                ctype = getattr(c, "type", "")
                if ctype in ("output_text", "text"):
                    value = getattr(c, "text", "")
                    if value:
                        pieces.append(value)

        txt = "\n".join(pieces).strip()
        if txt:
            return txt
    except Exception:
        pass

    try:
        raw = response.model_dump()
        return json.dumps(raw, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return ""


# =========================================================
# Keywords fallback
# =========================================================
def build_fallback_keywords(
    producto: str,
    marca: str,
    linea: str,
    anio: str,
    estado: str = "",
    medida: str = "",
    motor: str = "",
) -> list[str]:
    producto = clean(producto)
    marca = clean(marca)
    linea = clean(linea)
    anio = clean(anio)
    estado = clean(estado)
    medida = clean(medida)
    motor = clean(motor)

    years = expand_years(anio)
    vehicle = join_non_empty([marca, linea])
    product_forms = get_product_variations(producto)

    kws = []

    for pf in product_forms[:8]:
        kws.append(join_non_empty([pf, marca, linea]))
        kws.append(join_non_empty([pf, "para", marca, linea]))
        kws.append(join_non_empty([pf, marca]))
        kws.append(join_non_empty([pf, linea]))
        kws.append(join_non_empty([pf, "guatemala"]))
        kws.append(join_non_empty([pf, vehicle, "guatemala"]))
        kws.append(join_non_empty(["repuestos", marca, "guatemala"]))
        kws.append(join_non_empty(["autopartes", marca, "guatemala"]))
        kws.append(join_non_empty(["repuestos", vehicle, "guatemala"]))
        kws.append(join_non_empty([pf, "marketplace guatemala"]))
        kws.append(join_non_empty([pf, "disponible guatemala"]))
        kws.append(join_non_empty([pf, "original", marca]))
        kws.append(join_non_empty([pf, "usado", marca]))
        kws.append(join_non_empty([pf, "usado original", marca]))

        if motor:
            kws.append(join_non_empty([pf, marca, linea, motor]))
            kws.append(join_non_empty([pf, "para", marca, linea, motor]))

        if medida:
            kws.append(join_non_empty([pf, medida]))
            kws.append(join_non_empty([pf, marca, linea, medida]))

    for y in years[:10]:
        for pf in product_forms[:5]:
            kws.append(join_non_empty([pf, marca, linea, y]))
            kws.append(join_non_empty([pf, "para", marca, linea, y]))

    fam = detect_product_family(producto)

    if fam == "ventilador":
        kws.extend([
            join_non_empty(["ventilador de radiador", marca, linea]),
            join_non_empty(["fan de radiador", marca, linea]),
            join_non_empty(["electroventilador", marca, linea]),
        ])

    if fam == "condensador":
        kws.extend([
            join_non_empty(["condensador de aire", marca, linea]),
            join_non_empty(["condensador ac", marca, linea]),
            join_non_empty(["radiador de aire acondicionado", marca, linea]),
        ])

    if fam == "radiador":
        kws.extend([
            join_non_empty(["radiador de agua", marca, linea]),
            join_non_empty(["radiador de motor", marca, linea]),
        ])

    if fam == "bumper":
        kws.extend([
            join_non_empty(["bumper delantero", marca, linea]),
            join_non_empty(["bumper trasero", marca, linea]),
            join_non_empty(["parachoques", marca, linea]),
        ])

    if fam == "faro":
        kws.extend([
            join_non_empty(["faro delantero", marca, linea]),
            join_non_empty(["silvin", marca, linea]),
            join_non_empty(["foco delantero", marca, linea]),
        ])

    if fam == "llanta":
        kws.extend([
            join_non_empty(["llantas", marca, linea]),
            join_non_empty(["juego de llantas", marca, linea]),
        ])

    if fam == "aro":
        kws.extend([
            join_non_empty(["aros", marca, linea]),
            join_non_empty(["juego de aros", marca, linea]),
            join_non_empty(["rines", marca, linea]),
        ])

    kws = [normalize_text_for_kw(x) for x in kws if clean(x)]
    kws = unique_keep_order(kws)

    final = []
    for kw in kws:
        words = kw.split()
        if 2 <= len(words) <= 7:
            final.append(kw)
        if len(final) >= 24:
            break

    return final


# =========================================================
# Normalización de salida
# =========================================================
def normalize_title(titulo: str, producto: str, marca: str, linea: str, anio: str) -> str:
    titulo = clean(titulo)
    if not titulo:
        titulo = clean(f"{producto} {marca} {linea} {anio}")

    titulo = normalize_spaces(titulo)
    words = titulo.split()
    if len(words) > 18:
        titulo = " ".join(words[:18])

    return titulo


def normalize_keywords(
    keywords: Any,
    producto: str,
    marca: str,
    linea: str,
    anio: str,
    estado: str = "",
    medida: str = "",
    motor: str = "",
) -> list[str]:
    out = []
    seen = set()

    if isinstance(keywords, str):
        items = re.split(r"[\n,;|]+", keywords)
    elif isinstance(keywords, list):
        items = keywords
    else:
        items = []

    for item in items:
        kw = normalize_text_for_kw(str(item))
        if not kw:
            continue
        wc = len(kw.split())
        if wc < 2 or wc > 7:
            continue
        if kw in seen:
            continue
        seen.add(kw)
        out.append(kw)

    if len(out) < 18:
        extra = build_fallback_keywords(
            producto=producto,
            marca=marca,
            linea=linea,
            anio=anio,
            estado=estado,
            medida=medida,
            motor=motor,
        )
        for kw in extra:
            if kw in seen:
                continue
            seen.add(kw)
            out.append(kw)
            if len(out) >= 20:
                break

    return out[:20]


def fallback_payload(
    producto: str,
    marca: str,
    linea: str,
    anio: str,
    estado: str,
    precio: str = "",
    medida: str = "",
    motor: str = "",
) -> dict:
    years = expand_years(anio)
    years_text = ", ".join(years) if years else anio

    titulo = clean(f"{producto} {marca} {linea} {anio}")

    intro = clean(
        f"{producto} para {marca} {linea} compatible con modelos {years_text}."
    )

    descripcion_parts = [
        f"{producto} disponible para {marca} {linea}.",
        f"Compatible con años {years_text}." if years_text else "",
        f"Motor: {motor}." if motor else "",
        f"Detalle o medida: {medida}." if medida else "",
        f"Estado: {estado}." if estado else "",
        f"Precio: Q{precio}." if precio else "",
        "Ideal para búsquedas en Marketplace Guatemala.",
    ]
    descripcion = clean(" ".join([p for p in descripcion_parts if clean(p)]))

    keywords = build_fallback_keywords(
        producto=producto,
        marca=marca,
        linea=linea,
        anio=anio,
        estado=estado,
        medida=medida,
        motor=motor,
    )

    return {
        "titulo": titulo,
        "intro": intro,
        "descripcion": descripcion,
        "keywords": keywords[:20],
    }


# =========================================================
# Generación principal
# =========================================================
def generate_marketplace_seo(data: dict) -> dict:
    producto = clean(data.get("producto", ""))
    marca = clean(data.get("marca", ""))
    linea = clean(data.get("linea", ""))
    anio = clean(data.get("anio", ""))
    estado = clean(data.get("estado", ""))
    precio = clean(data.get("precio", ""))
    medida = clean(data.get("medida", ""))
    motor = clean(data.get("motor", ""))

    if not producto:
        raise ValueError("Falta producto")

    years = expand_years(anio)
    years_text = ", ".join(years) if years else anio
    variations = get_product_variations(producto)
    variations_text = ", ".join(variations[:10])

    prompt = f"""
Eres un experto en SEO para Facebook Marketplace en Guatemala, especializado en repuestos automotrices.

Genera contenido optimizado para este producto:

Producto: {producto}
Marca: {marca}
Línea / modelo: {linea}
Año(s): {anio}
Años expandidos: {years_text}
Motor: {motor}
Estado: {estado}
Precio: {precio}
Detalle adicional / medida: {medida}
Variaciones del producto: {variations_text}

Objetivo:
- Crear un título con intención de búsqueda
- Crear una introducción clara
- Crear una descripción persuasiva
- Generar de 18 a 20 keywords tipo frase para búsquedas reales de Marketplace

Reglas:
- Responde en español
- No uses hashtags
- No uses emojis
- No inventes información no proporcionada
- Las keywords deben ser frases entre 2 y 7 palabras
- No repitas frases
- Prioriza búsquedas reales en Guatemala
- Incluye variaciones por marca, línea, años, estado, motor o medida si aplica
- Devuelve únicamente JSON válido

Formato exacto:
{{
  "titulo": "string",
  "intro": "string",
  "descripcion": "string",
  "keywords": ["frase 1", "frase 2", "frase 3"]
}}
""".strip()

    try:
        response = client.responses.create(
            model=MODEL,
            input=prompt,
        )

        txt = extract_response_text(response)
        print("RAW IA RESPONSE:")
        print(txt if txt else "[VACIO]")

        if not txt:
            raise RuntimeError("IA devolvió respuesta vacía")

        parsed = parse_json_from_text(txt)

        titulo = normalize_title(
            parsed.get("titulo", ""),
            producto=producto,
            marca=marca,
            linea=linea,
            anio=anio,
        )

        intro = clean(parsed.get("intro", ""))
        descripcion = clean(parsed.get("descripcion", ""))

        keywords = normalize_keywords(
            parsed.get("keywords", []),
            producto=producto,
            marca=marca,
            linea=linea,
            anio=anio,
            estado=estado,
            medida=medida,
            motor=motor,
        )

        if not intro:
            intro = clean(
                f"{producto} para {marca} {linea} compatible con modelos {years_text}."
            )

        if not descripcion:
            descripcion_parts = [
                f"{producto} disponible para {marca} {linea}.",
                f"Compatible con modelos {years_text}." if years_text else "",
                f"Motor: {motor}." if motor else "",
                f"Detalle o medida: {medida}." if medida else "",
                f"Estado: {estado}." if estado else "",
            ]
            descripcion = clean(" ".join([x for x in descripcion_parts if clean(x)]))

        if len(keywords) < 10:
            raise RuntimeError("La IA devolvió pocas keywords útiles")

        return {
            "titulo": titulo,
            "intro": intro,
            "descripcion": descripcion,
            "keywords": keywords,
        }

    except Exception as e:
        print("WARN ai_seo fallback:", e)
        return fallback_payload(
            producto=producto,
            marca=marca,
            linea=linea,
            anio=anio,
            estado=estado,
            precio=precio,
            medida=medida,
            motor=motor,
        )


# =========================================================
# Test manual
# =========================================================
if __name__ == "__main__":
    ejemplo = {
        "producto": "Juego de Llantas y Aros",
        "marca": "Honda",
        "linea": "Civic",
        "anio": "2001-2005",
        "precio": "2250",
        "estado": "Usado Original",
        "motor": "",
        "medida": "195/65R15",
    }

    resultado = generate_marketplace_seo(ejemplo)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
