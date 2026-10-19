"""Static site generator: a daily newspaper, an archive and one page per player."""
from datetime import date
from html import escape
from pathlib import Path

from .roasts import DESKS
from .util import fmt_int, fmt_num, fmt_pct, long_date, short_date, slugify

POINTS = [5, 3, 2, 1]  # daily shame points by position in the ranking

CSS = r"""
:root{
  color-scheme:light;
  --bg:#cfc3a6; --paper:#efe4c8; --paper2:#e6d7b4; --ink:#241a10; --muted:#5f4e39; --rule:#8b7757;
  --accent:#7e1e12; --chip:#e2d2ab; --good:#2f5122;
  --noise:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 .32  0 0 0 0 .23  0 0 0 0 .1  0 0 0 .13 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>");
}
*{box-sizing:border-box;margin:0;padding:0}
html{overflow-x:hidden}
body{background:var(--noise),radial-gradient(ellipse at top,#d8ccaf,#bfb08e);color:var(--ink);
  font-family:"Libre Caslon Text",Georgia,serif;line-height:1.55;font-size:17px}
a{color:inherit}
.wrap{max-width:1180px;margin:0 auto;padding:0 16px}
.paper{background:var(--noise),radial-gradient(ellipse at center,transparent 55%,rgba(110,80,30,.20)),var(--paper);
  border:1px solid #a8956c;box-shadow:0 2px 0 rgba(0,0,0,.06),0 22px 50px rgba(60,40,10,.28);
  margin:22px auto 40px;padding:26px 34px 36px;position:relative}
.paper::before{content:"";position:absolute;inset:8px;border:1px solid rgba(80,60,30,.25);pointer-events:none}
/* masthead */
.mast{text-align:center;padding-bottom:6px}
.topline{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-family:"IM Fell English SC",serif;
  font-size:.92rem;letter-spacing:.06em;color:var(--muted);border-bottom:1px solid var(--ink);padding-bottom:6px}
.title{font-family:"UnifrakturMaguntia",serif;font-weight:400;font-size:clamp(2.7rem,10vw,6.4rem);line-height:1.02;
  margin:12px 0 2px;text-decoration:none;display:inline-block;color:var(--ink);text-shadow:0 1px 0 rgba(255,255,255,.35)}
.tagline{font-family:"Old Standard TT",serif;font-style:italic;color:var(--muted);font-size:1rem}
.rules{border-top:3px solid var(--ink);border-bottom:1px solid var(--ink);height:6px;margin-top:12px}
nav.menu{display:flex;justify-content:center;gap:6px 26px;flex-wrap:wrap;padding:7px 0;font-family:"IM Fell English SC",serif;
  font-size:1rem;letter-spacing:.08em;border-bottom:1px solid var(--ink)}
nav.menu a{text-decoration:none}
nav.menu a:hover{color:var(--accent)}
/* ticker */
.ticker{display:flex;align-items:center;border-bottom:1px solid var(--ink);overflow:hidden;font-size:.92rem;margin:0 0 24px;
  font-family:"Old Standard TT",serif;font-style:italic}
.ticker b{background:var(--ink);color:var(--paper);padding:6px 12px;font-family:"IM Fell English SC",serif;font-style:normal;
  font-size:.9rem;letter-spacing:.08em;white-space:nowrap;flex:none}
.ticker .run{white-space:nowrap;animation:run 70s linear infinite;padding-left:100%}
.ticker .run span{margin-right:30px}
.ticker .run span::after{content:"\2726";margin-left:30px;color:var(--muted)}
@keyframes run{to{transform:translateX(-100%)}}
/* section labels */
.kicker{font-family:"IM Fell English SC",serif;font-size:.98rem;letter-spacing:.06em;color:var(--accent)}
.kicker .desk{font-family:"Old Standard TT",serif;font-style:italic;font-size:.85rem;letter-spacing:0;color:var(--muted)}
.orn{text-align:center;color:var(--muted);margin:4px 0 20px;letter-spacing:.8em;font-size:1rem}
/* lead story */
.lead{display:grid;grid-template-columns:1.65fr 1fr;gap:30px;border-bottom:3px double var(--ink);padding-bottom:22px;margin-bottom:8px}
.lead h2{font-family:"Old Standard TT",Georgia,serif;font-weight:700;font-size:clamp(2rem,4.6vw,3.5rem);line-height:1.04;
  margin:6px 0 14px;letter-spacing:-.01em}
.lead p{font-size:1.08rem;text-align:justify;hyphens:auto;column-count:2;column-gap:26px;column-rule:1px solid var(--rule)}
.lead p::first-letter{font-family:"Old Standard TT",serif;font-weight:700;float:left;font-size:3.6rem;line-height:.82;padding:6px 8px 0 0}
.bigstat{border:4px double var(--ink);background:var(--paper2);padding:18px;text-align:center;align-self:start}
.bigstat .n{font-family:"Old Standard TT",serif;font-weight:700;font-size:clamp(2.6rem,7vw,4.6rem);line-height:1;color:var(--accent)}
.bigstat .l{font-style:italic;font-size:.9rem;color:var(--muted);margin-top:6px}
.bigstat .who{margin-top:12px;font-family:"IM Fell English SC",serif;font-size:1rem;letter-spacing:.06em}
figure{margin:10px 0 12px}
figure img{display:block;width:100%;height:auto;border:1px solid var(--ink);padding:4px;background:var(--paper2);
  filter:grayscale(1) sepia(.5) contrast(1.12) brightness(.96)}
figcaption{font-family:"Old Standard TT",serif;font-style:italic;font-size:.82rem;color:var(--muted);margin-top:5px;text-align:center}
/* body */
.cols{display:grid;grid-template-columns:1fr 320px;gap:32px}
.cols>*,.lead>*,.profile>*,.news>*{min-width:0}
.news{display:grid;grid-template-columns:1fr 1fr;gap:0 30px;align-content:start;
  background:linear-gradient(var(--rule),var(--rule)) center top/1px 100% no-repeat}
.news article{border-top:1px solid var(--ink);padding:14px 0 18px;background:var(--paper)}
.news article:nth-child(odd){padding-right:2px}
.news article.wide{grid-column:1/-1}
.news h3{font-family:"Old Standard TT",Georgia,serif;font-weight:700;font-size:1.36rem;line-height:1.14;margin:4px 0 8px}
.news p{text-align:justify;hyphens:auto}
.news .stat{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;border-top:1px dotted var(--rule);border-bottom:1px dotted var(--rule);
  padding:3px 0;margin:0 0 9px}
.news .stat .n{font-family:"Old Standard TT",serif;font-weight:700;font-size:1.45rem;line-height:1;color:var(--accent)}
.news .stat .l{font-style:italic;font-size:.85rem;color:var(--muted);line-height:1.2}
.byline{font-family:"Old Standard TT",serif;font-style:italic;font-size:.85rem;color:var(--muted);margin-top:8px}
.byline a{text-decoration:none;border-bottom:1px dotted var(--muted)}
aside .box{border:3px double var(--ink);background:rgba(255,250,235,.25);padding:14px 16px;margin-bottom:20px}
aside h4{font-family:"IM Fell English SC",serif;font-weight:400;font-size:1.12rem;letter-spacing:.05em;text-align:center;
  border-bottom:1px solid var(--ink);padding-bottom:6px;margin-bottom:10px}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th{text-align:left;font-family:"IM Fell English SC",serif;font-weight:400;color:var(--muted);font-size:.86rem;
  border-bottom:1px solid var(--ink);padding:4px 4px}
td{padding:5px 4px;border-bottom:1px dotted var(--rule)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr.top td{color:var(--accent);font-weight:700}
.quote{font-family:"Old Standard TT",serif;font-style:italic;font-size:1.18rem;line-height:1.35;text-align:center}
.small{font-size:.88rem;color:var(--muted)}
.win{color:var(--good);font-weight:700}.loss{color:var(--accent);font-weight:700}
footer{text-align:center;font-family:"Old Standard TT",serif;font-style:italic;font-size:.8rem;color:#4a3d2c;padding:0 16px 40px;max-width:900px;margin:0 auto}
/* player page */
.profile{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-bottom:26px}
.profile h2{font-family:"Old Standard TT",serif;font-weight:700;font-size:clamp(2.2rem,5vw,3.2rem);line-height:1.02}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.kpi{border:1px solid var(--ink);background:rgba(255,250,235,.25);padding:10px;text-align:center}
.kpi .n{font-family:"Old Standard TT",serif;font-weight:700;font-size:1.55rem;color:var(--accent);line-height:1.1}
.kpi .l{font-style:italic;font-size:.75rem;color:var(--muted)}
.spark{width:100%;height:auto}
.archive li{list-style:none;border-top:1px solid var(--ink);padding:12px 0;display:grid;grid-template-columns:170px 1fr;gap:14px}
.archive li a{font-family:"Old Standard TT",serif;font-weight:700;font-size:1.15rem;text-decoration:none}
.tablewrap{overflow-x:auto}
/* AI extras: special edition banner + opinion column */
.special{--sp:var(--accent);border:5px double var(--sp);background:var(--paper2);padding:22px 22px 18px;margin-bottom:22px;text-align:center}
.special .kicker{color:var(--sp);font-size:1.15rem;letter-spacing:.2em}
.special h2{font-family:"Old Standard TT",Georgia,serif;font-weight:700;font-size:clamp(2.1rem,5.6vw,4rem);line-height:1.02;margin:8px 0}
.special p{font-family:"Old Standard TT",serif;font-style:italic;font-size:1.12rem;color:var(--muted);max-width:760px;margin:0 auto}
.special.t-oro{--sp:#8a6410}.special.t-negro{--sp:var(--ink)}.special.t-verde{--sp:#2f5122}
.special.t-azul{--sp:#1d3f6b}.special.t-morado{--sp:#5a2d6e}
.news article.column{background:var(--paper2);border:1px solid var(--ink);outline:1px solid var(--ink);outline-offset:-6px;
  padding:20px 22px 12px;margin:12px 0 8px}
.news article.column p{margin-bottom:10px}
.news article.column p:first-of-type::first-letter{font-family:"Old Standard TT",serif;font-weight:700;float:left;font-size:2.6rem;line-height:.85;padding:4px 6px 0 0}
.news article.column h3{font-style:italic;text-align:center;font-size:1.6rem}
.news article.column .kicker,.news article.column .byline{text-align:center}
.news article.faro{background:linear-gradient(180deg,rgba(212,170,60,.18),transparent);}
.news article.faro .kicker::before{content:"\263C  "}
@media (max-width:900px){
  .cols,.lead,.profile{grid-template-columns:1fr}
  .news{grid-template-columns:1fr;background:none}
  .lead p{column-count:1}
}
@media (max-width:560px){
  body{font-size:16px}
  .paper{padding:20px 16px 26px;margin:10px auto 26px}
  .paper::before{inset:5px}
  .topline{justify-content:center}
  .kpis{grid-template-columns:repeat(2,1fr)}
  .archive li{grid-template-columns:1fr;gap:2px}
}
@media (prefers-reduced-motion:reduce){.ticker .run{animation:none;padding-left:12px}}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=IM+Fell+English+SC&family=Libre+Caslon+Text:ital,wght@0,400;0,700;1,400'
         '&family=Old+Standard+TT:ital,wght@0,400;0,700;1,400&family=UnifrakturMaguntia&display=swap" '
         'rel="stylesheet">')

LEGAL = ("El Feed Diario no está avalado por Riot Games y no refleja las opiniones de Riot Games ni de "
         "nadie implicado oficialmente en la producción o gestión de League of Legends. League of Legends "
         "y Riot Games son marcas registradas de Riot Games, Inc. Sátira entre amigos: datos reales, "
         "mala leche inventada.")


def _e(x):
    return escape(str(x), quote=True)


def _date(s):
    y, m, d = map(int, s.split("-"))
    return date(y, m, d)


def page(cfg, title, body, rel, edition=None, description=""):
    top = ""
    if edition:
        top = (f'<div class="topline"><span>{_e(long_date(_date(edition["date"])).capitalize())}</span>'
               f'<span>Año I · Edición nº {edition["number"]}</span><span>Precio: 1 LP</span></div>')
    else:
        top = ('<div class="topline"><span>Fundado en la Grieta del Invocador</span><span>Hemeroteca</span>'
               '<span>Precio: 1 LP</span></div>')
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<meta name="description" content="{_e(description or cfg['site_tagline'])}">
{FONTS}
<link rel="stylesheet" href="{rel}style.css">
</head>
<body>
<div class="wrap"><div class="paper">
<header class="mast">
{top}
<a class="title" href="{rel}index.html">{_e(cfg['site_title'])}</a>
<p class="tagline">{_e(cfg['site_tagline'])}</p>
<div class="rules"></div>
<nav class="menu"><a href="{rel}index.html">Portada</a><a href="{rel}archivo.html">Hemeroteca</a><a href="{rel}jugadores.html">Jugadores</a></nav>
</header>
{body}
</div></div>
<footer>{_e(LEGAL)}</footer>
</body>
</html>
"""


