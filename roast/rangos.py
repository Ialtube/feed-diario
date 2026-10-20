"""Ranked positions and the 'LP stock market': who climbed, who fell, who went bust."""
TIERS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]
TIER_ES = {"IRON": "Hierro", "BRONZE": "Bronce", "SILVER": "Plata", "GOLD": "Oro", "PLATINUM": "Platino",
           "EMERALD": "Esmeralda", "DIAMOND": "Diamante", "MASTER": "Maestro", "GRANDMASTER": "Gran Maestro",
           "CHALLENGER": "Aspirante"}
DIVS = {"IV": 0, "III": 1, "II": 2, "I": 3}
COLAS = {"solo": "SoloQ", "flex": "Flex"}


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


def market(ranks, date, roster):
    """Today's positions with the change since the previous day that has data."""
    today = ranks.get(date) or {}
    prev_dates = sorted(d for d in ranks if d < date)
    before = ranks.get(prev_dates[-1]) if prev_dates else {}
    alias = {r["slug"]: r["alias"] for r in roster}
    rows = []
    for slug, queues in today.items():
        row = {"slug": slug, "alias": alias.get(slug, slug)}
        for q in COLAS:
            cur, old = queues.get(q), (before.get(slug) or {}).get(q)
            if not cur:
                continue
            v, w = value(cur), value(old)
            change = None
            if old and (cur.get("tier"), cur.get("rank")) != (old.get("tier"), old.get("rank")) and v is not None and w is not None:
                change = "ascenso" if v > w else "descenso"
            row[q] = {"posicion": label(cur), "lp": cur.get("lp", 0), "delta": (v - w) if v is not None and w is not None else None,
                      "cambio": change, "antes": label(old) if old else None,
                      "victorias": cur.get("wins", 0), "derrotas": cur.get("losses", 0)}
        if len(row) > 2:
            rows.append(row)
    rows.sort(key=lambda r: min((r[q]["delta"] or 0) for q in COLAS if q in r))
    return {"fecha": date, "desde": prev_dates[-1] if prev_dates else None, "filas": rows}
