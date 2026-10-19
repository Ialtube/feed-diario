"""AI edition support for the daily Claude routine.

Flow (see ai/GUIA.md):
  1. python -m roast ai-context            -> ai/contexto-AAAA-MM-DD.json (everything Claude needs)
  2. Claude writes ai/edicion-AAAA-MM-DD.json
  3. python -m roast apply-ai <file>       -> validates, merges into the day's edition, rebuilds docs/
"""
import re
import time
from pathlib import Path

from .site import general_leaderboard
from .util import ROOT, load_json, save_json

EVENTS_FILE = ROOT / "eventos.md"
AI_DIR = ROOT / "ai"
THEMES = ("rojo", "oro", "negro", "verde", "azul", "morado")
MAX_EXTRA = 6


class AIError(ValueError):
    pass


# --------------------------------------------------------------------------- events file
def read_events(path=EVENTS_FILE):
    """Returns the pending events ('- ' lines under '## Pendientes')."""
    if not Path(path).exists():
        return []
    pending, section = [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if section == "pendientes" and line.strip().startswith("- "):
            text = line.strip()[2:].strip()
            if text and not text.startswith("("):
                pending.append(text)
    return [{"n": i + 1, "texto": t} for i, t in enumerate(pending)]


def mark_events_published(numbers, date_str, path=EVENTS_FILE):
    if not numbers or not Path(path).exists():
        return 0
    events = {e["n"]: e["texto"] for e in read_events(path)}
    used = [events[n] for n in numbers if n in events]
    if not used:
        return 0
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    out, section, removed = [], None, set()
    for line in lines:
        if line.startswith("## "):
            section = line[3:].strip().lower()
        if section == "pendientes" and line.strip().startswith("- ") and line.strip()[2:].strip() in used \
                and line.strip()[2:].strip() not in removed:
            removed.add(line.strip()[2:].strip())
            continue
        out.append(line)
        if line.strip().lower() == "## publicados":
            out += [f"- {date_str} · {t}" for t in used]
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")
    return len(used)


# --------------------------------------------------------------------------- status
def ai_status(edition):
    """'pendiente' (never rewritten), 'obsoleta' (re-generated after a rewrite) or 'hecha'."""
    if not edition.get("ai"):
        return "pendiente"
    return "obsoleta" if edition["ai"].get("stale") else "hecha"


# --------------------------------------------------------------------------- context
def build_context(store, date_str, history_days=7):
    editions = sorted(store.editions(), key=lambda e: e["date"])
    today = next((e for e in editions if e["date"] == date_str), None)
    if not today:
        raise AIError(f"No existe la edición del {date_str}. Ejecuta antes el robot (python -m roast run) "
                      "o lanza el workflow de GitHub.")
    previous = [e for e in editions if e["date"] < date_str][-history_days:]
    events = read_events()
    weekday = time.strptime(date_str, "%Y-%m-%d").tm_wday
    return {
        "fecha": date_str,
        "dia_semana": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][weekday],
        "numero": today["number"],
        "estado_ia": ai_status(today),
        "eventos_pendientes": events,
        "noticias": [{k: it.get(k) for k in ("id", "kind", "section", "player", "alias", "headline", "body",
                                              "stat", "stat_label", "facts")}
                     for it in today["items"] if it.get("kind") != "ia"],
        "clasificacion_hoy": today["ranking"],
        "partidas_hoy": today["games"],
        "duos": today["duos"],
        "derbis": today["derbies"],
        "totales": today["totals"],
        "ausentes": today["absent"],
        "frase_actual": today["frase"],
        "general_verguenza": general_leaderboard(editions[:editions.index(today) + 1]),
        "historial": [{
            "fecha": e["date"],
            "portada": e["items"][0]["headline"] if e["items"] else None,
            "clasificacion": [{k: r[k] for k in ("alias", "games", "wins", "losses", "kda", "d", "score")}
                              for r in e["ranking"]],
            "columna": (e.get("columna") or {}).get("titulo"),
            "especial": (e.get("especial") or {}).get("titulo"),
        } for e in previous],
        "jugadores": sorted({r["slug"]: r["alias"] for e in editions for r in e["ranking"]}.items()),
    }