# --------------------------------------------------------------------------- pieces
def _ranking_table(ranking, rel):
    if not ranking:
        return '<p class="small">Hoy nadie ha jugado.</p>'
    rows = []
    for i, r in enumerate(ranking):
        dmg = fmt_pct(r["dmg_share"], 0) if r.get("dmg_share") is not None else "–"
        rows.append(
            f'<tr class="{"top" if i == 0 else ""}"><td>{i + 1}</td>'
            f'<td><a href="{rel}jugadores/{_e(r["slug"])}.html">{_e(r["alias"])}</a></td>'
            f'<td class="num">{r["wins"]}–{r["losses"]}</td><td class="num">{fmt_num(r["kda"], 2)}</td>'
            f'<td class="num">{dmg}</td></tr>')
    return ('<div class="tablewrap"><table><thead><tr><th>#</th><th>Jugador</th><th class="num">V–D</th>'
            '<th class="num">KDA</th><th class="num">Daño</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>"
            '<p class="small" style="margin-top:8px">Ordenado de peor a mejor. «Daño» es su cuota media del '
            'daño a campeones de su equipo.</p>')


def general_leaderboard(editions):
    tot = {}
    for ed in editions:
        for i, r in enumerate(ed.get("ranking", [])):
            t = tot.setdefault(r["slug"], {"slug": r["slug"], "alias": r["alias"], "points": 0,
                                           "portadas": 0, "games": 0, "wins": 0, "losses": 0})
            t["alias"] = r["alias"]
            t["points"] += POINTS[i] if i < len(POINTS) else 0
            t["portadas"] += 1 if i == 0 else 0
            t["games"] += r["games"]
            t["wins"] += r["wins"]
            t["losses"] += r["losses"]
    return sorted(tot.values(), key=lambda t: (-t["points"], -t["portadas"]))


