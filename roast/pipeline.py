"""Glue: facts -> roast items -> edition JSON."""
import time

from .analyze import build_facts
from .roasts import write_edition

GAME_KEYS = ("slug", "alias", "match", "end", "dur", "champ", "role", "queue_name", "win", "k", "d", "a",
             "dmg_share", "gold_share", "kp", "lowest_dmg", "support")


def make_edition(cfg, store, players, start_ms, end_ms, date_str, number):
    facts = build_facts(store.matches(), players, start_ms, end_ms, cfg["ignored_queues"])
    written = write_edition(facts, date_str, cfg["items_per_player"])
    ranking = [{
        "slug": s["slug"], "alias": s["alias"], "riot_id": s["riot_id"], "games": s["games"],
        "wins": s["wins"], "losses": s["losses"], "kda": s["kda"], "dmg_share": s["dmg_share"],
        "kp": s["kp"], "d": s["d"], "dead": s["dead"], "score": s["score"],
    } for s in facts["players"]]
    games = [{k: r[k] for k in GAME_KEYS} for s in facts["players"] for r in s["rows"]]
    return {
        "date": date_str,
        "number": number,
        "generated_at": int(time.time() * 1000),
        "window": [start_ms, end_ms],
        "items": written["items"],
        "frase": written["frase"],
        "ranking": ranking,
        "absent": facts["absent"],
        "duos": facts["duos"],
        "derbies": facts["derbies"],
        "totals": facts["totals"],
        "games": sorted(games, key=lambda g: g["end"]),
    }
