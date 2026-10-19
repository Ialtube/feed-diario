"""Resolve friends' Riot IDs and download their new matches."""
import time


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