def _general_table(board, rel):
    if not board:
        return '<p class="small">Aún no hay clasificación.</p>'
    rows = "".join(
        f'<tr class="{"top" if i == 0 else ""}"><td>{i + 1}</td>'
        f'<td><a href="{rel}jugadores/{_e(t["slug"])}.html">{_e(t["alias"])}</a></td>'
        f'<td class="num">{t["points"]}</td><td class="num">{t["portadas"]}</td></tr>'
        for i, t in enumerate(board))
    return ('<div class="tablewrap"><table><thead><tr><th>#</th><th>Jugador</th><th class="num">Puntos</th>'
            '<th class="num">Portadas</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
            '<p class="small" style="margin-top:8px">El peor del día suma 5 puntos, el segundo 3, el '
            'tercero 2 y el cuarto 1.</p>')


def _kicker(it):
    section = "EL FARO DE LA ESPERANZA" if it.get("section") == "MENCIÓN" else it["section"]  # older editions
    desk = it.get("desk") or DESKS.get(section, "")
    return (f'<div class="kicker">{_e(section)}'
            + (f'<span class="desk"> · {_e(desk)}</span>' if desk else "") + '</div>')


# Official champion art from Riot's Data Dragon CDN (allowed for free fan projects that carry
# Riot's legal notice). Champion names in match data are already Data Dragon ids ("Kaisa");
# display names ("Kai'Sa") are normalised here.
DDRAGON_IDS = {"wukong": "MonkeyKing", "nunu & willump": "Nunu", "renata glasc": "Renata",
               "kog'maw": "KogMaw", "rek'sai": "RekSai", "k'sante": "KSante", "leblanc": "Leblanc",
               "dr. mundo": "DrMundo", "jarvan iv": "JarvanIV", "bel'veth": "Belveth"}

