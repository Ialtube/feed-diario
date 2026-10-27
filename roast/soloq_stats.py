"""SoloQ Challenge: everything that can be told about one player from his games in the race (the
«ficha» of the board) and the pieces that join the games of everybody (the history board).
Pure functions over the games stored in data/soloq/partidas.json; a game saved before a field existed
simply does not count for the averages of that field."""
from collections import Counter
from datetime import datetime

POS_ES = {"TOP": "Top", "JUNGLE": "Jungla", "MIDDLE": "Mid", "BOTTOM": "ADC", "UTILITY": "Support"}
POS_ORDER = list(POS_ES)
FRANJAS = [("Madrugada", "0–6 h", 0, 6), ("Mañana", "6–12 h", 6, 12), ("Tarde", "12–18 h", 12, 18), ("Noche", "18–24 h", 18, 24)]
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
DURACIONES = [("Cortas", "menos de 25 min", 0, 25 * 60), ("Medias", "25–35 min", 25 * 60, 35 * 60),
              ("Largas", "más de 35 min", 35 * 60, 10 ** 9)]
MULTI = {2: "Dobles", 3: "Triples", 4: "Cuádruples", 5: "Pentakills"}


def best_multi(multi):
    """The biggest multikill of a game from [doubles, triples, quadras, pentas], 0 if none."""
    for i in (3, 2, 1, 0):
        if i < len(multi or []) and multi[i]:
            return i + 2
    return 0


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _per_min(g, key):
    return g[key] / (g["dur"] / 60) if g.get(key) is not None and g.get("dur") else None


def kda_of(g):
    return (g["k"] + g["a"]) / max(g["d"], 1)


def _split(games, key, labels):
    """Games and wins grouped by a function of the game (one entry per label, in order)."""
    out = {i: [0, 0] for i in range(len(labels))}
    for g in games:
        i = key(g)
        if i is not None:
            out[i][0] += 1
            out[i][1] += g["win"]
    return [{"nombre": lab[0], "detalle": lab[1], "n": out[i][0], "v": out[i][1]} for i, lab in enumerate(labels)]


def _record(g, titulo, valor):
    return {"titulo": titulo, "valor": valor, "champ": g["champ"], "cid": g.get("cid"), "win": g["win"], "fin": g["fin"],
            "kda": f'{g["k"]}/{g["d"]}/{g["a"]}'}


def lp_por_partida(hist, value, lo_ms=None, hi_ms=None):
    """LP gained or lost in each game, read from the league history: [(index in history, game won, LP)].
    Only the steps where exactly one game was played inside the same ladder count."""
    out = []
    for i in range(1, len(hist)):
        prev, cur = hist[i - 1], hist[i]
        if lo_ms and cur[0] < lo_ms or hi_ms and cur[0] > hi_ms:
            continue
        v0, v1 = value(prev), value(cur)
        if v0 is None or v1 is None or (cur[4] + cur[5]) - (prev[4] + prev[5]) != 1:
            continue
        out.append((i, cur[4] > prev[4], v1 - v0))
    return out


