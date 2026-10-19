"""Turns stored matches into per-player daily facts.

Every number the roasts quote comes from here, so the headlines can always be checked
against the match data.
"""
from collections import Counter, defaultdict

from .util import champ_name

QUEUE_NAMES = {
    420: "Ranked Solo/Dúo", 440: "Ranked Flex", 400: "Normal Draft", 430: "Normal",
    490: "Partida rápida", 480: "Swiftplay", 450: "ARAM", 900: "URF", 1900: "URF",
    1020: "Uno para todos", 1300: "Nexus Blitz", 700: "Clash", 720: "Clash ARAM",
}
REMAKE_SECONDS = 300
ROLE_NAMES = {"TOP": "top", "JUNGLE": "jungla", "MIDDLE": "mid", "BOTTOM": "ADC", "UTILITY": "support"}


def queue_name(q):
    return QUEUE_NAMES.get(q, f"Cola {q}")


def game_shame(r):
    """'Puntos de vergüenza' of one game. Higher = worse. Only used for ranking."""
    s = r["d"] * 1.2 - (r["k"] + 0.6 * r["a"]) * 0.5
    if not r["support"]:
        s += max(0.0, 0.20 - r["dmg_share"]) * 50
        if r["lowest_dmg"]:
            s += 3
    if not r["win"]:
        s += 2.5
    if r["d"] >= 10:
        s += 3
    s += max(0.0, 0.40 - r["kp"]) * 12
    if r["win"] and r["kda"] >= 5:
        s -= 2
    return round(s, 2)


def game_rows(match, friend_by_puuid):
    """One row per friend that played this match, with team context."""
    parts = match["parts"]
    minutes = max(match["dur"], 1) / 60
    teams = defaultdict(list)
    for p in parts:
        teams[p["team"]].append(p)
    rows = []
    for p in parts:
        friend = friend_by_puuid.get(p["puuid"])
        if not friend:
            continue
        team = teams[p["team"]]
        team_k = sum(q["k"] for q in team)
        team_dmg = sum(q["dmg"] for q in team) or 1
        team_gold = sum(q["gold"] for q in team) or 1
        dmg_rank = 1 + sum(1 for q in team if q["dmg"] > p["dmg"])
        death_rank = 1 + sum(1 for q in team if q["d"] > p["d"])
        allies = [friend_by_puuid[q["puuid"]]["alias"] for q in team
                  if q["puuid"] != p["puuid"] and q["puuid"] in friend_by_puuid]
        rivals = [friend_by_puuid[q["puuid"]]["alias"] for q in parts
                  if q["team"] != p["team"] and q["puuid"] in friend_by_puuid]
        kda = (p["k"] + p["a"]) / max(p["d"], 1)
        r = {
            "match": match["id"], "queue": match["queue"], "queue_name": queue_name(match["queue"]),
            "end": match["end"], "dur": match["dur"],
            "alias": friend["alias"], "slug": friend["slug"],
            "champ": champ_name(p["champ"]), "pos": p["pos"], "role": ROLE_NAMES.get(p["pos"], p["pos"].lower() or "?"),
            "support": p["pos"] == "UTILITY",
            "win": p["win"], "k": p["k"], "d": p["d"], "a": p["a"], "kda": round(kda, 2),
            "dmg": p["dmg"], "gold": p["gold"],
            "dmg_share": p["dmg"] / team_dmg, "gold_share": p["gold"] / team_gold,
            "kp": (p["k"] + p["a"]) / max(team_k, 1),
            "dmg_rank": dmg_rank, "team_size": len(team),
            "lowest_dmg": len(team) > 1 and dmg_rank == len(team),
            "most_deaths": len(team) > 1 and death_rank == 1 and p["d"] > 0,
            "cspm": p["cs"] / minutes, "vspm": p["vision"] / minutes, "dpm": p["dmg"] / minutes,
            "dead": p["dead"], "pings": p["pings"], "multi": p["multi"], "fb": p["fb"],
            "surrendered_loss": (p["surr"] or p["esurr"]) and not p["win"],
            "early_surrender": p["esurr"],
            "allies": allies, "rivals": rivals,
        }
        r["shame"] = game_shame(r)
        rows.append(r)
    return rows