CAPTIONS = [
    "{champ}, en una imagen de archivo, minutos antes de que {alias} lo cogiera.",
    "Fotografía de {champ} tomada por los Centinelas de la Luz como prueba del delito.",
    "{champ}, visiblemente decepcionado tras la partida de {alias}.",
    "Retrato oficial de {champ}. Su abogado ha pedido que no se le relacione con {alias}.",
    "{champ}, ayer, preguntando quién le había hecho esto.",
    "La Comisaría de Piltover difunde esta imagen de {champ} por si alguien reconoce al culpable.",
]


def _ddragon_id(name):
    key = name.strip().lower()
    if key in DDRAGON_IDS:
        return DDRAGON_IDS[key]
    if "'" in name or "." in name or " " in name:
        clean = "".join(ch for ch in name if ch.isalnum())
        return clean[0].upper() + clean[1:].lower() if "'" in name else clean
    return name


def _figure(it, rel):
    """Image for an article: a picture the group sent (docs/img/) or the champion's splash art."""
    if it.get("imagen"):
        src = f"{rel}img/{it['imagen']}"
        caption = it.get("pie") or ""
    else:
        champ = it.get("campeon") or (it.get("facts") or {}).get("champ")
        if not champ:
            return ""
        src = f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{_ddragon_id(champ)}_0.jpg"
        alias = it.get("alias") or "el grupo"
        caption = it.get("pie") or CAPTIONS[sum(map(ord, it["headline"])) % len(CAPTIONS)].format(
            champ=champ, alias=alias)
    return (f'<figure><img src="{_e(src)}" alt="{_e(caption)}" loading="lazy" '
            f'onerror="this.closest(\'figure\').remove()">'
            + (f'<figcaption>{_e(caption)}</figcaption>' if caption else "") + '</figure>')


