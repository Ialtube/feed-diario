"""SoloQ Challenge: who climbs highest in Solo/Duo before the deadline. Anyone signs up on the
website (docs/soloq/) with a Riot ID; the robot follows the account every 30 minutes.

data/soloq/
  inscritos.json   the accounts that signed up (website through Supabase, or config.json "soloq.a_mano")
  historial.json   each account's Solo/Duo position every time it changed: [ms, tier, division, LP, wins, losses]
  partidas.json    each account's Solo/Duo games since the challenge started (compact)

The standings at any moment are computed from the history, so the newspaper can ask for the table
as it was when an edition closed, and for what moved during its day."""
import hashlib
import re
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from .lectores import _get as supabase_get
from .rangos import DIVS, TIER_ES, TIERS
from .util import ROOT, champ_name, fmt_num, get_tz, load_json, save_json

DIR = ROOT / "data" / "soloq"
SOLO_QUEUE = 420
REMAKE_SECONDS = 300
RIOT_ID = re.compile(r"^[^#]{3,16}#[^#\s]{2,5}$")
ICON_EVERY_MS = 12 * 3600 * 1000      # profile icon and level are refreshed twice a day
DDRAGON = "https://ddragon.leagueoflegends.com"

DEFAULTS = {
    "nombre": "SoloQ Challenge",
    "lema": "A ver quién llega más lejos antes de que se le acabe la dignidad",
    "inicio": None,
    "fin": None,
    "min_partidas": 20,
    "max_inscritos": 40,
    "premio": "",
    "castigo": "",
    "a_mano": [],
}


# --------------------------------------------------------------------------- the challenge
def reto(cfg):
    """The challenge settings (config.json «soloq») with its start and end as epoch ms (end exclusive)."""
    r = dict(DEFAULTS, **(cfg.get("soloq") or {}))
    tz = get_tz(cfg.get("timezone", "Europe/Madrid"))
    today = datetime.now(tz).date()
    ini = datetime.fromisoformat(r["inicio"]).date() if r.get("inicio") else today
    fin = datetime.fromisoformat(r["fin"]).date() if r.get("fin") else ini + timedelta(days=56)
    r["inicio"], r["fin"] = ini.isoformat(), fin.isoformat()
    r["inicio_ms"] = int(datetime(ini.year, ini.month, ini.day, tzinfo=tz).timestamp() * 1000)
    end = fin + timedelta(days=1)
    r["fin_ms"] = int(datetime(end.year, end.month, end.day, tzinfo=tz).timestamp() * 1000)
    r["tz"] = tz
    r["cutoff_hour"] = cfg.get("cutoff_hour", 7)
    return r


def fase(r, now_ms):
    if now_ms < r["inicio_ms"]:
        return "previa"
    return "finalizado" if now_ms >= r["fin_ms"] else "en_juego"


def ultimo_corte(r, now_ms):
    """The last cut-off (07:00 local) before now_ms: where «today» starts, as in the newspaper."""
    now = datetime.fromtimestamp(now_ms / 1000, r["tz"])
    cut = now.replace(hour=r["cutoff_hour"], minute=0, second=0, microsecond=0)
    if now < cut:
        cut -= timedelta(days=1)
    return int(cut.timestamp() * 1000)


# --------------------------------------------------------------------------- ranks
def value(rec):
    """A Solo/Duo position as one number (higher is better): 400 per tier, 100 per division, plus LP."""
    if not rec or rec[1] not in TIERS:
        return None
    i = TIERS.index(rec[1])
    if i >= TIERS.index("MASTER"):
        return TIERS.index("MASTER") * 400 + rec[3]
    return i * 400 + DIVS.get(rec[2], 0) * 100 + rec[3]


def apex(tier):
    return tier in TIERS and TIERS.index(tier) >= TIERS.index("MASTER")


def liga(rec, lp=True):
    """'Oro II · 45 LP' (or 'Sin clasificar')."""
    if not rec or rec[1] not in TIERS:
        return "Sin clasificar"
    name = TIER_ES[rec[1]] + ("" if apex(rec[1]) else f" {rec[2]}")
    return f"{name} · {rec[3]} LP" if lp else name


def target_value(tier):
    """The number an objective means: the bottom of that tier (Master and above: Master 0 LP)."""
    if tier not in TIERS:
        return None
    return min(TIERS.index(tier), TIERS.index("MASTER")) * 400


# --------------------------------------------------------------------------- storage
class Datos:
    def __init__(self, base=DIR):
        self.dir = Path(base)
        self.inscritos = load_json(self.dir / "inscritos.json", None) or {"cuentas": {}}
        self.inscritos.setdefault("cuentas", {})
        self.historial = load_json(self.dir / "historial.json", None) or {}
        self.partidas = load_json(self.dir / "partidas.json", None) or {}

    @property
    def cuentas(self):
        return self.inscritos["cuentas"]

    def save(self):
        save_json(self.dir / "inscritos.json", self.inscritos)
        save_json(self.dir / "historial.json", self.historial, indent=None)
        save_json(self.dir / "partidas.json", self.partidas, indent=None)


