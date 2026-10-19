"""Optional: post the daily front page to a Discord channel through a webhook."""
import json
import os
import urllib.error
import urllib.request


def discord_payload(edition, cfg, site_url=""):
    items = edition["items"]
    lead = items[0] if items else None
    others = "\n".join(f"• **{it['section'].capitalize()}**: {it['headline']}" for it in items[1:6])
    url = site_url.rstrip("/") + "/" if site_url else None
    embed = {
        "title": lead["headline"] if lead else cfg["site_title"],
        "description": ((lead["body"] + "\n\n") if lead else "") + others,
        "color": 0xB3261E,
        "footer": {"text": f"{cfg['site_title']} · Edición nº {edition['number']} · {edition['date']}"},
    }
    if url:
        embed["url"] = url
    return {"username": cfg["site_title"],
            "content": f"📰 Ya está en la calle la edición de hoy{(': ' + url) if url else ''}",
            "embeds": [embed]}


def post_discord(edition, cfg, log=print):
    hook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not hook:
        return False
    data = json.dumps(discord_payload(edition, cfg, os.environ.get("SITE_URL", "")), ensure_ascii=False).encode()
    req = urllib.request.Request(hook, data=data, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "el-feed-diario/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20):
            pass
        log("  Portada enviada a Discord")
        return True
    except urllib.error.URLError as e:
        log(f"  ! No se pudo enviar a Discord: {e}")
        return False