def _article(it, rel, wide=False, image=False):
    who = ""
    if it.get("player"):
        who = (f'<div class="byline">Sobre <a href="{rel}jugadores/{_e(it["player"])}.html">'
               f'{_e(it["alias"])}</a></div>')
    classes = " ".join(c for c in ("wide" if wide else "", "faro" if it.get("kind") == "mencion" else "") if c)
    stat = _stat(it) if it.get("stat") else ""
    fig = _figure(it, rel) if image else ""
    return (f'<article class="{classes}">{_kicker(it)}'
            f'<h3>{_e(it["headline"])}</h3>{fig}{stat}<p>{_e(it["body"])}</p>{who}</article>')


def _stat(it):
    return (f'<div class="stat"><span class="n">{_e(it["stat"])}</span>'
            f'<span class="l">{_e(it["stat_label"])}</span></div>')


def render_edition(cfg, ed, editions_until, rel):
    items = ed["items"]
    lead = items[0] if items else None
    rest = items[1:]
    ticker = " ".join(f"<span>{_e(i['headline'])}</span>" for i in items[:8])
    t = ed["totals"]
    lead_html = ""
    if lead:
        who = (f'<div class="who"><a href="{rel}jugadores/{_e(lead["player"])}.html">{_e(lead["alias"])}</a></div>'
               if lead.get("player") else "")
        stat_box = (f'<div class="bigstat"><div class="n">{_e(lead["stat"])}</div>'
                    f'<div class="l">{_e(lead["stat_label"])}</div>{who}</div>') if lead.get("stat") else ""
        lead_html = (f'<section class="lead"><div>{_kicker(lead)}'
                     f'<h2>{_e(lead["headline"])}</h2><p>{_e(lead["body"])}</p></div>'
                     f'<div>{_figure(lead, rel)}{stat_box}</div></section><div class="orn">✦ ✦ ✦</div>')
    # pictures on the first few articles only, to keep the page light
    with_img, pics = set(), 0
    for i, it in enumerate(rest):
        if pics < 3 and (it.get("imagen") or it.get("campeon") or (it.get("facts") or {}).get("champ")):
            with_img.add(i)
            pics += 1
    news = "".join(_article(it, rel, wide=(i == 0 and len(rest) % 2 == 1), image=i in with_img)
                   for i, it in enumerate(rest))
    col = ed.get("columna")
    if col:
        paras = "".join(f"<p>{_e(p)}</p>" for p in col["cuerpo"])
        news = (f'<article class="wide column"><div class="kicker">La columna</div><h3>{_e(col["titulo"])}</h3>'
                f'<div class="byline">Por {_e(col["autor"])}</div>{paras}</article>') + news
    special = ""
    esp = ed.get("especial")
    if esp:
        special = (f'<section class="special t-{_e(esp["tema"])}"><div class="kicker">{_e(esp["antetitulo"])}</div>'
                   f'<h2>{_e(esp["titulo"])}</h2>'
                   + (f'<p>{_e(esp["subtitulo"])}</p>' if esp.get("subtitulo") else "") + '</section>')
    totals = (f'<p>{t["games"]} partidas del grupo en {t["matches"]} partidas distintas. '
              f'{fmt_int(t["deaths"])} muertes y {int(t["dead_seconds"] // 60)} minutos en la pantalla gris, '
              f'de {int(t["play_seconds"] // 60)} minutos jugados.</p>')
    board = general_leaderboard(editions_until)
    writer = ""
    if ed.get("written_by"):
        version = (ed.get("ai") or {}).get("version")
        writer = (f'<p class="small" style="margin-top:10px">Redacción: {_e(ed["written_by"])}'
                  + (f' (versión {version})' if version and version > 1 else "") + '.</p>')
    body = f"""
<div class="ticker"><b>ÚLTIMA HORA</b><div class="run">{ticker}</div></div>
{special}
{lead_html}
<div class="cols">
  <section class="news">{news or '<p class="small">Sin más noticias por hoy.</p>'}</section>
  <aside>
    <div class="box"><h4>Clasificación del día</h4>{_ranking_table(ed.get("ranking", []), rel)}</div>
    <div class="box"><h4>General de la vergüenza</h4>{_general_table(board, rel)}</div>
    <div class="box"><h4>Frase del día</h4><p class="quote">«{_e(ed["frase"])}»</p></div>
    <div class="box"><h4>El día en cifras</h4>{totals}{writer}</div>
  </aside>
</div>"""
    title = f"{cfg['site_title']} · {short_date(_date(ed['date']))}"
    desc = lead["headline"] if lead else cfg["site_tagline"]
    return page(cfg, title, body, rel, edition=ed, description=desc)


