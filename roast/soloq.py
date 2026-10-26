"""SoloQ Challenge: who climbs highest in Solo/Duo with a brand-new account. Everyone signs up their
challenge account by hand on the website (docs/soloq/); the admin fires the starting gun
(python -m roast soloq --empezar, or the «SoloQ Challenge» workflow) and the robot follows every
account every 30 minutes.

data/soloq/
  inscritos.json   the accounts that signed up (website through Supabase, or config.json "soloq.a_mano"),
                   plus "reto": when the admin started (and ended) the race, and the Discord notices sent
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
    "inicio": None,          # normally empty: the admin starts the race by hand
    "fin": None,
    "duracion_dias": 30,     # how long the race lasts once started (None: until the admin ends it)
    "aviso_hora": 9,         # the daily Discord notice goes out after this hour (local time)
    "min_partidas": 20,
    "max_inscritos": 40,
    "premio": "",
    "castigo": "",
    "a_mano": [],
}


# --------------------------------------------------------------------------- the challenge
def reto(cfg, estado=None):
    """The challenge settings (config.json «soloq») with its start and end as epoch ms (end exclusive).
    `estado` is inscritos.json «reto»: the start (and end) the admin fired by hand, which wins over
    the dates in config.json. Without a start the race is still taking sign-ups."""
    r = dict(DEFAULTS, **(cfg.get("soloq") or {}))
    tz = get_tz(cfg.get("timezone", "Europe/Madrid"))
    est = estado or {}

    def midnight(d):
        return int(datetime(d.year, d.month, d.day, tzinfo=tz).timestamp() * 1000)

    ini = est.get("inicio_ms") or (midnight(datetime.fromisoformat(r["inicio"]).date()) if r.get("inicio") else None)
    fin = est.get("fin_ms")
    if not fin and r.get("fin"):
        fin = midnight(datetime.fromisoformat(r["fin"]).date() + timedelta(days=1))
    if not fin and ini and r.get("duracion_dias"):
        fin = ini + int(r["duracion_dias"]) * 24 * 3600 * 1000
    r["inicio_ms"], r["fin_ms"] = ini, fin
    r["inicio"] = datetime.fromtimestamp(ini / 1000, tz).date().isoformat() if ini else None
    r["fin"] = datetime.fromtimestamp((fin - 1) / 1000, tz).date().isoformat() if fin else None
    r["tz"] = tz
    r["cutoff_hour"] = cfg.get("cutoff_hour", 7)
    return r


def fase(r, now_ms):
    """«inscripcion» until the starting gun, «en_juego», then «finalizado»."""
    if not r["inicio_ms"] or now_ms < r["inicio_ms"]:
        return "inscripcion"
    return "finalizado" if r["fin_ms"] and now_ms >= r["fin_ms"] else "en_juego"


def leer_control(cfg):
    """The admin's latest schedule from the board (table soloq_control, written only through the
    password-checked function soloq_programar), or None."""
    rows = supabase_get(cfg, "soloq_control", [("select", "id,inicio,fin,created_at"), ("order", "id.desc"), ("limit", "1")])
    return rows[0] if rows else None


def _ms(iso):
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000) if iso else None


def aplicar_control(datos, fila):
    """Takes the admin's schedule if it is newer than the last one applied. Returns True if it changed."""
    if not fila or fila.get("id", 0) <= datos.inscritos.get("control_id", 0):
        return False
    datos.inscritos["reto"] = {"inicio_ms": _ms(fila["inicio"]), "fin_ms": _ms(fila.get("fin"))}
    datos.inscritos["control_id"] = fila["id"]
    return True


def cuando(ms, tz):
    """'lunes, 2 de noviembre de 2026 a las 20:00'"""
    from .util import long_date
    d = datetime.fromtimestamp(ms / 1000, tz)
    return f"{long_date(d.date())} a las {d:%H:%M}"


