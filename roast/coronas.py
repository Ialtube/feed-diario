"""La Lonja de Coronas: a betting game with the paper's own currency.

Every edition opens a few markets about the next one (who will die the most, how the group's Flex
will go, whether the target of the day ends up on the podium of shame), each answer with fixed odds
worked out from the archive. Readers bet Coronas from the web until the closing hour of the day; the
next edition settles the markets. Everyone starts with SALDO_INICIAL Coronas, and whoever goes broke
is rescued by the Lonja, which the paper will not let them forget.

The bets live in Supabase (table `apuestas`); the robot copies them to data/coronas.json and the
balances are worked out from scratch on every build, so nothing can be cheated from the browser: a
bet placed after the closing time, on an answer that does not exist or with Coronas the reader did
not have, simply does not count.
"""
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from . import lectores
from .util import ROOT, get_tz, load_json, save_json

FILE = ROOT / "data" / "coronas.json"
SALDO_INICIAL = 100
RESCATE = 10           # the Lonja tops a broke reader up to this, once per market day
MARGEN = 0.88          # the house always wins a little
CIERRE_HORA = 20       # bets close at this local hour of the edition's day
FLEX = "Ranked Flex"


def _odds(p):
    return round(min(15.0, max(1.1, MARGEN / max(p, 0.01))), 1)


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _ts(text):
    """Supabase and our own timestamps (with or without fractions, «Z» or «+00:00») as UTC datetimes."""
    t = str(text or "").strip().replace("Z", "+00:00")
    m = re.match(r"(.*T\d\d:\d\d:\d\d)(?:\.(\d+))?(.*)", t)
    if not m:
        return datetime.min.replace(tzinfo=timezone.utc)
    frac = ((m.group(2) or "") + "000000")[:6]
    try:
        dt = datetime.fromisoformat(f"{m.group(1)}.{frac}{m.group(3) or '+00:00'}")
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _flex_sessions(edition):
    """(wins, losses) of the group's Flex games: two or more friends on the same team."""
    teams = defaultdict(list)
    for g in edition.get("games") or []:
        if g["queue_name"] == FLEX:
            teams[(g["match"], g["win"])].append(g)
    group = [won for (_, won), t in teams.items() if len(t) >= 2]
    return sum(group), len(group) - sum(group)


def _flex_outcome(edition):
    w, l = _flex_sessions(edition)
    return "sin_flex" if w + l == 0 else "mas_v" if w > l else "mas_d" if l > w else "empate"


def _podium(edition):
    from .site import day_points
    pts = day_points(edition.get("ranking") or [])
    return [s for s, p in sorted(pts.items(), key=lambda kv: -kv[1])][:3]


# ---------------------------------------------------------------- opening the markets
def create(edition, editions, cfg):
    """The markets of an edition (about the next one), with odds from the last 14 editions."""
    prev = [e for e in sorted(editions, key=lambda e: e["date"]) if e["date"] <= edition["date"]][-14:]
    if not prev:
        return None
    tz = get_tz(cfg.get("timezone", "Europe/Madrid"))
    y, m, d = map(int, edition["date"].split("-"))
    close = datetime(y, m, d, cfg.get("cierre_apuestas", CIERRE_HORA), tzinfo=tz)
    markets = []

    # 1. who will die the most
    played = Counter(r["slug"] for e in prev for r in e.get("ranking") or [])
    alias = {r["slug"]: r["alias"] for e in prev for r in e.get("ranking") or []}
    deaths = defaultdict(list)
    tops = Counter()
    for e in prev:
        rk = e.get("ranking") or []
        for r in rk:
            deaths[r["slug"]].append(r["d"])
        if rk:
            tops[max(rk, key=lambda r: r["d"])["slug"]] += 1
    regulars = [s for s, n in played.most_common() if n >= 2][:6]
    if len(regulars) >= 2:
        # how often they play times how much they die when they do, with a nudge for those who already topped it
        weight = {s: (1 + tops[s] / len(prev)) * (sum(deaths[s]) / len(deaths[s])) * played[s] / len(prev) for s in regulars}
        total = sum(weight.values()) * 1.15          # someone else can still top it
        markets.append({"id": f"{edition['date']}-muertes", "tipo": "muertes",
                        "pregunta": "¿Quién morirá más veces en la próxima edición?",
                        "opciones": [{"id": s, "texto": alias[s], "cuota": _odds(weight[s] / total)} for s in regulars]})

    # 2. how the group's Flex will go
    outs = Counter(_flex_outcome(e) for e in prev)
    n = len(prev) + 4
    texts = {"mas_v": "Más victorias que derrotas", "mas_d": "Más derrotas que victorias",
             "empate": "Empate", "sin_flex": "No habrá Flex del grupo"}
    markets.append({"id": f"{edition['date']}-flex", "tipo": "flex", "pregunta": "¿Cómo acabará la Flex del grupo?",
                    "opciones": [{"id": k, "texto": t, "cuota": _odds((outs[k] + 1) / n)} for k, t in texts.items()]})

    # 3. will today's target end up on the podium of shame
    from .site import general_leaderboard
    board = general_leaderboard(sorted(editions, key=lambda e: e["date"]))
    rk = edition.get("ranking") or []
    target = (board[0]["slug"] if board else None) or (rk[0]["slug"] if rk else None)
    if target:
        name = alias.get(target) or next((t["alias"] for t in board if t["slug"] == target), target)
        p = (sum(1 for e in prev if target in _podium(e)) + 1) / (len(prev) + 2)
        markets.append({"id": f"{edition['date']}-podio-{target}", "tipo": "podio", "jugador": target,
                        "pregunta": f"¿Acabará {name} en el podio de la vergüenza?",
                        "opciones": [{"id": "si", "texto": "Sí", "cuota": _odds(p)},
                                     {"id": "no", "texto": "No", "cuota": _odds(1 - p)}]})
    return {"cierre": _iso(close), "lista": markets}


