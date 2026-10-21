"""Resolve friends' Riot IDs and download their new matches."""
import time
from .rangos import snapshot


def summarize_match(m):
    """Shrink a full match-v5 payload (~40 KB) to the fields the roasts use (~3 KB)."""
    info = m.get("info") or {}
    meta = m.get("metadata") or {}
    start = info.get("gameStartTimestamp") or info.get("gameCreation") or 0
    duration = info.get("gameDuration") or 0
    if not info.get("gameEndTimestamp") and duration > 20000:  # very old payloads used ms
        duration //= 1000
    end = info.get("gameEndTimestamp") or (start + duration * 1000)

    parts = []
    for p in info.get("participants", []):
        ch = p.get("challenges") or {}
        pings = sum(v for k, v in p.items() if k.endswith("Pings") and isinstance(v, (int, float)))
        name = p.get("riotIdGameName") or p.get("summonerName") or "?"
        tag = p.get("riotIdTagline") or ""
        parts.append({
            "puuid": p.get("puuid"),
            "name": f"{name}#{tag}" if tag else name,
            "champ": p.get("championName", "?"),
            "pos": p.get("teamPosition") or p.get("individualPosition") or "",
            "team": p.get("teamId", 0),
            "win": bool(p.get("win")),
            "k": p.get("kills", 0), "d": p.get("deaths", 0), "a": p.get("assists", 0),
            "dmg": p.get("totalDamageDealtToChampions", 0),
            "taken": p.get("totalDamageTaken", 0),
            "obj": p.get("damageDealtToObjectives", 0),
            "gold": p.get("goldEarned", 0),
            "cs": p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0),
            "vision": p.get("visionScore", 0),
            "wards": p.get("wardsPlaced", 0),
            "dead": p.get("totalTimeSpentDead", 0),
            "fb": bool(p.get("firstBloodKill")),
            "multi": [p.get("doubleKills", 0), p.get("tripleKills", 0),
                      p.get("quadraKills", 0), p.get("pentaKills", 0)],
            "pings": int(pings),
            "solo": ch.get("soloKills", 0),
            "surr": bool(p.get("gameEndedInSurrender")),
            "esurr": bool(p.get("gameEndedInEarlySurrender")),
        })
    return {
        "id": meta.get("matchId") or f"{info.get('platformId', 'X')}_{info.get('gameId', 0)}",
        "queue": info.get("queueId", 0),
        "mode": info.get("gameMode", ""),
        "start": start,
        "end": end,
        "dur": duration,
        "parts": parts,
    }


def resolve_players(client, store, friends, log=print):
    """Returns the friends with a 'puuid' field. PUUIDs are cached in data/state.json."""
    players = []
    for f in friends:
        st = store.player_state(f["riot_id"])
        if not st.get("puuid"):
            name, tag = f["riot_id"].rsplit("#", 1)
            acc = client.account_by_riot_id(name, tag)
            if not acc or not acc.get("puuid"):
                log(f"  ! No encuentro a {f['riot_id']} en Riot (¿nombre o tag mal escrito?)")
                continue
            st["puuid"] = acc["puuid"]
            st["resolved_at"] = int(time.time())
        players.append({**f, "puuid": st["puuid"]})
    store.save_state()
    return players


QUEUES = {"RANKED_SOLO_5x5": "solo", "RANKED_FLEX_SR": "flex"}


def summarize_timeline(tl, puuids):
    """What happened inside a match for the friends: first blood, when and where they died,
    deaths to towers or minions, and the epic monsters they took."""
    info = (tl or {}).get("info") or {}
    pid = {p.get("participantId"): p.get("puuid") for p in info.get("participants", [])}
    out = {"fb": None, "jug": {}}
    deaths = {}
    for fr in info.get("frames", []):
        for ev in fr.get("events", []):
            t = ev.get("type")
            if t == "CHAMPION_KILL":
                victim, killer = pid.get(ev.get("victimId")), pid.get(ev.get("killerId"))
                if out["fb"] is None:
                    out["fb"] = {"killer": killer, "victim": victim, "min": round(ev.get("timestamp", 0) / 60000, 1)}
                if victim in puuids:
                    deaths.setdefault(victim, []).append((ev.get("timestamp", 0), ev.get("position") or {},
                                                          not ev.get("killerId")))
            elif t == "ELITE_MONSTER_KILL":
                k = pid.get(ev.get("killerId"))
                if k in puuids:
                    out["jug"].setdefault(k, {}).setdefault("objetivos", []).append(ev.get("monsterType"))
    for p, ds in deaths.items():
        mins = [round(ts / 60000, 1) for ts, _, _ in ds]
        pts = [(pos["x"], pos["y"]) for _, pos, _ in ds if "x" in pos and "y" in pos]
        spot = max((sum(1 for a, b in pts if (a - x) ** 2 + (b - y) ** 2 <= 1200 ** 2) for x, y in pts), default=0)
        out["jug"].setdefault(p, {}).update({
            "muertes_min": mins, "antes_del_10": sum(1 for m in mins if m < 10),
            "mismo_sitio": spot, "ejecutado": sum(1 for *_, e in ds if e)})
    return out


def fetch_timelines(client, store, players, start_ms, end_ms, log=print):
    """Adds the timeline summary to every match of the window that does not have it yet."""
    puuids = {p["puuid"] for p in players}
    done = 0
    for m in sorted(store.matches().values(), key=lambda m: m["end"]):
        if not (start_ms <= m["end"] < end_ms) or "tl" in m:
            continue
        if not any(p["puuid"] in puuids for p in m["parts"]):
            continue
        tl = client.timeline(m["id"])
        if tl:
            store.update_match(dict(m, tl=summarize_timeline(tl, puuids)))
            done += 1
    log(f"  {done} líneas temporales de partidas descargadas")
    return done


def fetch_ranks(client, store, players, date_str, log=print):
    """Today's ranked position of every account (smurfs apart), kept day by day in data/rangos.json."""
    ranks = store.ranks()

    def entries_of(p):
        return {QUEUES[e["queueType"]]: {"tier": e.get("tier"), "rank": e.get("rank"),
                                         "lp": e.get("leaguePoints", 0), "wins": e.get("wins", 0),
                                         "losses": e.get("losses", 0)}
                for e in client.league_entries(p["puuid"]) if e.get("queueType") in QUEUES}
    today = snapshot(players, entries_of)
    ranks[date_str] = today
    store.save_ranks(ranks)
    log(f"  Rangos guardados de {sum(1 for v in today.values() if 'solo' in v or 'flex' in v)} cuentas")
    return today


def fetch_new_matches(client, store, players, since_ms, max_per_player=20, log=print):
    """Downloads matches ended after since_ms that are not stored yet. Returns how many were added."""
    added = 0
    seen = set()
    for p in players:
        ids = client.match_ids(p["puuid"], start_time_s=since_ms // 1000, count=max_per_player)
        new_ids = [i for i in ids if i not in seen and not store.has_match(i)]
        seen.update(ids)
        log(f"  {p['alias']}: {len(ids)} partidas recientes, {len(new_ids)} nuevas")
        for match_id in new_ids:
            raw = client.match(match_id)
            if raw and store.add_match(summarize_match(raw)):
                added += 1
    return added
