"""Command line.

  python -m roast run      fetch new matches, write today's edition, rebuild docs/, notify Discord
  python -m roast build    rebuild docs/ from the stored editions
  python -m roast check    check the Riot key and find every friend
  python -m roast demo     full pipeline with fake data -> demo_site/ (no key needed)
  python -m roast avisar   tell Discord that today's edition by Claude is out (once)
  python -m roast previa   the evening preview of the night's markets on Discord
  python -m roast informe  the editor's weekly report in informes/
"""
import json
import argparse
from collections import Counter
import os
import shutil
import sys
import time
from datetime import datetime, timedelta

from .ai import AIError, ai_status, apply_file, mark_stale_on_regenerate, prepare_games, read_events, write_context
from . import coronas
from . import informe
from .fetch import fetch_new_matches, fetch_ranks, fetch_timelines, resolve_players
from . import porra as porra_mod
from .rangos import market
from .llm import polish
from .notify import discord_payload, post_discord, post_previa, previa_payload
from .pipeline import make_edition
from .riot import RiotClient, RiotError
from . import correcciones
from .site import build_site
from .sorteo import draw
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
    date_str, day_start, end_ms = edition_window(cfg, datetime.now(tz))

    # The edition of day D holds the games that ended between the cut-off hour of D-1 and that of D,
    # whenever the robot runs: an evening session always lands, whole, in the next morning's paper.
    existing = store.edition(date_str)
    previous = next((e for e in sorted(store.editions(), key=lambda e: e["date"], reverse=True)
                     if e["date"] < date_str), None)
    start_ms = previous["window"][1] if previous else day_start   # no gaps and no overlaps
    start_ms = max(start_ms, now_ms - cfg["max_backfill_hours"] * HOUR_MS)
    number = existing["number"] if existing else len(store.editions()) + 1

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
    # extras: what happened inside the games, and the ranked positions (never stop the paper for them)
    try:
        fetch_timelines(client, store, players, start_ms, end_ms)
        fetch_ranks(client, store, players, date_str)
    except RiotError as e:
        print(f"  ! No se pudieron descargar líneas temporales o rangos: {e}")

    edition = make_edition(cfg, store, players, start_ms, end_ms, date_str, number)
    edition["bolsa"] = market(store.ranks(), date_str, players)
    print(f"  {edition['totals']['games']} partidas del grupo en la ventana, {len(edition['items'])} noticias")
    same_games = existing and {g["match"] for g in existing.get("games", [])} == {g["match"] for g in edition["games"]}
    if existing and existing.get("ai") and same_games and existing["window"] == edition["window"]:
        print("  La edición ya estaba hecha con estas mismas partidas: no se toca")
        return
    if existing and existing.get("ai"):
        edition = mark_stale_on_regenerate(existing, edition)
        print("  La edición ya tenía versión IA: se conservan columna/especial y queda marcada para reescribir")
    for k in ("quien_fue", "mercados"):        # the day's games never move once published
        if existing and k in existing:
            edition[k] = existing[k]
    prepare_games(edition, store.editions() + ([] if existing else [edition]), cfg)
    coronas.sync(cfg)
    if existing and existing.get("sorteo"):
        # the draw already happened: re-running the robot must not move it or re-check tickets
        edition["sorteo"], edition["generated_at"] = existing["sorteo"], existing["generated_at"]
        edition["porra"] = existing.get("porra")
    else:
        previous = next((e for e in sorted(store.editions(), key=lambda e: e["date"], reverse=True)
                         if e["date"] < date_str), None)
        edition["sorteo"] = draw(cfg, edition, previous)
        edition["porra"] = porra_mod.resolve(cfg, edition, previous)
        s = edition["sorteo"]
        print(f"  Sorteo: {'-'.join(map(str, s['combinacion']))}, {s['participantes']} boletos, "
              f"{len(s['acertantes'])} acertantes")
    if not args.no_llm:
        try:
            polish(edition, cfg["llm_model"])
        except Exception as e:  # the edition must come out even if the optional rewrite breaks
            print(f"  ! Fallo inesperado con Claude ({e!r}); se usan las plantillas")
    store.save_edition(edition)
    store.state["last_edition_end"] = end_ms
    store.save_state()
    build_site(cfg, friends, store.editions(), ROOT / "docs")
    print("Web regenerada en docs/")
    # Discord hears about the paper when Claude's edition is out (python -m roast avisar), never
    # about the robot's numbers: a notice with the edition still at the printer's is a wasted click.
    if not args.no_notify and edition.get("ai") and not edition["ai"].get("stale"):
        cmd_avisar(args)


