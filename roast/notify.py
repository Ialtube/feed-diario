"""Discord: the morning notice when the edition written by Claude is out, and the evening preview
of the night's markets ("Esta noche en la Grieta"), both through a channel webhook."""
import json
import os
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime

from .canon import is_redaccion, load as load_canon, open_threads
from .util import get_tz


def _splash(champ):
    from .site import _ddragon_id
    return f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{_ddragon_id(champ)}_0.jpg"


def discord_payload(edition, cfg, site_url=""):
    """The morning notice: the front page with its picture, who is in today's paper, the question of
    the popular jury and what the paper will be watching."""
    items = edition["items"]
    lead = items[0] if items else None
    url = site_url.rstrip("/") + "/" if site_url else None
    footer = {"text": f"{cfg['site_title']} · Edición nº {edition['number']} · {edition['date']}"}
    content = f"📰 Ya está en la calle la edición de hoy{(': ' + url) if url else ''}"
    if not edition.get("ai"):
        # an edition without Claude's pass: just the headlines
        others = "\n".join(f"• **{it['section'].capitalize()}**: {it['headline']}" for it in items[1:6])
        embed = {"title": lead["headline"] if lead else cfg["site_title"],
                 "description": ((lead["body"] + "\n\n") if lead else "") + others, "color": 0xB3261E, "footer": footer}
        if url:
            embed["url"] = url
        return {"username": cfg["site_title"], "content": content, "embeds": [embed]}

    who = Counter(it["alias"] for it in items if it.get("alias"))
    lines = []
    if lead and lead.get("subtitulo"):
        lines.append(f"*{lead['subtitulo']}*")
    others = [it for it in items[1:] if it.get("peso") in ("grande", "mediana")][:4]
    if others:
        lines.append("\n".join(f"• **{it['section'].capitalize()}**: {it['headline']}" for it in others))
    if who:
        lines.append("**Hoy salen:** " + ", ".join(f"{a} ({n})" if n > 1 else a for a, n in who.most_common()))
    if edition.get("gaceta"):
        lines.append(f"**La Gaceta de Noxus replica:** {edition['gaceta']['titular']}")
    if edition.get("jurado"):
        j = edition["jurado"]
        lines.append(f"⚖️ **El jurado popular:** {j['pregunta']} ({' / '.join(j['opciones'])})")
    if edition.get("manana"):
        lines.append("🔭 **Mañana en El Rincón:** " + " · ".join(m["texto"] for m in edition["manana"]))
    embed = {"title": lead["headline"] if lead else cfg["site_title"], "description": "\n\n".join(lines)[:4000],
             "color": 0xB3261E, "footer": footer}
    if lead and lead.get("saga"):
        embed["author"] = {"name": f"{lead['saga']['titulo']} · capítulo {lead['saga']['capitulo']}"}
    if lead and lead.get("campeon"):
        embed["image"] = {"url": _splash(lead["campeon"])}
    if url:
        embed["url"] = url
    return {"username": cfg["site_title"], "content": content, "embeds": [embed]}


def previa_payload(edition, cfg, site_url=""):
    """The evening preview: the night's markets with their odds and closing time, the sagas to
    follow and what the paper promised to watch."""
    url = site_url.rstrip("/") + "/" if site_url else None
    lines = []
    mk = edition.get("mercados") or {}
    for m in mk.get("lista", []):
        best = sorted(m["opciones"], key=lambda o: o["cuota"])[:4]
        lines.append(f"**{m['pregunta']}**\n" + " · ".join(f"{o['texto']} ×{o['cuota']}" for o in best))
    if mk.get("cierre"):
        hour = datetime.fromisoformat(mk["cierre"].replace("Z", "+00:00")).astimezone(get_tz(cfg["timezone"]))
        lines.append(f"Las apuestas cierran a las **{hour:%H:%M}**.")
    sagas = [h for h in open_threads(load_canon()) if not is_redaccion(h)][-3:]
    if sagas:
        lines.append("**Sagas en juego esta noche:** " + " · ".join(h["titulo"] for h in sagas))
    if edition.get("manana"):
        lines.append("**La redacción vigila:** " + " · ".join(m["texto"] for m in edition["manana"]))
    embed = {"title": "Esta noche en la Grieta", "description": "\n\n".join(lines)[:4000] or "Nada que vigilar. Sospechoso.",
             "color": 0x7D5A0E, "footer": {"text": f"{cfg['site_title']} · La Lonja de Coronas"}}
    if url:
        embed["url"] = url + "#lonja"
    return {"username": cfg["site_title"], "content": "🎲 Abre la Lonja de Coronas: ¿quién la lía esta noche?",
            "embeds": [embed]}


def _post(payload, log=print):
    hook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not hook:
        log("  (sin DISCORD_WEBHOOK_URL: no se avisa a Discord)")
        return False
    data = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(hook, data=data, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "el-feed-diario/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20):
            pass
        return True
    except urllib.error.URLError as e:
        log(f"  ! No se pudo enviar a Discord: {e}")
        return False


def _site_url(cfg):
    return os.environ.get("SITE_URL", "") or cfg.get("site_url", "")


def post_discord(edition, cfg, log=print):
    ok = _post(discord_payload(edition, cfg, _site_url(cfg)), log)
    if ok:
        log("  Portada enviada a Discord")
    return ok


def post_previa(edition, cfg, log=print):
    ok = _post(previa_payload(edition, cfg, _site_url(cfg)), log)
    if ok:
        log("  Previa enviada a Discord")
    return ok
