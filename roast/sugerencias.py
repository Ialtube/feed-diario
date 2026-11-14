"""The suggestion box of the SoloQ Challenge board: readers ask for cards, data or changes they want
to see, and the next day the newspaper's AI newsroom does them, without asking the admin.

- A suggestion that can be answered with the race's data becomes a card nailed to the board
  (a figure, a list, bars, a table or a short text), refreshed every day by the newsroom: «hecha».
- One that needs a change in the website or in the race's rules is programmed and applied right
  away: «aplicada», with what changed in ``motivo``.
- Only the ones that make no sense, already exist, attack someone outside the game or would expose
  private data or the site's security are discarded, with the reason.
Every «hecha» or «aplicada» suggestion is announced once on Discord (``roast soloq``).

The newsroom's decisions and the cards live in each edition (``sugerencias_tablon`` and
``tarjetas``), so they travel with the paper. A change programmed by hand in a Claude Code session is
written down in data/soloq/buzon_decisiones.json (``apuntar``), which has the last word.
data/soloq/sugerencias.json only caches what was pending when the context was written, for the
validator. The old «permiso» and «programar» (the admin's permission, until 2026-11-14) count as
pending again unless the admin rejected them."""
import re

from .lectores import _get as supabase_get
from .util import load_json, save_json

TIPOS = {
    "cifra": 'una cifra grande: {"valor": "≤24", "etiqueta": "≤100", "quien": "opcional ≤40"}',
    "lista": 'un ranking: {"filas": [{"nombre": "≤40", "valor": "≤30"}, …]} (1–12 filas)',
    "barras": 'barras horizontales: {"filas": [{"nombre": "≤40", "valor": número, "texto": "opcional ≤20"}, …]} (1–12)',
    "tabla": 'una tabla: {"columnas": ["≤24", …] (2–6), "filas": [["≤30", …], …] (1–15, tantas celdas como columnas)}',
    "texto": 'un texto corto: {"texto": "≤600"}',
}
DECISIONES = ("hecha", "aplicada", "descartada")
ANTIGUAS = ("permiso", "programar")     # waited for the admin until 2026-11-14: back in the box
MAX_TARJETAS = 10
ESTADOS = {  # what the board stamps on each suggestion
    "pendiente": "En el buzón", "hecha": "Hecha", "aplicada": "Aplicada", "descartada": "Descartada",
    "rechazada": "Rechazada por el jefe",
}


class SugerenciaError(ValueError):
    pass


def leer(cfg):
    """(suggestions, the admin's decisions) from Supabase; (None, None) if it could not be read."""
    rows = supabase_get(cfg, "soloq_sugerencias", [("select", "id,nombre,texto,created_at"), ("order", "id.desc"),
                                                    ("limit", "200")])
    perms = supabase_get(cfg, "soloq_permisos", [("select", "sugerencia,decision,nota,created_at"), ("order", "id.asc"),
                                                 ("limit", "1000")])
    return rows, perms


def manuales(path):
    """The decisions written down by hand (``apuntar``): [{id, decision, motivo, fecha}]."""
    return load_json(path, None) or []


def apuntar(path, sid, decision, motivo, fecha):
    """Write down a decision taken outside the daily edition (a change programmed in a Claude Code session)."""
    if decision not in DECISIONES:
        raise SugerenciaError(f"decision debe ser una de {', '.join(DECISIONES)}")
    rows = [m for m in manuales(path) if m.get("id") != sid]
    rows.append({"id": sid, "decision": decision, "motivo": _txt(motivo, "motivo", 5, 300), "fecha": fecha})
    save_json(path, sorted(rows, key=lambda m: m["id"]))


def decisiones(editions, manual=()):
    """The newsroom's last word on every suggestion: {id: {estado, motivo, tarjeta, fecha}}. The decisions
    written down by hand win over the editions."""
    out = {}
    for ed in sorted(editions or [], key=lambda e: e["date"]):
        for d in ed.get("sugerencias_tablon") or []:
            out[d["id"]] = {"estado": d["decision"], "motivo": d.get("motivo"), "tarjeta": d.get("tarjeta"),
                            "fecha": ed["date"]}
    for m in manual or ():
        out[m["id"]] = {"estado": m["decision"], "motivo": m.get("motivo"), "tarjeta": None, "fecha": m.get("fecha")}
    return out


def _permiso(perms, sid):
    last = None
    for p in perms or []:
        if p.get("sugerencia") == sid:
            last = p
    return last


def _estado(d, p):
    """pendiente, hecha, aplicada, descartada or rechazada (an old «permiso» the admin turned down)."""
    est = (d or {}).get("estado")
    if est in ANTIGUAS:
        return "rechazada" if p and p.get("decision") == "rechazada" else "pendiente"
    return est or "pendiente"