def _sparkline(values, w=320, h=70):
    if len(values) < 2:
        return '<p class="small">Hacen falta al menos dos días con partidas para dibujar la evolución.</p>'
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    pts = " ".join(f"{i * (w - 10) / (len(values) - 1) + 5:.1f},{h - 8 - (v - lo) / span * (h - 16):.1f}"
                   for i, v in enumerate(values))
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" role="img" aria-label="Evolución de la vergüenza">'
            f'<polyline points="{pts}" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round" style="color:var(--accent)"/></svg>'
            '<p class="small">Puntos de vergüenza por día (más alto, peor).</p>')


def render_player(cfg, friend, editions):
    slug = friend["slug"]
    games, items, scores = [], [], []
    portadas = 0
    for ed in editions:
        for i, r in enumerate(ed.get("ranking", [])):
            if r["slug"] == slug:
                scores.append(r["score"])
                portadas += 1 if i == 0 else 0
        games += [dict(g, date=ed["date"]) for g in ed.get("games", []) if g["slug"] == slug]
        items += [dict(it, date=ed["date"]) for it in ed["items"] if it.get("player") == slug]
    g = len(games)
    wins = sum(x["win"] for x in games)
    k = sum(x["k"] for x in games); d = sum(x["d"] for x in games); a = sum(x["a"] for x in games)
    ns = [x for x in games if not x["support"]]
    low = sum(1 for x in ns if x["lowest_dmg"])
    dmg = sum(x["dmg_share"] for x in ns) / len(ns) if ns else None
    kpis = [
        (f"{wins}–{g - wins}", "victorias–derrotas"),
        (fmt_num((k + a) / max(d, 1), 2), "KDA"),
        (str(portadas), "portadas como peor"),
        (fmt_pct(dmg, 1) if dmg is not None else "–", "cuota media de daño"),
        (f"{low}/{len(ns)}", "último en daño de su equipo"),
        (fmt_int(d), "muertes"),
    ]
    kpi_html = "".join(f'<div class="kpi"><div class="n">{_e(n)}</div><div class="l">{_e(l)}</div></div>'
                       for n, l in kpis)
    news = "".join(
        f'<article><div class="kicker">{_e(it["section"])} · {_e(short_date(_date(it["date"])))}</div>'
        f'<h3>{_e(it["headline"])}</h3>{_stat(it)}<p>{_e(it["body"])}</p></article>'
        for it in reversed(items[-20:]))
    rows = "".join(
        f'<tr><td>{_e(short_date(_date(x["date"])))}</td><td>{_e(x["champ"])}</td><td>{_e(x["role"])}</td>'
        f'<td>{_e(x["queue_name"])}</td><td class="{"win" if x["win"] else "loss"}">{"V" if x["win"] else "D"}</td>'
        f'<td class="num">{x["k"]}/{x["d"]}/{x["a"]}</td>'
        f'<td class="num">{fmt_pct(x["dmg_share"], 0)}</td></tr>' for x in reversed(games[-25:]))
    body = f"""
<section class="profile" style="margin-top:22px">
  <div><div class="kicker">Ficha policial</div><h2>{_e(friend["alias"])}</h2>
    <p class="small">{_e(friend["riot_id"])} · {g} partidas registradas</p>
    <div style="margin-top:16px">{_sparkline(scores[-30:])}</div></div>
  <div class="kpis">{kpi_html}</div>
</section>
<div class="cols">
  <section class="news" style="grid-template-columns:1fr">{news or '<p class="small">Todavía no ha salido en el periódico.</p>'}</section>
  <aside><div class="box"><h4>Últimas partidas</h4>
    {('<div class="tablewrap"><table><thead><tr><th>Día</th><th>Campeón</th><th>Rol</th><th>Cola</th><th></th>'
      '<th class="num">KDA</th><th class="num">Daño</th></tr></thead><tbody>' + rows + '</tbody></table></div>')
     if rows else '<p class="small">Sin partidas todavía.</p>'}
  </div></aside>
</div>"""
    return page(cfg, f"{friend['alias']} · {cfg['site_title']}", body, "../",
                description=f"Expediente de {friend['alias']} en {cfg['site_title']}")


