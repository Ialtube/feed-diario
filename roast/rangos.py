"""Ranked positions and the 'LP stock market': who climbed, who fell, who went bust.

data/rangos.json keeps, for each day, the position of every *account* (keyed by Riot ID): a smurf is
never mixed with its owner's main account, and each account is only compared with itself."""
TIERS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]
TIER_ES = {"IRON": "Hierro", "BRONZE": "Bronce", "SILVER": "Plata", "GOLD": "Oro", "PLATINUM": "Platino",
           "EMERALD": "Esmeralda", "DIAMOND": "Diamante", "MASTER": "Maestro", "GRANDMASTER": "Gran Maestro",
           "CHALLENGER": "Aspirante"}
DIVS = {"IV": 0, "III": 1, "II": 2, "I": 3}
COLAS = {"solo": "SoloQ", "flex": "Flex"}
MAX_LP_PER_GAME = 60    # a change bigger than this per game played is not believable (wrong data, not a story)


def value(e):
    """A single number for a ranked position (higher is better): 400 per tier, 100 per division."""
    if not e or e.get("tier") not in TIERS:
        return None
    i = TIERS.index(e["tier"])
    if i >= TIERS.index("MASTER"):
        return TIERS.index("MASTER") * 400 + e.get("lp", 0)
    return i * 400 + DIVS.get(e.get("rank"), 0) * 100 + e.get("lp", 0)


def label(e):
    if not e or e.get("tier") not in TIERS:
        return "Sin clasificar"
    apex = TIERS.index(e["tier"]) >= TIERS.index("MASTER")
    return f"{TIER_ES[e['tier']]}{'' if apex else ' ' + str(e.get('rank'))} · {e.get('lp', 0)} LP"


def accounts(day):
    """The accounts stored for a day (old files keyed by person, which mixed smurfs, are ignored)."""
    return {k: v for k, v in (day or {}).items() if isinstance(v, dict) and v.get("riot_id")}


def snapshot(players, entries_of):
    """One day's positions: {riot_id (lowercase): {riot_id, slug, alias, principal, solo, flex}}.
    The main account is the first one listed for that person in friends.json."""
    seen, out = set(), {}
    for p in players:
        out[p["riot_id"].lower()] = {"riot_id": p["riot_id"], "slug": p["slug"], "alias": p["alias"],
                                     "principal": p["slug"] not in seen, **entries_of(p)}
        seen.add(p["slug"])
    return out


def market(ranks, date, roster):
    """Today's position of every account, with the change since the last day that same account was seen."""
    today = accounts(ranks.get(date))
    past = sorted((d for d in ranks if d < date), reverse=True)
    order = {r["riot_id"].lower(): i for i, r in enumerate(roster) if r.get("riot_id")}
    alias = {r["slug"]: r["alias"] for r in roster}
    rows = []
    for rid, acc in today.items():
        prev_date = next((d for d in past if rid in accounts(ranks[d])), None)
        before = accounts(ranks[prev_date])[rid] if prev_date else {}
        row = {"slug": acc["slug"], "alias": alias.get(acc["slug"], acc["alias"]), "cuenta": acc["riot_id"],
               "principal": acc.get("principal", True), "desde": prev_date}
        for q in COLAS:
            cur, old = acc.get(q), before.get(q)
            if not cur:
                continue
            v, w = value(cur), value(old)
            delta = (v - w) if v is not None and w is not None else None
            games = ((cur.get("wins", 0) + cur.get("losses", 0)) - (old.get("wins", 0) + old.get("losses", 0))) if old else None
            fiable = delta is not None and games is not None and games >= 0 and abs(delta) <= MAX_LP_PER_GAME * max(games, 1)
            change = None
            if fiable and (cur.get("tier"), cur.get("rank")) != (old.get("tier"), old.get("rank")):
                change = "ascenso" if v > w else "descenso"
            row[q] = {"posicion": label(cur), "lp": cur.get("lp", 0), "delta": delta if fiable else None,
                      "cambio": change, "antes": label(old) if old else None, "partidas": games,
                      "victorias": cur.get("wins", 0), "derrotas": cur.get("losses", 0),
                      **({} if fiable or delta is None else {"dudoso": True})}
        if any(q in row for q in COLAS):
            rows.append(row)
    # people in roster order, each with the main account first and the smurfs below
    first = {}
    for r in rows:
        first[r["slug"]] = min(first.get(r["slug"], 1e9), order.get(r["cuenta"].lower(), 1e9))
    rows.sort(key=lambda r: (first[r["slug"]], not r["principal"], order.get(r["cuenta"].lower(), 1e9)))
    since = max((r["desde"] for r in rows if r["desde"]), default=None)
    return {"fecha": date, "desde": since, "filas": rows}
