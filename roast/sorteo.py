"""El Sorteo de la Grieta: readers pick three numbers (0-99) on the web; each edition draws
the day's combination from the games and checks the tickets sold since the previous edition.

The combination is the deaths of the three friends who died the most that day (fewer than three
players: their deaths plus the group's games and grey-screen minutes). Order does not matter.
"""
import json
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone

PRIZE_STEP = 100  # LP added to the jackpot for every draw without a full winner (it's a joke prize)


def combination(edition):
    """Three numbers 0-99 and where each one comes from."""
    ranking = sorted(edition.get("ranking") or [], key=lambda r: (-r["d"], r["alias"]))
    nums = [(r["d"] % 100, f"muertes de {r['alias']}") for r in ranking[:3]]
    t = edition.get("totals") or {}
    extras = [(t.get("games", 0) % 100, "partidas del grupo"),
              (int(t.get("dead_seconds", 0) // 60) % 100, "minutos en gris del grupo"),
              (t.get("deaths", 0) % 100, "muertes del grupo")]
    for n in extras:
        if len(nums) >= 3:
            break
        nums.append(n)
    return [n for n, _ in nums], [why for _, why in nums]


def _iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_tickets(cfg, since_ms, until_ms, timeout=15):
    """Tickets bought in (since, until]. None if the table is missing or Supabase is unreachable."""
    url, key = cfg.get("supabase_url"), cfg.get("supabase_anon_key")
    if not url or not key:
        return None
    q = urllib.parse.urlencode([("select", "nombre,numeros,created_at"),
                                ("created_at", f"gt.{_iso(since_ms)}"), ("created_at", f"lte.{_iso(until_ms)}"),
                                ("order", "created_at.asc")])
    req = urllib.request.Request(f"{url}/rest/v1/boletos?{q}", headers={"apikey": key, "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def hits(numbers, combo):
    return sum((Counter(numbers) & Counter(combo)).values())


def draw(cfg, edition, previous=None, tickets=None):
    """The result stored in the edition. `tickets` can be passed in (tests); otherwise fetched."""
    combo, origin = combination(edition)
    since = (previous or {}).get("generated_at") or edition["window"][0]
    until = edition.get("generated_at") or edition["window"][1]
    if tickets is None:
        tickets = fetch_tickets(cfg, since, until)
    result = {"combinacion": combo, "origen": origin, "estado": "ok" if tickets is not None else "sin_boletos",
              "participantes": 0, "acertantes": [], "segundos": []}
    prev_bote = ((previous or {}).get("sorteo") or {}).get("bote", 0)
    for t in tickets or []:
        nums = [int(n) for n in (t.get("numeros") or [])][:3]
        name = str(t.get("nombre") or "Anónimo")[:40]
        h = hits(nums, combo)
        result["participantes"] += 1
        if h == 3:
            result["acertantes"].append({"nombre": name, "numeros": nums})
        elif h == 2:
            result["segundos"].append({"nombre": name, "numeros": nums})
    result["bote"] = 0 if result["acertantes"] else prev_bote + PRIZE_STEP
    return result
