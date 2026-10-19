"""Reader proposals ("La Voz de Runeterra") stored in Supabase.

The website lets anyone send a proposal (text + optional image) straight to Supabase.
Here we read the ones not published yet, download their images into docs/img/ so the
newspaper keeps them, and remember which ones were used or discarded.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .util import ROOT, load_json, save_json

STATE_FILE = ROOT / "data" / "propuestas.json"
IMG_DIR = ROOT / "docs" / "img"


def _headers(cfg):
    key = cfg["supabase_anon_key"]
    return {"apikey": key, "Authorization": f"Bearer {key}", "User-Agent": "el-rincon-del-feeder/1.0"}


def configured(cfg):
    return bool(cfg.get("supabase_url") and cfg.get("supabase_anon_key"))


def _state():
    return load_json(STATE_FILE, None) or {"usadas": [], "descartadas": [], "pendientes": {}}


def fetch_pending(cfg, log=print):
    """Returns the proposals not used/discarded yet, with images downloaded to docs/img/."""
    if not configured(cfg):
        return []
    url = cfg["supabase_url"].rstrip("/")
    query = urllib.parse.urlencode({"select": "id,nombre,titulo,texto,imagen,created_at",
                                    "order": "id.asc", "limit": "200"})
    req = urllib.request.Request(f"{url}/rest/v1/propuestas?{query}", headers=_headers(cfg))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError) as e:
        log(f"  ! No se pudieron leer las propuestas de Supabase: {e}")
        return []

    st = _state()
    done = set(st["usadas"]) | set(st["descartadas"])
    pending = []
    for p in rows:
        if p["id"] in done:
            continue
        p["imagen_local"] = _download_image(cfg, p, log)
        pending.append(p)
    st["pendientes"] = {str(p["id"]): p for p in pending}
    save_json(STATE_FILE, st)
    return pending


def _download_image(cfg, p, log):
    path = (p.get("imagen") or "").strip()
    if not path:
        return None
    ext = Path(path).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        return None
    name = f"voz-{p['id']}{ext}"
    target = IMG_DIR / name
    if target.exists():
        return name
    src = path if path.startswith("http") else \
        f"{cfg['supabase_url'].rstrip('/')}/storage/v1/object/public/propuestas/{urllib.parse.quote(path)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "el-rincon-del-feeder/1.0"}),
                                    timeout=30) as resp:
            data = resp.read(6 * 1024 * 1024)
    except urllib.error.URLError as e:
        log(f"  ! No se pudo descargar la imagen de la propuesta {p['id']}: {e}")
        return None
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return name


def pending_cache():
    return {int(k): v for k, v in _state()["pendientes"].items()}


def mark(used, discarded):
    st = _state()
    st["usadas"] = sorted(set(st["usadas"]) | set(used))
    st["descartadas"] = sorted(set(st["descartadas"]) | set(discarded))
    for i in list(used) + list(discarded):
        st["pendientes"].pop(str(i), None)
    save_json(STATE_FILE, st)


def safe_name(text):
    return re.sub(r"\s+", " ", text or "").strip()[:40]