def empezar(datos, cfg, now_ms, dias=None):
    """The starting gun: from now on every Solo/Duo game of the accounts counts."""
    r = dict(DEFAULTS, **(cfg.get("soloq") or {}))
    dias = dias if dias is not None else r.get("duracion_dias")
    datos.inscritos["reto"] = {"inicio_ms": now_ms, "fin_ms": now_ms + int(dias) * 24 * 3600 * 1000 if dias else None}
    datos.inscritos["actualizado"] = now_ms
    return reto(cfg, datos.inscritos["reto"])


def terminar(datos, cfg, now_ms):
    est = datos.inscritos.setdefault("reto", {})
    est["fin_ms"] = now_ms
    datos.inscritos["actualizado"] = now_ms
    return reto(cfg, est)


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
    alias = {f["slug"]: f["alias"] for f in friends}
    for c in cuentas.values():      # the name the newspaper uses for that person
        c["persona"] = alias.get(c.get("jugador"))
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

    # games count from the starting gun to the end (plus a last pass to catch the final games)
    playing = bool(r["inicio_ms"]) and r["inicio_ms"] <= now_ms < (r["fin_ms"] or now_ms + 1) + 2 * 3600 * 1000
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
            if g:
                games.append(g)
                changed = True
        games.sort(key=lambda g: g["fin"])
        if new:
            log(f"  {c['apodo']}: {liga(rec)}, {len(new)} partidas nuevas")
    if changed:
        datos.inscritos["actualizado"] = now_ms
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
    ini = r["inicio_ms"]
    base = (_at(h, ini) or h[0]) if ini and ini <= at_ms else h[0]
    before = _at(h, ref_ms) if ref_ms else None
    end = min(at_ms, r["fin_ms"] or at_ms)
    games = [g for g in games_all if ini and ini <= g["fin"] <= end and not g.get("rem")] if ini else []
    today = [g for g in games if ref_ms and g["fin"] > ref_ms]
    wins = sum(g["win"] for g in games)
    k, d, a = (sum(g[x] for g in games) for x in "kda")
    champs = Counter(g["champ"] for g in games)
    # a brand-new account starts unranked: its LP in the race count from its first league
    first = next((x for x in h if base[0] <= x[0] <= at_ms and value(x) is not None), None)
    v, v0, vb = value(rec), value(base) if value(base) is not None else value(first), value(before)
    series = [(x[0], value(x)) for x in h if base[0] <= x[0] <= at_ms and value(x) is not None]
    peak = max((x for x in h if base[0] <= x[0] <= at_ms and value(x) is not None), key=value, default=None)
    goal = c.get("objetivo")
    gv = target_value(goal)
    reached = bool(goal and rec[1] in TIERS and TIERS.index(rec[1]) >= TIERS.index(goal))
    return {
        "key": key, "nombre": c.get("persona") or c["apodo"], "apodo": c["apodo"], "riot_id": c["riot_id"],
        "jugador": c.get("jugador"),
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
        out.append({"premio": key, "titulo": title, "criterio": how, "nombre": row["nombre"], "jugador": row["jugador"],
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
        base = dict(key=key, nombre=c.get("persona") or c["apodo"], apodo=c["apodo"], jugador=c.get("jugador"))
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


def reto_de(cfg, datos):
    return reto(cfg, datos.inscritos.get("reto"))


def puesta_al_dia(datos, r, at_ms, ref_ms=None):
    """The table at at_ms with the web's humour line on every row."""
    at = min(at_ms, r["fin_ms"] or at_ms)
    rows = tabla(datos, r, at, ref_ms)
    day = datetime.fromtimestamp(at / 1000, r["tz"]).date().isoformat()
    for x in rows:
        x["veredicto"] = veredicto(x, rows, day)
    return rows


def datos_completos(datos, r, at_ms, max_games=150):
    """Everything the newsroom may need to answer a reader's suggestion with a card: every account's
    games in the race and its league history, in plain words."""
    out = []
    for x in puesta_al_dia(datos, r, at_ms):
        games = [g for g in datos.partidas.get(x["key"]) or [] if r["inicio_ms"] and r["inicio_ms"] <= g["fin"] <= at_ms]
        out.append({
            "nombre": x["nombre"], "mote": x["apodo"], "jugador": x["jugador"], "cuenta": x["riot_id"], "liga": x["liga"],
            "historial_liga": [[datetime.fromtimestamp(h[0] / 1000, r["tz"]).strftime("%Y-%m-%d %H:%M"), liga(h)]
                               for h in datos.historial.get(x["key"]) or [] if h[0] <= at_ms][-60:],
            "partidas": [{"fin": datetime.fromtimestamp(g["fin"] / 1000, r["tz"]).strftime("%Y-%m-%d %H:%M"),
                          "campeon": g["champ"], "victoria": g["win"], "k": g["k"], "d": g["d"], "a": g["a"],
                          "minutos": round(g["dur"] / 60), "posicion": g.get("pos"), "cs": g.get("cs"),
                          **({"remake": True} if g.get("rem") else {})} for g in games[-max_games:]],
        })
    return out


# --------------------------------------------------------------------------- notes pinned to the board
FIRMAS = ["Anónimo", "Alguien de la cola", "El de la limpieza", "Tu jungla", "La mesa del fondo", "Un smurf arrepentido",
          "El tabernero", "Un soporte cansado", "La Guardia de Piltover", "Tu madre", "El que sube las persianas",
          "Un Teemo resentido"]
RELLENO = [
    "Prohibido pedir dúo. Esto es SoloQ, no terapia de pareja.",
    "Se vende teclado poco usado. La tecla del /ff, gastadísima.",
    "Recordatorio: el /mute all es gratis y salva amistades.",
    "Perdido: el MMR de alguien de este tablón. Si lo encontráis, quedáoslo.",
    "Se busca jungla que no culpe al top. Razón: imposible.",
    "Comprarse una cuenta nueva no te hace mejor jugador. Te hace el mismo manco con menos LP.",
    "Aviso a los inscritos: «es que me tocan unos equipos…» no cuenta como estrategia.",
    "Se alquila silla con la forma exacta de un culo en racha de derrotas. Razón: abajo.",
]


def notas(rows, ph, day, cast=(), limit=11):
    """The notes nailed around the table: pieces of mockery about the race and its people, signed
    by the newspaper's cast or by «somebody». Always about how they play."""
    out, kinds = [], Counter()
    firmas = list(FIRMAS) + list(cast)

    def add(text, seed, kind=None, most=2):
        """At most `most` notes of each kind, so the board does not repeat itself."""
        if isinstance(text, list):
            text = _pick(text, day + seed)
        if kind and kinds[kind] >= most or text in (n["texto"] for n in out):
            return
        kinds[kind] += 1
        out.append({"texto": text, "firma": _pick(firmas, day + seed)})

    if ph == "inscripcion":
        add("Nadie juega hasta que el jefe dé el pistoletazo. Lo que juguéis antes no cuenta, pero se nota.", "pist")
        if not rows:
            add("Se buscan valientes con cuenta recién comprada. Razón: aquí mismo. Abstenerse llorones.", "vacio")
        for x in sorted(rows, key=lambda x: _pick(list(range(97)), day + x["key"])):
            n, goal = x["nombre"], x.get("objetivo_es")
            if x["valor"] is not None:
                add(f"La cuenta «nueva» de {n} ya tiene liga ({x['liga_corta']}). Nueva, dice. Y yo soy Faker.",
                    x["key"], "vieja", 3)
            if goal:
                add([f"{n} se apunta diciendo que llega a {goal}. Lo clavo aquí para cuando esté en Bronce.",
                     f"Apuesto una cerveza a que {n} no huele {goal} ni de lejos.",
                     f"{n} promete {goal}. También prometió dejar de jugar a Yasuo."], x["key"], "promesa")
            if x.get("lema"):
                add(f"«{x['lema']}», dice {n}. Guardad esta nota para el día que pierda cinco seguidas.", x["key"], "lema")
            add([f"{n} ya tiene su cuenta de cero. Toda la ilusión del mundo. Que la disfrute, dura poco.",
                 f"Cuenta nueva, {n}, mismas manos. Veremos.",
                 f"{n} se ha comprado una cuenta limpia para ensuciarla él solito."], x["key"], "nuevo")
    else:
        ranked = [x for x in rows if x["valor"] is not None]
        if ranked:
            add(f"Que alguien le baje los humos a {ranked[0]['nombre']}: va primero y ya habla como si fuera Challenger.", "lider")
        if len(ranked) > 2:
            add(_pick([f"{ranked[-1]['nombre']}: el Hierro no es un destino, es un aviso. Y te está avisando.",
                       f"Si encontráis el MMR de {ranked[-1]['nombre']}, no se lo devolváis. Le va mejor sin él."], day),
                "ultimo")
        if len(ranked) > 1 and ranked[0]["valor"] - ranked[1]["valor"] <= 40:
            add(f"Entre {ranked[0]['nombre']} y {ranked[1]['nombre']} hay {ranked[0]['valor'] - ranked[1]['valor']} LP. "
                "Esto se decide en una partida con un jungla manco.", "cerca")
        for x in sorted(rows, key=lambda x: _pick(list(range(97)), day + x["key"])):   # a different few every day
            n, lp = x["nombre"], x.get("lp_hoy") or 0
            if lp <= -40:
                add([f"{n} ha palmado {-lp} LP hoy. Si le veis, no le habléis de la SoloQ. Ni de nada.",
                     f"−{-lp} LP hoy para {n}. Riot debería mandarle una tarjeta de condolencias."], x["key"] + "lp", "palma")
            elif lp >= 40:
                add([f"{n} ha ganado {lp} LP hoy. Ha sido sin querer, tranquilos.",
                     f"+{lp} LP para {n} hoy. Alguien le ha cambiado los cables."], x["key"] + "lp", "gana")
            if x["racha"] <= -3:
                add(f"{n}: {-x['racha']} derrotas seguidas. Suelta el ratón, sal a la calle y toca hierba. De la de verdad.",
                    x["key"] + "r", "racha_mala")
            elif x["racha"] >= 3:
                add(f"{n} lleva {x['racha']} seguidas ganadas. Que alguien mire quién le está jugando la cuenta.",
                    x["key"] + "r", "racha_buena")
            if not x["partidas"]:
                add(f"{n} no ha jugado ni una. Se apuntó para salir en el tablón y ya ha salido. Enhorabuena, cobarde.",
                    x["key"] + "0", "cero")
            elif x["partidas"] >= 10 and x["winrate"] <= 0.45:
                add(f"{n} gana el {_pct(x['winrate'])} de las partidas. Hay monedas al aire con más ambición.", x["key"] + "wr",
                    "wr", 1)
            if x.get("falta") and x["falta"] >= 300:
                add([f"{n} prometió {x['objetivo_es']} y va {x['liga_corta']}. Esta nota se queda aquí hasta que lo cumpla "
                     "o se muera de vergüenza.",
                     f"{x['objetivo_es']}, dijo {n}. Va {x['liga_corta']}. Yo también dije que iba al gimnasio."],
                    x["key"] + "o", "promesa")
            if (x.get("cambio") or 0) >= 2:
                add(f"{n} sube {x['cambio']} puestos de golpe. Que no se acostumbre.", x["key"] + "c", "sube", 1)
        played = [x for x in rows if x["partidas"]]
        if played:
            x = max(played, key=lambda x: x["partidas"])
            if x["partidas"] >= 15:
                add(f"{x['nombre']} lleva {x['partidas']} partidas. Dejadle comida en la puerta y no le abráis si llama.",
                    "adicto")
    for i, text in enumerate(sorted(RELLENO, key=lambda t: _pick([0, 1, 2, 3, 4, 5, 6, 7], day + t))):
        if len(out) >= limit:
            break
        add(text, f"r{i}")
    return out[:limit]


# --------------------------------------------------------------------------- for the newspaper
def cabecera(cfg, r, at_ms):
    """What every summary of the race says about the race itself."""
    started = bool(r["inicio_ms"] and r["inicio_ms"] <= at_ms)
    day = 24 * 3600 * 1000
    site = (cfg.get("site_url") or "").rstrip("/")
    return {
        "nombre": r["nombre"], "fase": fase(r, at_ms), "inicio": r["inicio"], "fin": r["fin"],
        "empieza": cuando(r["inicio_ms"], r["tz"]) if r["inicio_ms"] else None,
        "acaba": cuando(r["fin_ms"], r["tz"]) if r["fin_ms"] else None,
        "dias_restantes": max(0, -(-(r["fin_ms"] - at_ms) // day)) if r["fin_ms"] and started else None,
        "dia_del_reto": (at_ms - r["inicio_ms"]) // day + 1 if started else None,
        "min_partidas": r["min_partidas"], "premio": r.get("premio"), "castigo": r.get("castigo"),
        "url": f"{site}/soloq/" if site else "soloq/index.html", "clasificacion": [],
    }


def resumen(cfg, desde_ms, hasta_ms, datos=None):
    """The race as an edition sees it: the table when the edition closed (hasta_ms), what moved during
    its day (desde_ms → hasta_ms) and the wall of shame. While the race is taking sign-ups, who has
    signed up. None if there is nobody yet."""
    datos = datos or Datos()
    r = reto_de(cfg, datos)
    ph = fase(r, hasta_ms)
    rows = puesta_al_dia(datos, r, hasta_ms, desde_ms if ph == "en_juego" else None)
    if not rows:
        return None
    started = r["inicio_ms"] and r["inicio_ms"] <= hasta_ms
    before = [x for x in tabla(datos, r, desde_ms) if x["valor"] is not None] if started else []
    ranked = [x for x in rows if x["valor"] is not None] if started else []
    leader = ranked[0] if ranked else None
    return {
        **cabecera(cfg, r, hasta_ms),
        "lider": leader and leader["nombre"],
        "lider_antes": before[0]["nombre"] if before else None,
        "cambia_el_lider": bool(leader and before and before[0]["key"] != leader["key"]),
        "farolillo_rojo": ranked[-1]["nombre"] if len(ranked) > 2 else None,
        "inscritos_del_dia": [x["nombre"] for x in rows if x["desde"] > desde_ms],
        "clasificacion": [{
            "puesto": x["puesto"], "cambio_de_puesto": x.get("cambio"), "nombre": x["nombre"], "mote": x["apodo"],
            "riot_id": x["riot_id"], "jugador": x["jugador"], "liga": x["liga"], "lp_en_el_dia": x.get("lp_hoy"),
            "victorias_dia": x["hoy"][0], "derrotas_dia": x["hoy"][1],
            "partidas_reto": x["partidas"], "victorias_reto": x["victorias"], "derrotas_reto": x["derrotas"],
            "winrate_reto": round(x["winrate"], 3) if x["winrate"] is not None else None,
            "racha": x["racha"], "lp_en_el_reto": x["lp_reto"], "empezo_en": x["inicio"], "pico": x["pico"],
            "nivel": x["nivel"], "objetivo_declarado": x["objetivo_es"], "objetivo_cumplido": x["cumplido"],
            "lp_para_el_objetivo": x["falta"], "grito_de_guerra": x["lema"], "cualifica": x["partidas"] >= r["min_partidas"],
            "campeones": [f'{c["champ"]} ({c["partidas"]})' for c in x["campeones"]], "veredicto_web": x["veredicto"],
        } for x in rows],
        "movimientos_del_dia": [{k: m.get(k) for k in ("nombre", "jugador", "tipo", "antes", "ahora", "delta", "partidas",
                                                        "victorias", "derrotas")} for m in movimientos(datos, r, desde_ms, hasta_ms)],
        "muro_de_la_verguenza": [{k: p[k] for k in ("titulo", "criterio", "nombre", "jugador", "texto")}
                                 for p in premios(rows)] if started else [],
    }


# --------------------------------------------------------------------------- Discord
def _fmt_lp(n):
    return "" if not n else f" ({'+' if n > 0 else '−'}{abs(n)} LP)"


def aviso_payload(sq, cfg, tipo="diario", site_url="", nota=None):
    """The race on Discord: the daily notice (the newspaper's day, 07:00 to 07:00), the starting gun
    and the final result."""
    url = (site_url.rstrip("/") + "/soloq/") if site_url else None
    rows = sq["clasificacion"] if sq else []
    ranked = [x for x in rows if x["liga"] != "Sin clasificar"]
    lines = []
    if tipo == "programado":
        title, content = f"📅 Ya hay fecha para el {sq['nombre']}", "📅 El jefe ha hablado: ya hay fecha para el SoloQ Challenge."
        lines.append(f"**Empieza el {sq['empieza']}.**" + (f" Acaba el {sq['acaba']}." if sq.get("acaba") else ""))
        if rows:
            lines.append(f"**Inscritos ({len(rows)}):** " + ", ".join(x["nombre"] for x in rows))
        lines.append("¿Aún sin cuenta apuntada? Al tablón, que se acaba el plazo de hacer el ridículo gratis.")
    elif tipo == "inicio":
        title, content = f"🔔 ¡Pistoletazo de salida del {sq['nombre']}!", "🔔 Empieza el SoloQ Challenge. Que cada palo aguante su vela."
        if rows:
            lines.append(f"**{len(rows)} valientes** con cuenta de cero: " + ", ".join(x["nombre"] for x in rows))
        if sq.get("acaba"):
            lines.append(f"Termina el **{sq['acaba']}**. Mínimo {sq['min_partidas']} partidas para optar al trono.")
        if sq.get("premio"):
            lines.append(f"🏆 **Premio:** {sq['premio']}")
        if sq.get("castigo"):
            lines.append(f"🪓 **Castigo:** {sq['castigo']}")
    elif tipo == "final":
        title, content = f"🏆 Se acabó el {sq['nombre']}", "🏆 Fin del SoloQ Challenge. Ya hay culpables."
        medals = ["🥇", "🥈", "🥉"]
        lines.append("\n".join(f"{medals[i]} **{x['nombre']}** — {x['liga']} · {x['victorias_reto']}V {x['derrotas_reto']}D"
                               for i, x in enumerate(ranked[:3])))
        if sq.get("farolillo_rojo"):
            lines.append(f"🏮 **Farolillo rojo:** {sq['farolillo_rojo']}" + (f". Castigo: {sq['castigo']}" if sq.get("castigo") else ""))
    elif sq["fase"] == "inscripcion":
        title, content = f"📜 {sq['nombre']}: el vestuario", "📜 Novedades en el tablón del SoloQ Challenge"
        lines.append(f"**Inscritos ({len(rows)}):** " + ", ".join(x["nombre"] for x in rows))
        if sq.get("inscritos_del_dia"):
            lines.append("**Nuevos:** " + ", ".join(sq["inscritos_del_dia"]))
        lines.append("Nadie juega hasta el pistoletazo. Id calentando el dedo del /ff.")
    else:
        title = f"📜 Tablón del {sq['nombre']} · día {sq['dia_del_reto']}"
        content = "📜 El parte del SoloQ Challenge" + (f": quedan {sq['dias_restantes']} días" if sq.get("dias_restantes") else "")

        def arrow(x):
            c = x.get("cambio_de_puesto")
            return "" if not c else f" {'▲' if c > 0 else '▼'}{abs(c)}"
        lines.append("\n".join(f"**{x['puesto']}.** {x['nombre']} — {x['liga']}{arrow(x)}{_fmt_lp(x.get('lp_en_el_dia'))}"
                               for x in rows[:8]))
        moved = [x for x in rows if x.get("lp_en_el_dia")]
        if moved:
            up, down = max(moved, key=lambda x: x["lp_en_el_dia"]), min(moved, key=lambda x: x["lp_en_el_dia"])
            if up["lp_en_el_dia"] > 0:
                lines.append(f"📈 **El día de** {up['nombre']}: +{up['lp_en_el_dia']} LP ({up['victorias_dia']}V {up['derrotas_dia']}D)")
            if down["lp_en_el_dia"] < 0:
                lines.append(f"📉 **Se hunde** {down['nombre']}: −{-down['lp_en_el_dia']} LP ({down['victorias_dia']}V {down['derrotas_dia']}D)")
        if sq.get("cambia_el_lider"):
            lines.append(f"👑 **Nuevo líder:** {sq['lider']} (adiós, {sq['lider_antes']})")
        quiet = [x["nombre"] for x in rows if not x["victorias_dia"] and not x["derrotas_dia"]]
        if quiet and len(quiet) < len(rows):
            lines.append("🫥 **Ni una partida:** " + ", ".join(quiet))
    if nota and tipo == "diario":
        lines.append(f"📌 *«{nota['texto']}»* — {nota['firma']}")
    embed = {"title": title, "description": "\n\n".join(lines)[:4000], "color": 0x6B4A2B,
             "footer": {"text": f"{cfg.get('site_title', 'El Rincón del Feeder')} · SoloQ Challenge"}}
    if url:
        embed["url"] = url
    return {"username": f"{cfg.get('site_title', 'El Rincón del Feeder')} · SoloQ", "content": content, "embeds": [embed]}


def avisos_pendientes(datos, r, now_ms):
    """Which Discord notices are due now: the date the admin set, the starting gun, the daily one (once a
    day, after aviso_hora; while taking sign-ups only if somebody new signed up) and the final one."""
    st = datos.inscritos.setdefault("avisos", {})
    ph = fase(r, now_ms)
    if ph == "finalizado":
        return [] if st.get("final") else ["final"]
    due = []
    if ph == "inscripcion" and r["inicio_ms"] and st.get("programado") != r["inicio_ms"]:
        due.append("programado")
    if ph == "en_juego" and st.get("inicio") != r["inicio_ms"]:
        due.append("inicio")
    local = datetime.fromtimestamp(now_ms / 1000, r["tz"])
    if local.hour >= r.get("aviso_hora", 9) and st.get("diario") != local.date().isoformat():
        due.append("diario")
    return due


# --------------------------------------------------------------------------- demo
DEMO = [  # name in the paper, nickname, riot id, group slug, objective, war cry, skill, games per day
    ("TheTrevur", "Urgot.exe", "UrgotNuevo#URG", "thetrevur", "MASTER", "Urgot no se rinde, se reinicia", 0.58, 5),
    ("Wôlf", "Lobo de Saldo", "LoboComprado#1075", "wolf", "DIAMOND", "Este mes salgo de Esmeralda o desinstalo", 0.53, 7),
    ("grangalax", "La Moneda", "MonedaAlAire#OVD", "grangalax", "PLATINUM", "La moneda siempre cae de cara", 0.47, 6),
    ("Fr4nux", "Carry Not Found", "CarryNotFound#EUW", "fr4nux", "EMERALD", None, 0.45, 4),
    ("Saiko", "Saiko", "SaikoZero#EUW", "saiko", "GOLD", "Vengo a mirar", 0.52, 3),
    ("iPredatoRz", "Depredador", "PredatorDeCero#ESP", "ipredatorz", "CHALLENGER", "Diamante en una semana, apuntadlo", 0.40, 8),
    ("GSJoseador", "El Joseador", "JoseadorNuevo#2711", "gsjoseador", None, None, 0.55, 3),
    ("Dierophant", "Dierophant", "DieroDeCero#EUW", "dierophant", "DIAMOND", "Juego cuando tenga tiempo", 0.5, 0),
]


def _rec_of(v, ts, wins, losses):
    if v is None:
        return [ts, None, None, 0, wins, losses]
    v = max(v, 0)
    if v >= 2800:
        lp = v - 2800
        tier = "CHALLENGER" if lp >= 900 else "GRANDMASTER" if lp >= 500 else "MASTER"
        return [ts, tier, "I", lp, wins, losses]
    return [ts, TIERS[int(v // 400)], ["IV", "III", "II", "I"][int(v % 400 // 100)], int(v % 100), wins, losses]


def demo(cfg, now_ms, days=9, seed=3, empezado=True):
    """Fake brand-new accounts with a few days of games, to preview the website without a key."""
    import random
    rng = random.Random(seed)
    start = now_ms - days * 86400000
    d = Datos(base=Path("/nonexistent-soloq-demo"))
    if empezado:
        d.inscritos["reto"] = {"inicio_ms": start, "fin_ms": start + 30 * 86400000}
    champs = ["Urgot", "Ahri", "Jinx", "LeeSin", "Thresh", "Yasuo", "Kaisa", "Garen", "Viego", "Lux", "Ezreal", "MonkeyKing"]
    tz = get_tz(cfg.get("timezone", "Europe/Madrid"))
    for i, (persona, apodo, rid, slug, goal, lema, skill, per_day) in enumerate(DEMO):
        key = rid.lower()
        joined = start - (len(DEMO) - i) * 5 * 3600 * 1000
        d.cuentas[key] = {"riot_id": rid, "apodo": apodo, "jugador": slug, "persona": persona, "objetivo": goal, "lema": lema,
                          "inscrito": datetime.fromtimestamp(joined / 1000, tz).isoformat(), "origen": "web",
                          "id": i + 1, "estado": "ok", "puuid": f"demo-{i}", "icono": 4000 + i * 37, "nivel": 30 + i}
        h, games, wins, losses, v = [_rec_of(None, joined, 0, 0)], [], 0, 0, None
        mains = ["Urgot"] * 3 if persona == "TheTrevur" else rng.sample(champs, 3)
        t = start
        while empezado and per_day:
            t += rng.randint(2, 9) * 3600 * 1000 // max(per_day // 2, 1)
            if t >= now_ms:
                break
            win = rng.random() < skill
            cid = rng.choice(mains)
            games.append({"id": f"EUW1_{9000000 + len(games) + i * 1000}", "fin": t, "dur": rng.randint(1150, 2300),
                          "champ": champ_name(cid), "cid": cid, "win": win, "k": rng.randint(1, 14), "d": rng.randint(1, 12),
                          "a": rng.randint(2, 18), "pos": "", "cs": rng.randint(80, 260)})
            wins, losses = wins + win, losses + (not win)
            if v is None and len(games) >= 5:      # placements done
                v = rng.choice([780, 900, 1010, 1150, 1240]) + 40 * (wins - losses)
            elif v is not None:
                v += rng.randint(18, 27) if win else -rng.randint(16, 25)
            h.append(_rec_of(v, t + 60000, wins, losses))
        d.historial[key] = h
        d.partidas[key] = games
    d.cuentas["faker#kr2"] = {"riot_id": "Faker#KR2", "apodo": "Faker", "estado": "no_encontrado", "origen": "web",
                              "inscrito": datetime.fromtimestamp(now_ms / 1000, tz).isoformat(), "id": 99}
    d.inscritos["actualizado"] = now_ms - 25 * 60000
    return d
