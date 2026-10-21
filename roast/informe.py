"""The editor's weekly report: what made the group laugh and what nobody touched.

For the person who runs the paper, not for the readers: reactions and comments per story over the
last days, grouped by format, section, saga and columnist, the stories with no reaction at all, and
how many readers played the jury, «¿Quién fue?» and the Lonja de Coronas. Written as Markdown in
informes/ so it can be read on GitHub.
"""
from collections import Counter, defaultdict

from . import coronas, juegos, lectores
from .util import ROOT

DIR = ROOT / "informes"


def _rows(cfg, table, select, dates):
    out = []
    for d in dates:
        out += [dict(r, edicion=d) for r in lectores._get(cfg, table, [("select", select), ("edicion", f"eq.{d}")]) or []]
    return out


def build(cfg, editions, days=7):
    eds = sorted(editions, key=lambda e: e["date"])[-days:]
    if not eds:
        return None
    dates = [e["date"] for e in eds]
    reactions = _rows(cfg, "reacciones", "pieza,emoji", dates)
    comments = _rows(cfg, "comentarios", "pieza", dates)
    per = defaultdict(Counter)
    for r in reactions:
        per[(r["edicion"], r["pieza"])][r["emoji"]] += 1
    talk = Counter((c["edicion"], c.get("pieza")) for c in comments if c.get("pieza"))
    pieces = []
    for e in eds:
        for it in e.get("items") or []:
            k = (e["date"], it.get("id"))
            pieces.append({"fecha": e["date"], "titular": it["headline"], "formato": it.get("formato") or "—",
                           "seccion": it.get("section") or "—", "saga": (it.get("saga") or {}).get("titulo") or "—",
                           "peso": it.get("peso") or "—", "risas": per[k]["😂"] + per[k]["💀"],
                           "reacciones": sum(per[k].values()), "comentarios": talk[k]})
    groups = {}
    for field in ("formato", "seccion", "saga", "peso"):
        agg = defaultdict(lambda: [0, 0, 0])
        for p in pieces:
            a = agg[p[field]]
            a[0] += 1
            a[1] += p["reacciones"]
            a[2] += p["comentarios"]
        groups[field] = sorted(((k, n, r, c, r / n) for k, (n, r, c) in agg.items()), key=lambda x: -x[4])
    columnists = Counter()
    for e in eds:
        if e.get("columna"):
            columnists[e["columna"]["autor"]] += 1
    juries = [juegos.jury_result(cfg, e) for e in eds if e.get("jurado")]
    puzzles = [juegos.puzzle_result(cfg, e) for e in eds if e.get("quien_fue")]
    led = coronas.ledger(editions, coronas.stored_bets())
    return {"desde": dates[0], "hasta": dates[-1], "piezas": pieces, "grupos": groups, "columnistas": columnists,
            "jurados": [j for j in juries if j], "quien_fue": [p for p in puzzles if p],
            "coronas": led["cuentas"][:10], "sin_datos": not reactions and not comments}


def markdown(rep):
    lines = [f"# Informe de la redacción · {rep['desde']} → {rep['hasta']}", ""]
    if rep["sin_datos"]:
        lines += ["> No se han podido leer reacciones ni comentarios (¿Supabase sin configurar?).", ""]
    top = sorted(rep["piezas"], key=lambda p: (-p["risas"], -p["reacciones"]))[:8]
    lines += ["## Lo que más hizo reír", "", "| Fecha | Titular | Formato | 😂+💀 | Reacciones | Comentarios |",
              "|---|---|---|---|---|---|"]
    lines += [f"| {p['fecha']} | {p['titular']} | {p['formato']} | {p['risas']} | {p['reacciones']} | {p['comentarios']} |"
              for p in top]
    dead = [p for p in rep["piezas"] if not p["reacciones"] and not p["comentarios"]]
    lines += ["", f"## Lo que nadie tocó ({len(dead)} de {len(rep['piezas'])} piezas)", ""]
    lines += [f"- {p['fecha']} · *{p['formato']}* · {p['titular']}" for p in dead[:20]]
    names = {"formato": "Por formato", "seccion": "Por sección", "saga": "Por saga", "peso": "Por peso"}
    for field, title in names.items():
        lines += ["", f"## {title}", "", "| | Piezas | Reacciones | Comentarios | Reacciones por pieza |", "|---|---|---|---|---|"]
        lines += [f"| {k} | {n} | {r} | {c} | {avg:.1f} |" for k, n, r, c, avg in rep["grupos"][field]]
    if rep["columnistas"]:
        lines += ["", "## Columnistas", ""] + [f"- {a}: {n}" for a, n in rep["columnistas"].most_common()]
    lines += ["", "## Juegos de los lectores", ""]
    for j in rep["jurados"]:
        lines.append(f"- Jurado del {j['edicion']}: «{j['pregunta']}» · {j['total']} votos · "
                     + ", ".join(f"{o['texto']} {o['votos']}" for o in j["opciones"]))
    for p in rep["quien_fue"]:
        lines.append(f"- ¿Quién fue? del {p['edicion']}: {p['jugaron']} jugaron, {len(p['acertaron'])} acertaron")
    if rep["coronas"]:
        lines += ["", "## Lonja de Coronas", ""] + [f"- {a['nombre']}: {a['saldo']} coronas" for a in rep["coronas"]]
    return "\n".join(lines) + "\n"


def write(cfg, editions, days=7):
    rep = build(cfg, editions, days)
    if not rep:
        return None
    DIR.mkdir(exist_ok=True)
    path = DIR / f"informe-{rep['hasta']}.md"
    path.write_text(markdown(rep), encoding="utf-8")
    return path
