"""AI edition support for the daily Claude routine.

Flow (see ai/GUIA.md):
  1. python -m roast ai-context            -> ai/contexto-AAAA-MM-DD.json (everything Claude needs)
  2. Claude writes ai/edicion-AAAA-MM-DD.json
  3. python -m roast apply-ai <file>       -> validates, merges into the day's edition, rebuilds docs/
"""
import copy
import re
import time
from collections import Counter
from pathlib import Path

from . import canon as canon_mod
from . import correcciones
from . import lectores
from . import porra as porra_mod
from .dossier import FIXED, REQUIRED, build_dossier, detailed_games
from .roasts import DESKS
from .site import general_leaderboard
from . import propuestas as voz
from .util import ROOT, load_config, load_friends, load_json, save_json

EVENTS_FILE = ROOT / "eventos.md"
IMG_DIR = ROOT / "docs" / "img"
AI_DIR = ROOT / "ai"
THEMES = ("rojo", "oro", "negro", "verde", "azul", "morado")
MAX_EXTRA = 6        # newspaper extras
MAX_VOZ = 6          # reader proposals published per edition


# ---- edition format 2: Claude is the editor (picks angles, weight and format of every story)
FORMATOS = (
    "noticia", "crónica", "crónica deportiva", "parte policial", "entrevista", "análisis", "reportaje",
    "perfil", "editorial", "carta al director", "esquela", "anuncio por palabras", "telegrama",
    "parte meteorológico", "previa", "nota de prensa", "comunicado oficial", "juicio", "boletín médico",
    "encuesta", "ranking", "hace una semana", "fe de erratas", "breve",
)
PESOS = {  # stories of each weight per edition (min, max) and body length in characters
    "grande": ((1, 3), (700, 1900)),
    "mediana": ((2, 6), (350, 1100)),
    "breve": ((3, 10), (90, 450)),
}
SIGNOS = ("Top", "Jungla", "Mid", "Tirador", "Soporte")
MAX_REPEATED = 0.5  # at most half of the data stories may reuse an angle from the last days
# formats that only make sense in some sections
FORMAT_SECTIONS = {
    "parte meteorológico": {"EL TIEMPO"},
    "esquela": {"SUCESOS", "NECROLÓGICAS", "CULTURA", "SOCIEDAD"},
    "boletín médico": {"SALUD"},
    "parte policial": {"SUCESOS"},
    "juicio": {"SUCESOS", "POLÍTICA"},
    "editorial": {"OPINIÓN", "EDITORIAL"},
    "carta al director": {"OPINIÓN", "CARTAS"},
    "crónica deportiva": {"DEPORTES", "DERBI", "ACE LEAGUE"},
    "comunicado oficial": None,  # anyone can issue one
}
# stories are told, not tallied: at most this many figures per 100 words in big and medium stories
MAX_FIGURES_PER_100_WORDS = 6
LIST_FORMATS = {"ranking", "telegrama", "encuesta", "hace una semana", "anuncio por palabras"}


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
STOPWORDS = set("""de la el en y a que los las del se con por un una su al es lo para como más pero sus le ya o
este esta fue ha no sí ni muy sin sobre entre también hasta desde todo nos""".split())


def overused_phrases(editions, min_count=3, limit=30):
    """Three-word phrases repeated across recent editions, so the AI can avoid them."""
    counts = {}
    for e in editions:
        for it in e["items"]:
            words = re.findall(r"[a-záéíóúñü]+", f"{it['headline']} {it['body']}".lower())
            for i in range(len(words) - 2):
                tri = words[i:i + 3]
                if sum(w in STOPWORDS for w in tri) >= 2:
                    continue
                key = " ".join(tri)
                counts[key] = counts.get(key, 0) + 1
    common = [k for k, v in sorted(counts.items(), key=lambda kv: -kv[1]) if v >= min_count]
    return common[:limit]


