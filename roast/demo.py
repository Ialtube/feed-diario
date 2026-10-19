"""Fake data in the exact Riot match-v5 format, so the whole pipeline can run without an API key.

DemoRiot behaves like RiotClient (same three methods), which lets the demo and the tests
exercise the real fetch -> summarize -> analyze -> roast -> site path.
"""
import random
from datetime import datetime, timedelta

POSITIONS = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
CHAMPS = {
    "TOP": ["Urgot", "Garen", "Darius", "Malphite", "Sett", "Ambessa", "Cho'Gath"],
    "JUNGLE": ["Lee Sin", "Viego", "Kha'Zix", "Vi", "Graves", "Nidalee"],
    "MIDDLE": ["Azir", "Ahri", "Viktor", "Orianna", "Yasuo", "Taliyah", "Syndra"],
    "BOTTOM": ["Kai'Sa", "Jinx", "Caitlyn", "Ashe", "Zeri", "Ezreal", "Draven"],
    "UTILITY": ["Thresh", "Lulu", "Nautilus", "Bard", "Leona", "Senna"],
}
DMG_PM = {"TOP": 780, "JUNGLE": 560, "MIDDLE": 860, "BOTTOM": 920, "UTILITY": 340}
GOLD_PM = {"TOP": 410, "JUNGLE": 385, "MIDDLE": 425, "BOTTOM": 455, "UTILITY": 285}
CS_PM = {"TOP": 6.8, "JUNGLE": 5.6, "MIDDLE": 7.2, "BOTTOM": 7.6, "UTILITY": 1.2}

# How each demo friend tends to play (multipliers and preferences)
PROFILES = {
    "grangalax": {"roles": ["MIDDLE", "BOTTOM"], "dmg": 0.9, "deaths": 2.6, "win": 0.44, "games": (1, 6)},
    "thetrevur": {"roles": ["TOP"], "champ": "Urgot", "dmg": 1.15, "deaths": 0.0, "win": 0.56, "games": (0, 4)},
    "wolf": {"roles": ["JUNGLE", "MIDDLE"], "dmg": 1.0, "deaths": 1.2, "win": 0.48, "games": (0, 5), "pings": 2.5},
    "fr4nux": {"roles": ["BOTTOM", "MIDDLE"], "dmg": 0.68, "deaths": 0.4, "win": 0.5, "games": (1, 5)},
}
DEFAULT_PROFILE = {"roles": POSITIONS, "dmg": 1.0, "deaths": 1.0, "win": 0.5, "games": (0, 4)}


def demo_puuid(slug):
    return f"demo-{slug}-" + "x" * 40


def _participant(rng, puuid, name, tag, pos, team, win, minutes, prof):
    champ = prof.get("champ") if prof and prof.get("champ") else rng.choice(CHAMPS[pos])
    prof = prof or DEFAULT_PROFILE
    dmg = int(DMG_PM[pos] * minutes * rng.uniform(0.65, 1.35) * prof["dmg"] * (1.08 if win else 0.93))
    gold = int(GOLD_PM[pos] * minutes * rng.uniform(0.88, 1.12) * (1.06 if win else 0.94))
    kills = max(0, int(rng.gauss(7 if pos in ("MIDDLE", "BOTTOM", "TOP") else 4, 3) * (1.2 if win else 0.8)))
    deaths = max(0, int(rng.gauss(4.0 if win else 6.5, 2.2) + prof["deaths"]))
    assists = max(0, int(rng.gauss(9 if win else 6, 3.5) + (5 if pos == "UTILITY" else 0)))
    pings = int(rng.uniform(2, 22) * prof.get("pings", 1))
    return {
        "puuid": puuid, "riotIdGameName": name, "riotIdTagline": tag, "championName": champ,
        "teamPosition": pos, "individualPosition": pos, "teamId": team, "win": win,
        "kills": kills, "deaths": deaths, "assists": assists,
        "totalDamageDealtToChampions": dmg, "totalDamageTaken": int(dmg * rng.uniform(0.8, 1.6)),
        "damageDealtToObjectives": int(dmg * rng.uniform(0.2, 0.9)), "goldEarned": gold,
        "totalMinionsKilled": int(CS_PM[pos] * minutes * rng.uniform(0.75, 1.15)),
        "neutralMinionsKilled": int(minutes * (4.5 if pos == "JUNGLE" else 0.2)),
        "visionScore": int(minutes * (2.2 if pos == "UTILITY" else rng.uniform(0.35, 1.1))),
        "wardsPlaced": rng.randint(2, 30 if pos == "UTILITY" else 12),
        "totalTimeSpentDead": deaths * rng.randint(18, 48),
        "firstBloodKill": rng.random() < 0.06,
        "doubleKills": rng.randint(0, 2), "tripleKills": int(rng.random() < 0.12),
        "quadraKills": int(rng.random() < 0.03), "pentaKills": int(rng.random() < 0.006),
        "allInPings": pings // 3, "enemyMissingPings": pings // 3, "onMyWayPings": pings - 2 * (pings // 3),
        "challenges": {"soloKills": rng.randint(0, 3)},
        "gameEndedInSurrender": False, "gameEndedInEarlySurrender": False,
    }


