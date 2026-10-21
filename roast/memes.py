"""Memes for the paper, and the group's own picture library.

- Classic templates (Drake, the distracted boyfriend, «this is fine»…) drawn by memegen.link with the
  lines the editor writes, or a champion's splash art (any of its skins) with meme text on top.
  When the edition is applied the picture is made and saved in docs/img/memes/, so the paper never
  depends on an outside link and old editions keep their memes.
- The library (docs/img/biblioteca/): memes and pictures the group drops in for the paper to use,
  each with an optional description in its LEEME.md.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from .util import ROOT

API = "https://api.memegen.link/images"
DDRAGON = "https://ddragon.leagueoflegends.com"
IMG_DIR = ROOT / "docs" / "img"
MEMES_DIR = IMG_DIR / "memes"
LIBRARY_DIR = IMG_DIR / "biblioteca"
IMAGE_RE = re.compile(r"(?:(?:biblioteca|memes)/)?[\w\-][\w.\-]*\.(?:jpe?g|png|gif|webp)", re.I)

# The templates the paper uses: id -> (name, lines, what each line is for)
PLANTILLAS = {
    "drake": ("Drake", 2, "lo que rechaza / lo que prefiere"),
    "db": ("El novio distraído", 3, "la tentación / el que se distrae / lo que tenía"),
    "fine": ("This is fine", 2, "(vacío o contexto) / «todo bien» mientras arde"),
    "pigeon": ("¿Esto es una paloma?", 3, "el que se confunde / la cosa / la conclusión equivocada"),
    "gru": ("El plan de Gru", 4, "paso 1 / paso 2 / el desastre / el desastre, otra vez"),
    "stonks": ("Stonks", 2, "(vacío o contexto) / la mala inversión celebrada"),
    "panik-kalm-panik": ("Pánico, calma, pánico", 3, "el susto / el alivio / el susto definitivo"),
    "spiderman": ("Spider-Man señalándose", 2, "uno / el otro, que es lo mismo"),
    "cmm": ("Change my mind", 1, "la tesis polémica"),
    "rollsafe": ("Roll Safe", 2, "la idea brillante / la lógica tramposa"),
    "both": ("¿Por qué no ambos?", 2, "el dilema / «¿por qué no los dos?»"),
    "ds": ("La lucha diaria", 3, "botón A / botón B / el que suda"),
    "gb": ("Cerebro galáctico", 4, "idea normal / mejor / absurda / iluminada"),
    "exit": ("Salida de la autopista", 3, "lo sensato / lo que elige / el que da el volantazo"),
    "buzz": ("X, X por todas partes", 2, "la cosa / la cosa por todas partes"),
    "success": ("Success Kid", 2, "la situación / el triunfo pequeño"),
    "fry": ("Fry desconfiado", 2, "no sé si... / ...o si..."),
    "kermit": ("Kermit y el té", 2, "la pulla / «pero eso no es asunto mío»"),
    "woman-cat": ("Mujer gritando a un gato", 2, "la que acusa / el acusado, impasible"),
    "handshake": ("Apretón de manos épico", 3, "uno / otro / lo que tienen en común"),
    "midwit": ("La campana de la inteligencia", 3, "el simple / el que se complica / el sabio (lo mismo que el simple)"),
    "astronaut": ("Siempre lo ha sido", 4, "el que lo descubre / «siempre lo ha sido» / el primero / el segundo"),
    "drowning": ("Chocar los cinco mientras se ahoga", 3, "el que se ahoga / el que no ayuda / lo que dice"),
    "grave": ("La tumba", 3, "lo que ha muerto / el que llora / el que lo mató"),
    "regret": ("Me arrepiento al instante", 2, "(contexto) / el arrepentimiento"),
    "harold": ("Harold escondiendo el dolor", 2, "la situación / la sonrisa forzada"),
    "disastergirl": ("La niña del incendio", 2, "(el desastre) / «todo según el plan»"),
    "chosen": ("¡Tú eras el elegido!", 2, "(contexto) / la decepción"),
    "gandalf": ("Gandalf confundido", 2, "(contexto) / «no recuerdo este lugar»"),
    "mordor": ("Uno no entra en Mordor", 2, "uno no simplemente... / ...lo imposible"),
    "sparta": ("¡Esto es Esparta!", 2, "esto es... / ¡el grito!"),
    "same": ("Son la misma foto", 3, "una cosa / otra cosa / «son la misma foto»"),
    "right": ("Anakin y Padme", 5, "él / ella / el plan / «...¿verdad?» / «...¿verdad?» (sin respuesta)"),
    "noidea": ("No tengo ni idea de lo que hago", 2, "no tengo ni idea / de lo que hago"),
    "afraid": ("Me da miedo preguntar", 2, "no sé qué es... / ...y ya me da miedo preguntar"),
    "firsttry": ("¡A la primera!", 2, "(contexto) / ¡a la primera!"),
    "slap": ("El tortazo", 2, "el que pega / el que recibe"),
    "reveal": ("Scooby-Doo desenmascara", 4, "el disfraz / «veamos quién eres» / quién era de verdad / «¡lo sabía!»"),
    "worst": ("El peor día de tu vida (hasta ahora)", 2, "«es el peor día de mi vida» / «...de momento»"),
    "money": ("¡Calla y toma mi dinero!", 2, "calla y... / ...toma mi dinero"),
}


class MemeError(ValueError):
    pass


def _enc(text):
    """memegen's URL escaping for one line of text."""
    t = str(text).replace("_", "__").replace("-", "--").replace(" ", "_")
    for a, b in (("?", "~q"), ("&", "~a"), ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\\", "~b"),
                 ("<", "~l"), (">", "~g"), ('"', "''"), ("\n", "~n")):
        t = t.replace(a, b)
    return urllib.parse.quote(t or "_", safe="~_-'")