def ficha(games, hist, value, tz, lo_ms=None, hi_ms=None):
    """The stats of one player over his games in the race (oldest first, remakes already out)."""
    n = len(games)
    if not n:
        return {"n": 0}
    wins = sum(g["win"] for g in games)
    k, d, a = (sum(g[x] for g in games) for x in "kda")
    out = {"n": n, "victorias": wins, "derrotas": n - wins}
    out["k_media"], out["d_media"], out["a_media"] = k / n, d / n, a / n
    out["kda"] = (k + a) / max(d, 1)
    out["dur_media"] = _avg([g.get("dur") for g in games])
    out["horas"] = sum(g.get("dur") or 0 for g in games) / 3600
    out["cs_min"] = _avg([_per_min(g, "cs") for g in games])
    out["dmg_media"] = _avg([g.get("dmg") for g in games])
    out["dmg_min"] = _avg([_per_min(g, "dmg") for g in games])
    out["dmg_equipo"] = _avg([g.get("dp") for g in games])
    out["recibido_media"] = _avg([g.get("taken") for g in games])
    out["oro_min"] = _avg([_per_min(g, "gold") for g in games])
    out["vis_min"] = _avg([_per_min(g, "vis") for g in games])
    out["vis_media"] = _avg([g.get("vis") for g in games])
    out["kp"] = _avg([g.get("kp") for g in games])
    out["primeras_sangres"] = sum(1 for g in games if g.get("fb"))
    out["solo_kills"] = sum(g.get("solo") or 0 for g in games)
    out["objetivos_media"] = _avg([g.get("obj") for g in games])
    out["muerto"] = _avg([g["dead"] / g["dur"] if g.get("dead") is not None and g.get("dur") else None for g in games])
    mk = Counter(g.get("mk") or 0 for g in games)
    out["multi"] = [(MULTI[m], mk[m]) for m in MULTI]

    # personal records: the game, not just the number
    recs = []
    def top(titulo, key, fmt, pool=None, lowest=False):
        pool = [g for g in (pool or games) if key(g) is not None]
        if pool:
            g = (min if lowest else max)(pool, key=key)
            recs.append(_record(g, titulo, fmt(key(g))))
    top("Más asesinatos", lambda g: g["k"], lambda v: f"{v} asesinatos")
    top("Más muertes", lambda g: g["d"], lambda v: f"{v} muertes")
    top("Mejor KDA", kda_of, lambda v: f"KDA {v:.1f}")
    top("Más daño", lambda g: g.get("dmg"), lambda v: f"{v:,}".replace(",", ".") + " de daño")
    top("Más CS", lambda g: g.get("cs"), lambda v: f"{v} CS")
    top("Más oro", lambda g: g.get("gold"), lambda v: f"{v:,}".replace(",", ".") + " de oro")
    top("Más visión", lambda g: g.get("vis"), lambda v: f"{v} de visión")
    top("Partida más larga", lambda g: g.get("dur"), lambda v: f"{v // 60} min {v % 60:02d} s")
    top("Partida más corta", lambda g: g.get("dur"), lambda v: f"{v // 60} min {v % 60:02d} s", lowest=True)
    out["records"] = recs

    # by champion, lane, hour, weekday and length
    byc = {}
    for g in games:
        e = byc.setdefault(g["champ"], {"champ": g["champ"], "cid": g.get("cid"), "n": 0, "v": 0, "k": 0, "d": 0, "a": 0})
        e["n"] += 1
        e["v"] += g["win"]
        e["k"] += g["k"]
        e["d"] += g["d"]
        e["a"] += g["a"]
    out["campeones"] = sorted(({**e, "kda": (e["k"] + e["a"]) / max(e["d"], 1)} for e in byc.values()),
                              key=lambda e: (-e["n"], -e["v"], e["champ"]))
    byp = {}
    for g in games:
        if g.get("pos") in POS_ES:
            e = byp.setdefault(g["pos"], {"pos": g["pos"], "nombre": POS_ES[g["pos"]], "n": 0, "v": 0, "k": 0, "d": 0, "a": 0})
            e["n"] += 1
            e["v"] += g["win"]
            e["k"] += g["k"]
            e["d"] += g["d"]
            e["a"] += g["a"]
    out["lineas"] = sorted(({**e, "kda": (e["k"] + e["a"]) / max(e["d"], 1)} for e in byp.values()),
                           key=lambda e: (-e["n"], POS_ORDER.index(e["pos"])))
    local = [(g, datetime.fromtimestamp(g["fin"] / 1000, tz)) for g in games]
    idx = {id(g): dt for g, dt in local}
    out["franjas"] = _split(games, lambda g: next(i for i, f in enumerate(FRANJAS) if f[2] <= idx[id(g)].hour < f[3]),
                            [(f[0], f[1]) for f in FRANJAS])
    out["dias"] = _split(games, lambda g: idx[id(g)].weekday(), [(x, "") for x in DIAS])
    out["duraciones"] = _split(games, lambda g: next((i for i, f in enumerate(DURACIONES) if f[2] <= g["dur"] < f[3]), None)
                               if g.get("dur") else None, [(f[0], f[1]) for f in DURACIONES])

    # streaks and tilt: how he plays right after a win and right after a loss
    after = {True: [0, 0], False: [0, 0]}
    for prev, g in zip(games, games[1:]):
        after[prev["win"]][0] += 1
        after[prev["win"]][1] += g["win"]
    out["tras_victoria"], out["tras_derrota"] = after[True], after[False]
    days = Counter(dt.date() for _, dt in local)
    best_day, best_n = max(days.items(), key=lambda kv: (kv[1], kv[0]))
    out["dias_jugados"], out["mejor_dia"] = len(days), {"fecha": best_day.isoformat(), "n": best_n}
    span = (max(days) - min(days)).days + 1
    out["media_dia"] = n / span

    # LP per game from the league history
    steps = lp_por_partida(hist, value, lo_ms, hi_ms)
    ups, downs = [lp for _, w, lp in steps if w and lp > 0], [lp for _, w, lp in steps if not w and lp < 0]
    out["lp_victoria"], out["lp_derrota"] = _avg(ups), _avg(downs)
    return out