def player_summary(friend, rows):
    rows = sorted(rows, key=lambda r: r["end"])
    g = len(rows)
    base = {"alias": friend["alias"], "slug": friend["slug"], "riot_id": friend["riot_id"], "games": g}
    if not g:
        return base
    wins = sum(r["win"] for r in rows)
    k = sum(r["k"] for r in rows); d = sum(r["d"] for r in rows); a = sum(r["a"] for r in rows)
    non_sup = [r for r in rows if not r["support"]]
    laners = [r for r in rows if r["pos"] in ("TOP", "MIDDLE", "BOTTOM")]
    streak = 0
    for r in reversed(rows):
        if r["win"]:
            break
        streak += 1
    max_loss_streak = cur = 0
    for r in rows:
        cur = 0 if r["win"] else cur + 1
        max_loss_streak = max(max_loss_streak, cur)
    champs = Counter(r["champ"] for r in rows)
    champ_losses = Counter(r["champ"] for r in rows if not r["win"])
    worst = max(rows, key=lambda r: r["shame"])
    best = min(rows, key=lambda r: r["shame"])
    avg = lambda xs: sum(xs) / len(xs) if xs else 0.0
    mean_shame = avg([r["shame"] for r in rows])
    summary = {
        **base,
        "wins": wins, "losses": g - wins, "k": k, "d": d, "a": a,
        "kda": round((k + a) / max(d, 1), 2),
        "dmg_share": avg([r["dmg_share"] for r in non_sup]) if non_sup else None,
        "gold_share": avg([r["gold_share"] for r in non_sup]) if non_sup else None,
        "kp": avg([r["kp"] for r in rows]),
        "cspm": avg([r["cspm"] for r in laners]) if laners else None,
        "vspm": avg([r["vspm"] for r in rows]),
        "dead": sum(r["dead"] for r in rows),
        "play_seconds": sum(r["dur"] for r in rows),
        "lowest_dmg": sum(1 for r in non_sup if r["lowest_dmg"]),
        "non_support_games": len(non_sup),
        "most_deaths_games": sum(1 for r in rows if r["most_deaths"]),
        "max_deaths": max(r["d"] for r in rows),
        "loss_streak_end": streak, "max_loss_streak": max_loss_streak,
        "surrendered_losses": sum(r["surrendered_loss"] for r in rows),
        "early_surrenders": sum(r["early_surrender"] and not r["win"] for r in rows),
        "max_pings": max(r["pings"] for r in rows),
        "pentas": sum(r["multi"][3] for r in rows), "quadras": sum(r["multi"][2] for r in rows),
        "champs": champs.most_common(),
        "cursed_champ": next(([c, n] for c, n in champs.most_common()
                              if n >= 2 and champ_losses[c] == n), None),
        "roles": Counter(r["role"] for r in rows).most_common(),
        "worst": worst, "best": best,
        "score": round(mean_shame + 0.5 * (g - wins), 2),
        "rows": rows,
    }
    return summary


def build_facts(matches, players, start_ms, end_ms, ignored_queues=(0, 1700)):
    """All the facts for one edition: matches that ended inside [start_ms, end_ms)."""
    friend_by_puuid = {p["puuid"]: p for p in players}
    rows_by_player = defaultdict(list)
    used = []
    for m in matches.values():
        if not (start_ms <= m["end"] < end_ms):
            continue
        if m["queue"] in ignored_queues or m["dur"] < REMAKE_SECONDS:
            continue
        rows = game_rows(m, friend_by_puuid)
        if not rows:
            continue
        used.append(m["id"])
        for r in rows:
            rows_by_player[r["slug"]].append(r)

    summaries = [player_summary(p, rows_by_player.get(p["slug"], [])) for p in players]
    active = sorted([s for s in summaries if s["games"]], key=lambda s: -s["score"])
    absent = [s["alias"] for s in summaries if not s["games"]]

    # Friends playing together / against each other
    duo = {}
    derbies = []
    by_match = defaultdict(list)
    for s in active:
        for r in s["rows"]:
            by_match[r["match"]].append(r)
    for match_id, rows in by_match.items():
        for i, r1 in enumerate(rows):
            for r2 in rows[i + 1:]:
                if r1["slug"] == r2["slug"]:
                    continue
                if r1["alias"] in r2["allies"]:
                    key = tuple(sorted([r1["alias"], r2["alias"]]))
                    rec = duo.setdefault(key, {"a": key[0], "b": key[1], "w": 0, "l": 0})
                    rec["w" if r1["win"] else "l"] += 1
                elif r1["alias"] in r2["rivals"]:
                    win, lose = (r1, r2) if r1["win"] else (r2, r1)
                    derbies.append({"match": match_id, "winner": win["alias"], "loser": lose["alias"],
                                    "winner_champ": win["champ"], "loser_champ": lose["champ"],
                                    "winner_kda": f"{win['k']}/{win['d']}/{win['a']}",
                                    "loser_kda": f"{lose['k']}/{lose['d']}/{lose['a']}"})

    return {
        "window": [start_ms, end_ms],
        "players": active,
        "absent": absent,
        "duos": sorted(duo.values(), key=lambda x: (x["w"] - x["l"], -(x["w"] + x["l"]))),
        "derbies": derbies,
        "totals": {
            "matches": len(used),
            "games": sum(s["games"] for s in active),
            "deaths": sum(s["d"] for s in active),
            "dead_seconds": sum(s["dead"] for s in active),
            "play_seconds": sum(s["play_seconds"] for s in active),
        },
    }