def _clean(text, n):
    return re.sub(r"\s+", " ", str(text or "")).strip()[:n]


def slug_key(key):
    """An HTML-id-safe version of an account key (for the #j-... links to a row)."""
    from .util import slugify
    return slugify(key.replace("#", "-")) + "-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:6]


def clean_riot_id(text):
    rid = _clean(text, 40)
    if "#" in rid:
        name, tag = rid.rsplit("#", 1)
        rid = f"{name.strip()}#{tag.strip()}"
    return rid


def leer_supabase(cfg):
    """The sign-ups on the website, or None if Supabase could not be read."""
    return supabase_get(cfg, "soloq_inscritos", [("select", "id,riot_id,apodo,jugador,objetivo,lema,created_at"),
                                                 ("order", "id.asc"), ("limit", "1000")])


def sincronizar(datos, filas, r, friends, roster_slugs, now_ms=None):
    """Merges the website's sign-ups (rows from Supabase; None = not read) and config's «a_mano» into
    inscritos.json. A row deleted in Supabase drops its account (that is how a troll is moderated).
    The first sign-up of an account wins; a second one with the same Riot ID is ignored."""
    now_ms = now_ms or int(time.time() * 1000)
    cuentas = datos.cuentas
    owner = {f["riot_id"].lower(): f["slug"] for f in friends}
    nuevas = []

    def add(row, origen):
        rid = clean_riot_id(row.get("riot_id"))
        if not RIOT_ID.match(rid):
            return
        key = rid.lower()
        old = cuentas.get(key)
        if old and (old["estado"] != "baja" or (old.get("origen"), old.get("id")) == (origen, row.get("id"))):
            return
        jugador = owner.get(key) or (row.get("jugador") if row.get("jugador") in roster_slugs else None)
        cuentas[key] = {
            "riot_id": rid, "apodo": _clean(row.get("apodo"), 24) or rid.split("#")[0], "jugador": jugador,
            "objetivo": row.get("objetivo") if row.get("objetivo") in TIERS else None,
            "lema": _clean(row.get("lema"), 120) or None,
            "inscrito": row.get("created_at") or datetime.fromtimestamp(now_ms / 1000, r["tz"]).isoformat(),
            "origen": origen, "id": row.get("id"),
            "estado": "pendiente" if not (old or {}).get("puuid") else "ok",
            **({"puuid": old["puuid"]} if (old or {}).get("puuid") else {}),
        }
        nuevas.append(key)

    if filas is not None:
        ids = {f.get("id") for f in filas}
        for c in cuentas.values():
            if c.get("origen") == "web" and c.get("id") not in ids:
                c["estado"] = "baja"
        for f in sorted(filas, key=lambda f: f.get("id") or 0):
            add(f, "web")
    manual = {clean_riot_id(m.get("riot_id")).lower() for m in r.get("a_mano") or []}
    for c in cuentas.values():
        if c.get("origen") == "manual" and c["riot_id"].lower() not in manual:
            c["estado"] = "baja"
    for m in r.get("a_mano") or []:
        add(m, "manual")
    return nuevas


def activos(datos, r=None):
    """The accounts in the race: found in Riot, not removed, one per person of the group (the first
    one they signed up; a second account of the same person is «duplicado»), up to max_inscritos."""
    limit = (r or DEFAULTS)["max_inscritos"]
    out, people, rejected = [], set(), []
    for key, c in sorted(datos.cuentas.items(), key=lambda kv: kv[1].get("inscrito") or ""):
        if c["estado"] in ("baja",):
            continue
        if c["estado"] != "ok":
            rejected.append((key, c, c["estado"]))
            continue
        if c.get("jugador") and c["jugador"] in people:
            rejected.append((key, c, "duplicado"))
            continue
        if len(out) >= limit:
            rejected.append((key, c, "lleno"))
            continue
        people.add(c.get("jugador"))
        people.discard(None)
        out.append((key, c))
    return out, rejected


# --------------------------------------------------------------------------- Riot
def _game_row(match_id, end, dur, p):
    return {"id": match_id, "fin": end, "dur": dur, "champ": champ_name(p.get("champ") or "?"), "cid": p.get("champ") or "",
            "win": bool(p["win"]),
            "k": p["k"], "d": p["d"], "a": p["a"], "pos": p.get("pos") or "", "cs": p.get("cs", 0),
            **({"rem": True} if dur < REMAKE_SECONDS else {})}


def game_from_summary(m, puuid):
    """A game from a match already stored by the newspaper (roast.fetch.summarize_match)."""
    if m.get("queue") != SOLO_QUEUE:
        return None
    p = next((p for p in m["parts"] if p["puuid"] == puuid), None)
    return _game_row(m["id"], m["end"], m["dur"], p) if p else None