# ---------------------------------------------------------------- settling them
def resolve(market, nxt):
    """Winning answers of a market given the next edition; None = void (stakes back)."""
    rk = nxt.get("ranking") or []
    if market["tipo"] == "muertes":
        if not rk:
            return None
        top = max(r["d"] for r in rk)
        return [r["slug"] for r in rk if r["d"] == top]
    if market["tipo"] == "flex":
        return [_flex_outcome(nxt)]
    if market["tipo"] == "podio":
        return ["si" if market["jugador"] in _podium(nxt) else "no"]
    return None


def _key(name):
    return " ".join(str(name or "").split()).lower()


def ledger(editions, bets):
    """Balances of every reader and the fate of every bet, worked out from scratch."""
    eds = sorted(editions, key=lambda e: e["date"])
    markets, settle_at = {}, {}
    for i, e in enumerate(eds):
        for m in (e.get("mercados") or {}).get("lista", []):
            markets[m["id"]] = dict(m, cierre=e["mercados"]["cierre"], edicion=e["date"])
            if i + 1 < len(eds):
                nxt = eds[i + 1]
                settle_at[m["id"]] = (datetime.fromtimestamp((nxt.get("generated_at") or nxt["window"][1]) / 1000,
                                                             timezone.utc).isoformat().replace("+00:00", "Z"), nxt)
    events = [(_ts(b.get("created_at")), 0, b) for b in bets or []]
    events += [(_ts(at), 1, mid) for mid, (at, _) in settle_at.items()]
    accounts = {}
    open_bets = defaultdict(list)
    results = {}
    rescued_on = set()

    def acc(name):
        k = _key(name)
        if k not in accounts:
            accounts[k] = {"nombre": " ".join(str(name).split())[:40], "saldo": SALDO_INICIAL, "apostado": 0,
                           "ganado": 0, "aciertos": 0, "fallos": 0, "rescates": 0}
        return accounts[k]

    for when, kind, x in sorted(events, key=lambda ev: (ev[0], ev[1])):
        if kind == 0:
            b, m = x, markets.get(x.get("mercado"))
            if not m or not _key(b.get("nombre")) or when > _ts(m["cierre"]):
                continue
            if b.get("opcion") not in {o["id"] for o in m["opciones"]}:
                continue
            a = acc(b["nombre"])
            day = (m["edicion"], _key(b["nombre"]))
            if a["saldo"] < RESCATE and day not in rescued_on:
                a["rescates"] += 1
                a["saldo"] = RESCATE
                rescued_on.add(day)
            try:
                amount = int(b.get("importe"))
            except (TypeError, ValueError):
                continue
            if not 1 <= amount <= a["saldo"]:
                continue
            a["saldo"] -= amount
            a["apostado"] += amount
            cuota = next(o["cuota"] for o in m["opciones"] if o["id"] == b["opcion"])
            open_bets[m["id"]].append({"nombre": a["nombre"], "opcion": b["opcion"], "importe": amount, "cuota": cuota})
        else:
            m = markets[x]
            win = resolve(m, settle_at[x][1])
            prizes = []
            for bet in open_bets.pop(x, []):
                a = acc(bet["nombre"])
                if win is None:
                    a["saldo"] += bet["importe"]
                    a["apostado"] -= bet["importe"]
                elif bet["opcion"] in win:
                    prize = int(bet["importe"] * bet["cuota"])
                    a["saldo"] += prize
                    a["ganado"] += prize
                    a["aciertos"] += 1
                    prizes.append(dict(bet, premio=prize))
                else:
                    a["fallos"] += 1
                    prizes.append(dict(bet, premio=0))
            texts = {o["id"]: o["texto"] for o in m["opciones"]}
            results[x] = {"pregunta": m["pregunta"], "edicion": m["edicion"], "nula": win is None,
                          "ganadoras": [texts.get(w, w) for w in win or []], "apuestas": prizes}
    board = sorted(accounts.values(), key=lambda a: -a["saldo"])
    return {"cuentas": board, "resultados": results,
            "abiertas": {k: v for k, v in open_bets.items()}}


# ---------------------------------------------------------------- storage
def sync(cfg, log=print):
    """Copies every bet from Supabase to data/coronas.json (keeps the old copy if it cannot)."""
    rows = lectores._get(cfg, "apuestas", [("select", "id,nombre,lector,mercado,opcion,importe,created_at"),
                                           ("order", "id.asc"), ("limit", "10000")])
    data = load_json(FILE, None) or {"apuestas": []}
    if rows is None:
        log("  ! No se pudieron leer las apuestas de la Lonja de Coronas (¿falta la tabla?)")
        return data
    data["apuestas"] = rows
    save_json(FILE, data)
    return data


def stored_bets():
    return (load_json(FILE, None) or {}).get("apuestas", [])


def summary(editions, date_str, bets=None):
    """What the newsroom needs to know: yesterday's markets settled today, the rich and the broke."""
    eds = [e for e in sorted(editions, key=lambda e: e["date"]) if e["date"] <= date_str]
    if not eds:
        return None
    led = ledger(eds, stored_bets() if bets is None else bets)
    prev = eds[-2]["date"] if len(eds) > 1 else None
    settled = {k: v for k, v in led["resultados"].items() if v["edicion"] == prev}
    return {"resueltos_hoy": list(settled.values()),
            "mas_ricos": led["cuentas"][:5],
            "arruinados": [a for a in led["cuentas"] if a["saldo"] < RESCATE or a["rescates"]][:5],
            "lectores_con_cuenta": len(led["cuentas"])}
