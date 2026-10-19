"""Command line.

  python -m roast run      fetch new matches, write today's edition, rebuild docs/, notify Discord
  python -m roast build    rebuild docs/ from the stored editions
  python -m roast check    check the Riot key and find every friend
  python -m roast demo     full pipeline with fake data -> demo_site/ (no key needed)
"""
import argparse
import os
import shutil
import sys
import time
from datetime import datetime, timedelta

from .fetch import fetch_new_matches, resolve_players
from .llm import polish
from .notify import post_discord
from .pipeline import make_edition
from .riot import RiotClient, RiotError
from .site import build_site
from .store import Store
from .util import ROOT, get_tz, load_config, load_friends

HOUR_MS = 3600 * 1000


def _client(cfg):
    key = os.environ.get("RIOT_API_KEY", "").strip()
    if not key:
        sys.exit("Falta la variable RIOT_API_KEY (ver README, paso 1).")
    return RiotClient(key, region=cfg["region"], platform=cfg["platform"])


def cmd_run(args):
    cfg, friends = load_config(), load_friends()
    store = Store(ROOT / "data")
    tz = get_tz(cfg["timezone"])
    now_ms = int(time.time() * 1000)
    date_str = datetime.now(tz).date().isoformat()

    existing = store.edition(date_str)
    if existing:
        start_ms, number = existing["window"][0], existing["number"]
    else:
        start_ms = store.state.get("last_edition_end") or now_ms - cfg["window_hours"] * HOUR_MS
        number = len(store.editions()) + 1
    start_ms = max(start_ms, now_ms - cfg["max_backfill_hours"] * HOUR_MS)

    print(f"Edición nº {number} del {date_str}")
    client = _client(cfg)
    try:
        print("Buscando jugadores...")
        players = resolve_players(client, store, friends)
        print("Descargando partidas...")
        added = fetch_new_matches(client, store, players, since_ms=start_ms - 2 * HOUR_MS,
                                  max_per_player=cfg["max_matches_per_player"])
    except RiotError as e:
        sys.exit(f"Error con la API de Riot: {e}")
    print(f"  {added} partidas nuevas guardadas ({client.requests_made} peticiones a Riot)")

    edition = make_edition(cfg, store, players, start_ms, now_ms, date_str, number)
    print(f"  {edition['totals']['games']} partidas del grupo en la ventana, {len(edition['items'])} noticias")
    if not args.no_llm:
        try:
            polish(edition, cfg["llm_model"])
        except Exception as e:  # the edition must come out even if the optional rewrite breaks
            print(f"  ! Fallo inesperado con Claude ({e!r}); se usan las plantillas")
    store.save_edition(edition)
    store.state["last_edition_end"] = now_ms
    store.save_state()
    build_site(cfg, friends, store.editions(), ROOT / "docs")
    print("Web regenerada en docs/")
    if not args.no_notify:
        try:
            post_discord(edition, cfg)
        except Exception as e:
            print(f"  ! Fallo inesperado con Discord ({e!r})")


def cmd_build(args):
    cfg, friends = load_config(), load_friends()
    store = Store(ROOT / "data")
    build_site(cfg, friends, store.editions(), ROOT / "docs")
    print("Web regenerada en docs/")


def cmd_check(args):
    cfg, friends = load_config(), load_friends()
    store = Store(ROOT / "data")
    client = _client(cfg)
    try:
        players = resolve_players(client, store, friends)
        for p in players:
            ids = client.match_ids(p["puuid"], count=1)
            print(f"  OK  {p['riot_id']:<28} última partida: {ids[0] if ids else '(ninguna)'}")
    except RiotError as e:
        sys.exit(f"Error con la API de Riot: {e}")
    missing = len(friends) - len(players)
    print(f"{len(players)} jugadores encontrados" + (f", {missing} sin encontrar" if missing else ""))


def cmd_demo(args):
    from .demo import DemoRiot, generate_matches

    cfg, friends = load_config(), load_friends()
    tz = get_tz(cfg["timezone"])
    data_dir, out_dir = ROOT / "demo_data", ROOT / args.out
    if data_dir.exists():
        shutil.rmtree(data_dir)
    store = Store(data_dir)
    now = datetime.now(tz).replace(hour=8, minute=0, second=0, microsecond=0)
    raw = generate_matches(friends, days=args.days, seed=args.seed, now=now, tz=tz)
    client = DemoRiot(friends, raw)
    players = resolve_players(client, store, friends, log=lambda *_: None)
    fetch_new_matches(client, store, players, since_ms=int((now - timedelta(days=args.days + 1)).timestamp() * 1000),
                      max_per_player=100, log=lambda *_: None)
    for i in range(args.days, 0, -1):
        end = now - timedelta(days=i - 1)
        start = end - timedelta(days=1)
        ed = make_edition(cfg, store, players, int(start.timestamp() * 1000), int(end.timestamp() * 1000),
                          end.date().isoformat(), args.days - i + 1)
        store.save_edition(ed)
    build_site(cfg, friends, store.editions(), out_dir)
    print(f"Demo con {len(raw)} partidas falsas y {args.days} ediciones en {out_dir}")
    print(f"Ábrela con: {out_dir / 'index.html'}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m roast", description="El Feed Diario")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="edición de hoy")
    r.add_argument("--no-llm", action="store_true", help="no usar Claude aunque haya clave")
    r.add_argument("--no-notify", action="store_true", help="no avisar por Discord")
    r.set_defaults(fn=cmd_run)
    sub.add_parser("build", help="regenerar la web").set_defaults(fn=cmd_build)
    sub.add_parser("check", help="comprobar clave y jugadores").set_defaults(fn=cmd_check)
    d = sub.add_parser("demo", help="demo con datos falsos")
    d.add_argument("--days", type=int, default=7)
    d.add_argument("--seed", type=int, default=7)
    d.add_argument("--out", default="demo_site")
    d.set_defaults(fn=cmd_demo)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
