"""La porra: readers bet (no money, no prizes) on who will be the worst player of the next
edition. Each edition checks the bets placed since the previous one; the most recent bet of
each reader is the one that counts."""
from collections import Counter

from .sorteo import _iso
from . import lectores


def fetch_bets(cfg, since_ms, until_ms):
    return lectores._get(cfg, "porras", [("select", "nombre,lector,prediccion,created_at"),
                                         ("created_at", f"gt.{_iso(since_ms)}"), ("created_at", f"lte.{_iso(until_ms)}"),
                                         ("order", "created_at.asc")])


def resolve(cfg, edition, previous=None, bets=None):
    since = (previous or {}).get("generated_at") or edition["window"][0]
    until = edition.get("generated_at") or edition["window"][1]
    if bets is None:
        bets = fetch_bets(cfg, since, until)
    ranking = edition.get("ranking") or []
    worst = ranking[0] if ranking else None
    alias = {r["slug"]: r["alias"] for r in ranking}
    latest = {}
    for b in bets or []:
        latest[b.get("lector") or b["nombre"]] = b
    votes = Counter(b["prediccion"] for b in latest.values())
    hits = [{"nombre": b["nombre"][:40]} for b in latest.values() if worst and b["prediccion"] == worst["slug"]]
    return {"peor": worst["alias"] if worst else None, "peor_slug": worst["slug"] if worst else None,
            "participantes": len(latest), "acertantes": hits,
            "votos": {alias.get(k, k): n for k, n in votes.most_common()},
            "estado": "ok" if bets is not None else "sin_datos"}


def seers(editions, limit=8):
    """Readers who have guessed the worst player the most times."""
    c = Counter(a["nombre"] for e in editions for a in (e.get("porra") or {}).get("acertantes", []))
    return c.most_common(limit)