def write_context(store, date_str):
    ctx = build_context(store, date_str)
    path = AI_DIR / f"contexto-{date_str}.json"
    save_json(path, ctx)
    return path, ctx


# --------------------------------------------------------------------------- validation + merge
def _text(value, field, lo, hi):
    if not isinstance(value, str):
        raise AIError(f"'{field}' debe ser texto")
    v = re.sub(r"\s+", " ", value).strip()
    if not lo <= len(v) <= hi:
        raise AIError(f"'{field}' debe tener entre {lo} y {hi} caracteres (tiene {len(v)}): {v[:60]!r}")
    return v


def validate(data, edition, known_slugs):
    if not isinstance(data, dict):
        raise AIError("El archivo debe ser un objeto JSON")
    ids = {it["id"] for it in edition["items"] if it.get("kind") != "ia"}
    clean = {"items": [], "extra": [], "columna": None, "especial": None, "frase": None,
             "eventos_usados": [], "firma": "Claude"}

    for i, it in enumerate(data.get("items") or []):
        if it.get("id") not in ids:
            raise AIError(f"items[{i}]: id {it.get('id')!r} no existe en la edición de hoy")
        clean["items"].append({"id": it["id"],
                               "headline": _text(it.get("headline"), f"items[{i}].headline", 8, 160),
                               "body": _text(it.get("body"), f"items[{i}].body", 10, 700)})

    extra = data.get("extra") or []
    if len(extra) > MAX_EXTRA:
        raise AIError(f"Como mucho {MAX_EXTRA} artículos extra")
    for i, it in enumerate(extra):
        player = it.get("player")
        if player is not None and player not in known_slugs:
            raise AIError(f"extra[{i}].player {player!r} no es un jugador conocido ({', '.join(sorted(known_slugs))})")
        clean["extra"].append({
            "section": _text(it.get("section") or "OPINIÓN", f"extra[{i}].section", 3, 24).upper(),
            "headline": _text(it.get("headline"), f"extra[{i}].headline", 8, 160),
            "body": _text(it.get("body"), f"extra[{i}].body", 10, 900),
            "stat": _text(it.get("stat") or "", f"extra[{i}].stat", 0, 16),
            "stat_label": _text(it.get("stat_label") or "", f"extra[{i}].stat_label", 0, 50),
            "player": player,
            "portada": bool(it.get("portada")),
        })
    if sum(e["portada"] for e in clean["extra"]) > 1:
        raise AIError("Solo un artículo extra puede llevar portada: true")

    col = data.get("columna")
    if col:
        paras = col.get("cuerpo") or []
        if not isinstance(paras, list) or not 1 <= len(paras) <= 6:
            raise AIError("columna.cuerpo debe ser una lista de 1 a 6 párrafos")
        clean["columna"] = {
            "titulo": _text(col.get("titulo"), "columna.titulo", 5, 120),
            "autor": _text(col.get("autor") or "La Redacción", "columna.autor", 3, 60),
            "cuerpo": [_text(p, f"columna.cuerpo[{i}]", 20, 900) for i, p in enumerate(paras)],
        }

    esp = data.get("especial")
    if esp:
        tema = esp.get("tema") or "rojo"
        if tema not in THEMES:
            raise AIError(f"especial.tema debe ser uno de {THEMES}")
        clean["especial"] = {
            "antetitulo": _text(esp.get("antetitulo") or "EDICIÓN ESPECIAL", "especial.antetitulo", 3, 40).upper(),
            "titulo": _text(esp.get("titulo"), "especial.titulo", 5, 120),
            "subtitulo": _text(esp.get("subtitulo") or "", "especial.subtitulo", 0, 260),
            "tema": tema,
        }

    if data.get("frase"):
        clean["frase"] = _text(data["frase"], "frase", 10, 220)
    used = data.get("eventos_usados") or []
    if not all(isinstance(n, int) for n in used):
        raise AIError("eventos_usados debe ser una lista de números (el campo 'n' del contexto)")
    clean["eventos_usados"] = used
    if data.get("firma"):
        clean["firma"] = _text(data["firma"], "firma", 3, 60)
    if not (clean["items"] or clean["extra"] or clean["columna"] or clean["especial"]):
        raise AIError("No hay nada que aplicar: reescribe noticias, añade extra, columna o especial")
    return clean