def cmd_backfill(args):
    """Creates the editions of the N days before the first stored one (template text)."""
    cfg, friends = load_config(), load_friends()
    store = Store(ROOT / "data")
    tz = get_tz(cfg["timezone"])
    editions = sorted(store.editions(), key=lambda e: e["date"])
    anchor = editions[0]["window"][0] if editions else int(time.time() * 1000)
    since = anchor - args.days * 24 * HOUR_MS
    client = _client(cfg)
    try:
        players = resolve_players(client, store, friends)
        print(f"Descargando partidas de los {args.days} días anteriores...")
        added = fetch_new_matches(client, store, players, since_ms=since - 2 * HOUR_MS, max_per_player=100)
    except RiotError as e:
        sys.exit(f"Error con la API de Riot: {e}")
    print(f"  {added} partidas nuevas guardadas ({client.requests_made} peticiones a Riot)")

    created = 0
    for k in range(args.days, 0, -1):
        start = anchor - k * 24 * HOUR_MS
        end = start + 24 * HOUR_MS
        date_str = datetime.fromtimestamp((end - 1) / 1000, tz).date().isoformat()
        if store.edition(date_str):
            continue
        ed = make_edition(cfg, store, players, start, end, date_str, 0)
        store.save_edition(ed)
        created += 1
        print(f"  {date_str}: {ed['totals']['games']} partidas, {len(ed['items'])} noticias")

    # number every edition in date order
    for n, ed in enumerate(sorted(store.editions(), key=lambda e: e["date"]), start=1):
        if ed["number"] != n:
            ed["number"] = n
            store.save_edition(ed)
    if store.state.get("last_edition_end") is None and editions:
        store.state["last_edition_end"] = editions[-1]["window"][1]
    store.save_state()
    build_site(cfg, friends, store.editions(), ROOT / "docs")
    print(f"{created} ediciones nuevas. Web regenerada en docs/")


def cmd_rangos(args):
    """Only the ranked positions: stores today's (per account) and refreshes the LP market of today's paper."""
    cfg, friends = load_config(), load_friends()
    store = Store(ROOT / "data")
    date_str = edition_window(cfg, datetime.now(get_tz(cfg["timezone"])))[0]
    try:
        players = resolve_players(_client(cfg), store, friends)
        fetch_ranks(_client(cfg), store, players, date_str)
    except RiotError as e:
        sys.exit(f"Error con la API de Riot: {e}")
    edition = store.edition(date_str)
    if edition:
        edition["bolsa"] = market(store.ranks(), date_str, players)
        store.save_edition(edition)
        build_site(cfg, friends, store.editions(), ROOT / "docs")
        print(f"Bolsa de LP de la edición del {date_str} actualizada")


def _latest(store):
    eds = sorted(store.editions(), key=lambda e: e["date"])
    return eds[-1] if eds else None


