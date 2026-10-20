"""The admin's corrections and the newspaper's style memory.

The admin edits stories on the website (edit mode). Each change is stored in Supabase as
before/after. Here we:
  * apply them to the stored editions (so the static pages carry them),
  * keep them as examples in data/estilo.json,
  * hand the new ones to Claude, who must work out *why* the admin changed them and turn that
    into style guidelines (not copy the jokes) that every following edition follows.
"""
from . import lectores
from .util import ROOT, load_json, save_json

STATE_FILE = ROOT / "data" / "correcciones.json"
STYLE_FILE = ROOT / "data" / "estilo.json"
MAX_EXAMPLES = 40


def _state(path=None):
    return load_json(path or STATE_FILE, None) or {"aplicadas": []}


def load_style(path=None):
    st = load_json(path or STYLE_FILE, None) or {}
    st.setdefault("pautas", [])
    st.setdefault("ejemplos", [])
    return st


def fetch(cfg):
    return lectores._get(cfg, "correcciones", [("select", "id,edicion,pieza,campo,antes,despues,nota,created_at"),
                                               ("order", "id.asc"), ("limit", "500")])


def _apply_one(edition, c):
    campo, pieza, text = c["campo"], c["pieza"], c["despues"]
    if campo == "frase":
        edition["frase"] = text
        return True
    if campo.startswith("columna.") and edition.get("columna"):
        if campo == "columna.titulo":
            edition["columna"]["titulo"] = text
        else:
            edition["columna"]["cuerpo"] = [p.strip() for p in text.split("\n\n") if p.strip()]
        return True
    for it in edition.get("items", []):
        if it.get("id") == pieza and campo in ("headline", "subtitulo", "body"):
            it[campo] = text
            return True
    return False


def sync(cfg, store, rows=None, state_path=None, style_path=None):
    """Applies the corrections not seen yet and records them as style examples. Returns the new ones."""
    rows = fetch(cfg) if rows is None else rows
    if not rows:
        return []
    st = _state(state_path)
    done = set(st["aplicadas"])
    style = load_style(style_path)
    new = []
    for c in rows:
        if c["id"] in done:
            continue
        ed = store.edition(str(c["edicion"]))
        if ed and _apply_one(ed, c):
            ed.setdefault("correcciones", []).append({k: c.get(k) for k in ("id", "pieza", "campo", "created_at")})
            store.save_edition(ed)
        style["ejemplos"].append({"id": c["id"], "edicion": str(c["edicion"]), "campo": c["campo"],
                                  "antes": c["antes"], "despues": c["despues"], "nota": c.get("nota"),
                                  "analizado": False})
        st["aplicadas"].append(c["id"])
        new.append(c)
    style["ejemplos"] = style["ejemplos"][-MAX_EXAMPLES:]
    save_json(state_path or STATE_FILE, st)
    save_json(style_path or STYLE_FILE, style)
    return new


def for_context(style_path=None):
    style = load_style(style_path)
    return {
        "pautas": style["pautas"],
        "correcciones_nuevas": [e for e in style["ejemplos"] if not e.get("analizado")],
        "ejemplos_anteriores": [e for e in style["ejemplos"] if e.get("analizado")][-15:],
    }


def apply_learning(changes, date, style_path=None):
    """Merges the guidelines Claude drew from the corrections; re-applying a date replaces its own."""
    style = load_style(style_path)
    style["pautas"] = [p for p in style["pautas"] if p.get("desde") != date]
    retire = {t.strip().lower() for t in changes.get("pautas_retiradas") or []}
    style["pautas"] = [p for p in style["pautas"] if p["texto"].strip().lower() not in retire]
    for t in changes.get("pautas_nuevas") or []:
        style["pautas"].append({"texto": t.strip(), "desde": date})
    for e in style["ejemplos"]:
        if not e.get("analizado") and changes.get("pautas_nuevas"):
            e["analizado"] = date
    save_json(style_path or STYLE_FILE, style)
    return style