def estados(rows, perms, editions, manual=()):
    """Every suggestion with its status for the board, newest first."""
    dec = decisiones(editions, manual)
    out = []
    for r in rows or []:
        d = dec.get(r["id"], {})
        p = _permiso(perms, r["id"])
        est = _estado(d, p)
        motivo = (p or {}).get("nota") if est == "rechazada" else d.get("motivo") if est != "pendiente" else None
        out.append({"id": r["id"], "nombre": _clean(r.get("nombre"), 40) or "Anónimo", "texto": _clean(r.get("texto"), 400),
                    "estado": est, "sello": ESTADOS[est], "motivo": motivo,
                    "tarjeta": d.get("tarjeta"), "fecha": (r.get("created_at") or "")[:10]})
    return out


def pendientes(rows, perms, editions, manual=()):
    """What the newsroom has to do today: the suggestions nobody has done or discarded yet."""
    dec = decisiones(editions, manual)
    return [{"id": r["id"], "nombre": _clean(r.get("nombre"), 40), "texto": _clean(r.get("texto"), 400)}
            for r in sorted(rows or [], key=lambda r: r["id"])
            if _estado(dec.get(r["id"]), _permiso(perms, r["id"])) == "pendiente"]


def hechas(buzon):
    """The suggestions that changed something (a card or the website), for the Discord notice."""
    return [b for b in buzon if b["estado"] in ("hecha", "aplicada")]


def _clean(text, n):
    return re.sub(r"\s+", " ", str(text or "")).strip()[:n]


def para_contexto(cfg, editions, cache_path, fetch=True, manual=()):
    """The suggestion box as the newsroom sees it, and a note of what is pending for the validator."""
    rows, perms = leer(cfg) if fetch else (None, None)
    pend = pendientes(rows, perms, editions, manual) if rows is not None else []
    save_json(cache_path, {"pendientes": [p["id"] for p in pend]})
    latest = next((e for e in sorted(editions or [], key=lambda e: e["date"], reverse=True) if e.get("tarjetas") is not None), None)
    return {
        "pendientes": pend,
        "ya_hechas": [{k: s[k] for k in ("id", "texto", "estado", "motivo")}
                      for s in hechas(estados(rows, perms, editions, manual))][:30] if rows is not None else [],
        "tarjetas_actuales": (latest or {}).get("tarjetas") or [],
        "tipos_de_tarjeta": TIPOS,
    }


def pendientes_guardadas(cache_path):
    return set((load_json(cache_path, None) or {}).get("pendientes") or [])


# --------------------------------------------------------------------------- validation
def _txt(v, where, lo, hi):
    if not isinstance(v, (str, int, float)) or isinstance(v, bool):
        raise SugerenciaError(f"{where} debe ser texto")
    v = _clean(v, 10_000)
    if not lo <= len(v) <= hi:
        raise SugerenciaError(f"{where} debe tener entre {lo} y {hi} caracteres (tiene {len(v)}): {v[:50]!r}")
    return v


def _rows(v, where, lo, hi):
    if not isinstance(v, list) or not lo <= len(v) <= hi:
        raise SugerenciaError(f"{where} debe ser una lista de {lo} a {hi} elementos")
    return v


def _datos(tipo, d, w):
    if not isinstance(d, dict):
        raise SugerenciaError(f"{w}.datos debe ser un objeto: {TIPOS[tipo]}")
    if tipo == "cifra":
        out = {"valor": _txt(d.get("valor"), f"{w}.datos.valor", 1, 24), "etiqueta": _txt(d.get("etiqueta"), f"{w}.datos.etiqueta", 2, 100)}
        if d.get("quien"):
            out["quien"] = _txt(d["quien"], f"{w}.datos.quien", 1, 40)
        return out
    if tipo == "lista":
        return {"filas": [{"nombre": _txt(f.get("nombre") if isinstance(f, dict) else None, f"{w}.datos.filas[{i}].nombre", 1, 40),
                           "valor": _txt(f.get("valor") if isinstance(f, dict) else None, f"{w}.datos.filas[{i}].valor", 1, 30)}
                          for i, f in enumerate(_rows(d.get("filas"), f"{w}.datos.filas", 1, 12))]}
    if tipo == "barras":
        filas = []
        for i, f in enumerate(_rows(d.get("filas"), f"{w}.datos.filas", 1, 12)):
            if not isinstance(f, dict) or not isinstance(f.get("valor"), (int, float)) or isinstance(f.get("valor"), bool):
                raise SugerenciaError(f"{w}.datos.filas[{i}].valor debe ser un número")
            fila = {"nombre": _txt(f.get("nombre"), f"{w}.datos.filas[{i}].nombre", 1, 40), "valor": f["valor"]}
            if f.get("texto"):
                fila["texto"] = _txt(f["texto"], f"{w}.datos.filas[{i}].texto", 1, 20)
            filas.append(fila)
        return {"filas": filas}
    if tipo == "tabla":
        cols = [_txt(c, f"{w}.datos.columnas[{i}]", 1, 24) for i, c in enumerate(_rows(d.get("columnas"), f"{w}.datos.columnas", 2, 6))]
        filas = []
        for i, f in enumerate(_rows(d.get("filas"), f"{w}.datos.filas", 1, 15)):
            if not isinstance(f, list) or len(f) != len(cols):
                raise SugerenciaError(f"{w}.datos.filas[{i}] debe tener {len(cols)} celdas")
            filas.append([_txt(c, f"{w}.datos.filas[{i}][{j}]", 0, 30) for j, c in enumerate(f)])
        return {"columnas": cols, "filas": filas}
    return {"texto": _txt(d.get("texto"), f"{w}.datos.texto", 10, 600)}