def cmd_avisar(args):
    """Posts today's edition to Discord once, as soon as Claude has written it."""
    cfg = load_config()
    store = Store(ROOT / "data")
    ed = store.edition(args.date) if getattr(args, "date", None) else _latest(store)
    if not ed or not ed.get("ai"):
        print("La edición de hoy aún no tiene versión IA: no se avisa")
        return
    if getattr(args, "dry_run", False):
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(discord_payload(ed, cfg, cfg.get("site_url", "")), ensure_ascii=False, indent=2))
        return
    if ed.get("avisado") and not getattr(args, "forzar", False):
        print(f"La edición del {ed['date']} ya se avisó a Discord")
        return
    try:
        if post_discord(ed, cfg):
            ed["avisado"] = ed["ai"]["version"]
            store.save_edition(ed)
    except Exception as e:
        print(f"  ! Fallo inesperado con Discord ({e!r})")


def cmd_previa(args):
    cfg = load_config()
    ed = _latest(Store(ROOT / "data"))
    if not ed:
        return
    if args.dry_run:
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(previa_payload(ed, cfg, cfg.get("site_url", "")), ensure_ascii=False, indent=2))
        return
    post_previa(ed, cfg)


def cmd_informe(args):
    cfg = load_config()
    store = Store(ROOT / "data")
    coronas.sync(cfg)
    path = informe.write(cfg, store.editions(), args.dias)
    print(f"Informe escrito en {path.relative_to(ROOT)}" if path else "No hay ediciones")


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


def _today(cfg):
    return datetime.now(get_tz(cfg["timezone"])).date().isoformat()


def edition_window(cfg, now):
    """(date, start_ms, end_ms) of the edition whose cut-off was the last one before `now`."""
    cut = now.replace(hour=cfg["cutoff_hour"], minute=0, second=0, microsecond=0)
    if now < cut:
        cut -= timedelta(days=1)
    start = cut - timedelta(days=1)
    return cut.date().isoformat(), int(start.timestamp() * 1000), int(cut.timestamp() * 1000)


def cmd_ai_status(args):
    cfg = load_config()
    store = Store(ROOT / "data")
    date_str = args.date or _today(cfg)
    ed = store.edition(date_str)
    events = read_events()
    if not ed:
        print(f"SIN_EDICION {date_str}")
        return
    status = ai_status(ed)
    if status == "hecha":
        # One AI edition a day: once published it is not rewritten. New events and reader
        # proposals wait for tomorrow's edition.
        print(f"HECHA {date_str} eventos_pendientes={len(events)} (saldrán mañana)")
        print("NADA_QUE_HACER")
        return
    from .propuestas import fetch_pending
    props = fetch_pending(cfg, log=lambda *_: None)
    print(f"{status.upper()} {date_str} eventos_pendientes={len(events)} propuestas_pendientes={len(props)}")


def cmd_correcciones(args):
    """Applies the admin's corrections to the stored editions and rebuilds the site."""
    cfg, friends = load_config(), load_friends()
    store = Store(ROOT / "data")
    new = correcciones.sync(cfg, store)
    build_site(cfg, friends, store.editions(), ROOT / "docs")
    print(f"{len(new)} correcciones nuevas aplicadas. Web regenerada en docs/")


def cmd_ai_context(args):
    cfg = load_config()
    store = Store(ROOT / "data")
    new = correcciones.sync(cfg, store)       # the admin's corrections go into the style memory first
    if new:
        print(f"  {len(new)} correcciones nuevas del administrador incorporadas a la memoria de estilo")
    date_str = args.date or _today(cfg)
    try:
        path, ctx = write_context(store, date_str)
    except AIError as e:
        sys.exit(str(e))
    print(f"Contexto escrito en {path.relative_to(ROOT)}")
    print(f"  estado IA: {ctx['estado_ia']} · {len(ctx['dossier']['angulos'])} ángulos en el dossier · "
          f"{len(ctx['eventos_pendientes'])} eventos pendientes · {len(ctx['propuestas_lectores'])} propuestas de lectores · "
          f"{len(ctx['historial'])} días de historial")