def build_context(store, date_str, history_days=7, fetch_proposals=True, cfg=None, friends=None):
    editions = sorted(store.editions(), key=lambda e: e["date"])
    today = next((e for e in editions if e["date"] == date_str), None)
    if not today:
        raise AIError(f"No existe la edición del {date_str}. Ejecuta antes el robot (python -m roast run) "
                      "o lanza el workflow de GitHub.")
    previous = [e for e in editions if e["date"] < date_str][-history_days:]
    events = read_events()
    weekday = time.strptime(date_str, "%Y-%m-%d").tm_wday
    cfg, friends = cfg or load_config(), friends or load_friends()
    dossier = build_dossier(cfg, store, friends, today, editions)
    template = today.get("items_plantilla") or [it for it in today["items"] if it.get("kind") != "ia"]
    return {
        "formato_edicion": 2,
        "estilo": correcciones.for_context(Path(store.dir) / "estilo.json"),
        "canon": canon_mod.for_context(canon_mod.load(Path(store.dir) / "canon.json")),
        "lectores_ayer": lectores.feedback(cfg, previous[-1] if previous else None) if fetch_proposals else None,
        "cotillas": lectores.snoops(cfg, previous[-1]["generated_at"] if previous else today["window"][0],
                                    today.get("generated_at") or today["window"][1],
                                    [{"slug": f["slug"], "alias": f["alias"]} for f in friends]) if fetch_proposals else None,
        "replicas_pendientes": lectores.fetch_replies(cfg, editions) if fetch_proposals else [],
        "porra": today.get("porra"),
        "videntes": porra_mod.seers(editions),
        "bolsa_lp": today.get("bolsa"),
        "ace_league": load_json(Path(store.dir) / "ace_league.json", None),
        "dossier": dossier,
        "partidas_detalle": detailed_games(cfg, store, friends, today),
        "sorteo": today.get("sorteo"),
        "formatos_disponibles": list(FORMATOS),
        "formatos_recientes": [it.get("formato") for e in previous[-3:] for it in e["items"] if it.get("formato")],
        "secciones_recientes": [it.get("section") for e in previous[-3:] for it in e["items"]],
        "fecha": date_str,
        "dia_semana": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][weekday],
        "numero": today["number"],
        "estado_ia": ai_status(today),
        "eventos_pendientes": events,
        "portada_del_robot": template[0]["headline"] if template else None,
        "clasificacion_hoy": today["ranking"],
        "partidas_hoy": today["games"],
        "duos": today["duos"],
        "derbis": today["derbies"],
        "totales": today["totals"],
        "ausentes": today["absent"],
        "frase_actual": today["frase"],
        "general_verguenza": general_leaderboard(editions[:editions.index(today) + 1]),
        "propuestas_lectores": [{k: p.get(k) for k in ("id", "nombre", "titulo", "texto", "imagen_local", "created_at")}
                                for p in (voz.fetch_pending(load_config()) if fetch_proposals else [])],
        "expresiones_gastadas": overused_phrases(previous),
        "titulares_recientes": [it["headline"] for e in previous[-4:] for it in e["items"]],
        "historial": [{
            "fecha": e["date"],
            "portada": e["items"][0]["headline"] if e["items"] else None,
            "clasificacion": [{k: r[k] for k in ("alias", "games", "wins", "losses", "kda", "d", "score")}
                              for r in e["ranking"]],
            "columna": (e.get("columna") or {}).get("titulo"),
            "especial": (e.get("especial") or {}).get("titulo"),
        } for e in previous],
        "jugadores": sorted({r["slug"]: r["alias"] for e in editions for r in e["ranking"]}.items()),
        "imagenes_disponibles": sorted(p.name for p in IMG_DIR.glob("*")
                                       if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"))
                                if IMG_DIR.exists() else [],
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


def _voz_fields(it, where, pending, clean):
    prop = it.get("propuesta")
    lector, imagen = None, it.get("imagen")
    if prop is not None:
        if prop not in pending:
            raise AIError(f"{where}.propuesta {prop!r} no está entre las propuestas pendientes")
        lector = voz.safe_name(pending[prop]["nombre"]) or "Un lector"
        imagen = imagen or pending[prop].get("imagen_local")
        clean["propuestas_usadas"].append(prop)
    if imagen:
        if not re.fullmatch(r"[\w.\-]+\.(jpe?g|png|gif|webp)", imagen, re.I) or not (IMG_DIR / imagen).exists():
            raise AIError(f"{where}.imagen {imagen!r} no existe en docs/img/ (pon solo el nombre del archivo)")
    return lector, imagen


def figures_per_100_words(text):
    words = max(len(re.findall(r"\w+", text)), 1)
    # numbers as figures, not digits inside names like «Fr4nux»
    return len(re.findall(r"(?<![^\W\d_])\d+(?:[.,:/–-]\d+)*(?![^\W\d_])", text)) * 100 / words


def lectores_name(n):
    return re.sub(r"\s+", " ", n or "").strip()[:40] or "El aludido"


def validate_v2(data, edition, known_slugs, dossier, canon=None, context_extra=None):
    """Edition format 2: a list of 'piezas' chosen by Claude from the dossier."""
    angles = {a["id"]: a for a in dossier["angulos"]}
    # validate against the canon as it was before this day's own changes (so a day can be rewritten)
    canon = canon_mod.strip_date(copy.deepcopy(canon), edition["date"]) if canon is not None else canon_mod.empty()
    clean = {"formato": 2, "piezas": [], "horoscopo": [], "columna": None, "especial": None, "frase": None,
             "eventos_usados": [], "firma": "Claude", "propuestas_usadas": [], "propuestas_descartadas": [],
             "tiempo": [], "canon": None, "replicas_usadas": [], "replicas_descartadas": []}
    replies = lectores.replies_cache()
    pending = voz.known_cache()
    seen = set()
    for i, it in enumerate(data.get("piezas") or []):
        w = f"piezas[{i}]"
        peso = it.get("peso")
        if peso not in PESOS:
            raise AIError(f"{w}.peso debe ser uno de {tuple(PESOS)}")
        formato = (it.get("formato") or "").strip().lower()
        if formato not in FORMATOS:
            raise AIError(f"{w}.formato {formato!r} no está en el catálogo: {', '.join(FORMATOS)}")
        angle = None
        if it.get("angulo") is not None:
            angle = angles.get(it["angulo"])
            if not angle:
                raise AIError(f"{w}.angulo {it['angulo']!r} no existe en el dossier de hoy")
            if it["angulo"] in seen:
                raise AIError(f"{w}: el ángulo {it['angulo']} ya se usa en otra pieza")
            seen.add(it["angulo"])
        player = it.get("player") or (angle["jugador"] if angle and angle["jugador"] in known_slugs else None)
        if player is not None and player not in known_slugs:
            raise AIError(f"{w}.player {player!r} no es un jugador conocido ({', '.join(sorted(known_slugs))})")
        lector, imagen = _voz_fields(it, w, pending, clean)
        lo, hi = PESOS[peso][1]
        section = _text(it.get("seccion") or (angle or {}).get("tema") or "SOCIEDAD", f"{w}.seccion", 3, 30).upper()
        if lector:
            section = "LA VOZ DE RUNETERRA"
        clean["piezas"].append({
            "angulo": it.get("angulo"), "clave": angle["clave"] if angle else None,
            "angle_campeon": angle.get("campeon") if angle else None,
            "repetido": bool(angle and angle["tipo"] not in FIXED and angle["novedad"] != "nuevo"),
            "peso": peso, "formato": formato, "section": section,
            "desk": _text(it.get("desk") or DESKS.get(section, ""), f"{w}.desk", 0, 50),
            "headline": _text(it.get("headline"), f"{w}.headline", 8, 140),
            "subtitulo": _text(it.get("subtitulo") or "", f"{w}.subtitulo", 0, 220),
            "body": _paras(it.get("body"), f"{w}.body", lo, hi if not lector else max(hi, 1100)),
            "stat": _text(it.get("stat") or "", f"{w}.stat", 0, 16),
            "stat_label": _text(it.get("stat_label") or "", f"{w}.stat_label", 0, 50),
            "player": player, "portada": bool(it.get("portada")), "imagen": imagen,
            "campeon": _text(it.get("campeon") or "", f"{w}.campeon", 0, 30) or None,
            "pie": _text(it.get("pie") or "", f"{w}.pie", 0, 200),
            "meme_arriba": _text(it.get("meme_arriba") or "", f"{w}.meme_arriba", 0, 60),
            "meme_abajo": _text(it.get("meme_abajo") or "", f"{w}.meme_abajo", 0, 60),
            "lector": lector, "hilo": it.get("hilo") or None, "replica": it.get("replica"),
        })
        if it.get("replica") is not None:
            rep = replies.get(it["replica"])
            if not rep:
                raise AIError(f"{w}.replica {it['replica']!r} no está entre las réplicas pendientes")
            clean["piezas"][-1].update(section="DERECHO DE RÉPLICA", lector=None,
                                       replica_de=lectores_name(rep["nombre"]))
            clean["replicas_usadas"].append(it["replica"])
        allowed = FORMAT_SECTIONS.get(formato)
        if allowed and section not in allowed and not lector:
            raise AIError(f"{w}: un «{formato}» va en {' o '.join(sorted(allowed))}, no en {section}")
        body = clean["piezas"][-1]["body"]
        if peso != "breve" and formato not in LIST_FORMATS and figures_per_100_words(body) > MAX_FIGURES_PER_100_WORDS:
            raise AIError(f"{w} ({clean['piezas'][-1]['headline'][:50]}…) parece un acta: "
                          f"{figures_per_100_words(body):.0f} cifras por cada 100 palabras (máximo "
                          f"{MAX_FIGURES_PER_100_WORDS}). Cuéntalo como una historia y deja solo las cifras que pesan")
    news = [p for p in clean["piezas"] if not p["lector"]]
    portadas = [p for p in clean["piezas"] if p["portada"]]  # a reader's story can open the paper too
    if len(portadas) != 1 or portadas[0]["peso"] != "grande":
        raise AIError("Tiene que haber exactamente una pieza con portada: true, y de peso «grande»")
    for peso, ((lo, hi), _) in PESOS.items():
        n = sum(1 for p in news if p["peso"] == peso)
        if not lo <= n <= hi:
            raise AIError(f"Hay {n} piezas de peso «{peso}»: tienen que ser entre {lo} y {hi}")
    with_angle = [p for p in news if p["clave"]]
    repeated = [p for p in with_angle if p["repetido"]]
    if with_angle and len(repeated) > MAX_REPEATED * len(with_angle):
        raise AIError(f"{len(repeated)} de {len(with_angle)} piezas repiten ángulos de los últimos días "
                      f"({', '.join(p['clave'] for p in repeated)}); como mucho la mitad")
    formats = Counter(p["formato"] for p in news)
    if len(formats) < 4:
        raise AIError(f"Usa al menos 4 formatos distintos (ahora: {', '.join(formats)})")
    top, n = formats.most_common(1)[0]
    if top != "breve" and n > 0.4 * len(news):
        raise AIError(f"El formato «{top}» se repite en {n} de {len(news)} piezas: varía más")
    if any(a["tipo"] == "faro" for a in dossier["angulos"]) and \
            not any(p["section"] == "EL FARO DE LA ESPERANZA" for p in news):
        raise AIError("Falta El Faro de la Esperanza: al menos una pieza con seccion «EL FARO DE LA ESPERANZA»")
    def mentions(slug, alias):
        a = alias.lower()
        return sum(1 for p in news if p["player"] == slug or
                   a in f'{p["headline"]} {p["subtitulo"]} {p["body"]}'.lower())
    left_out = [r["alias"] for r in edition.get("ranking", []) if not mentions(r["slug"], r["alias"])]
    if left_out:
        raise AIError("Hay que repartir para todos: nadie que haya jugado se libra. Falta caña para " + ", ".join(left_out))
    target = dossier.get("blanco_historico")
    if target and any(r["slug"] == target["slug"] for r in edition.get("ranking", [])) \
            and mentions(target["slug"], target["alias"]) < 2:
        raise AIError(f"{target['alias']} es el peor de la historia del periódico (lidera la General) y ha jugado: "
                      "tiene que salir al menos en dos piezas")
    used_ids = {p["angulo"] for p in clean["piezas"] if p["angulo"]}
    missing = [a for a in dossier["angulos"] if a["tipo"] in REQUIRED - {"faro"} and a["id"] not in used_ids]
    if missing:
        raise AIError("Faltan piezas obligatorias: " + ", ".join(f"{a['id']} ({a['titulo']})" for a in missing)
                      + ". La sesión de Flex del grupo y las colas SoloQ/DuoQ siempre se cuentan")
    n_voz = len(clean["piezas"]) - len(news)
    if n_voz > MAX_VOZ:
        raise AIError(f"Como mucho {MAX_VOZ} piezas de La Voz de Runeterra")

    # the admin's corrections must be studied and turned into guidelines
    est = data.get("estilo") or {}
    new_corr = (context_extra or {}).get("correcciones_nuevas") or []
    nuevas = [str(t).strip() for t in est.get("pautas_nuevas") or [] if str(t).strip()]
    for t in nuevas:
        if not 15 <= len(t) <= 300:
            raise AIError(f"estilo.pautas_nuevas: cada pauta entre 15 y 300 caracteres ({t[:40]!r}…)")
    if new_corr and not nuevas:
        raise AIError(f"Hay {len(new_corr)} correcciones nuevas del administrador en estilo.correcciones_nuevas: "
                      "estúdialas y escribe en estilo.pautas_nuevas qué has aprendido de su humor (sin copiar sus chistes)")
    clean["estilo"] = {"pautas_nuevas": nuevas,
                       "pautas_retiradas": [str(t) for t in est.get("pautas_retiradas") or []]}

    # every reply waiting is published (with the paper's answer) or discarded
    pending_r = lectores.pending_replies()
    discarded_r = data.get("replicas_descartadas") or []
    for n in discarded_r:
        if n not in pending_r:
            raise AIError(f"replicas_descartadas: {n!r} no está entre las réplicas pendientes")
    left = [n for n in pending_r if n not in clean["replicas_usadas"] and n not in discarded_r]
    if left:
        raise AIError(f"Hay réplicas sin publicar ni descartar: {left}. El aludido tiene derecho a contestar: "
                      "publícalas en una pieza con «replica»")
    clean["replicas_descartadas"] = discarded_r

    # readers' letters get an answer
    fb = (context_extra or {}).get("lectores_ayer") or {}
    if fb.get("comentarios") and not any(p["formato"] == "carta al director" or p["section"] == "CARTAS" for p in news):
        raise AIError("Ayer hubo comentarios de los lectores: contéstalos en una pieza con formato «carta al director»")

    # the canon: threads that run from one edition to the next
    try:
        changes = canon_mod.validate_changes(data.get("canon"), canon, known_slugs)
    except canon_mod.CanonError as e:
        raise AIError(str(e))
    open_ids = {h["id"] for h in canon_mod.open_threads(canon)}
    opened = {h["id"] for h in changes["hilos"] if h["accion"] == "abrir"}
    touched = {h["id"] for h in changes["hilos"]}
    valid = open_ids | opened
    for i, p in enumerate(clean["piezas"]):
        if p["hilo"] and p["hilo"] not in valid:
            raise AIError(f"piezas[{i}].hilo {p['hilo']!r} no es un hilo abierto ni uno que abras hoy en canon.hilos")
        if p["hilo"] and p["hilo"] not in touched:
            raise AIError(f"piezas[{i}] avanza el hilo {p['hilo']!r}: añádelo a canon.hilos con lo que pasa hoy")
    in_pieces = {p["hilo"] for p in clean["piezas"] if p["hilo"]}
    if len(open_ids) >= 2 and len(in_pieces) < 2:
        raise AIError("El periódico tiene memoria: avanza al menos dos hilos abiertos del canon (campo «hilo» de las piezas)")
    if valid and not portadas[0]["hilo"]:
        raise AIError("La portada tiene que pertenecer a un hilo (lleva su cintillo de saga): ponle «hilo»")
    clean["canon"] = changes

    # El Tiempo: a forecast for everyone who played
    tiempo = {t.get("jugador"): t.get("texto") for t in data.get("tiempo") or []}
    for r in edition.get("ranking", []):
        if not tiempo.get(r["slug"]):
            raise AIError(f"Falta la previsión de El Tiempo de {r['alias']} (tiempo: [{{\"jugador\": \"{r['slug']}\", \"texto\": …}}])")
        clean["tiempo"].append({"jugador": r["slug"], "texto": _text(tiempo[r["slug"]], f"tiempo.{r['slug']}", 30, 220)})

    horos = data.get("horoscopo") or []
    signos = [h.get("signo") for h in horos]
    if sorted(signos) != sorted(SIGNOS):
        raise AIError(f"horoscopo debe tener una entrada por signo: {', '.join(SIGNOS)}")
    clean["horoscopo"] = [{"signo": h["signo"], "texto": _text(h.get("texto"), f"horoscopo.{h['signo']}", 30, 260)}
                          for h in sorted(horos, key=lambda h: SIGNOS.index(h["signo"]))]
    if not data.get("frase") or not data.get("columna"):
        raise AIError("Faltan la frase del día o la columna")
    _common(data, clean, pending)
    return clean


def _paras(value, field, lo, hi):
    """Body text; paragraphs separated by a blank line."""
    if not isinstance(value, str):
        raise AIError(f"'{field}' debe ser texto")
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", value) if p.strip()]
    total = sum(len(p) for p in paras)
    if not lo <= total <= hi:
        raise AIError(f"'{field}' debe tener entre {lo} y {hi} caracteres (tiene {total})")
    return "\n\n".join(paras)


def _common(data, clean, pending):
    """Column, special edition, quote, events and discarded proposals (both formats)."""
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
    discarded = data.get("propuestas_descartadas") or []
    for n in discarded:
        if n not in pending:
            raise AIError(f"propuestas_descartadas: {n!r} no está entre las propuestas pendientes")
    clean["propuestas_descartadas"] = discarded
    used = data.get("eventos_usados") or []
    if not all(isinstance(n, int) for n in used):
        raise AIError("eventos_usados debe ser una lista de números (el campo 'n' del contexto)")
    clean["eventos_usados"] = used
    if data.get("firma"):
        clean["firma"] = _text(data["firma"], "firma", 3, 60)


def apply_v2(edition, clean, canon_path=None):
    """Replaces the robot's stories with Claude's; the robot's stay in items_plantilla.
    With `canon_path`, the canon changes are merged into that file."""
    if "items_plantilla" not in edition:
        edition["items_plantilla"] = [it for it in edition["items"] if it.get("kind") != "ia"]
    aliases = {r["slug"]: r["alias"] for r in edition["ranking"]}
    base = {"portada": 1000, "grande": 600, "mediana": 400, "breve": 200}
    items = []
    for i, p in enumerate(clean["piezas"]):
        campeon = p["campeon"] or (p["angle_campeon"] if p["peso"] != "breve" else None)
        items.append({
            "id": i + 1, "kind": "ia", "peso": p["peso"], "formato": p["formato"], "clave": p["clave"],
            "section": p["section"], "desk": p["desk"], "player": p["player"],
            "alias": aliases.get(p["player"]) if p["player"] else None,
            "headline": p["headline"], "subtitulo": p["subtitulo"], "body": p["body"],
            "stat": p["stat"], "stat_label": p["stat_label"], "imagen": p["imagen"], "campeon": campeon,
            "pie": p["pie"], "meme_arriba": p["meme_arriba"], "meme_abajo": p["meme_abajo"], "lector": p["lector"],
            "severity": (base["portada"] if p["portada"] else base[p["peso"]]) - i, "facts": {},
            "hilo": p["hilo"], "replica": p.get("replica"),
        })
    edition["items"] = sorted(items, key=lambda it: -it["severity"])
    if canon_path and clean.get("canon"):
        canon = canon_mod.load(canon_path)
        heads = {}
        for it in edition["items"]:
            if it["hilo"]:
                heads.setdefault(it["hilo"], []).append(it["headline"])
        canon_mod.apply_changes(canon, clean["canon"], edition["date"], heads)
        canon_mod.save(canon, canon_path)
        sagas = {h["id"]: h for h in canon["hilos"]}
        for it in edition["items"]:
            h = sagas.get(it["hilo"])
            if h:
                it["saga"] = {"id": h["id"], "titulo": h["titulo"], "capitulo": len(h.get("capitulos", [])),
                              "estado": canon_mod.hilo_estado(h)}
    for it, p in zip(items, clean["piezas"]):
        if p.get("replica_de"):
            it["replica_de"] = p["replica_de"]
    edition["canon_cambios"] = clean.get("canon")
    edition["tiempo"] = clean.get("tiempo") or []
    edition["angulos_usados"] = [p["clave"] for p in clean["piezas"] if p["clave"]]
    edition["horoscopo"] = clean["horoscopo"]
    if "template_frase" not in edition:
        edition["template_frase"] = edition["frase"]
    edition["frase"] = clean["frase"] or edition["template_frase"]
    edition["columna"] = clean["columna"]
    edition["especial"] = clean["especial"]
    prev = edition.get("ai") or {}
    edition["ai"] = {"version": prev.get("version", 0) + 1, "updated_at": int(time.time() * 1000),
                     "firma": clean["firma"], "stale": False, "formato": 2}
    edition["written_by"] = clean["firma"]
    return edition


def validate(data, edition, known_slugs):
    if not isinstance(data, dict):
        raise AIError("El archivo debe ser un objeto JSON")
    ids = {it["id"] for it in edition["items"] if it.get("kind") != "ia"}
    clean = {"items": [], "extra": [], "columna": None, "especial": None, "frase": None,
             "eventos_usados": [], "firma": "Claude", "propuestas_usadas": [], "propuestas_descartadas": []}
    pending = voz.pending_cache()

    for i, it in enumerate(data.get("items") or []):
        if it.get("id") not in ids:
            raise AIError(f"items[{i}]: id {it.get('id')!r} no existe en la edición de hoy")
        clean["items"].append({"id": it["id"],
                               "headline": _text(it.get("headline"), f"items[{i}].headline", 8, 160),
                               "body": _text(it.get("body"), f"items[{i}].body", 10, 700)})

    extra = data.get("extra") or []
    n_voz = sum(1 for it in extra if it.get("propuesta") is not None)
    if len(extra) - n_voz > MAX_EXTRA or n_voz > MAX_VOZ:
        raise AIError(f"Como mucho {MAX_EXTRA} artículos extra y {MAX_VOZ} de La Voz de Runeterra")
    for i, it in enumerate(extra):
        player = it.get("player")
        if player is not None and player not in known_slugs:
            raise AIError(f"extra[{i}].player {player!r} no es un jugador conocido ({', '.join(sorted(known_slugs))})")
        prop = it.get("propuesta")
        lector = None
        imagen = it.get("imagen")
        if prop is not None:
            if prop not in pending:
                raise AIError(f"extra[{i}].propuesta {prop!r} no está entre las propuestas pendientes")
            lector = voz.safe_name(pending[prop]["nombre"]) or "Un lector"
            imagen = imagen or pending[prop].get("imagen_local")
            clean["propuestas_usadas"].append(prop)
        if imagen:
            if not re.fullmatch(r"[\w.\-]+\.(jpe?g|png|gif|webp)", imagen, re.I) or not (IMG_DIR / imagen).exists():
                raise AIError(f"extra[{i}].imagen {imagen!r} no existe en docs/img/ (pon solo el nombre del archivo)")
        clean["extra"].append({
            "section": _text(it.get("section") or "OPINIÓN", f"extra[{i}].section", 3, 30).upper(),
            "desk": _text(it.get("desk") or "", f"extra[{i}].desk", 0, 50),
            "headline": _text(it.get("headline"), f"extra[{i}].headline", 8, 160),
            "body": _text(it.get("body"), f"extra[{i}].body", 10, 900),
            "stat": _text(it.get("stat") or "", f"extra[{i}].stat", 0, 16),
            "stat_label": _text(it.get("stat_label") or "", f"extra[{i}].stat_label", 0, 50),
            "player": player,
            "portada": bool(it.get("portada")),
            "imagen": imagen,
            "campeon": _text(it.get("campeon") or "", f"extra[{i}].campeon", 0, 30) or None,
            "pie": _text(it.get("pie") or "", f"extra[{i}].pie", 0, 200),
            "meme_arriba": _text(it.get("meme_arriba") or "", f"extra[{i}].meme_arriba", 0, 60),
            "meme_abajo": _text(it.get("meme_abajo") or "", f"extra[{i}].meme_abajo", 0, 60),
            "lector": lector,
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
    discarded = data.get("propuestas_descartadas") or []
    for n in discarded:
        if n not in pending:
            raise AIError(f"propuestas_descartadas: {n!r} no está entre las propuestas pendientes")
    clean["propuestas_descartadas"] = discarded
    used = data.get("eventos_usados") or []
    if not all(isinstance(n, int) for n in used):
        raise AIError("eventos_usados debe ser una lista de números (el campo 'n' del contexto)")
    clean["eventos_usados"] = used
    if data.get("firma"):
        clean["firma"] = _text(data["firma"], "firma", 3, 60)
    if not (clean["items"] or clean["extra"] or clean["columna"] or clean["especial"] or discarded):
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
            "kind": "ia", "section": e["section"], "desk": e["desk"], "player": e["player"],
            "alias": None, "headline": e["headline"], "body": e["body"],
            "stat": e["stat"], "stat_label": e["stat_label"],
            "imagen": e["imagen"], "campeon": e["campeon"], "pie": e["pie"],
            "meme_arriba": e["meme_arriba"], "meme_abajo": e["meme_abajo"], "lector": e["lector"],
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


def apply_file(store, path, date_str=None, cfg=None, friends=None):
    data = load_json(path)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", Path(path).name)
    date_str = date_str or (m.group(1) if m else None)
    if not date_str:
        raise AIError("No sé a qué día corresponde: usa --date AAAA-MM-DD")
    edition = store.edition(date_str)
    if not edition:
        raise AIError(f"No existe la edición del {date_str}")
    known = {r["slug"] for e in store.editions() for r in e["ranking"]}
    if "piezas" in data:
        dossier = build_dossier(cfg or load_config(), store, friends or load_friends(), edition, store.editions())
        canon_path = Path(store.dir) / "canon.json"
        cfg = cfg or load_config()
        prev = [e for e in sorted(store.editions(), key=lambda e: e["date"]) if e["date"] < edition["date"]]
        style_path = Path(store.dir) / "estilo.json"
        extra = {"lectores_ayer": lectores.feedback(cfg, prev[-1] if prev else None),
                 "correcciones_nuevas": correcciones.for_context(style_path)["correcciones_nuevas"]}
        clean = validate_v2(data, edition, known, dossier, canon_mod.load(canon_path), extra)
        apply_v2(edition, clean, canon_path)
        edition["lectores_ayer"] = extra["lectores_ayer"]
        correcciones.apply_learning(clean["estilo"], edition["date"], style_path)
        roster = [{"slug": f["slug"], "alias": f["alias"]} for f in (friends or load_friends())]
        edition["cotillas"] = lectores.snoops(cfg, prev[-1]["generated_at"] if prev else edition["window"][0],
                                              edition.get("generated_at") or edition["window"][1], roster)
    else:
        clean = validate(data, edition, known)
        apply(edition, clean, date_str)
    store.save_edition(edition)
    published = mark_events_published(clean["eventos_usados"], date_str)
    if clean.get("replicas_usadas") or clean.get("replicas_descartadas"):
        lectores.mark_replies(clean["replicas_usadas"], clean["replicas_descartadas"])
    if clean["propuestas_usadas"] or clean["propuestas_descartadas"]:
        voz.mark(clean["propuestas_usadas"], clean["propuestas_descartadas"])
    return edition, clean, published


def mark_stale_on_regenerate(old, new):
    """Called by `run` when it regenerates a day that already had an AI pass: keep the
    column/special/extras and flag it so the routine rewrites it again."""
    if not old or not old.get("ai"):
        return new
    if old["ai"].get("formato") == 2:
        new["items_plantilla"] = new["items"]
        new["items"] = old["items"]
        for k in ("horoscopo", "angulos_usados", "columna", "especial", "template_frase", "frase", "written_by"):
            if k in old:
                new[k] = old[k]
        new["ai"] = dict(old["ai"], stale=True)
        return new
    new["columna"] = old.get("columna")
    new["especial"] = old.get("especial")
    extras = [it for it in old["items"] if it.get("kind") == "ia"]
    if extras:
        new["items"] = sorted(new["items"] + extras, key=lambda it: -it["severity"])
    new["ai"] = dict(old["ai"], stale=True)
    return new
