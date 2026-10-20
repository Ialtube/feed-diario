"""The newspaper's canon: its memory from one edition to the next.

Characters (each friend as a figure of Runeterra), the recurring fictional cast, the story
threads that open, escalate and close, the group's habits and the running jokes. Claude reads it
before writing and sends back what changed; every change is stamped with the edition date, so
rewriting a day replaces that day's changes instead of piling them up.
"""
import re

from .util import ROOT, load_json, save_json

CANON_FILE = ROOT / "data" / "canon.json"
ESTADOS = ("abierto", "escalando", "desenlace", "cerrado")
ACCIONES = ("abrir", "avanzar", "cerrar")


class CanonError(ValueError):
    pass


def empty():
    return {"personajes": {}, "elenco": [], "hilos": [], "costumbres": [], "chistes": []}


def load(path=None):
    c = load_json(path or CANON_FILE, None) or empty()
    for k, v in empty().items():
        c.setdefault(k, v)
    return c


def save(canon, path=None):
    save_json(path or CANON_FILE, canon)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "hilo"


def hilo_estado(h):
    return h["estados"][-1]["estado"] if h.get("estados") else "abierto"


def open_threads(canon):
    return [h for h in canon["hilos"] if hilo_estado(h) != "cerrado"]


def for_context(canon, recent_chapters=4):
    """What Claude needs to keep the story going (open threads with their last chapters)."""
    def thread(h):
        return {"id": h["id"], "titulo": h["titulo"], "estado": hilo_estado(h), "abierto": h["abierto"],
                "protagonistas": h.get("protagonistas", []), "resumen": h.get("resumen", ""),
                "ultimos_capitulos": h.get("capitulos", [])[-recent_chapters:],
                "capitulos": len(h.get("capitulos", []))}
    return {
        "personajes": canon["personajes"],
        "elenco": canon["elenco"],
        "hilos_abiertos": [thread(h) for h in open_threads(canon)],
        "hilos_cerrados": [{"id": h["id"], "titulo": h["titulo"]} for h in canon["hilos"] if hilo_estado(h) == "cerrado"][-10:],
        "costumbres": canon["costumbres"],
        "chistes": sorted(canon["chistes"], key=lambda j: -j.get("usos", 0)),
    }


def strip_date(canon, date):
    """Undo everything an edition of `date` added (so it can be applied again)."""
    canon["hilos"] = [h for h in canon["hilos"] if h.get("abierto") != date or h.get("semilla")]
    for h in canon["hilos"]:
        h["capitulos"] = [c for c in h.get("capitulos", []) if c.get("fecha") != date]
        h["estados"] = [e for e in h.get("estados", []) if e.get("fecha") != date] or h.get("estados", [])[:1]
    for p in canon["personajes"].values():
        for k in ("apodos", "rasgos", "maldiciones", "rivales"):
            p[k] = [x for x in p.get(k, []) if not (isinstance(x, dict) and x.get("fecha") == date)]
        p["titulos"] = [t for t in p.get("titulos", []) if t.get("fecha") != date]
    canon["elenco"] = [e for e in canon["elenco"] if e.get("fecha") != date]
    canon["costumbres"] = [c for c in canon["costumbres"] if c.get("fecha") != date]
    for j in canon["chistes"]:
        j["fechas"] = [f for f in j.get("fechas", []) if f != date]
        j["usos"] = len(j["fechas"])
    canon["chistes"] = [j for j in canon["chistes"] if j["fechas"] or j.get("semilla")]
    return canon


