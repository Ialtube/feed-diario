"""Optional: let Claude rewrite the template headlines so they read funnier.

Only runs when ANTHROPIC_API_KEY is set and the `anthropic` package is installed.
The facts never change here: Claude only rewrites wording, and any problem (no key,
network error, refusal, bad JSON) leaves the template text untouched.
"""
import json
import os

SYSTEM = """Eres el redactor jefe de «El Rincón del Feeder», un periódico satírico que un grupo de amigos \
lee cada mañana sobre sus propias partidas de League of Legends. Reescribes titulares y entradillas \
para que piquen más y hagan reír al grupo.

Reglas:
- Español de España, humor de colegas, ironía y exageración periodística (sucesos, deportes, economía...).
- Métete solo con su forma de jugar: muertes, daño, farmeo, decisiones, rachas. Nunca con su físico, \
familia, origen, orientación, salud ni nada fuera del juego. Nada de insultos graves.
- Conserva exactamente todas las cifras, nombres de jugadores y campeones que aparecen en el texto \
original. No inventes datos nuevos.
- Titular de 110 caracteres como máximo. Cuerpo de 1 a 3 frases, 320 caracteres como máximo.
- Devuelve una entrada por cada noticia recibida, con el mismo id."""

SCHEMA = {
    "type": "object",
    "properties": {
        "noticias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "titular": {"type": "string"},
                    "cuerpo": {"type": "string"},
                },
                "required": ["id", "titular", "cuerpo"],
                "additionalProperties": False,
            },
        },
        "frase_del_dia": {"type": "string"},
    },
    "required": ["noticias", "frase_del_dia"],
    "additionalProperties": False,
}


def polish(edition, model, log=print):
    """Returns True if Claude rewrote the edition in place."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic
    except ImportError:
        log("  (anthropic no está instalado: se usan los titulares de plantilla)")
        return False

    payload = {
        "fecha": edition["date"],
        "frase_del_dia_actual": edition["frase"],
        "noticias": [{"id": it["id"], "seccion": it["section"], "jugador": it["alias"],
                      "titular": it["headline"], "cuerpo": it["body"],
                      "dato": f"{it['stat']} {it['stat_label']}"} for it in edition["items"]],
    }
    client = anthropic.Anthropic()
    try:
        resp = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "high",
                           "format": {"type": "json_schema", "schema": SCHEMA}},
            system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
    except anthropic.RateLimitError:
        log("  ! Claude: límite de peticiones; se usan las plantillas")
        return False
    except anthropic.APIStatusError as e:
        log(f"  ! Claude devolvió HTTP {e.status_code}; se usan las plantillas")
        return False
    except anthropic.APIConnectionError:
        log("  ! Claude: sin conexión; se usan las plantillas")
        return False

    if resp.stop_reason in ("refusal", "max_tokens"):
        log(f"  ! Claude terminó con {resp.stop_reason}; se usan las plantillas")
        return False
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log("  ! Claude devolvió JSON inválido; se usan las plantillas")
        return False

    by_id = {n["id"]: n for n in data.get("noticias", [])}
    changed = 0
    for it in edition["items"]:
        n = by_id.get(it["id"])
        if not n:
            continue
        head, body = n["titular"].strip(), n["cuerpo"].strip()
        if 10 <= len(head) <= 140 and 10 <= len(body) <= 420:
            it["template_headline"], it["template_body"] = it["headline"], it["body"]
            it["headline"], it["body"] = head, body
            changed += 1
    frase = (data.get("frase_del_dia") or "").strip()
    if 10 <= len(frase) <= 200:
        edition["frase"] = frase
    edition["written_by"] = resp.model
    log(f"  Claude ({resp.model}) ha reescrito {changed} de {len(edition['items'])} noticias")
    return changed > 0
