"""The suggestion box of the SoloQ Challenge board: readers ask for cards or data they want to see,
and the next day the newspaper's AI newsroom reviews them.

- A suggestion that can be answered with the race's data becomes a card nailed to the board
  (a figure, a list, bars, a table or a short text), refreshed every day by the newsroom.
- One that looks risky (security, privacy), very heavy, unrelated to the website, or that needs new
  code, is never applied: it waits for the admin's permission, who approves or rejects it on the
  board with the password (Supabase function soloq_decidir). An approved one comes back to the
  newsroom the next day; one that needs new code waits to be programmed.
- The rest are discarded, with the reason.

The newsroom's decisions and the cards live in each edition (``sugerencias_tablon`` and
``tarjetas``), so they travel with the paper; data/soloq/sugerencias.json only caches what was
pending when the context was written, for the validator."""
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
DECISIONES = ("hecha", "descartada", "permiso", "programar")
MAX_TARJETAS = 10
ESTADOS = {  # what the board stamps on each suggestion
    "pendiente": "En el buzón", "hecha": "Hecha", "descartada": "Descartada", "permiso": "Esperando al jefe",
    "aprobada": "Aprobada por el jefe", "rechazada": "Rechazada por el jefe", "programar": "Aprobada · por programar",
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


def decisiones(editions):
    """The newsroom's last word on every suggestion: {id: {estado, motivo, tarjeta, fecha}}."""
    out = {}
    for ed in sorted(editions or [], key=lambda e: e["date"]):
        for d in ed.get("sugerencias_tablon") or []:
            out[d["id"]] = {"estado": d["decision"], "motivo": d.get("motivo"), "tarjeta": d.get("tarjeta"),
                            "fecha": ed["date"]}
    return out


def _permiso(perms, sid):
    last = None
    for p in perms or []:
        if p.get("sugerencia") == sid:
            last = p
    return last


def estados(rows, perms, editions):
    """Every suggestion with its status for the board, newest first."""
    dec = decisiones(editions)
    out = []
    for r in rows or []:
        d = dec.get(r["id"], {})
        est = d.get("estado") or "pendiente"
        p = _permiso(perms, r["id"])
        if est == "permiso" and p:
            est = "aprobada" if p["decision"] == "aprobada" else "rechazada"
        out.append({"id": r["id"], "nombre": _clean(r.get("nombre"), 40) or "Anónimo", "texto": _clean(r.get("texto"), 400),
                    "estado": est, "sello": ESTADOS[est], "motivo": d.get("motivo") or (p or {}).get("nota"),
                    "tarjeta": d.get("tarjeta"), "fecha": (r.get("created_at") or "")[:10]})
    return out


def pendientes(rows, perms, editions):
    """What the newsroom has to decide today: new suggestions, and the ones the admin approved since
    the newsroom asked for permission."""
    dec = decisiones(editions)
    out = []
    for r in sorted(rows or [], key=lambda r: r["id"]):
        d = dec.get(r["id"])
        p = _permiso(perms, r["id"])
        if not d:
            out.append({"id": r["id"], "nombre": _clean(r.get("nombre"), 40), "texto": _clean(r.get("texto"), 400)})
        elif d["estado"] == "permiso" and p and p["decision"] == "aprobada":
            out.append({"id": r["id"], "nombre": _clean(r.get("nombre"), 40), "texto": _clean(r.get("texto"), 400),
                        "aprobada_por_el_jefe": True, "nota_del_jefe": p.get("nota"), "motivo_de_la_consulta": d.get("motivo")})
    return out


def esperando_permiso(rows, perms, editions):
    """The suggestions the newsroom left for the admin, not answered yet."""
    return [s for s in estados(rows, perms, editions) if s["estado"] == "permiso"]


def _clean(text, n):
    return re.sub(r"\s+", " ", str(text or "")).strip()[:n]


def para_contexto(cfg, editions, cache_path, fetch=True):
    """The suggestion box as the newsroom sees it, and a note of what is pending for the validator."""
    rows, perms = leer(cfg) if fetch else (None, None)
    pend = pendientes(rows, perms, editions) if rows is not None else []
    save_json(cache_path, {"pendientes": [p["id"] for p in pend]})
    latest = next((e for e in sorted(editions or [], key=lambda e: e["date"], reverse=True) if e.get("tarjetas") is not None), None)
    return {
        "pendientes": pend,
        "esperando_permiso_del_jefe": [{k: s[k] for k in ("id", "texto", "motivo")}
                                       for s in esperando_permiso(rows, perms, editions)] if rows is not None else [],
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
                              "«descartada», «permiso» (si es rara, insegura, muy pesada o no tiene que ver: pregunta al jefe) "
                              "o «programar» (aprobada por el jefe pero necesita código nuevo)")
    return cards, decided