def apply(edition, clean, date_str):
    """Merges validated AI content into the edition (in place)."""
    # start from the template text so re-applying is idempotent
    base = [it for it in edition["items"] if it.get("kind") != "ia"]
    for it in base:
        if "template_headline" in it:
            it["headline"], it["body"] = it.pop("template_headline"), it.pop("template_body")
    by_id = {it["id"]: it for it in base}
    for rw in clean["items"]:
        it = by_id[rw["id"]]
        it["template_headline"], it["template_body"] = it["headline"], it["body"]
        it["headline"], it["body"] = rw["headline"], rw["body"]

    extras = []
    for i, e in enumerate(clean["extra"]):
        extras.append({
            "id": 1000 + i,  # template items keep their ids so a later context/apply still matches
            "kind": "ia", "section": e["section"], "player": e["player"],
            "alias": None, "headline": e["headline"], "body": e["body"],
            "stat": e["stat"], "stat_label": e["stat_label"],
            # an extra marked as front page goes first; the rest right after the front page
            "severity": 1000 if e["portada"] else 99 - i, "facts": {},
        })
    aliases = {r["slug"]: r["alias"] for r in edition["ranking"]}
    for e in extras:
        e["alias"] = aliases.get(e["player"]) if e["player"] else None
    if any(e["severity"] == 1000 for e in extras):
        for it in base:
            if it["kind"] in ("portada", "vacio"):
                it["section"] = "TAMBIÉN EN PORTADA" if it["section"] == "PORTADA" else it["section"]
    edition["items"] = sorted(base + extras, key=lambda it: -it["severity"])
    if "template_frase" not in edition:
        edition["template_frase"] = edition["frase"]
    edition["frase"] = clean["frase"] or edition["template_frase"]
    edition["columna"] = clean["columna"]
    edition["especial"] = clean["especial"]
    prev = edition.get("ai") or {}
    edition["ai"] = {"version": prev.get("version", 0) + 1, "updated_at": int(time.time() * 1000),
                     "firma": clean["firma"], "stale": False}
    edition["written_by"] = clean["firma"]
    return edition


def apply_file(store, path, date_str=None):
    data = load_json(path)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", Path(path).name)
    date_str = date_str or (m.group(1) if m else None)
    if not date_str:
        raise AIError("No sé a qué día corresponde: usa --date AAAA-MM-DD")
    edition = store.edition(date_str)
    if not edition:
        raise AIError(f"No existe la edición del {date_str}")
    known = {r["slug"] for e in store.editions() for r in e["ranking"]}
    clean = validate(data, edition, known)
    apply(edition, clean, date_str)
    store.save_edition(edition)
    published = mark_events_published(clean["eventos_usados"], date_str)
    return edition, clean, published


def mark_stale_on_regenerate(old, new):
    """Called by `run` when it regenerates a day that already had an AI pass: keep the
    column/special/extras and flag it so the routine rewrites it again."""
    if not old or not old.get("ai"):
        return new
    new["columna"] = old.get("columna")
    new["especial"] = old.get("especial")
    extras = [it for it in old["items"] if it.get("kind") == "ia"]
    if extras:
        new["items"] = sorted(new["items"] + extras, key=lambda it: -it["severity"])
    new["ai"] = dict(old["ai"], stale=True)
    return new
