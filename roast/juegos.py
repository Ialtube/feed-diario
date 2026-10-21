"""The readers' daily games that need no money: the popular jury and «¿Quién fue?».

- The popular jury: every edition asks the readers one question (Claude writes it, with two to four
  answers). The votes are counted in the next edition, which publishes the verdict.
- «¿Quién fue?»: one game of the day, with the player hidden. The clues come out one by one and the
  readers guess who played it; the fewer clues they need, the better.
"""
import base64
import hashlib

from . import lectores
from .util import champ_name, fmt_pct, get_tz, ms_to_local

COLAS = {"Ranked Flex": "Flex", "Ranked Solo/Dúo": "SoloQ", "Normal Draft": "normal"}


# ---------------------------------------------------------------- the popular jury
def jury_result(cfg, edition, votes=None):
    """Yesterday's question with the votes per answer (None if there was no question)."""
    j = (edition or {}).get("jurado")
    if not j:
        return None
    if votes is None:
        votes = lectores._get(cfg, "jurado", [("select", "opcion,nombre,lector"), ("edicion", f"eq.{edition['date']}")])
    counts = [0] * len(j["opciones"])
    names = [[] for _ in j["opciones"]]
    seen = set()
    for v in votes or []:
        if v.get("lector") in seen or not 0 <= v.get("opcion", -1) < len(counts):
            continue
        seen.add(v.get("lector"))
        counts[v["opcion"]] += 1
        if v.get("nombre"):
            names[v["opcion"]].append(v["nombre"])
    return {"edicion": edition["date"], "pregunta": j["pregunta"], "juicio": j.get("juicio", False),
            "opciones": [{"texto": t, "votos": n, "quien": sorted(set(w))} for t, n, w in zip(j["opciones"], counts, names)],
            "total": sum(counts), "estado": "ok" if votes is not None else "sin_datos"}


# ---------------------------------------------------------------- ¿Quién fue?
def _encode(slug):
    return base64.b64encode(slug[::-1].encode("utf-8")).decode("ascii")


def puzzle(edition, tz_name="Europe/Madrid"):
    """The game of the day to guess, with its clues from vaguest to most obvious."""
    games = edition.get("games") or []
    players = {r["slug"]: r["alias"] for r in edition.get("ranking") or []}
    if len(players) < 2 or not games:
        return None
    # the juiciest games first (many deaths or a defeat), then a stable pick by date
    pool = sorted(games, key=lambda g: (-(g["d"] >= 6 or not g["win"]), g["match"], g["slug"]))
    pool = [g for g in pool if g["d"] >= 6 or not g["win"]] or pool
    seed = int(hashlib.sha1(edition["date"].encode()).hexdigest(), 16)
    g = pool[seed % len(pool)]
    tz = get_tz(tz_name)
    start = ms_to_local(g["end"] - g["dur"] * 1000, tz)
    cola = COLAS.get(g["queue_name"], g["queue_name"])
    pistas = [
        # never the role: everyone in the group plays the same position, so it would give the answer away
        f"Una {cola} de ayer. Acabó en {'victoria' if g['win'] else 'derrota'}.",
        f"KDA {g['k']}/{g['d']}/{g['a']}" + (f" y el {fmt_pct(g['dmg_share'], 0)} del daño de su equipo."
                                              if g.get("dmg_share") is not None else "."),
        f"Empezó a las {start:%H:%M} y duró {round(g['dur'] / 60)} minutos.",
        f"Campeón: {champ_name(g['champ'])}.",
    ]
    return {"pistas": pistas, "opciones": [{"slug": s, "alias": a} for s, a in sorted(players.items(), key=lambda x: x[1].lower())],
            "clave": _encode(g["slug"]), "campeon": champ_name(g["champ"]), "alias": g["alias"]}


def puzzle_result(cfg, edition, rows=None):
    """How the readers did with the puzzle of an edition."""
    if not (edition or {}).get("quien_fue"):
        return None
    if rows is None:
        rows = lectores._get(cfg, "quienfue", [("select", "nombre,lector,intentos,acierto"), ("edicion", f"eq.{edition['date']}")])
    best = {}
    for r in rows or []:
        k = r.get("lector") or r.get("nombre")
        if k not in best:
            best[k] = r
    solved = sorted((r for r in best.values() if r.get("acierto")), key=lambda r: r.get("intentos", 9))
    return {"edicion": edition["date"], "solucion": edition["quien_fue"]["alias"],
            "campeon": edition["quien_fue"]["campeon"], "jugaron": len(best),
            "acertaron": [{"nombre": r.get("nombre") or "anónimo", "intentos": r.get("intentos")} for r in solved],
            "fallaron": len(best) - len(solved), "estado": "ok" if rows is not None else "sin_datos"}