def validar(data, pendientes_ids, known_ids=()):
    """The newsroom's cards and its decision on every pending suggestion. Returns (cards, decisions)."""
    cards, seen = [], set()
    raw = data.get("tarjetas")      # missing: the board keeps yesterday's cards
    if raw is not None and not isinstance(raw, list):
        raise SugerenciaError("«tarjetas» es una lista de tarjetas para el tablón")
    for i, c in enumerate(raw or []):
        w = f"tarjetas[{i}]"
        if not isinstance(c, dict):
            raise SugerenciaError(f"{w} debe ser un objeto")
        cid = str(c.get("id") or "")
        if not re.fullmatch(r"[a-z0-9-]{3,40}", cid) or cid in seen:
            raise SugerenciaError(f"{w}.id {cid!r}: minúsculas, números y guiones (3–40), sin repetir")
        seen.add(cid)
        tipo = c.get("tipo")
        if tipo not in TIPOS:
            raise SugerenciaError(f"{w}.tipo debe ser uno de {', '.join(TIPOS)}")
        card = {"id": cid, "tipo": tipo, "titulo": _txt(c.get("titulo"), f"{w}.titulo", 3, 60), "datos": _datos(tipo, c.get("datos"), w)}
        for k, hi in (("subtitulo", 140), ("pie", 140)):
            if c.get(k):
                card[k] = _txt(c[k], f"{w}.{k}", 1, hi)
        if c.get("sugerencia") is not None:
            if c["sugerencia"] not in set(pendientes_ids) | set(known_ids):
                raise SugerenciaError(f"{w}.sugerencia {c['sugerencia']!r} no es ninguna sugerencia del buzón")
            card["sugerencia"] = c["sugerencia"]
        cards.append(card)
    if raw is None:
        cards = None
    elif len(cards) > MAX_TARJETAS:
        raise SugerenciaError(f"Como mucho {MAX_TARJETAS} tarjetas en el tablón (hay {len(cards)}): retira las menos vistas")
    decided = []
    for i, d in enumerate(data.get("sugerencias_tablon") or []):
        w = f"sugerencias_tablon[{i}]"
        if not isinstance(d, dict) or d.get("id") not in pendientes_ids:
            raise SugerenciaError(f"{w}.id {d.get('id') if isinstance(d, dict) else d!r} no está entre las sugerencias pendientes")
        if d.get("decision") not in DECISIONES:
            raise SugerenciaError(f"{w}.decision debe ser una de {', '.join(DECISIONES)}")
        item = {"id": d["id"], "decision": d["decision"], "motivo": _txt(d.get("motivo"), f"{w}.motivo", 5, 300)}
        if d["decision"] == "hecha":
            tarjeta = d.get("tarjeta")
            if tarjeta not in seen and not (cards is None and tarjeta):
                raise SugerenciaError(f"{w}: una sugerencia «hecha» dice en «tarjeta» el id de la tarjeta que la cumple")
            item["tarjeta"] = tarjeta
        decided.append(item)
    missing = sorted(set(pendientes_ids) - {d["id"] for d in decided})
    if missing:
        raise SugerenciaError(f"Faltan por decidir las sugerencias del tablón {missing}: «hecha» (con su tarjeta), "
                              "«aplicada» (programaste el cambio en la web o en las normas: di en «motivo» qué cambió) "
                              "o «descartada» (sin sentido, ya existe, ataca a alguien fuera del juego o expone datos privados)")
    return cards, decided