def splash(champ, skin=0):
    from .site import _ddragon_id
    return f"{DDRAGON}/cdn/img/champion/splash/{_ddragon_id(champ)}_{int(skin)}.jpg"


def validate(meme, where):
    """A meme block of a story: {"plantilla": id, "lineas": [...]} or {"campeon": "Zed", "aspecto": 0, "lineas": [top, bottom]}."""
    if not isinstance(meme, dict):
        raise MemeError(f"{where}.meme debe ser un objeto")
    lines = [re.sub(r"\s+", " ", str(x)).strip() for x in meme.get("lineas") or []]
    if not lines or any(len(x) > 90 for x in lines):
        raise MemeError(f"{where}.meme.lineas: el texto del meme, cada línea de 90 caracteres como mucho")
    tpl = meme.get("plantilla")
    if tpl:
        if tpl not in PLANTILLAS:
            raise MemeError(f"{where}.meme.plantilla {tpl!r} no está en el catálogo ({', '.join(PLANTILLAS)})")
        n = PLANTILLAS[tpl][1]
        if len(lines) > n:
            raise MemeError(f"{where}.meme: la plantilla {tpl} tiene {n} líneas, no {len(lines)}")
        return {"plantilla": tpl, "lineas": lines + [""] * (n - len(lines))}
    champ = str(meme.get("campeon") or "").strip()
    if not champ:
        raise MemeError(f"{where}.meme: pon una «plantilla» del catálogo o un «campeon» de fondo")
    if len(lines) > 2:
        raise MemeError(f"{where}.meme con campeón de fondo: dos líneas como mucho (arriba y abajo)")
    try:
        skin = int(meme.get("aspecto") or 0)
    except (TypeError, ValueError):
        raise MemeError(f"{where}.meme.aspecto debe ser el número del aspecto (0 = el básico)")
    return {"campeon": champ[:30], "aspecto": skin, "lineas": (lines + [""])[:2]}


def url(meme):
    path = "/".join(_enc(x) for x in meme["lineas"])
    if meme.get("plantilla"):
        return f"{API}/{meme['plantilla']}/{path}.jpg"
    return f"{API}/custom/{path}.jpg?" + urllib.parse.urlencode({"background": splash(meme["campeon"], meme["aspecto"])})


def make(meme, name, timeout=30):
    """Draws the meme with memegen and saves it as docs/img/memes/<name>.jpg. Returns the path for «imagen»."""
    MEMES_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url(meme), headers={"User-Agent": "el-rincon-del-feeder/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except (urllib.error.URLError, OSError) as e:
        raise MemeError(f"memegen no ha podido dibujar el meme: {e}")
    if len(data) < 2000 or not data[:3] == b"\xff\xd8\xff":
        raise MemeError("memegen no ha devuelto una imagen")
    (MEMES_DIR / f"{name}.jpg").write_bytes(data)
    return f"memes/{name}.jpg"


# ---------------------------------------------------------------- the group's library
def library(editions=()):
    """Every picture in docs/img/biblioteca/ with its description (LEEME.md) and when it was last used."""
    if not LIBRARY_DIR.exists():
        return []
    notes = {}
    readme = LIBRARY_DIR / "LEEME.md"
    if readme.exists():
        for line in readme.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*-\s*([^:]+?)\s*:\s*(.+)$", line)
            if m:
                notes[m.group(1).strip()] = m.group(2).strip()
    used = {}
    for e in sorted(editions, key=lambda e: e["date"]):
        for it in e.get("items") or []:
            if it.get("imagen"):
                used[it["imagen"]] = e["date"]
    out = []
    for p in sorted(LIBRARY_DIR.iterdir()):
        if IMAGE_RE.fullmatch(f"biblioteca/{p.name}"):
            key = f"biblioteca/{p.name}"
            out.append({"imagen": key, "descripcion": notes.get(p.name), "usada_por_ultima_vez": used.get(key)})
    return out


def skins(champs, timeout=15):
    """The skins of some champions, from Riot's Data Dragon: {champion: [[number, name], ...]}."""
    from .site import _ddragon_id
    from .util import champ_name
    try:
        with urllib.request.urlopen(f"{DDRAGON}/api/versions.json", timeout=timeout) as resp:
            version = json.loads(resp.read())[0]
    except (urllib.error.URLError, OSError, ValueError, IndexError):
        return {}
    out = {}
    for c in sorted(set(champs)):
        cid = _ddragon_id(champ_name(c))
        try:
            with urllib.request.urlopen(f"{DDRAGON}/cdn/{version}/data/es_ES/champion/{cid}.json", timeout=timeout) as resp:
                data = json.loads(resp.read())["data"][cid]
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            continue
        # chromas (colour variants, with «parentSkin») have no splash art of their own
        out[champ_name(c)] = [[s["num"], s["name"] if s["num"] else "básico"] for s in data.get("skins", [])
                              if "parentSkin" not in s]
    return out


def catalog():
    return [{"id": k, "nombre": n, "lineas": l, "uso": u} for k, (n, l, u) in PLANTILLAS.items()]