def generate_matches(friends, days=7, seed=7, now=None, tz=None):
    """Returns {match_id: raw_match} for `days` days ending at `now`."""
    rng = random.Random(seed)
    now = now or datetime.now(tz)
    matches = {}
    gid = 7_100_000_000
    for day in range(days, 0, -1):
        base = (now - timedelta(days=day)).replace(hour=15, minute=0, second=0, microsecond=0)
        # who plays how many games today
        plan = []
        for f in friends:
            prof = PROFILES.get(f["slug"], DEFAULT_PROFILE)
            plan += [f] * rng.randint(*prof["games"])
        rng.shuffle(plan)
        t = base
        while plan:
            gid += 1
            minutes = rng.uniform(19, 38)
            start = t + timedelta(minutes=rng.uniform(5, 50))
            t = start + timedelta(minutes=minutes)
            main = plan.pop()
            group = [main]
            for other in list(plan):
                if len(group) < 3 and other["slug"] not in {g["slug"] for g in group} and rng.random() < 0.28:
                    group.append(other)
                    plan.remove(other)
            rival = None
            for other in list(plan):
                if other["slug"] not in {g["slug"] for g in group} and rng.random() < 0.06:
                    rival = other
                    plan.remove(other)
                    break
            win_prob = sum(PROFILES.get(g["slug"], DEFAULT_PROFILE)["win"] for g in group) / len(group)
            blue_win = rng.random() < win_prob
            parts = []
            for team, won in ((100, blue_win), (200, not blue_win)):
                members = group if team == 100 else ([rival] if rival else [])
                free = POSITIONS[:]
                assigned = {}
                for m in members:
                    prof = PROFILES.get(m["slug"], DEFAULT_PROFILE)
                    pos = next((p for p in prof["roles"] if p in free), free[0])
                    free.remove(pos)
                    assigned[pos] = m
                for pos in POSITIONS:
                    m = assigned.get(pos)
                    if m:
                        name, tag = m["riot_id"].rsplit("#", 1)
                        parts.append(_participant(rng, demo_puuid(m["slug"]), name, tag, pos, team, won,
                                                  minutes, PROFILES.get(m["slug"], DEFAULT_PROFILE)))
                    else:
                        parts.append(_participant(rng, f"rnd-{gid}-{team}-{pos}", f"Rival{rng.randint(10, 9999)}",
                                                  "EUW", pos, team, won, minutes, None))
            if not blue_win and rng.random() < 0.25:
                for p in parts:
                    p["gameEndedInSurrender"] = True
            start_ms = int(start.timestamp() * 1000)
            match_id = f"EUW1_{gid}"
            matches[match_id] = {
                "metadata": {"matchId": match_id},
                "info": {
                    "gameId": gid, "platformId": "EUW1", "queueId": rng.choice([420, 420, 420, 440, 400, 450]),
                    "gameMode": "CLASSIC", "gameCreation": start_ms - 60_000, "gameStartTimestamp": start_ms,
                    "gameEndTimestamp": start_ms + int(minutes * 60_000), "gameDuration": int(minutes * 60),
                    "participants": parts,
                },
            }
    return matches


class DemoRiot:
    """Stand-in for RiotClient that serves generated matches."""

    def __init__(self, friends, matches):
        self.accounts = {f["riot_id"].lower(): demo_puuid(f["slug"]) for f in friends}
        self.raw = matches
        self.requests_made = 0

    def account_by_riot_id(self, name, tag):
        self.requests_made += 1
        puuid = self.accounts.get(f"{name}#{tag}".lower())
        return {"puuid": puuid, "gameName": name, "tagLine": tag} if puuid else None

    def match_ids(self, puuid, start_time_s=None, count=20):
        self.requests_made += 1
        ids = [mid for mid, m in self.raw.items()
               if any(p["puuid"] == puuid for p in m["info"]["participants"])
               and (not start_time_s or m["info"]["gameEndTimestamp"] // 1000 >= start_time_s)]
        ids.sort(key=lambda i: -self.raw[i]["info"]["gameEndTimestamp"])
        return ids[:count]

    def match(self, match_id):
        self.requests_made += 1
        return self.raw.get(match_id)