def cmd_apply_ai(args):
    cfg, friends = load_config(), load_friends()
    store = Store(ROOT / "data")
    try:
        ed, clean, published = apply_file(store, args.file, args.date)
    except AIError as e:
        sys.exit(f"ERROR en el archivo de la IA: {e}")
    coronas.sync(cfg)
    build_site(cfg, friends, store.editions(), ROOT / "docs")
    if clean.get("formato") == 2:
        pesos = Counter(p["peso"] for p in clean["piezas"])
        summary = (f"{len(clean['piezas'])} piezas ({pesos['grande']} grandes, {pesos['mediana']} medianas, "
                   f"{pesos['breve']} breves), {len({p['formato'] for p in clean['piezas']})} formatos")
    else:
        summary = f"{len(clean['items'])} noticias reescritas, {len(clean['extra'])} artículos nuevos"
    print(f"Edición del {ed['date']} actualizada (versión IA {ed['ai']['version']}): " + summary
          + (", columna" if clean["columna"] else "") + (", edición especial" if clean["especial"] else "")
          + (f", {published} eventos publicados" if published else "")
          + (f", {len(clean['propuestas_usadas'])} propuestas de lectores" if clean["propuestas_usadas"] else "")
          + (f", {len(clean['propuestas_descartadas'])} descartadas" if clean["propuestas_descartadas"] else ""))
    print("Web regenerada en docs/")


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
    ap = argparse.ArgumentParser(prog="python -m roast", description="El Rincón del Feeder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="edición de hoy")
    r.add_argument("--no-llm", action="store_true", help="no usar Claude aunque haya clave")
    r.add_argument("--no-notify", action="store_true", help="no avisar por Discord")
    r.set_defaults(fn=cmd_run)
    b = sub.add_parser("backfill", help="crear las ediciones de los días anteriores")
    b.add_argument("--days", type=int, default=7)
    b.set_defaults(fn=cmd_backfill)
    sub.add_parser("build", help="regenerar la web").set_defaults(fn=cmd_build)
    sub.add_parser("rangos", help="guardar los rangos de hoy y actualizar la bolsa de LP").set_defaults(fn=cmd_rangos)
    sub.add_parser("correcciones", help="aplica las correcciones del administrador y regenera la web").set_defaults(fn=cmd_correcciones)
    sub.add_parser("check", help="comprobar clave y jugadores").set_defaults(fn=cmd_check)
    s = sub.add_parser("ai-status", help="¿la edición de hoy ya tiene versión IA?")
    s.add_argument("--date")
    s.set_defaults(fn=cmd_ai_status)
    c = sub.add_parser("ai-context", help="prepara ai/contexto-FECHA.json para la rutina de Claude")
    c.add_argument("--date")
    c.set_defaults(fn=cmd_ai_context)
    a = sub.add_parser("apply-ai", help="aplica ai/edicion-FECHA.json y regenera la web")
    a.add_argument("file")
    a.add_argument("--date")
    a.set_defaults(fn=cmd_apply_ai)
    v = sub.add_parser("avisar", help="avisa a Discord de la edición IA de hoy (una sola vez)")
    v.add_argument("--date")
    v.add_argument("--dry-run", action="store_true", help="enseña el mensaje sin mandarlo")
    v.add_argument("--forzar", action="store_true", help="avisa aunque ya se avisara")
    v.set_defaults(fn=cmd_avisar)
    pv = sub.add_parser("previa", help="la previa de la noche en Discord (mercados de la Lonja de Coronas)")
    pv.add_argument("--dry-run", action="store_true", help="enseña el mensaje sin mandarlo")
    pv.set_defaults(fn=cmd_previa)
    inf = sub.add_parser("informe", help="informe semanal de la redacción en informes/")
    inf.add_argument("--dias", type=int, default=7)
    inf.set_defaults(fn=cmd_informe)
    d = sub.add_parser("demo", help="demo con datos falsos")
    d.add_argument("--days", type=int, default=7)
    d.add_argument("--seed", type=int, default=7)
    d.add_argument("--out", default="demo_site")
    d.set_defaults(fn=cmd_demo)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
