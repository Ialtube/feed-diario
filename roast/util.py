"""Small shared helpers: JSON files, Spanish number/date formatting, slugs, time zones."""
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data, indent=2):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    tmp.replace(path)


def load_config(root=ROOT):
    cfg = load_json(Path(root) / "config.json", {}) or {}
    cfg.setdefault("site_title", "El Rincón del Feeder")
    cfg.setdefault("site_tagline", "")
    cfg.setdefault("region", "europe")
    cfg.setdefault("platform", "euw1")
    cfg.setdefault("timezone", "Europe/Madrid")
    cfg.setdefault("window_hours", 24)
    cfg.setdefault("cutoff_hour", 7)   # each edition covers the games that ended before this hour
    cfg.setdefault("max_backfill_hours", 72)
    cfg.setdefault("max_matches_per_player", 20)
    cfg.setdefault("ignored_queues", [0, 1700])
    cfg.setdefault("llm_model", "claude-opus-5-5")
    cfg.setdefault("items_per_player", 2)
    cfg.setdefault("supabase_url", "")
    cfg.setdefault("supabase_anon_key", "")
    return cfg


def load_friends(root=ROOT):
    """Accounts to follow. Several accounts with the same alias are one person (smurfs)."""
    friends, seen = [], set()
    for f in load_json(Path(root) / "friends.json", []) or []:
        if f.get("enabled", True) is False:
            continue
        riot_id = f["riot_id"].strip()
        if "#" not in riot_id:
            raise ValueError(f"Riot ID sin '#': {riot_id!r} (formato: Nombre#TAG)")
        if riot_id.lower() in seen:   # the same account listed twice
            continue
        seen.add(riot_id.lower())
        alias = f.get("alias") or riot_id.split("#")[0]
        friends.append({"riot_id": riot_id, "alias": alias, "slug": slugify(alias)})
    return friends


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "jugador"


def get_tz(name):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:  # Windows without tzdata: assume CET
        return timezone(timedelta(hours=1))


def ms_to_local(ms, tz):
    return datetime.fromtimestamp(ms / 1000, tz)


CHAMP_NAMES = {
    "MonkeyKing": "Wukong", "Chogath": "Cho'Gath", "Kaisa": "Kai'Sa", "Khazix": "Kha'Zix",
    "KogMaw": "Kog'Maw", "RekSai": "Rek'Sai", "Velkoz": "Vel'Koz", "Belveth": "Bel'Veth",
    "KSante": "K'Sante", "Leblanc": "LeBlanc", "JarvanIV": "Jarvan IV", "LeeSin": "Lee Sin",
    "MasterYi": "Master Yi", "MissFortune": "Miss Fortune", "TahmKench": "Tahm Kench",
    "TwistedFate": "Twisted Fate", "XinZhao": "Xin Zhao", "AurelionSol": "Aurelion Sol",
    "DrMundo": "Dr. Mundo", "Nunu": "Nunu y Willump", "Renata": "Renata Glasc",
}


def champ_name(champ_id):
    """Riot's internal champion id ('JarvanIV') -> display name ('Jarvan IV')."""
    return CHAMP_NAMES.get(champ_id, champ_id)


def fmt_int(n):
    return f"{int(round(n)):,}".replace(",", ".")


def fmt_num(x, dec=1):
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(x, dec=1):
    """x is a fraction (0.183 -> '18,3 %')."""
    return fmt_num(x * 100, dec) + " %"


def fmt_minutes(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"


def long_date(d):
    """date -> 'lunes, 19 de octubre de 2026'"""
    return f"{DAYS[d.weekday()]}, {d.day} de {MONTHS[d.month - 1]} de {d.year}"


def short_date(d):
    return f"{d.day} {MONTHS[d.month - 1][:3]} {d.year}"