def render_archive(cfg, editions):
    def title(ed):
        if ed.get("especial"):
            return f'{ed["especial"]["antetitulo"].capitalize()}: {ed["especial"]["titulo"]}'
        return ed["items"][0]["headline"] if ed["items"] else "Sin noticias"
    lis = "".join(
        f'<li><span class="small">{_e(long_date(_date(ed["date"])).capitalize())}<br>Edición nº {ed["number"]}</span>'
        f'<a href="ediciones/{ed["date"]}.html">{_e(title(ed))}</a></li>'
        for ed in reversed(editions))
    body = (f'<section style="margin-top:22px"><div class="kicker">Hemeroteca</div>'
            f'<ul class="archive">{lis or "<li>Aún no hay ediciones.</li>"}</ul></section>')
    return page(cfg, f"Hemeroteca · {cfg['site_title']}", body, "")


def render_players_index(cfg, friends, editions):
    board = {t["slug"]: t for t in general_leaderboard(editions)}
    cards = "".join(
        f'<article><div class="kicker">{_e(f["riot_id"])}</div><h3><a href="jugadores/{_e(f["slug"])}.html">'
        f'{_e(f["alias"])}</a></h3><p class="small">{board.get(f["slug"], {}).get("points", 0)} puntos de vergüenza · '
        f'{board.get(f["slug"], {}).get("portadas", 0)} portadas</p></article>' for f in friends)
    body = f'<section class="news" style="margin-top:12px">{cards}</section>'
    return page(cfg, f"Jugadores · {cfg['site_title']}", body, "")


def build_site(cfg, friends, editions, out_dir):
    out = Path(out_dir)
    (out / "ediciones").mkdir(parents=True, exist_ok=True)
    (out / "jugadores").mkdir(parents=True, exist_ok=True)
    (out / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    editions = sorted(editions, key=lambda e: e["date"])

    known = {f["slug"]: f for f in friends}
    for ed in editions:
        for r in ed.get("ranking", []):
            known.setdefault(r["slug"], {"slug": r["slug"], "alias": r["alias"], "riot_id": r.get("riot_id", "")})
    friends_all = list(known.values())

    for i, ed in enumerate(editions):
        html = render_edition(cfg, ed, editions[:i + 1], "../")
        (out / "ediciones" / f"{ed['date']}.html").write_text(html, encoding="utf-8")
    if editions:
        index = render_edition(cfg, editions[-1], editions, "")
    else:
        index = page(cfg, cfg["site_title"],
                     '<section style="margin:30px 0"><h2 class="kicker">Próximamente</h2>'
                     '<p>La primera edición saldrá en cuanto se ejecute el robot.</p></section>', "")
    (out / "index.html").write_text(index, encoding="utf-8")
    (out / "archivo.html").write_text(render_archive(cfg, editions), encoding="utf-8")
    (out / "jugadores.html").write_text(render_players_index(cfg, friends_all, editions), encoding="utf-8")
    for f in friends_all:
        (out / "jugadores" / f"{f['slug']}.html").write_text(render_player(cfg, f, editions), encoding="utf-8")
    return out
