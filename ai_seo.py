# ~/cm_bot/ai_seo.py
import os
import json
import re
from openai import OpenAI
from pathlib import Path
import os

ENV_PATH = Path.home() / "cm_bot" / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")


def _years_expand(anio: str) -> str:
    anio = (anio or "").strip().replace("–", "-")
    m = re.search(r"(19\d{2}|20\d{2})\s*-\s*(19\d{2}|20\d{2})", anio)
    if not m:
        return anio
    a, b = int(m.group(1)), int(m.group(2))
    if b < a or (b - a) > 25:
        return f"{a}-{b}"
    return " ".join(str(y) for y in range(a, b + 1))


SEO_JSON_SCHEMA = {
    "name": "marketplace_seo",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "titulo": {"type": "string"},
            "intro": {"type": "string"},
            "descripcion": {"type": "string"},
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 10,
                "maxItems": 16,
            },
        },
        "required": ["titulo", "intro", "descripcion", "keywords"],
    },
    "strict": True,
}


def generate_marketplace_seo(data: dict) -> dict:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Falta OPENAI_API_KEY")

    producto = data.get("producto", "")
    marca = data.get("marca", "")
    linea = data.get("linea", "")
    anio = data.get("anio", "")
    precio = data.get("precio", "")
    estado = data.get("estado", "")
    medida = data.get("medida", "")

    years = _years_expand(anio)

    prompt = f"""
Sos experto en ventas de repuestos y SEO para Facebook Marketplace en Guatemala.

OBJETIVO:
- Crear 1 publicación lista para pegar en Marketplace.
- Maximizar coincidencia de búsqueda y mensajes.
- No usar hashtags.
- No incluir número de teléfono.
- Tono comercial profesional.

DATOS:
Producto: {producto}
Marca: {marca}
Línea/Modelo: {linea}
Año(s): {anio} (expandido: {years})
Precio: Q{precio}
Estado: {estado}
Detalle/Medida: {medida}

REGLAS:
1) TITULO: Producto + Marca + Línea + años individuales si aplica.
2) INTRO: repetir producto + modelo + años.
3) DESCRIPCION: natural, útil, sin spam.
4) KEYWORDS:
   - devolver entre 10 y 16 FRASES CORTAS
   - cada keyword debe tener entre 2 y 6 palabras
   - NO devolver palabras sueltas
   - NO devolver hashtags
   - incluir búsquedas reales tipo:
     "bumper trasero toyota tacoma"
     "parachoques trasero tacoma 1996"
     "repuestos toyota guatemala"
   - evitar repetir exactamente la misma frase
"""

    resp = client.responses.create(
        model=MODEL,
        input=[{"role": "user", "content": prompt}],
        text={
            "format": {
                "type": "json_schema",
                "name": SEO_JSON_SCHEMA["name"],
                "schema": SEO_JSON_SCHEMA["schema"],
                "strict": True,
            }
        },
    )

    return json.loads(resp.output_text)
