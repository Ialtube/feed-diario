"""What the readers did on the website, read back from Supabase for the next edition:
reactions and comments on yesterday's stories, who snooped on whose profile, and the
right-of-reply requests of those who were roasted."""
import json
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone

from .util import ROOT, load_json, save_json

REPLICAS_FILE = ROOT / "data" / "replicas.json"


def _get(cfg, table, params, timeout=20):
    url, key = cfg.get("supabase_url"), cfg.get("supabase_anon_key")
    if not url or not key:
        return None
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url.rstrip('/')}/rest/v1/{table}?{q}",
                                 headers={"apikey": key, "Authorization": f"Bearer {key}",
                                          "User-Agent": "el-rincon-del-feeder/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError):
        return None


def _iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def feedback(cfg, previous, reactions=None, comments=None):
    """Yesterday's paper as the readers saw it: the most reacted stories and what they said."""
    if not previous:
        return None
    if reactions is None:
        reactions = _get(cfg, "reacciones", [("select", "pieza,emoji,nombre"), ("edicion", f"eq.{previous['date']}")])
    if comments is None:
        comments = _get(cfg, "comentarios", [("select", "pieza,nombre,texto,created_at"),
                                             ("edicion", f"eq.{previous['date']}"), ("order", "created_at.asc")])
    if reactions is None and comments is None:
        return None
    heads = {it["id"]: it["headline"] for it in previous.get("items", [])}
    per = defaultdict(Counter)
    who = defaultdict(set)
    for r in reactions or []:
        per[r["pieza"]][r["emoji"]] += 1
        if r.get("nombre"):
            who[r["pieza"]].add(r["nombre"])
    top = sorted(per.items(), key=lambda kv: -sum(kv[1].values()))[:5]
    return {
        "edicion": previous["date"],
        "mas_reaccionadas": [{"pieza": pid, "titular": heads.get(pid, "?"), "total": sum(c.values()),
                              "emojis": dict(c.most_common()), "quien": sorted(who[pid])}
                             for pid, c in top if pid in heads],
        "comentarios": [{"pieza": c.get("pieza"), "titular": heads.get(c.get("pieza")) if c.get("pieza") else None,
                         "nombre": c["nombre"], "texto": c["texto"]} for c in comments or []][-30:],
    }


def snoops(cfg, since_ms, until_ms, roster, visits=None):
    """Who looked at whose profile between two editions (only readers who said who they are)."""
    if visits is None:
        visits = _get(cfg, "visitas", [("select", "pagina,nombre,created_at"), ("pagina", "like.jugador:*"),
                                       ("created_at", f"gt.{_iso(since_ms)}"), ("created_at", f"lte.{_iso(until_ms)}")])
    if visits is None:
        return None
    alias = {r["slug"]: r["alias"] for r in roster}
    pairs = Counter()
    for v in visits:
        if not v.get("nombre"):
            continue
        slug = v["pagina"].split(":", 1)[1]
        pairs[(v["nombre"], alias.get(slug, slug))] += 1
    out = [{"cotilla": a, "ficha": b, "veces": n, "se_mira_a_si_mismo": a == b} for (a, b), n in pairs.most_common(10)]
    return out


# ---------------------------------------------------------------- right of reply
def _state():
    return load_json(REPLICAS_FILE, None) or {"usadas": [], "descartadas": [], "pendientes": {}}


def fetch_replies(cfg, editions):
    """Replies not published yet, with the headline they answer."""
    rows = _get(cfg, "replicas", [("select", "id,edicion,pieza,nombre,texto,created_at"), ("order", "id.asc"),
                                  ("limit", "100")])
    st = _state()
    if rows is None:
        return [dict(v) for v in st["pendientes"].values()]
    done = set(st["usadas"]) | set(st["descartadas"])
    heads = {(e["date"], it["id"]): it["headline"] for e in editions for it in e.get("items", [])}
    pending = []
    for r in rows:
        if r["id"] in done:
            continue
        r["titular"] = heads.get((r["edicion"], r["pieza"]))
        pending.append(r)
    st["pendientes"] = {str(r["id"]): r for r in pending}
    save_json(REPLICAS_FILE, st)
    return pending


def replies_cache():
    st = _state()
    known = {int(k): v for k, v in st.get("publicadas", {}).items()}
    known.update({int(k): v for k, v in st["pendientes"].items()})
    return known


def pending_replies():
    return {int(k): v for k, v in _state()["pendientes"].items()}


def mark_replies(used, discarded):
    st = _state()
    st["usadas"] = sorted(set(st["usadas"]) | set(used))
    st["descartadas"] = sorted(set(st["descartadas"]) | set(discarded))
    pub = st.setdefault("publicadas", {})
    for i in used:
        p = st["pendientes"].get(str(i)) or pub.get(str(i))
        if p:
            pub[str(i)] = {k: p.get(k) for k in ("id", "nombre", "edicion", "pieza", "titular")}
    for i in list(used) + list(discarded):
        st["pendientes"].pop(str(i), None)
    save_json(REPLICAS_FILE, st)