def validate_changes(data, canon, known_slugs):
    """Checks the 'canon' block of an edition file. Returns a clean copy."""
    ch = data or {}
    out = {"hilos": [], "personajes": {}, "elenco": [], "costumbres": [], "chistes": []}
    existing = {h["id"]: h for h in canon["hilos"]}
    for i, h in enumerate(ch.get("hilos") or []):
        acc = h.get("accion")
        if acc not in ACCIONES:
            raise CanonError(f"canon.hilos[{i}].accion debe ser una de {ACCIONES}")
        if acc == "abrir":
            titulo = str(h.get("titulo") or "").strip()
            if not 5 <= len(titulo) <= 90:
                raise CanonError(f"canon.hilos[{i}]: un hilo nuevo necesita «titulo» (5–90 caracteres)")
            hid = h.get("id") or slug(titulo)
            if hid in existing:
                raise CanonError(f"canon.hilos[{i}]: ya existe un hilo con id {hid!r}; usa «avanzar»")
        else:
            hid = h.get("id")
            if hid not in existing:
                raise CanonError(f"canon.hilos[{i}].id {hid!r} no existe en el canon")
            if hilo_estado(existing[hid]) == "cerrado":
                raise CanonError(f"canon.hilos[{i}]: el hilo {hid!r} ya está cerrado")
        estado = h.get("estado") or ("cerrado" if acc == "cerrar" else "abierto" if acc == "abrir" else None)
        if estado and estado not in ESTADOS:
            raise CanonError(f"canon.hilos[{i}].estado debe ser uno de {ESTADOS}")
        resumen = str(h.get("resumen") or "").strip()
        if not 10 <= len(resumen) <= 400:
            raise CanonError(f"canon.hilos[{i}].resumen: qué ha pasado hoy en el hilo, 10–400 caracteres")
        prot = [s for s in (h.get("protagonistas") or []) if s in known_slugs]
        out["hilos"].append({"id": hid, "accion": acc, "titulo": h.get("titulo"), "estado": estado,
                             "resumen": resumen, "protagonistas": prot})
    for s, p in (ch.get("personajes") or {}).items():
        if s not in known_slugs:
            raise CanonError(f"canon.personajes: {s!r} no es un jugador conocido")
        clean = {}
        for k in ("titulo", "faccion", "apodo", "rasgo", "maldicion", "rival"):
            v = str(p.get(k) or "").strip()
            if v:
                if len(v) > 120:
                    raise CanonError(f"canon.personajes.{s}.{k}: como mucho 120 caracteres")
                clean[k] = v
        out["personajes"][s] = clean
    for e in ch.get("elenco") or []:
        if not (e.get("nombre") and e.get("cargo")):
            raise CanonError("canon.elenco: cada personaje nuevo necesita «nombre» y «cargo»")
        out["elenco"].append({k: str(e.get(k) or "")[:120] for k in ("nombre", "cargo", "institucion", "rasgo")})
    out["costumbres"] = [str(c)[:200] for c in ch.get("costumbres") or [] if str(c).strip()]
    out["chistes"] = [str(c)[:120] for c in ch.get("chistes") or [] if str(c).strip()]
    return out


def apply_changes(canon, changes, date, headlines):
    """Merges validated changes. `headlines` maps thread id -> headlines of today's stories in it."""
    strip_date(canon, date)
    by_id = {h["id"]: h for h in canon["hilos"]}
    for h in changes["hilos"]:
        if h["accion"] == "abrir":
            t = {"id": h["id"], "titulo": h["titulo"].strip(), "abierto": date, "protagonistas": h["protagonistas"],
                 "resumen": h["resumen"], "estados": [{"fecha": date, "estado": h["estado"] or "abierto"}], "capitulos": []}
            canon["hilos"].append(t)
            by_id[t["id"]] = t
        t = by_id[h["id"]]
        if h["accion"] != "abrir" and h["estado"]:
            t.setdefault("estados", []).append({"fecha": date, "estado": h["estado"]})
        if h["protagonistas"]:
            t["protagonistas"] = sorted(set(t.get("protagonistas", [])) | set(h["protagonistas"]))
        t["resumen"] = h["resumen"] if h["accion"] == "abrir" else t.get("resumen", h["resumen"])
        t.setdefault("capitulos", []).append({"fecha": date, "resumen": h["resumen"],
                                              "titulares": headlines.get(h["id"], [])})
    for s, p in changes["personajes"].items():
        cur = canon["personajes"].setdefault(s, {})
        if p.get("titulo"):
            cur.setdefault("titulos", []).append({"fecha": date, "texto": p["titulo"]})
        if p.get("faccion"):
            cur["faccion"] = p["faccion"]
        for k, field in (("apodo", "apodos"), ("rasgo", "rasgos"), ("maldicion", "maldiciones"), ("rival", "rivales")):
            if p.get(k):
                cur.setdefault(field, []).append({"fecha": date, "texto": p[k]})
    for e in changes["elenco"]:
        canon["elenco"].append(dict(e, fecha=date))
    for c in changes["costumbres"]:
        canon["costumbres"].append({"fecha": date, "texto": c})
    jokes = {j["texto"].lower(): j for j in canon["chistes"]}
    for c in changes["chistes"]:
        j = jokes.get(c.lower())
        if not j:
            j = {"texto": c, "fechas": []}
            canon["chistes"].append(j)
            jokes[c.lower()] = j
        if date not in j["fechas"]:
            j["fechas"].append(date)
        j["usos"] = len(j["fechas"])
    return canon


def current_title(p):
    """The latest title of a character (titles are earned and replaced over time)."""
    ts = p.get("titulos") or []
    return ts[-1]["texto"] if ts else p.get("titulo_inicial")


def texts(items):
    return [x["texto"] if isinstance(x, dict) else x for x in items or []]