def game_from_raw(raw, puuid):
    from .fetch import summarize_match
    return game_from_summary(summarize_match(raw), puuid) if raw else None


def _ids_since(client, puuid, since_s, cap=300):
    ids, start = [], 0
    while start < cap:
        page = client.match_ids(puuid, start_time_s=since_s, count=100, queue=SOLO_QUEUE, start=start)
        ids += page
        if len(page) < 100:
            break
        start += 100
    return ids


def ddragon_version(timeout=15):
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(f"{DDRAGON}/api/versions.json", timeout=timeout) as resp:
            return json.loads(resp.read())[0]
    except Exception:  # noqa: BLE001 - icons are a nicety; the table never waits for them
        return None


def actualizar(client, datos, r, now_ms=None, known_matches=None, known_puuids=None, max_games=40, log=print):
    """One pass of the robot: finds the new accounts, stores every position change and the new games.
    Returns True if anything changed."""
    now_ms = now_ms or int(time.time() * 1000)
    known_matches, known_puuids = known_matches or {}, known_puuids or {}
    changed = False
    for key, c in list(datos.cuentas.items()):
        if c["estado"] != "pendiente":
            continue
        puuid = known_puuids.get(key)
        if not puuid:
            name, tag = c["riot_id"].rsplit("#", 1)
            acc = client.account_by_riot_id(name, tag)
            if acc and acc.get("gameName") and acc.get("tagLine"):
                c["riot_id"] = f'{acc["gameName"]}#{acc["tagLine"]}'
            puuid = (acc or {}).get("puuid")
        c["estado"] = "ok" if puuid else "no_encontrado"
        if puuid:
            c["puuid"] = puuid
        log(f"  {'Nueva cuenta' if puuid else '! No existe en Riot'}: {c['riot_id']} ({c['apodo']})")
        changed = True

    playing = fase(r, now_ms) == "en_juego"
    for key, c in activos(datos, r)[0]:
        puuid = c["puuid"]
        if now_ms - c.get("icono_ms", 0) >= ICON_EVERY_MS and hasattr(client, "summoner_by_puuid"):
            s = client.summoner_by_puuid(puuid) or {}
            if s:
                if (s.get("profileIconId"), s.get("summonerLevel")) != (c.get("icono"), c.get("nivel")):
                    changed = True
                c["icono"], c["nivel"], c["icono_ms"] = s.get("profileIconId"), s.get("summonerLevel"), now_ms
        solo = next((e for e in client.league_entries(puuid) or [] if e.get("queueType") == "RANKED_SOLO_5x5"), None)
        rec = ([now_ms, solo.get("tier"), solo.get("rank"), solo.get("leaguePoints", 0), solo.get("wins", 0),
                solo.get("losses", 0)] if solo else [now_ms, None, None, 0, 0, 0])
        h = datos.historial.setdefault(key, [])
        if not h or h[-1][1:] != rec[1:]:
            h.append(rec)
            changed = True
        if not playing:
            continue
        games = datos.partidas.setdefault(key, [])
        have = {g["id"] for g in games}
        new = [i for i in _ids_since(client, puuid, r["inicio_ms"] // 1000) if i not in have][:max_games]
        for mid in new:
            g = (game_from_summary(known_matches[mid], puuid) if mid in known_matches
                 else game_from_raw(client.match(mid), puuid))
            if g and r["inicio_ms"] <= g["fin"] < r["fin_ms"]:
                games.append(g)
                changed = True
        games.sort(key=lambda g: g["fin"])
        if new:
            log(f"  {c['apodo']}: {liga(rec)}, {len(new)} partidas nuevas")
    return changed


# --------------------------------------------------------------------------- standings
def _at(h, t):
    rec = None
    for x in h:
        if x[0] > t:
            break
        rec = x
    return rec


def _streak(games):
    if not games:
        return 0
    last, n = games[-1]["win"], 0
    for g in reversed(games):
        if g["win"] != last:
            break
        n += 1
    return n if last else -n


def _worst_streak(games):
    best = cur = 0
    for g in games:
        cur = 0 if g["win"] else cur + 1
        best = max(best, cur)
    return best


def _row(key, c, h, games_all, r, at_ms, ref_ms):
    rec = _at(h, at_ms)
    if rec is None:
        return None
    base = _at(h, r["inicio_ms"]) or h[0]
    before = _at(h, ref_ms) if ref_ms else None
    games = [g for g in games_all if r["inicio_ms"] <= g["fin"] <= at_ms and not g.get("rem")]
    today = [g for g in games if ref_ms and g["fin"] > ref_ms]
    wins = sum(g["win"] for g in games)
    k, d, a = (sum(g[x] for g in games) for x in "kda")
    champs = Counter(g["champ"] for g in games)
    v, v0, vb = value(rec), value(base), value(before)
    series = [(x[0], value(x)) for x in h if base[0] <= x[0] <= at_ms and value(x) is not None]
    peak = max((x for x in h if base[0] <= x[0] <= at_ms and value(x) is not None), key=value, default=None)
    goal = c.get("objetivo")
    gv = target_value(goal)
    reached = bool(goal and rec[1] in TIERS and TIERS.index(rec[1]) >= TIERS.index(goal))
    return {
        "key": key, "apodo": c["apodo"], "riot_id": c["riot_id"], "jugador": c.get("jugador"),
        "icono": c.get("icono"), "nivel": c.get("nivel"), "lema": c.get("lema"), "inscrito": c.get("inscrito"),
        "tier": rec[1], "division": rec[2], "lp": rec[3], "valor": v, "liga": liga(rec), "liga_corta": liga(rec, lp=False),
        "temporada": [rec[4], rec[5]],
        "inicio": liga(base), "lp_reto": (v - v0) if v is not None and v0 is not None else None,
        "lp_hoy": (v - vb) if v is not None and vb is not None else None,
        "pico": liga(peak) if peak else None, "pico_valor": value(peak) if peak else None,
        "partidas": len(games), "victorias": wins, "derrotas": len(games) - wins,
        "winrate": wins / len(games) if games else None,
        "hoy": [sum(g["win"] for g in today), sum(not g["win"] for g in today)],
        "racha": _streak(games), "peor_racha": _worst_streak(games),
        "kda": (k + a) / max(d, 1) if games else None, "muertes_partida": d / len(games) if games else None,
        "horas": sum(g["dur"] for g in games) / 3600,
        "ultimas": [{"win": g["win"], "champ": g["champ"], "cid": g.get("cid"), "k": g["k"], "d": g["d"], "a": g["a"],
                     "fin": g["fin"]} for g in reversed(games[-10:])],
        "campeones": [{"champ": ch, "cid": next(g.get("cid") for g in games if g["champ"] == ch), "partidas": n,
                       "victorias": sum(g["win"] for g in games if g["champ"] == ch)} for ch, n in champs.most_common(3)],
        "objetivo": goal, "objetivo_es": TIER_ES.get(goal), "cumplido": reached,
        "falta": max(gv - v, 0) if gv is not None and v is not None and not reached else None,
        "serie": series + ([(at_ms, v)] if v is not None else []),
        "desde": base[0],
    }


def _order(row):
    ranked = row["valor"] is not None
    return (not ranked, -(row["valor"] or 0), row["partidas"] if ranked else -row["partidas"], row["inscrito"] or "")


def tabla(datos, r, at_ms, ref_ms=None):
    """The standings at at_ms, each row with its position change and LP since ref_ms."""
    accs, _ = activos(datos, r)

    def rows_at(t, ref):
        rows = [x for x in (_row(k, c, datos.historial.get(k) or [], datos.partidas.get(k) or [], r, t, ref)
                            for k, c in accs) if x]
        rows.sort(key=_order)
        for i, x in enumerate(rows, 1):
            x["puesto"] = i
        return rows

    rows = rows_at(at_ms, ref_ms)
    if ref_ms:
        before = {x["key"]: x["puesto"] for x in rows_at(ref_ms, None)}
        for x in rows:
            x["antes"] = before.get(x["key"])
            x["cambio"] = (before[x["key"]] - x["puesto"]) if x["key"] in before else None
    return rows


# --------------------------------------------------------------------------- humour
def _pick(options, seed):
    return options[int(hashlib.sha1(seed.encode("utf-8")).hexdigest(), 16) % len(options)]


def _pct(x):
    return f"{round(x * 100)} %"


VEREDICTOS = {
    "sin_jugar": [
        "Inscrito y desaparecido. Mucho grito de guerra y cero colas.",
        "Tiene el reto como el gimnasio: pagado y sin pisar.",
        "Cero partidas. Ha encontrado la única forma de no perder LP y la está explotando.",
        "Se apuntó, sacó pecho y se esfumó. Como en las fiestas de la uni.",
    ],
    "sin_clasificar": [
        "Jugando las de clasificación. Riot aún está decidiendo cuánto humillarle.",
        "Sin liga todavía. El sistema le está midiendo y ya se le nota la cara de susto.",
    ],
    "lider": [
        "Líder. Ser el mejor de este grupo es como ser el más alto de los enanitos, pero la corona pesa igual.",
        "Manda en la tabla. Que lo disfrute: en EUW eso es ser el tuerto en el país de los ciegos.",
        "Primero. Los demás le persiguen con la misma eficacia con la que ponen guardianes.",
        "Arriba del todo. Que nadie le diga que el listón estaba a la altura del tobillo.",
    ],
    "ultimo": [
        "Farolillo rojo. Su MMR está en busca y captura.",
        "Último. Juega como si le pagaran por perder, y encima lo hace gratis.",
        "Cierra la tabla. Por debajo solo quedan el Hierro y su dignidad.",
        "Último de la tabla. Si el elo fuera un ligue, ya le habría bloqueado.",
    ],
    "racha_mala": [
        "{n} derrotas seguidas y sigue dándole a buscar partida. Eso no es constancia, es una adicción.",
        "Lleva {n} palizas seguidas. El botón de rendirse ya tiene su huella dactilar.",
        "{n} seguidas perdidas. Lo suyo con la SoloQ ya no es tilt: es una relación tóxica.",
    ],
    "racha_buena": [
        "Racha de {n} victorias. Que la disfrute, que estadísticamente viene la hostia.",
        "{n} seguidas ganadas. Que alguien compruebe si le está jugando el primo.",
    ],
    "donante": [
        "Gana el {wr} de las partidas. Donante universal de LP: la Cruz Roja le quiere poner una placa.",
        "Un {wr} de victorias. Hay monedas al aire con más ambición.",
    ],
    "sospechoso": [
        "Gana el {wr}. Demasiado bueno para ser de este grupo: se pide control antidopaje.",
        "Un {wr} de victorias. O ha mejorado de verdad o ha pagado a alguien. Apostamos por lo segundo.",
    ],
    "adicto": [
        "{n} partidas. Ha visto más pantallas de carga que la luz del sol.",
        "{n} partidas en el reto. No tiene vida social: tiene MMR.",
    ],
    "promesa": [
        "Dijo {objetivo}. Va {liga}. Le faltan {falta} LP y bastante vergüenza.",
        "Prometió {objetivo}. Ahora mismo lo tiene tan lejos como un Barón bien hecho.",
        "Se apuntó diciendo {objetivo}. A este ritmo llega para la temporada que viene, o la otra.",
    ],
    "cumplido": [
        "Ha llegado a {objetivo}, como prometió. Que alguien le baje el ego antes de que lo tire todo.",
    ],
    "caida": [
        "{n} LP menos desde que empezó el reto. Más que escalar, hace espeleología.",
        "Ha perdido {n} LP desde el inicio. Su gráfica parece la bolsa en 2008.",
    ],
    "subida": [
        "+{n} LP desde el inicio. O ha mejorado o ha encontrado a alguien que le juegue.",
        "Ha subido {n} LP en el reto. Sospechoso de narices.",
    ],
    "normal": [
        "Ni fu ni fa. El típico que escribe «gg jungla» al minuto 3 y luego no hace nada.",
        "En tierra de nadie: demasiado malo para presumir, demasiado bueno para dar pena.",
        "Ni sube ni baja. Su elo tiene más estabilidad que todas sus relaciones juntas.",
        "Juega la SoloQ como Tinder: mucho match y muy poca victoria.",
        "Sigue en el reto con la fe de quien pide /ff a los 15 y luego dice «se podía».",
    ],
}


def veredicto(row, rows, day=""):
    """One adult-humour line about how this account is doing in the race (always about the game)."""
    seed = row["key"] + day
    n = row["partidas"]

    def say(kind, **kw):
        return _pick(VEREDICTOS[kind], seed + kind).format(**kw)

    if not n:
        return say("sin_jugar")
    if row["valor"] is None:
        return say("sin_clasificar")
    ranked = [x for x in rows if x["valor"] is not None]
    if row["racha"] <= -4:
        return say("racha_mala", n=-row["racha"])
    if row["puesto"] == 1 and len(ranked) > 1:
        return say("lider")
    if ranked and row is ranked[-1] and len(ranked) > 2:
        return say("ultimo")
    if row["racha"] >= 4:
        return say("racha_buena", n=row["racha"])
    if row["cumplido"]:
        return say("cumplido", objetivo=row["objetivo_es"])
    if row["falta"] and row["falta"] >= 300:
        return say("promesa", objetivo=row["objetivo_es"], liga=row["liga_corta"], falta=row["falta"])
    if n >= 10 and row["winrate"] < 0.42:
        return say("donante", wr=_pct(row["winrate"]))
    if n >= 10 and row["winrate"] >= 0.6:
        return say("sospechoso", wr=_pct(row["winrate"]))
    if (row["lp_reto"] or 0) <= -100:
        return say("caida", n=-row["lp_reto"])
    if (row["lp_reto"] or 0) >= 150:
        return say("subida", n=row["lp_reto"])
    if n >= 60 and n == max(x["partidas"] for x in rows):
        return say("adicto", n=n)
    return say("normal")


PREMIOS = [
    # key, title, how it is chosen, line
    ("adicto", "El Adicto", "Más partidas jugadas", "{n} partidas. La silla ya tiene la forma exacta de su culo."),
    ("horas", "Horas que no volverán", "Más horas en la Grieta", "{n} horas en Solo/Dúo. Con eso se sacaba un máster."),
    ("donante", "Donante de LP", "Peor porcentaje de victorias (mín. 10)", "Gana el {n}. Gracias por su generosidad."),
    ("kamikaze", "El Kamikaze", "Más muertes por partida (mín. 5)", "{n} muertes por partida. El rival ya le tiene en favoritos."),
    ("caida", "Caída libre", "Más LP perdidos desde que se apuntó", "{n} LP. Sin paracaídas y de cabeza."),
    ("cohete", "El Cohete", "Más LP ganados desde que se apuntó", "+{n} LP. Que alguien revise quién juega en esa cuenta."),
    ("racha", "Racha maldita", "Más derrotas seguidas en el reto", "{n} seguidas sin levantarse de la silla. Fe o masoquismo."),
    ("onetrick", "Fiel hasta la muerte", "Un mismo campeón en más partidas (mín. 10)", "{champ} en el {n} de sus partidas. Más fiel que a nadie."),
    ("turista", "El Turista", "Menos partidas jugadas", "{n} partidas. Vino a hacerse la foto y a irse."),
]


def premios(rows):
    """The wall of shame: one award per category, with its winner and the number that earned it."""
    out = []
    played = [x for x in rows if x["partidas"]]

    def give(key, row, n, **kw):
        title, how, line = next((t, h, ln) for k, t, h, ln in PREMIOS if k == key)
        out.append({"premio": key, "titulo": title, "criterio": how, "apodo": row["apodo"], "jugador": row["jugador"],
                    "key": row["key"], "texto": line.format(n=n, **kw)})

    if played:
        x = max(played, key=lambda x: x["partidas"])
        give("adicto", x, x["partidas"])
        x = max(played, key=lambda x: x["horas"])
        if x["horas"] >= 1:
            give("horas", x, fmt_num(x["horas"], 1))
    pool = [x for x in played if x["partidas"] >= 10]
    if pool:
        x = min(pool, key=lambda x: x["winrate"])
        give("donante", x, _pct(x["winrate"]))
    pool = [x for x in played if x["partidas"] >= 5]
    if pool:
        x = max(pool, key=lambda x: x["muertes_partida"])
        give("kamikaze", x, fmt_num(x["muertes_partida"], 1))
    moved = [x for x in rows if x["lp_reto"] is not None]
    if moved:
        x = min(moved, key=lambda x: x["lp_reto"])
        if x["lp_reto"] < 0:
            give("caida", x, -x["lp_reto"])
        x = max(moved, key=lambda x: x["lp_reto"])
        if x["lp_reto"] > 0:
            give("cohete", x, x["lp_reto"])
    if played:
        x = max(played, key=lambda x: x["peor_racha"])
        if x["peor_racha"] >= 3:
            give("racha", x, x["peor_racha"])
    pool = [x for x in played if x["partidas"] >= 10 and x["campeones"]]
    if pool:
        x = max(pool, key=lambda x: x["campeones"][0]["partidas"] / x["partidas"])
        share = x["campeones"][0]["partidas"] / x["partidas"]
        if share >= 0.4:
            give("onetrick", x, _pct(share), champ=x["campeones"][0]["champ"])
    if len(rows) > 2:
        x = min(rows, key=lambda x: (x["partidas"], x["inscrito"] or ""))
        give("turista", x, x["partidas"])
    return out


# --------------------------------------------------------------------------- movements
MOVES = {
    "ascenso": ["Sube a {ahora}. Que alguien avise a su madre.", "Asciende a {ahora}. Ya puede cambiarse la foto de perfil.",
                "Asciende a {ahora}. A ver cuánto le dura."],
    "descenso": ["Baja a {ahora}. Caída con estilo: de boca.", "Desciende a {ahora}. Riot le ha bajado de categoría y de autoestima.",
                 "Pierde la división: {ahora}. Lo de escalar era otra cosa."],
    "sube": ["+{n} LP. Hoy no ha tirado la partida.", "+{n} LP. Hasta un reloj parado acierta dos veces al día.",
             "+{n} LP. Que no se acostumbre."],
    "baja": ["−{n} LP. Donación recibida, gracias.", "−{n} LP. Otro ingreso en la cuenta del enemigo.",
             "−{n} LP. Lo de «una más y me acuesto» ha salido caro."],
    "liga": ["Termina las de clasificación: {ahora}. El sistema ya le ha calado.",
             "Primera liga del reto: {ahora}. Ya tiene suelo. O techo."],
    "inscripcion": ["Se apunta al reto. Valiente o inconsciente: pronto lo sabremos.",
                    "Nuevo inscrito. Otra víctima para la tabla.", "Entra en el reto con más ganas que macro."],
}


def movimientos(datos, r, desde_ms, hasta_ms, limit=None):
    """What happened between two moments: every change of position stored in the history, newest first."""
    out = []
    for key, c in activos(datos, r)[0]:
        h = [x for x in datos.historial.get(key) or [] if x[0] <= hasta_ms]
        base = dict(key=key, apodo=c["apodo"], jugador=c.get("jugador"))
        if h and desde_ms < h[0][0]:
            out.append(dict(base, ts=h[0][0], tipo="inscripcion", ahora=liga(h[0]),
                            texto=_pick(MOVES["inscripcion"], key)))
        for prev, cur in zip(h, h[1:]):
            if not desde_ms < cur[0] <= hasta_ms:
                continue
            v0, v1 = value(prev), value(cur)
            games = (cur[4] + cur[5]) - (prev[4] + prev[5])
            item = dict(base, ts=cur[0], antes=liga(prev), ahora=liga(cur), partidas=max(games, 0),
                        victorias=max(cur[4] - prev[4], 0), derrotas=max(cur[5] - prev[5], 0))
            if v0 is None and v1 is not None:
                tipo, n = "liga", None
            elif v1 is None or v0 is None:
                continue
            else:
                n = v1 - v0
                if (prev[1], prev[2]) != (cur[1], cur[2]):
                    tipo = "ascenso" if n > 0 else "descenso"
                elif n:
                    tipo = "sube" if n > 0 else "baja"
                else:
                    continue
            item.update(tipo=tipo, delta=n,
                        texto=_pick(MOVES[tipo], f"{key}{cur[0]}").format(ahora=liga(cur, lp=False), n=abs(n or 0)))
            out.append(item)
    out.sort(key=lambda x: -x["ts"])
    return out[:limit] if limit else out


# --------------------------------------------------------------------------- for the newspaper
def resumen(cfg, desde_ms, hasta_ms, datos=None):
    """The race as an edition sees it: the table when the edition closed (hasta_ms), what moved during
    its day (desde_ms → hasta_ms) and the wall of shame. None if nobody is in the race yet."""
    datos = datos or Datos()
    r = reto(cfg)
    if hasta_ms < r["inicio_ms"] - 7 * 24 * 3600 * 1000:
        return None
    rows = tabla(datos, r, hasta_ms, desde_ms)
    if not rows:
        return None
    day = datetime.fromtimestamp(hasta_ms / 1000, r["tz"]).date().isoformat()
    for x in rows:
        x["veredicto"] = veredicto(x, rows, day)
    before = [x for x in tabla(datos, r, desde_ms) if x["valor"] is not None]
    ranked = [x for x in rows if x["valor"] is not None]
    leader = ranked[0] if ranked else None
    site = (cfg.get("site_url") or "").rstrip("/")
    return {
        "nombre": r["nombre"], "fase": fase(r, hasta_ms), "inicio": r["inicio"], "fin": r["fin"],
        "dias_restantes": max(0, -(-(r["fin_ms"] - hasta_ms) // (24 * 3600 * 1000))),
        "min_partidas": r["min_partidas"], "premio": r.get("premio"), "castigo": r.get("castigo"),
        "url": f"{site}/soloq/" if site else "soloq/index.html",
        "lider": leader and leader["apodo"],
        "lider_antes": before[0]["apodo"] if before else None,
        "cambia_el_lider": bool(leader and before and before[0]["key"] != leader["key"]),
        "farolillo_rojo": ranked[-1]["apodo"] if len(ranked) > 2 else None,
        "clasificacion": [{
            "puesto": x["puesto"], "cambio_de_puesto": x.get("cambio"), "apodo": x["apodo"], "riot_id": x["riot_id"],
            "jugador": x["jugador"], "liga": x["liga"], "lp_en_el_dia": x.get("lp_hoy"),
            "victorias_dia": x["hoy"][0], "derrotas_dia": x["hoy"][1],
            "partidas_reto": x["partidas"], "victorias_reto": x["victorias"], "derrotas_reto": x["derrotas"],
            "winrate_reto": round(x["winrate"], 3) if x["winrate"] is not None else None,
            "racha": x["racha"], "lp_desde_que_se_apunto": x["lp_reto"], "empezo_en": x["inicio"], "pico": x["pico"],
            "objetivo_declarado": x["objetivo_es"], "objetivo_cumplido": x["cumplido"], "lp_para_el_objetivo": x["falta"],
            "grito_de_guerra": x["lema"], "cualifica": x["partidas"] >= r["min_partidas"],
            "campeones": [f'{c["champ"]} ({c["partidas"]})' for c in x["campeones"]], "veredicto_web": x["veredicto"],
        } for x in rows],
        "movimientos_del_dia": [{k: m.get(k) for k in ("apodo", "jugador", "tipo", "antes", "ahora", "delta", "partidas",
                                                        "victorias", "derrotas")} for m in movimientos(datos, r, desde_ms, hasta_ms)],
        "muro_de_la_verguenza": [{k: p[k] for k in ("titulo", "criterio", "apodo", "jugador", "texto")} for p in premios(rows)],
    }


# --------------------------------------------------------------------------- demo
DEMO = [  # apodo, riot id, group slug, objective, war cry, starting value, skill, games per day
    ("TheTrevur", "TheTrevur#URGOD", "thetrevur", "MASTER", "Urgot no se rinde, se reinicia", 2410, 0.58, 4),
    ("Wôlf", "Wôlf172#1075", "wolf", "DIAMOND", "Este mes salgo de Esmeralda o desinstalo", 1622, 0.51, 6),
    ("grangalax", "grangalax#OVD", "grangalax", "PLATINUM", "La moneda siempre cae de cara", 1218, 0.47, 5),
    ("Fr4nux", "Fr4nux#EUW", "fr4nux", "EMERALD", None, 1340, 0.45, 3),
    ("Saiko", "Kailordl#EUW", "saiko", "GOLD", "Vengo a mirar", 980, 0.52, 2),
    ("El Primo de Zaun", "PrimoZaun#666", None, "CHALLENGER", "Diamante en una semana, apuntadlo", 1475, 0.40, 7),
    ("Lady Tilt", "LadyTilt#EUW", None, None, None, 1105, 0.55, 3),
    ("Turista", "SoloMiro#EUW", None, "DIAMOND", "Juego cuando tenga tiempo", 1530, 0.5, 0),
]


def _rec_of(v, ts, wins, losses):
    if v is None:
        return [ts, None, None, 0, wins, losses]
    v = max(v, 0)
    if v >= 2800:
        lp = v - 2800
        tier = "CHALLENGER" if lp >= 900 else "GRANDMASTER" if lp >= 500 else "MASTER"
        return [ts, tier, "I", lp, wins, losses]
    tier = TIERS[int(v // 400)]
    return [ts, tier, ["IV", "III", "II", "I"][int(v % 400 // 100)], int(v % 100), wins, losses]


def demo(cfg, now_ms, days=9, seed=3):
    """Fake participants with a few days of games, to preview the website without a key."""
    import random
    rng = random.Random(seed)
    r = reto(cfg)
    start = min(r["inicio_ms"], now_ms - days * 86400000)
    d = Datos(base=Path("/nonexistent-soloq-demo"))
    champs = ["Urgot", "Ahri", "Jinx", "LeeSin", "Thresh", "Yasuo", "Kaisa", "Garen", "Viego", "Lux", "Ezreal", "MonkeyKing"]
    for i, (apodo, rid, slug, goal, lema, v, skill, per_day) in enumerate(DEMO):
        key = rid.lower()
        joined = start + i * 3 * 3600 * 1000
        d.cuentas[key] = {"riot_id": rid, "apodo": apodo, "jugador": slug, "objetivo": goal, "lema": lema,
                          "inscrito": datetime.fromtimestamp(joined / 1000, r["tz"]).isoformat(), "origen": "web",
                          "id": i + 1, "estado": "ok", "puuid": f"demo-{i}", "icono": 4000 + i * 37, "nivel": 120 + i * 41}
        wins, losses = rng.randint(40, 200), rng.randint(40, 200)
        placed = i != 6        # one of them is still playing the placement games
        h = [_rec_of(v if placed else None, joined, wins, losses)]
        games, t, mains = [], joined, rng.sample(champs, 3)
        if apodo == "TheTrevur":
            mains = ["Urgot", "Urgot", "Urgot"]
        while per_day:
            t += rng.randint(2, 9) * 3600 * 1000 // max(per_day // 2, 1)
            if t >= now_ms:
                break
            win = rng.random() < skill
            dur = rng.randint(1150, 2300)
            cid = rng.choice(mains)
            games.append({"id": f"EUW1_{9000000 + len(games) + i * 1000}", "fin": t, "dur": dur, "champ": champ_name(cid),
                          "cid": cid, "win": win, "k": rng.randint(1, 14), "d": rng.randint(1, 12), "a": rng.randint(2, 18),
                          "pos": "", "cs": rng.randint(80, 260)})
            wins, losses = wins + win, losses + (not win)
            if not placed and len(games) >= 5:
                placed, v = True, 1180
            elif placed:
                v += rng.randint(18, 27) if win else -rng.randint(16, 25)
            h.append(_rec_of(v if placed else None, t + 60000, wins, losses))
        d.historial[key] = h
        d.partidas[key] = games
    d.cuentas["faker#kr2"] = {"riot_id": "Faker#KR2", "apodo": "Faker", "estado": "no_encontrado", "origen": "web",
                              "inscrito": datetime.fromtimestamp(now_ms / 1000, r["tz"]).isoformat(), "id": 99}
    d.inscritos["actualizado"] = now_ms - 25 * 60000
    return d
