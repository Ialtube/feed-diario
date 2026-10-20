"""Static site generator: a daily old-style newspaper, an archive, player pages,
reader comments and the "propose a story" page."""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

from . import canon as canon_mod
from .porra import seers
from .roasts import DESKS
from .util import ROOT, champ_name, fmt_int, fmt_num, fmt_pct, load_json, long_date, short_date, slugify

POINTS = [5, 3, 2, 1]  # daily shame points by position in the ranking

NOISE = ("url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='260' height='260'>"
         "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='3' stitchTiles='stitch'/>"
         "<feColorMatrix values='0 0 0 0 .3  0 0 0 0 .22  0 0 0 0 .1  0 0 0 .16 0'/></filter>"
         "<rect width='100%25' height='100%25' filter='url(%23n)'/></svg>\")")

CSS = r"""
:root{
  color-scheme:light;
  --desk:#2e261f; --paper:#d8ccae; --paper2:#cdbf9e; --paper3:#c4b591; --ink:#2a2017; --muted:#5a4a37;
  --rule:#7b6850; --accent:#7a2416; --good:#2f4f22; --noise:NOISE;
}
*{box-sizing:border-box;margin:0;padding:0}
[hidden]{display:none!important}
html{overflow-x:hidden}
body{background:var(--noise),radial-gradient(ellipse at top,#3b3128,#221c16);color:var(--ink);
  font-family:"Libre Caslon Text",Georgia,serif;line-height:1.55;font-size:17px}
a{color:inherit}
.wrap{max-width:1440px;margin:0 auto;padding:0 16px}
/* ---------------------------------------------------------------- the newspaper sheet */
.paper{position:relative;margin:26px auto 40px;padding:28px 40px 40px;border:1px solid #8f7c5a;
  background:
    var(--noise),
    repeating-linear-gradient(0deg,rgba(80,60,30,.03) 0 1px,transparent 1px 3px),
    repeating-linear-gradient(90deg,rgba(80,60,30,.02) 0 1px,transparent 1px 4px),
    radial-gradient(circle at 9% 14%,rgba(130,92,38,.16),transparent 16%),
    radial-gradient(circle at 88% 62%,rgba(120,84,34,.13),transparent 20%),
    radial-gradient(circle at 34% 92%,rgba(110,78,30,.11),transparent 14%),
    linear-gradient(90deg,transparent calc(50% - 1px),rgba(60,40,15,.10) 50%,transparent calc(50% + 1px)),
    radial-gradient(ellipse at center,transparent 58%,rgba(70,48,18,.32)),
    var(--paper);
  box-shadow:0 2px 0 rgba(0,0,0,.25),0 30px 70px rgba(0,0,0,.55)}
.paper::before{content:"";position:absolute;inset:9px;border:1px solid rgba(60,42,18,.3);pointer-events:none}
/* masthead */
.mast{text-align:center;padding-bottom:6px}
.topline{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-family:"IM Fell English SC",serif;
  font-size:.95rem;letter-spacing:.06em;color:var(--muted);border-bottom:1px solid var(--ink);padding-bottom:6px}
.title{font-family:"UnifrakturMaguntia",serif;font-weight:400;font-size:clamp(2.6rem,9vw,6.6rem);line-height:1.02;
  margin:12px 0 2px;text-decoration:none;display:inline-block;color:var(--ink)}
.tagline{font-family:"Old Standard TT",serif;font-style:italic;color:var(--muted);font-size:1.02rem}
.rules{border-top:3px solid var(--ink);border-bottom:1px solid var(--ink);height:6px;margin-top:12px}
nav.menu{display:flex;justify-content:center;gap:6px 28px;flex-wrap:wrap;padding:7px 0;font-family:"IM Fell English SC",serif;
  font-size:1.02rem;letter-spacing:.08em;border-bottom:1px solid var(--ink)}
nav.menu a{text-decoration:none}
nav.menu a:hover,nav.menu a.cta{color:var(--accent)}
/* ticker */
.ticker{display:flex;align-items:center;border-bottom:1px solid var(--ink);overflow:hidden;font-size:.94rem;margin:0 0 24px;
  font-family:"Old Standard TT",serif;font-style:italic}
.ticker b{background:var(--ink);color:var(--paper);padding:6px 12px;font-family:"IM Fell English SC",serif;font-style:normal;
  font-size:.92rem;letter-spacing:.08em;white-space:nowrap;flex:none}
.ticker .run{white-space:nowrap;animation:run 80s linear infinite;padding-left:100%}
.ticker .run span{margin-right:30px}
.ticker .run span::after{content:"\2726";margin-left:30px;color:var(--muted)}
@keyframes run{to{transform:translateX(-100%)}}
/* labels */
.kicker{font-family:"IM Fell English SC",serif;font-size:1rem;letter-spacing:.06em;color:var(--accent)}
.kicker .desk{font-family:"Old Standard TT",serif;font-style:italic;font-size:.86rem;letter-spacing:0;color:var(--muted)}
.orn{text-align:center;color:var(--muted);margin:6px 0 4px;letter-spacing:.8em}
.small{font-size:.9rem;color:var(--muted)}
/* special edition banner */
.special{--sp:var(--accent);border:5px double var(--sp);background:rgba(255,248,225,.12);padding:22px;margin-bottom:22px;text-align:center}
.special .kicker{color:var(--sp);font-size:1.18rem;letter-spacing:.2em}
.special h2{font-family:"Old Standard TT",Georgia,serif;font-weight:700;font-size:clamp(2.1rem,5.4vw,4.2rem);line-height:1.02;margin:8px 0}
.special p{font-family:"Old Standard TT",serif;font-style:italic;font-size:1.14rem;color:var(--muted);max-width:820px;margin:0 auto}
.special.t-oro{--sp:#7d5a0e}.special.t-negro{--sp:var(--ink)}.special.t-verde{--sp:#2f4f22}
.special.t-azul{--sp:#1d3a63}.special.t-morado{--sp:#55295f}
/* lead story */
.lead{display:grid;grid-template-columns:1.7fr 1fr;gap:34px;border-bottom:3px double var(--ink);padding-bottom:22px}
.lead h2{font-family:"Old Standard TT",Georgia,serif;font-weight:700;font-size:clamp(2.1rem,4.6vw,3.8rem);line-height:1.03;margin:6px 0 14px}
.lead .txt{column-count:2;column-gap:28px;column-rule:1px solid var(--rule)}
.lead .txt p{font-size:1.1rem;text-align:justify;hyphens:auto}
.lead .txt p:first-child::first-letter{font-family:"Old Standard TT",serif;font-weight:700;float:left;font-size:3.7rem;line-height:.82;padding:6px 8px 0 0}
.bigstat{border:4px double var(--ink);padding:16px;text-align:center;margin-top:10px}
.bigstat .n{font-family:"Old Standard TT",serif;font-weight:700;font-size:clamp(2.4rem,6vw,4.2rem);line-height:1;color:var(--accent)}
.bigstat .l{font-style:italic;font-size:.92rem;color:var(--muted);margin-top:6px}
.bigstat .who{margin-top:10px;font-family:"IM Fell English SC",serif;font-size:1.02rem}
/* pictures and memes */
figure{margin:8px 0 12px;position:relative}
figure .ph{position:relative;border:1px solid var(--ink);padding:4px;background:var(--paper2)}
figure img{display:block;width:100%;height:auto;filter:grayscale(1) sepia(.45) contrast(1.15) brightness(.88)}
.meme{position:absolute;inset:4px;display:flex;flex-direction:column;justify-content:space-between;align-items:center;
  pointer-events:none;padding:6px 8px;text-align:center}
.meme span{font-family:"Anton",Impact,sans-serif;text-transform:uppercase;color:#fff;font-size:clamp(1rem,2.1vw,1.55rem);
  line-height:1.05;letter-spacing:.02em;-webkit-text-stroke:1.2px #000;paint-order:stroke fill;
  text-shadow:2px 2px 0 #000,-1px -1px 0 #000,1px -1px 0 #000,-1px 1px 0 #000}
.lead .meme span{font-size:clamp(1.2rem,2.6vw,2rem)}
figcaption{font-family:"Old Standard TT",serif;font-style:italic;font-size:.84rem;color:var(--muted);margin-top:5px;text-align:center}
/* layout */
.cols{display:grid;grid-template-columns:1fr 320px;gap:34px;margin-top:6px}
.full>.secblock.cont{margin-top:0}
.full .sec-grid{grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}
.cols>*,.lead>*,.profile>*,.sec-grid>*{min-width:0}
/* sections */
.secblock{margin-top:28px}
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:6px 16px;flex-wrap:wrap;
  border-top:4px double var(--ink);border-bottom:1px solid var(--ink);padding:6px 0 4px;margin-bottom:14px}
.sec-name{font-family:"UnifrakturMaguntia",serif;font-weight:400;font-size:clamp(1.7rem,3vw,2.3rem);line-height:1}
.sec-desk{font-family:"Old Standard TT",serif;font-style:italic;color:var(--muted)}
.sec-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:0 28px}
.sec-grid article{border-top:1px solid var(--rule);padding:12px 0 16px}
.sec-grid article.wide{grid-column:1/-1}
article h3{font-family:"Old Standard TT",Georgia,serif;font-weight:700;font-size:1.34rem;line-height:1.14;margin:4px 0 8px}
article p{text-align:justify;hyphens:auto}
.stat{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;border-top:1px dotted var(--rule);border-bottom:1px dotted var(--rule);
  padding:3px 0;margin:0 0 9px}
.stat .n{font-family:"Old Standard TT",serif;font-weight:700;font-size:1.45rem;line-height:1;color:var(--accent)}
.stat .l{font-style:italic;font-size:.86rem;color:var(--muted);line-height:1.2}
.byline{font-family:"Old Standard TT",serif;font-style:italic;font-size:.86rem;color:var(--muted);margin-top:8px}
.byline a{text-decoration:none;border-bottom:1px dotted var(--muted)}
/* section flavours */
.sec-sucesos article{position:relative;border:1px dashed var(--ink);padding:14px 14px 16px;margin:10px 0}
.sec-sucesos .sec-grid{gap:0 18px}
.sec-sucesos article::after{content:attr(data-exp);position:absolute;top:10px;right:-4px;transform:rotate(8deg);
  font-family:"IM Fell English SC",serif;font-size:.78rem;color:var(--accent);border:2px solid var(--accent);padding:1px 6px;opacity:.8}
.sec-economia .board,.sec-deportes .board,.sec-tiempo .board{margin-bottom:12px}
.board table{background:rgba(255,248,225,.1)}
.up{color:var(--good);font-weight:700}.down{color:var(--accent);font-weight:700}
.weather{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-bottom:12px}
.weather>div{border:1px solid var(--ink);padding:8px;text-align:center;background:rgba(255,248,225,.1)}
.weather .ic{font-size:1.9rem;line-height:1.1}
.weather b{display:block;font-family:"IM Fell English SC",serif;font-weight:400}
.weather span{font-style:italic;font-size:.85rem;color:var(--muted)}
.sec-politica article.radio{font-family:"Courier Prime","Courier New",monospace;background:rgba(40,30,20,.06);padding:12px 14px;margin:10px 0;border:1px solid var(--rule)}
.sec-politica article.radio h3{font-family:"Courier Prime","Courier New",monospace;font-size:1.12rem}
.sec-politica article.radio .kicker::before{content:"\25C9 EN DIRECTO · ";color:var(--accent)}
.sec-faro{position:relative;border:3px double #6b5214;padding:4px 18px 14px;
  background:conic-gradient(from 200deg at 92% 8%,rgba(212,170,60,.22),transparent 12%,rgba(212,170,60,.16) 24%,transparent 36%)}
.sec-faro .sec-name::before{content:"\263C ";color:#6b5214}
.sec-faro .sec-head{border-top:none}
.sec-voz article{background:rgba(255,248,225,.14);border:1px solid var(--rule);border-left:4px solid var(--ink);padding:12px 14px;margin:10px 0}
.voz-cta{border:2px dashed var(--ink);padding:12px 16px;text-align:center;font-style:italic;margin-bottom:10px}
.voz-cta a{font-family:"IM Fell English SC",serif;font-style:normal;color:var(--accent);font-size:1.08rem}
.sec-opinion article.column{background:rgba(255,248,225,.12);border:1px solid var(--ink);outline:1px solid var(--ink);outline-offset:-6px;padding:20px 24px 12px}
.sec-opinion article.column h3{font-style:italic;text-align:center;font-size:1.7rem}
.sec-opinion article.column .kicker,.sec-opinion article.column .byline{text-align:center}
.sec-opinion article.column .cbody{column-count:2;column-gap:28px;column-rule:1px solid var(--rule)}
.sec-opinion article.column p{margin-bottom:10px}
.sec-opinion article.column p:first-of-type::first-letter{font-family:"Old Standard TT",serif;font-weight:700;float:left;font-size:2.7rem;line-height:.85;padding:4px 6px 0 0}
/* aside */
aside .box{border:3px double var(--ink);padding:14px 16px;margin-bottom:20px;background:rgba(255,248,225,.08)}
aside h4{font-family:"IM Fell English SC",serif;font-weight:400;font-size:1.14rem;letter-spacing:.05em;text-align:center;
  border-bottom:1px solid var(--ink);padding-bottom:6px;margin-bottom:10px}
.quote{font-family:"Old Standard TT",serif;font-style:italic;font-size:1.18rem;line-height:1.35;text-align:center}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th{text-align:left;font-family:"IM Fell English SC",serif;font-weight:400;color:var(--muted);font-size:.9rem;border-bottom:1px solid var(--ink);padding:4px}
td{padding:5px 4px;border-bottom:1px dotted var(--rule)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr.top td{color:var(--accent);font-weight:700}
.win{color:var(--good);font-weight:700}.loss{color:var(--accent);font-weight:700}
.tablewrap{overflow-x:auto}
/* comments and forms */
.comentarios .lista{margin-bottom:14px}
.comentario{border-bottom:1px dotted var(--rule);padding:10px 0}
.comentario b{font-family:"IM Fell English SC",serif;font-weight:400;font-size:1.05rem}
.comentario time{font-style:italic;font-size:.82rem;color:var(--muted);margin-left:8px}
.comentario p{margin-top:4px;white-space:pre-wrap}
form.papel{display:grid;gap:10px;max-width:760px}
form.papel label{font-family:"IM Fell English SC",serif;font-size:1.02rem}
form.papel input[type=text],form.papel textarea{width:100%;font:inherit;color:var(--ink);background:rgba(255,248,225,.25);
  border:1px solid var(--ink);padding:8px 10px}
form.papel textarea{min-height:120px;resize:vertical}
form.papel button{justify-self:start;font-family:"IM Fell English SC",serif;font-size:1.08rem;letter-spacing:.06em;
  background:var(--ink);color:var(--paper);border:0;padding:9px 18px;cursor:pointer}
form.papel button:disabled{opacity:.6;cursor:wait}
.hp{position:absolute;left:-9999px}
.msg{font-style:italic}
footer{text-align:center;font-family:"Old Standard TT",serif;font-style:italic;font-size:.82rem;color:#b7a786;padding:0 16px 40px;max-width:900px;margin:0 auto}
/* player page / archive */
.profile{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin:22px 0 26px}
.profile h2{font-family:"Old Standard TT",serif;font-weight:700;font-size:clamp(2.2rem,5vw,3.2rem);line-height:1.02}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.kpi{border:1px solid var(--ink);padding:10px;text-align:center}
.kpi .n{font-family:"Old Standard TT",serif;font-weight:700;font-size:1.55rem;color:var(--accent);line-height:1.1}
.kpi .l{font-style:italic;font-size:.76rem;color:var(--muted)}
.spark{width:100%;height:auto}
.archive li{list-style:none;border-top:1px solid var(--ink);padding:12px 0;display:grid;grid-template-columns:180px 1fr;gap:14px}
.archive li a{font-family:"Old Standard TT",serif;font-weight:700;font-size:1.16rem;text-decoration:none}

/* column rules between the stories, like a printed page */
.sec-grid{overflow:hidden}
.sec-grid>*{position:relative}
.sec-grid>*::before{content:"";position:absolute;left:-15px;top:12px;bottom:12px;border-left:1px solid var(--rule)}
.sec-sucesos article::after{right:2px}
/* the placard: the figure printed big where a photo would go */
.cartel{border:4px double var(--ink);text-align:center;padding:12px 10px 14px;margin:6px 0 12px;
  background:radial-gradient(ellipse at center,rgba(255,248,225,.22),rgba(255,248,225,.04))}
.cartel .o{font-size:.8rem;letter-spacing:.6em;color:var(--muted)}
.cartel .n{font-family:"Old Standard TT",serif;font-weight:700;font-size:clamp(2.8rem,5vw,4rem);line-height:1;color:var(--accent);margin:4px 0}
.cartel .l{font-family:"IM Fell English SC",serif;font-size:1rem;letter-spacing:.05em;color:var(--ink)}
.sec-politica article.radio .cartel .n{font-family:"Courier Prime","Courier New",monospace}
/* small sections side by side */
.sec-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:0 28px;margin-top:28px}
.sec-row>.secblock{margin-top:0;position:relative}
.sec-row>.secblock+.secblock::before{content:"";position:absolute;left:-15px;top:0;bottom:0;border-left:1px solid var(--rule)}
.sec-row .sec-grid{grid-template-columns:1fr}
/* small ads and notices that fill the holes */
.anuncio{border:2px solid var(--ink);outline:1px solid var(--ink);outline-offset:-6px;margin:12px 0 16px;padding:16px 16px 14px;
  text-align:center;display:flex;flex-direction:column;justify-content:center;gap:6px;background:rgba(255,248,225,.1)}
.anuncio .t{font-family:"Old Standard TT",serif;font-weight:700;text-transform:uppercase;letter-spacing:.06em;font-size:1.25rem;line-height:1.1}
.anuncio .s{font-family:"IM Fell English SC",serif;font-size:1.05rem}
.anuncio p{font-size:.95rem;line-height:1.45;font-style:italic}
.anuncio .pie{font-family:"IM Fell English SC",serif;font-size:.85rem;color:var(--muted);border-top:1px solid var(--rule);padding-top:5px;margin-top:4px}
.anuncio ul{list-style:none;text-align:left;font-size:.95rem;line-height:1.4}
.anuncio li{padding:6px 0;border-bottom:1px dotted var(--rule)}
.anuncio li:last-child{border-bottom:0}
.k-busca .t{font-family:"UnifrakturMaguntia",serif;text-transform:none;font-weight:400;font-size:2.3rem;letter-spacing:0}
.k-busca .who{font-family:"Anton",Impact,sans-serif;font-size:1.9rem;text-transform:uppercase;letter-spacing:.04em;line-height:1}
.k-busca .rec{font-family:"Old Standard TT",serif;font-weight:700;font-size:1.15rem;color:var(--accent)}
.k-esquela{border:5px solid var(--ink);outline-color:transparent}
.k-esquela .cruz{font-size:1.8rem;line-height:1}
.k-esquela .t{font-size:1.05rem}
.k-esquela .n,.k-dato .n{font-family:"Old Standard TT",serif;font-weight:700;font-size:2.6rem;line-height:1;color:var(--accent)}
.k-dato{border-style:dashed}
.k-dato .l{font-family:"IM Fell English SC",serif}
.k-taller .t{font-family:"Anton",Impact,sans-serif;font-weight:400;font-size:1.7rem;letter-spacing:.08em}
.k-publi{background:rgba(42,32,23,.85);color:var(--paper);outline-color:var(--paper)}
.k-publi .t{font-family:"Anton",Impact,sans-serif;font-weight:400;font-size:1.6rem}
.k-publi p{color:#e6dac0}
.k-clasif .t,.k-horos .t{font-family:"IM Fell English SC",serif;text-transform:none;font-weight:400;font-size:1.25rem;
  border-bottom:1px solid var(--ink);padding-bottom:5px}
.k-erratas{outline:none;border-width:1px}
.anuncio.mini{margin:16px 0 0}
.sec-grid>article.grow{display:flex;flex-direction:column}
.sec-grid>article.grow .cartel{flex:1;display:flex;flex-direction:column;justify-content:center}
.sec-row>.secblock{display:flex;flex-direction:column}
.sec-row .voz-cta{flex:1;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:6px}
.k-loteria .nums{display:flex;justify-content:center;gap:8px}
.k-loteria .nums span{display:inline-block;min-width:2.2em;border:2px solid var(--ink);border-radius:50%;padding:6px 4px;
  font-family:"Old Standard TT",serif;font-weight:700;font-size:1.3rem;color:var(--accent);background:rgba(255,248,225,.25)}
.k-cartelera .t{font-family:"UnifrakturMaguntia",serif;text-transform:none;font-weight:400;font-size:1.9rem;letter-spacing:0}
.k-farmacia .t{font-family:"Anton",Impact,sans-serif;font-weight:400;letter-spacing:.08em;color:var(--good)}
.k-alquila{border-style:double;border-width:4px;outline:none}
.sec-row .sec-opinion article.column .cbody{column-count:1}


/* format 2: the news well and the data band */
.sec-grid.pozo{grid-template-columns:repeat(auto-fill,minmax(360px,1fr))}
.full .sec-grid.pozo{grid-template-columns:repeat(auto-fill,minmax(360px,1fr))}
/* medium stories: the picture sits beside the text, like a printed module */
@media (min-width:1000px){
  .pozo article.pieza-mediana figure{float:left;width:46%;margin:4px 18px 8px 0}
  .pozo article.pieza-mediana .stat{overflow:hidden}
}
.datos-grid{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-bottom:14px}
.datos-grid .board{margin-bottom:0}
.sec-grid>article.wide2{grid-column:span 2}
.pozo article.s-sucesos{border:1px dashed var(--ink);padding:14px 14px 16px;margin:10px 0;background:rgba(255,248,225,.06)}
.pozo article.s-sucesos::after{content:attr(data-exp);position:absolute;top:10px;right:2px;transform:rotate(8deg);
  font-family:"IM Fell English SC",serif;font-size:.78rem;color:var(--accent);border:2px solid var(--accent);padding:1px 6px;opacity:.8}
.pozo article.s-el-faro-de-la-esperanza{border:3px double #6b5214;padding:12px 14px 14px;margin:10px 0;
  background:conic-gradient(from 200deg at 92% 8%,rgba(212,170,60,.22),transparent 12%,rgba(212,170,60,.16) 24%,transparent 36%)}
.pozo article.s-el-faro-de-la-esperanza .kicker::before{content:"\263C ";color:#6b5214}
.pozo article.radio{font-family:"Courier Prime","Courier New",monospace;background:rgba(40,30,20,.06);padding:12px 14px;margin:10px 0;border:1px solid var(--rule)}
.pozo article.radio h3{font-family:"Courier Prime","Courier New",monospace;font-size:1.12rem}
/* weights: big stories take two columns and run their text in two columns, without growing the type */
.sec-grid{grid-auto-flow:row dense}
.sec-grid>article.pieza-grande{grid-column:span 2}
.pieza-grande h3{font-size:1.7rem;line-height:1.12}
.pieza-grande .txt{column-count:2;column-gap:26px;column-rule:1px solid var(--rule)}
.pieza-grande .txt p{break-inside:avoid-column}
.txt p+p{margin-top:8px;text-indent:1.2em}
p.sub{font-family:"Old Standard TT",serif;font-style:italic;font-size:1.05rem;line-height:1.35;color:var(--muted);margin:-2px 0 10px;text-align:left}
.lead p.sub{font-size:1.25rem;margin-bottom:14px}
.ante{font-family:"Old Standard TT",serif;font-style:italic;font-size:.95rem;color:var(--ink);border-bottom:1px solid var(--rule);
  display:inline-block;padding:0 6px 1px 0;margin-top:4px}
/* formats with a look of their own */
article.f-telegrama{font-family:"Courier Prime","Courier New",monospace;background:rgba(255,248,225,.14);border:1px solid var(--rule);padding:12px 14px}
article.f-telegrama h3,article.f-telegrama .txt{font-family:"Courier Prime","Courier New",monospace;text-transform:uppercase;letter-spacing:.02em}
article.f-telegrama .txt{font-size:.92rem}
article.f-esquela{border:5px solid var(--ink)!important;padding:14px 16px;text-align:center}
article.f-esquela h3::before{content:"† ";}
article.f-esquela .txt p{text-align:center;font-style:italic}
article.f-carta-al-director .txt p,article.f-editorial .txt p{font-style:italic}
article.f-editorial h3{text-transform:uppercase;letter-spacing:.03em}
article.f-anuncio-por-palabras{border:2px solid var(--ink);outline:1px solid var(--ink);outline-offset:-6px;padding:14px 16px;text-align:center}
article.f-entrevista .txt p:first-child{font-weight:700}
article.f-parte-policial .txt,article.f-juicio .txt{border-left:3px double var(--ink);padding-left:10px}
article.f-ranking .txt p,article.f-encuesta .txt p{font-family:"Old Standard TT",serif}
article.f-parte-meteorologico{background:rgba(160,175,190,.08)}
/* briefs column */
.breves .breve{padding:10px 0;border-bottom:1px dotted var(--rule)}
.breves .breve:last-child{border-bottom:0}
.breve .bk{font-family:"IM Fell English SC",serif;font-size:.85rem;color:var(--accent);letter-spacing:.05em}
.breve h5{font-family:"Old Standard TT",serif;font-weight:700;font-size:1.06rem;line-height:1.2;margin:2px 0 4px}
.breve p{font-size:.92rem;line-height:1.45;text-align:justify;hyphens:auto}
.breve.f-telegrama p,.breve.f-telegrama h5{font-family:"Courier Prime","Courier New",monospace;text-transform:uppercase;font-size:.85rem}
.anuncios-extra .anuncio{margin:0 0 20px}
/* pastimes: the lottery and the horoscope */
.pasa-grid{display:grid;grid-template-columns:1fr 1fr;gap:28px}
.sorteo,.horoscopo{border:3px double var(--ink);padding:16px 18px;background:rgba(255,248,225,.1)}
.sorteo h4,.horoscopo h4{font-family:"UnifrakturMaguntia",serif;font-weight:400;font-size:1.7rem;text-align:center;
  border-bottom:1px solid var(--ink);padding-bottom:6px;margin-bottom:12px}
.bolas{display:flex;justify-content:center;gap:14px;margin:6px 0 10px}
.bolas span{width:3.2rem;height:3.2rem;border-radius:50%;border:3px solid var(--ink);display:flex;align-items:center;justify-content:center;
  font-family:"Old Standard TT",serif;font-weight:700;font-size:1.5rem;color:var(--accent);
  background:radial-gradient(circle at 35% 30%,rgba(255,248,225,.7),rgba(255,248,225,.1))}
.sorteo .origen{text-align:center;font-style:italic;color:var(--muted);font-size:.92rem;margin-bottom:8px}
.sorteo form{margin-top:12px;border-top:1px dashed var(--ink);padding-top:12px}
.sorteo .nums{display:flex;gap:10px}
.sorteo .nums input{width:5em;font:inherit;font-size:1.3rem;text-align:center;color:var(--ink);background:rgba(255,248,225,.25);border:2px solid var(--ink);padding:6px}
.horoscopo ul{list-style:none}
.horoscopo li{padding:8px 0;border-bottom:1px dotted var(--rule);line-height:1.45}
.horoscopo li:last-child{border-bottom:0}
.horoscopo .glifo{font-size:1.3rem;margin-right:6px;color:var(--accent)}

/* who are you */
nav.menu a.yo{border:1px solid var(--ink);padding:0 8px}
.yo-dialog{border:3px double var(--ink);background:var(--paper);color:var(--ink);padding:18px 22px;max-width:min(560px,92vw)}
.yo-dialog::backdrop{background:rgba(20,14,8,.6)}
.yo-dialog h4{font-family:"UnifrakturMaguntia",serif;font-weight:400;font-size:1.8rem}
.yo-lista{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:4px 12px;margin:6px 0}
.yo-op{font-family:"IM Fell English SC",serif;font-size:1.02rem;cursor:pointer}
.yo-botones{display:flex;gap:10px;flex-wrap:wrap}
form.papel button.sec{background:transparent;color:var(--ink);border:1px solid var(--ink)}
.yo-nota{margin:0 0 4px}
/* reactions and comments on each story */
.rx{display:flex;flex-wrap:wrap;align-items:center;gap:4px;margin-top:10px;padding-top:6px;border-top:1px dotted var(--rule);position:relative}
.rx button{font:inherit;font-size:.92rem;background:transparent;border:1px solid transparent;border-radius:12px;padding:1px 6px;cursor:pointer;color:var(--ink);line-height:1.4}
.rx button:hover{border-color:var(--rule);background:rgba(255,248,225,.25)}
.rx button b{font-family:"Old Standard TT",serif;font-size:.85rem;margin-left:3px}
.rx button.mine{border-color:var(--accent);background:rgba(122,36,22,.08)}
.rx-c{position:relative;margin-left:auto}
.rx-pop{display:none;position:absolute;right:0;top:100%;z-index:20;width:min(340px,86vw);background:var(--paper);
  border:3px double var(--ink);padding:10px 12px;box-shadow:0 10px 30px rgba(0,0,0,.35);text-align:left}
.rx-c:hover .rx-pop,.rx-c.open .rx-pop,.rx-c:focus-within .rx-pop{display:block}
.rx-pop .comentario{padding:6px 0}
.rx-pop .comentario p{font-size:.92rem;text-align:left}
.rx-list{max-height:260px;overflow:auto;margin-bottom:6px}
.rx-form{display:grid;gap:6px}
.rx-form textarea{font:inherit;font-size:.92rem;min-height:60px;resize:vertical;color:var(--ink);background:rgba(255,248,225,.3);border:1px solid var(--ink);padding:6px}
.rx-form button{justify-self:start;font-family:"IM Fell English SC",serif;background:var(--ink);color:var(--paper);border:0;padding:5px 12px;border-radius:0}
.lead .rx{margin-top:14px}
.breve .rx button{font-size:.82rem;padding:0 4px}
.sec-grid{overflow-x:clip;overflow-y:visible}  /* clips the column rules, lets comment pop-ups drop down */
.visitas b{font-family:"IM Fell English SC",serif;font-weight:400;color:var(--ink)}

/* sagas */
a.saga{display:inline-block;font-family:"IM Fell English SC",serif;font-size:.85rem;letter-spacing:.06em;text-decoration:none;
  background:var(--ink);color:var(--paper);padding:1px 8px;margin-bottom:4px}
a.saga:hover{background:var(--accent)}
.sagas{grid-template-columns:repeat(auto-fill,minmax(360px,1fr))}
.saga-ficha.est-cerrado{opacity:.75}
.saga-ficha h3{font-size:1.5rem}
ol.capitulos{margin:8px 0 0 18px}
ol.capitulos li{padding:4px 0;border-bottom:1px dotted var(--rule)}
ol.capitulos li p{font-size:.9rem;font-style:italic;color:var(--muted)}
ul.elenco{list-style:none;columns:2;column-gap:30px}
ul.elenco li{padding:6px 0;break-inside:avoid;border-bottom:1px dotted var(--rule)}
/* weather forecasts */
.weather.con-prevision{grid-template-columns:repeat(auto-fill,minmax(210px,1fr))}
.weather .prevision{font-family:"Old Standard TT",serif;font-style:italic;font-size:.9rem;line-height:1.35;margin-top:6px;text-align:left}
/* Runeterra card and achievements */
.ficha-rt .titulo-rt{font-family:"UnifrakturMaguntia",serif;font-size:1.6rem;text-align:center;line-height:1.1}
.ficha-rt .faccion{text-align:center;font-style:italic}
.ficha-rt ul,.logros ul{list-style:none}
.ficha-rt li,.logros li{padding:5px 0;border-bottom:1px dotted var(--rule);font-size:.92rem}
.logros li span{display:inline-block;width:1.6em}

/* readers, pool, LP market, league */
.mas-reido ol{margin-left:18px}.mas-reido li{padding:5px 0;border-bottom:1px dotted var(--rule);font-size:.92rem}
.mas-reido .emojis{display:block;font-size:.85rem;color:var(--muted)}
.cotilla ul,.ace-box ul{list-style:none}.cotilla li,.ace-box li{padding:5px 0;border-bottom:1px dotted var(--rule);font-size:.92rem}
.porra-box{border:3px double var(--ink);padding:16px 18px;background:rgba(255,248,225,.1)}
.porra-box h4{font-family:"UnifrakturMaguntia",serif;font-weight:400;font-size:1.7rem;text-align:center;border-bottom:1px solid var(--ink);padding-bottom:6px;margin-bottom:12px}
.porra-box select{font:inherit;color:var(--ink);background:rgba(255,248,225,.25);border:1px solid var(--ink);padding:6px;width:100%}
.porra-box form{margin-top:10px;border-top:1px dashed var(--ink);padding-top:10px}
.pasa-grid{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.bolsa{margin-top:14px}
.rx .rx-share{margin-left:4px}
.rx-rep{display:flex;gap:6px;align-items:center;font-size:.85rem}
@media (max-width:980px){
  .cols,.lead,.profile{grid-template-columns:1fr}
  .lead .txt,.sec-opinion article.column .cbody{column-count:1}
}
@media (max-width:700px){
  .sec-grid>article.pieza-grande{grid-column:auto}
  .pieza-grande .txt{column-count:1}
  .pasa-grid,.datos-grid{grid-template-columns:1fr}
  .sec-grid>article.wide2{grid-column:auto}
}
@media (max-width:560px){
  body{font-size:16px}
  .paper{padding:20px 16px 26px;margin:10px auto 26px}
  .paper::before{inset:5px}
  .topline{justify-content:center}
  .kpis{grid-template-columns:repeat(2,1fr)}
  .archive li{grid-template-columns:1fr;gap:2px}
  .sec-grid{grid-template-columns:1fr}
}
@media (prefers-reduced-motion:reduce){.ticker .run{animation:none;padding-left:12px}}
""".replace("NOISE", NOISE)

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Anton&family=Courier+Prime&family=IM+Fell+English+SC'
         '&family=Libre+Caslon+Text:ital,wght@0,400;0,700;1,400'
         '&family=Old+Standard+TT:ital,wght@0,400;0,700;1,400&family=UnifrakturMaguntia&display=swap" '
         'rel="stylesheet">')

LEGAL = ("{title} no está avalado por Riot Games y no refleja las opiniones de Riot Games ni de "
         "nadie implicado oficialmente en la producción o gestión de League of Legends. League of Legends "
         "y Riot Games son marcas registradas de Riot Games, Inc. Sátira entre amigos: datos reales, "
         "mala leche inventada.")

# Reader comments and proposals talk straight to Supabase from the browser.
LECTORES_JS = r"""(function(){
  var C = window.FEEDER || {}, ok = !!(C.url && C.key);
  var H = ok ? {apikey: C.key, Authorization: 'Bearer ' + C.key} : {};
  var EDICION = document.body.getAttribute('data-edicion'), PAGINA = document.body.getAttribute('data-pagina');
  var EMOJIS = ['😂', '💀', '🔥', '🤡', '🧂', '👑'];
  function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function when(t){try{return new Date(t).toLocaleString('es-ES',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});}catch(e){return '';}}
  function api(path, opts){opts=opts||{};var h=Object.assign({},H,opts.headers||{});
    return fetch(C.url.replace(/\/$/,'')+path,Object.assign({},opts,{headers:h})).then(function(r){
      if(!r.ok) return r.text().then(function(t){var e=new Error(t||r.status);e.status=r.status;throw e;}); return r;});}
  function post(table, row){return api('/rest/v1/'+table,{method:'POST',headers:{'Content-Type':'application/json',Prefer:'return=minimal'},body:JSON.stringify(row)});}
  function remember(k,v){try{if(v===undefined)return localStorage.getItem(k)||'';localStorage.setItem(k,v);}catch(e){return '';}}

  // ------------------------------------------------------------------ who is reading
  // Each reader says once who they are (one or several accounts, for the smurfs); it stays in
  // this browser and fills every form: comments, proposals, lottery tickets.
  var Yo = {
    get: function(){
      try { var y = JSON.parse(localStorage.getItem('feeder-yo') || 'null'); if (y && y.nombre) return y; } catch(e){}
      var n = remember('feeder-nombre'); return n ? {nombre: n, cuentas: []} : null;
    },
    set: function(y){
      try { if (y) { localStorage.setItem('feeder-yo', JSON.stringify(y)); localStorage.setItem('feeder-nombre', y.nombre); }
            else { localStorage.removeItem('feeder-yo'); localStorage.removeItem('feeder-nombre'); } } catch(e){}
      Yo.render();
    },
    lector: function(){
      var id = remember('feeder-lector');
      if (!id) { id = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2);
                 remember('feeder-lector', id); }
      return id;
    },
    render: function(){
      var y = Yo.get(), b = document.getElementById('yo-btn');
      if (b) b.textContent = y ? 'Eres: ' + y.nombre : '¿Quién eres?';
      Array.prototype.forEach.call(document.querySelectorAll('form input[name=nombre]'), function(inp){
        var label = inp.closest('label'), f = inp.form, note = f.querySelector('.yo-nota');
        if (y) {
          inp.value = y.nombre; if (label) label.hidden = true;
          if (!note) { note = document.createElement('p'); note.className = 'yo-nota small'; f.insertBefore(note, f.firstElementChild); }
          note.innerHTML = 'Escribes como <b></b> · <a href="#">cambiar</a>';
          note.querySelector('b').textContent = y.nombre;
          note.querySelector('a').onclick = function(e){ e.preventDefault(); Yo.open(); };
        } else { if (label) label.hidden = false; if (note) note.remove(); }
      });
    },
    open: function(done){
      var d = document.getElementById('yo-dialog');
      if (!d) {
        d = document.createElement('dialog'); d.id = 'yo-dialog'; d.className = 'yo-dialog';
        var lista = (C.jugadores || []).map(function(j){
          return '<label class="yo-op"><input type="checkbox" value="'+esc(j.slug)+'" data-alias="'+esc(j.alias)+'"> '+esc(j.alias)+'</label>';
        }).join('');
        d.innerHTML = '<form method="dialog" class="papel"><h4>¿Quién eres?</h4>'+
          '<p class="small">Marca tu cuenta, o tus cuentas si tienes smurfs (la primera que marques será tu nombre). '+
          'Se guarda en este navegador: no tendrás que volver a escribirlo para comentar, reaccionar, proponer noticias '+
          'o jugar al sorteo. Tus visitas a las páginas quedarán apuntadas con ese nombre.</p>'+
          '<div class="yo-lista">'+lista+'</div>'+
          '<label>¿No estás en la lista? Tu nombre<input type="text" name="otro" maxlength="40"></label>'+
          '<div class="yo-botones"><button type="submit" value="ok">Guardar</button>'+
          '<button type="button" class="sec" data-a="cancel">Cancelar</button>'+
          '<button type="button" class="sec" data-a="forget">Olvidarme</button></div></form>';
        document.body.appendChild(d);
        var order = [];
        d.addEventListener('change', function(e){
          if (e.target.type !== 'checkbox') return;
          order = order.filter(function(s){ return s !== e.target.value; });
          if (e.target.checked) order.push(e.target.value);
        });
        d.querySelector('[data-a=cancel]').onclick = function(){ d.close(); };
        d.querySelector('[data-a=forget]').onclick = function(){ Yo.set(null); d.close(); };
        d.querySelector('form').addEventListener('submit', function(){
          var otro = d.querySelector('[name=otro]').value.trim();
          var checked = order.map(function(s){ return d.querySelector('input[value="'+s+'"]'); }).filter(Boolean);
          var nombre = checked.length ? checked[0].getAttribute('data-alias') : otro;
          if (!nombre) return;
          Yo.set({nombre: nombre.slice(0, 40), cuentas: checked.map(function(i){ return i.value; })});
          if (d._done) { var f = d._done; d._done = null; f(Yo.get()); }
        });
        d._order = function(v){ order = v; };
      }
      var y = Yo.get() || {cuentas: []};
      Array.prototype.forEach.call(d.querySelectorAll('input[type=checkbox]'), function(i){ i.checked = y.cuentas.indexOf(i.value) >= 0; });
      d._order((y.cuentas || []).slice());
      d.querySelector('[name=otro]').value = y.cuentas && y.cuentas.length ? '' : (y.nombre || '');
      d._done = done || null;
      if (d.showModal) d.showModal(); else d.setAttribute('open', '');
    },
    // a name for a form: the saved identity, or the one just typed (saved for next time)
    remember: function(nombre){ if (!Yo.get() && nombre) Yo.set({nombre: nombre.slice(0, 40), cuentas: []}); }
  };
  window.FeederYo = Yo;
  var yb = document.getElementById('yo-btn');
  if (yb) yb.addEventListener('click', function(e){ e.preventDefault(); Yo.open(); });
  Yo.render();

  // ------------------------------------------------------------------ letters to the editor (whole edition)
  var box = document.getElementById('comentarios');
  if (box) {
    var lista = box.querySelector('.lista'), form = box.querySelector('form'), msg = box.querySelector('.msg');
    var ed = box.getAttribute('data-edicion');
    if (!ok) { lista.innerHTML = '<p class="small">Los comentarios se activarán en cuanto se configure la base de datos.</p>'; form.hidden = true; }
    else {
      var load = function(){
        api('/rest/v1/comentarios?select=nombre,texto,created_at&edicion=eq.'+ed+'&pieza=is.null&order=created_at.asc')
          .then(function(r){return r.json();}).then(function(rows){
            lista.innerHTML = rows.length ? rows.map(function(c){return '<div class="comentario"><b>'+esc(c.nombre)+
              '</b><time>'+when(c.created_at)+'</time><p>'+esc(c.texto)+'</p></div>';}).join('')
              : '<p class="small">Nadie ha comentado todavía. Sé el primero en hurgar en la herida.</p>';
          }).catch(function(){lista.innerHTML='<p class="small">No se han podido cargar los comentarios.</p>';});
      };
      load();
      form.addEventListener('submit', function(ev){
        ev.preventDefault(); if (form.web.value) return;
        var nombre = form.nombre.value.trim(), texto = form.texto.value.trim();
        if (!nombre || !texto) return;
        form.querySelector('button').disabled = true; msg.textContent = 'Enviando…';
        Yo.remember(nombre);
        post('comentarios', {edicion:ed, nombre:nombre.slice(0,40), texto:texto.slice(0,1000)})
          .then(function(){form.texto.value='';msg.textContent='Publicado.';load();})
          .catch(function(){msg.textContent='No se pudo enviar. Inténtalo de nuevo.';})
          .then(function(){form.querySelector('button').disabled=false;});
      });
    }
  }

  // ------------------------------------------------------------------ reactions and comments on each story
  var piezas = document.querySelectorAll('[data-pieza]');
  if (EDICION && piezas.length) {
    var rx = {}, com = {}, mine = {};
    var bars = {};
    Array.prototype.forEach.call(piezas, function(el){
      var id = el.getAttribute('data-pieza'), host = el.classList.contains('lead') ? el.firstElementChild : el;
      var d = document.createElement('div'); d.className = 'rx'; d.setAttribute('data-id', id);
      d.innerHTML = EMOJIS.map(function(e){ return '<button type="button" class="rx-e" data-e="'+e+'">'+e+'<b></b></button>'; }).join('') +
        '<button type="button" class="rx-share" title="Compartir esta noticia">↗</button>' +
        '<span class="rx-c"><button type="button" class="rx-com" aria-label="Comentarios">💬<b></b></button>' +
        '<div class="rx-pop"><div class="rx-list"></div><form class="rx-form"><textarea name="texto" maxlength="800" ' +
        'placeholder="¿Qué opinas de esto?" required></textarea>' +
        '<label class="rx-rep" hidden><input type="checkbox" name="rep"> Es mi derecho de réplica: soy el aludido</label>' +
        '<button type="submit">Comentar</button><span class="msg small"></span></form></div></span>';
      var jug = el.getAttribute('data-jugador');
      var showRep = function(){ var y = Yo.get(); d.querySelector('.rx-rep').hidden = !(jug && y && (y.cuentas || []).indexOf(jug) >= 0); };
      showRep(); d.querySelector('.rx-c').addEventListener('mouseenter', showRep);
      d.querySelector('.rx-share').addEventListener('click', function(){
        var url = location.href.split('#')[0] + '#p-' + id, t = (el.querySelector('h2,h3,h5') || {}).textContent || document.title;
        if (navigator.share) navigator.share({title: t, url: url}).catch(function(){});
        else window.open('https://wa.me/?text=' + encodeURIComponent(t + ' ' + url), '_blank', 'noopener');
      });
      host.appendChild(d); bars[id] = d;
      d.querySelector('.rx-com').addEventListener('click', function(){ d.querySelector('.rx-c').classList.toggle('open'); });
      Array.prototype.forEach.call(d.querySelectorAll('.rx-e'), function(b){
        b.addEventListener('click', function(){ react(id, b.getAttribute('data-e')); });
      });
      d.querySelector('.rx-form').addEventListener('submit', function(ev){
        ev.preventDefault();
        var f = ev.target, texto = f.texto.value.trim(); if (!texto) return;
        var send = function(y){
          if (!y) return;
          f.querySelector('button').disabled = true; f.querySelector('.msg').textContent = 'Enviando…';
          if (f.rep.checked && !f.querySelector('.rx-rep').hidden) {
            if (texto.length < 10) { f.querySelector('.msg').textContent = 'La réplica necesita al menos 10 caracteres.'; f.querySelector('button').disabled = false; return; }
            post('replicas', {edicion: EDICION, pieza: Number(id), nombre: y.nombre, texto: texto.slice(0, 800)})
              .then(function(){ f.texto.value = ''; f.rep.checked = false;
                                f.querySelector('.msg').textContent = 'Réplica enviada: saldrá en la próxima edición.'; })
              .catch(function(){ f.querySelector('.msg').textContent = 'No se pudo enviar la réplica.'; })
              .then(function(){ f.querySelector('button').disabled = false; });
            return;
          }
          post('comentarios', {edicion: EDICION, pieza: Number(id), nombre: y.nombre, texto: texto.slice(0, 600)})
            .then(function(){ f.texto.value = ''; f.querySelector('.msg').textContent = '';
                              (com[id] = com[id] || []).push({nombre: y.nombre, texto: texto, created_at: new Date().toISOString()}); paint(id); })
            .catch(function(){ f.querySelector('.msg').textContent = 'No se pudo enviar.'; })
            .then(function(){ f.querySelector('button').disabled = false; });
        };
        var y = Yo.get(); if (y) send(y); else Yo.open(send);
      });
    });
    var paint = function(id){
      var d = bars[id]; if (!d) return;
      Array.prototype.forEach.call(d.querySelectorAll('.rx-e'), function(b){
        var who = (rx[id] || {})[b.getAttribute('data-e')] || [];
        b.querySelector('b').textContent = who.length ? who.length : '';
        b.classList.toggle('mine', !!mine[id + b.getAttribute('data-e')]);
        b.title = who.length ? who.join(', ') : 'Reaccionar';
      });
      var cs = com[id] || [];
      d.querySelector('.rx-com b').textContent = cs.length ? cs.length : '';
      d.querySelector('.rx-list').innerHTML = cs.length ? cs.map(function(c){
        return '<div class="comentario"><b>'+esc(c.nombre)+'</b><time>'+when(c.created_at)+'</time><p>'+esc(c.texto)+'</p></div>';
      }).join('') : '<p class="small">Sin comentarios todavía.</p>';
    };
    var react = function(id, e){
      if (!ok || mine[id + e]) return;
      var y = Yo.get(), name = y ? y.nombre : 'anónimo';
      mine[id + e] = true; ((rx[id] = rx[id] || {})[e] = rx[id][e] || []).push(name); paint(id);
      post('reacciones', {edicion: EDICION, pieza: Number(id), emoji: e, lector: Yo.lector(), nombre: y ? y.nombre : null})
        .catch(function(err){ if (err.status !== 409) { mine[id + e] = false; rx[id][e].pop(); paint(id); } });
    };
    Object.keys(bars).forEach(paint);
    if (ok) {
      var me = Yo.lector();
      api('/rest/v1/reacciones?select=pieza,emoji,nombre,lector&edicion=eq.' + EDICION).then(function(r){ return r.json(); })
        .then(function(rows){
          rx = {};
          rows.forEach(function(x){ ((rx[x.pieza] = rx[x.pieza] || {})[x.emoji] = rx[x.pieza][x.emoji] || []).push(x.nombre || 'anónimo');
                                    if (x.lector === me) mine[x.pieza + x.emoji] = true; });
          Object.keys(bars).forEach(paint);
        }).catch(function(){});
      api('/rest/v1/comentarios?select=pieza,nombre,texto,created_at&edicion=eq.' + EDICION + '&pieza=not.is.null&order=created_at.asc')
        .then(function(r){ return r.json(); })
        .then(function(rows){ com = {}; rows.forEach(function(c){ (com[c.pieza] = com[c.pieza] || []).push(c); });
                              Object.keys(bars).forEach(paint); }).catch(function(){});
    }
  }

  // ------------------------------------------------------------------ visits: who reads what
  if (ok && PAGINA) {
    var today = new Date().toISOString().slice(0, 10), key = 'feeder-v-' + PAGINA;
    if (remember(key) !== today) {
      var yv = Yo.get();
      post('visitas', {pagina: PAGINA, nombre: yv ? yv.nombre : null, lector: Yo.lector()})
        .then(function(){ remember(key, today); }).catch(function(){});
    }
  }
  Array.prototype.forEach.call(document.querySelectorAll('[data-visitas]'), function(el){
    if (!ok) { el.textContent = 'Se verá en cuanto se configure la base de datos.'; return; }
    api('/rest/v1/visitas?select=nombre,lector,created_at&pagina=eq.' + encodeURIComponent(el.getAttribute('data-visitas')) +
        '&order=created_at.desc&limit=1000').then(function(r){ return r.json(); }).then(function(rows){
      var names = {}, anon = {}, order = [];
      rows.forEach(function(v){
        if (v.nombre) { if (!names[v.nombre]) { names[v.nombre] = 0; order.push(v.nombre); } names[v.nombre]++; }
        else anon[v.lector || Math.random()] = 1;
      });
      var n = Object.keys(anon).length;
      var parts = order.map(function(nm){ return '<b>' + esc(nm) + '</b>' + (names[nm] > 1 ? ' (' + names[nm] + ')' : ''); });
      if (n) parts.push(n + ' anónimo' + (n > 1 ? 's' : ''));
      el.innerHTML = parts.length ? parts.join(', ') : 'Nadie todavía.';
    }).catch(function(){ el.textContent = 'No se han podido cargar las visitas.'; });
  });

  // ------------------------------------------------------------------ lottery tickets
  var bf = document.getElementById('boleto');
  if (bf) {
    var bmsg = bf.querySelector('.msg'), cnt = document.getElementById('boletos-cuenta');
    if (!ok) { bf.querySelector('button').disabled = true; bmsg.textContent = 'El sorteo se abrirá en cuanto se configure la base de datos.'; }
    else {
      var count = function(){
        api('/rest/v1/boletos?select=id&limit=1&created_at=gt.'+encodeURIComponent(bf.getAttribute('data-desde')),
            {headers:{Prefer:'count=exact'}}).then(function(r){
          var n = (r.headers.get('content-range')||'').split('/')[1]; if (cnt && n && n !== '*') cnt.textContent = n;
        }).catch(function(){});
      };
      count();
      bf.addEventListener('submit', function(ev){
        ev.preventDefault(); if (bf.web.value) return;
        var nums = [bf.n1, bf.n2, bf.n3].map(function(i){ return parseInt(i.value, 10); });
        if (nums.some(function(n){ return isNaN(n) || n < 0 || n > 99; })) { bmsg.textContent = 'Elige tres números del 0 al 99.'; return; }
        var nombre = bf.nombre.value.trim(); if (!nombre) return;
        Yo.remember(nombre);
        bf.querySelector('button').disabled = true; bmsg.textContent = 'Sellando…';
        post('boletos', {nombre:nombre.slice(0,40), numeros:nums})
          .then(function(){ bmsg.textContent = 'Boleto sellado: ' + nums.join(' · ') + '. Suerte mañana.'; count(); })
          .catch(function(){ bmsg.textContent = 'No se pudo sellar el boleto. Inténtalo de nuevo.'; })
          .then(function(){ bf.querySelector('button').disabled = false; });
      });
    }
  }

  // ------------------------------------------------------------------ the pool: who will be the worst tomorrow
  var pz = document.getElementById('porra');
  if (pz) {
    var zmsg = pz.querySelector('.msg'), zc = document.getElementById('porra-cuenta');
    if (!ok) { pz.querySelector('button').disabled = true; zmsg.textContent = 'La porra se abrirá en cuanto se configure la base de datos.'; }
    else {
      var zcount = function(){
        api('/rest/v1/porras?select=id&limit=1&created_at=gt.'+encodeURIComponent(pz.getAttribute('data-desde')),
            {headers:{Prefer:'count=exact'}}).then(function(r){
          var n = (r.headers.get('content-range')||'').split('/')[1]; if (zc && n && n !== '*') zc.textContent = n;
        }).catch(function(){});
      };
      zcount();
      pz.addEventListener('submit', function(ev){
        ev.preventDefault(); if (pz.web.value) return;
        var nombre = pz.nombre.value.trim(), pred = pz.prediccion.value; if (!nombre || !pred) return;
        Yo.remember(nombre);
        pz.querySelector('button').disabled = true; zmsg.textContent = 'Apostando…';
        post('porras', {nombre: nombre.slice(0, 40), lector: Yo.lector(), prediccion: pred})
          .then(function(){ zmsg.textContent = 'Apuesta hecha: ' + pz.prediccion.options[pz.prediccion.selectedIndex].text + '. Vale la última que hagas.'; zcount(); })
          .catch(function(){ zmsg.textContent = 'No se pudo apostar. Inténtalo de nuevo.'; })
          .then(function(){ pz.querySelector('button').disabled = false; });
      });
    }
  }

  // ------------------------------------------------------------------ proposals
  var pf = document.getElementById('proponer');
  if (pf) {
    var pmsg = pf.querySelector('.msg');
    if (!ok) { pf.querySelector('fieldset').disabled = true; pmsg.textContent = 'El buzón se abrirá en cuanto se configure la base de datos.'; }
    else {
      pf.addEventListener('submit', function(ev){
        ev.preventDefault(); if (pf.web.value) return;
        var file = pf.imagen.files[0], btn = pf.querySelector('button');
        if (file && file.size > 5*1024*1024) { pmsg.textContent = 'La imagen pesa más de 5 MB.'; return; }
        btn.disabled = true; pmsg.textContent = 'Enviando a la redacción…';
        Yo.remember(pf.nombre.value.trim());
        var up = Promise.resolve(null);
        if (file) {
          var ext = (file.name.split('.').pop()||'jpg').toLowerCase().replace(/[^a-z0-9]/g,'');
          var path = Date.now()+'-'+Math.random().toString(36).slice(2,8)+'.'+ext;
          up = api('/storage/v1/object/propuestas/'+path,{method:'POST',headers:{'Content-Type':file.type||'image/jpeg'},body:file})
            .then(function(){return path;});
        }
        up.then(function(path){
          return post('propuestas', {nombre:pf.nombre.value.trim().slice(0,40),titulo:pf.titulo.value.trim().slice(0,140),
              texto:pf.texto.value.trim().slice(0,2000),imagen:path});
        }).then(function(){pf.reset();Yo.render();
          pmsg.textContent='¡Recibida! La redacción la revisará y saldrá en La Voz de Runeterra de la próxima edición.';})
          .catch(function(){pmsg.textContent='No se pudo enviar. Revisa los campos e inténtalo de nuevo.';})
          .then(function(){btn.disabled=false;});
      });
    }
  }
})();
// When the sidebar ends, the rest of the stories take the whole width of the page instead of
// leaving an empty column on the right. It cuts between sections or between rows of stories,
// wherever the cut lands closest to the bottom of the sidebar.
(function(){
  var cols = document.querySelector('.cols.edicion');
  if (!cols) return;
  var main = cols.querySelector('main'), aside = cols.querySelector('aside');
  var full = document.createElement('div');
  full.className = 'full';
  cols.parentNode.insertBefore(full, cols.nextSibling);
  var moved = [];
  function move(node, target){ moved.push([node, node.parentNode, node.nextSibling]); target.appendChild(node); }
  function restore(){
    for (var i = moved.length - 1; i >= 0; i--) moved[i][1].insertBefore(moved[i][0], moved[i][2]);
    moved = []; full.innerHTML = '';
  }
  var tpl = document.getElementById('relleno');
  var pool = tpl ? Array.prototype.slice.call(tpl.content.children) : [];
  var used = 0;
  function clearFill(){
    Array.prototype.forEach.call(document.querySelectorAll('.sec-grid .anuncio, .anuncios-extra .anuncio'),
                                 function(a){ a.remove(); });
    used = 0;
  }
  // A story much shorter than its neighbours gets a small ad underneath, if one fits in the hole.
  function fillGaps(){
    Array.prototype.forEach.call(document.querySelectorAll('.sec-grid > article'), function(a){
      if (used >= pool.length) return;
      var h = a.getBoundingClientRect().height, inner = 0;
      Array.prototype.forEach.call(a.children, function(c){ inner = Math.max(inner, c.getBoundingClientRect().bottom); });
      if (h - (inner - a.getBoundingClientRect().top) < 150) return;
      var el = pool[used].cloneNode(true);
      el.classList.add('mini');
      a.appendChild(el);
      if (a.getBoundingClientRect().height > h + 1) el.remove(); else used++;
    });
  }
  // Fill the empty cells at the end of every grid with the small ads, stretched to the row height.
  function fill(){
    Array.prototype.forEach.call(document.querySelectorAll('.sec-grid'), function(g){
      var cols = getComputedStyle(g).gridTemplateColumns.split(' ').filter(Boolean).length;
      if (cols < 2) return;
      if (!g.children.length) return;
      // cells taken in the last row, measured (big stories span two columns)
      var st = getComputedStyle(g), cw = parseFloat(st.gridTemplateColumns), gap = parseFloat(st.columnGap) || 0;
      var lastTop = -1e9, taken = 0;
      Array.prototype.forEach.call(g.children, function(c){ lastTop = Math.max(lastTop, Math.round(c.getBoundingClientRect().top)); });
      Array.prototype.forEach.call(g.children, function(c){
        var b = c.getBoundingClientRect();
        if (Math.round(b.top) === lastTop) taken += Math.max(1, Math.round((b.width + gap) / (cw + gap)));
      });
      var rem = Math.max(0, cols - taken);
      while (rem > 0 && used < pool.length) {
        var el = pool[used++].cloneNode(true), span = (rem >= 2 && el.dataset.wide) ? 2 : 1;
        el.style.gridColumn = 'span ' + span;
        g.appendChild(el);
        rem -= span;
      }
    });
  }
  // Whatever hole is left under a story with a placard, the placard grows into it.
  function grow(){
    Array.prototype.forEach.call(document.querySelectorAll('.sec-grid > article.con-cartel'), function(a){
      a.classList.remove('grow');
      var inner = 0;
      Array.prototype.forEach.call(a.children, function(c){ inner = Math.max(inner, c.getBoundingClientRect().bottom); });
      if (a.getBoundingClientRect().bottom - inner > 40) a.classList.add('grow');
    });
  }
  // never fewer than three small ads: whatever did not fit in a hole goes under the briefs
  function spare(){
    var box = document.querySelector('.anuncios-extra');
    while (box && used < Math.min(3, pool.length)) {
      var el = pool[used++].cloneNode(true); el.classList.add('mini'); box.appendChild(el);
    }
  }
  function run(){ clearFill(); restore(); layout(); fill(); fillGaps(); spare(); grow(); }
  function layout(){
    var mr = main.getBoundingClientRect(), ar = aside.getBoundingClientRect();
    if (ar.left < mr.right) return;                       // phone: sidebar already below
    var last = aside.lastElementChild, top = mr.top, best = null;
    var h = last ? last.getBoundingClientRect().bottom - ar.top : 0;
    Array.prototype.forEach.call(main.children, function(sec){
      var y = sec.getBoundingClientRect().top - top;
      if (y > h / 2) consider({y: y, sec: sec});
      var grid = sec.classList.contains('sec-row') ? null : sec.querySelector('.sec-grid'), seen = {};
      if (!grid) return;
      Array.prototype.forEach.call(grid.children, function(a){
        var t = Math.round(a.getBoundingClientRect().top);
        if (t - top > h / 2 && !seen[t] && a !== grid.firstElementChild) { seen[t] = 1; consider({y: t - top, sec: sec, grid: grid, row: t}); }
      });
    });
    function consider(c){ if (!best || Math.abs(c.y - h) < Math.abs(best.y - h)) best = c; }
    if (!best || Math.abs(mr.height - h) <= Math.abs(best.y - h)) return;
    var rest = best.sec;
    if (best.grid) {
      var cont = document.createElement('section'), g = document.createElement('div');
      cont.className = best.sec.className + ' cont'; g.className = best.grid.className; cont.appendChild(g); full.appendChild(cont);
      Array.prototype.slice.call(best.grid.children).forEach(function(a){
        if (Math.round(a.getBoundingClientRect().top) >= best.row) move(a, g);
      });
      rest = best.sec.nextElementSibling;
    }
    while (rest) { var next = rest.nextElementSibling; move(rest, full); rest = next; }
  }
  var timer;
  function later(){ clearTimeout(timer); timer = setTimeout(run, 120); }
  run();
  window.addEventListener('load', later);
  window.addEventListener('resize', later);
  document.addEventListener('load', function(e){ if (e.target.tagName === 'IMG') later(); }, true);
  if (document.fonts) document.fonts.ready.then(later);
})();
"""

# Changes whenever the stylesheet or the script change, so browsers never keep an old copy.
ASSET_VERSION = hashlib.sha1((CSS + LECTORES_JS).encode("utf-8")).hexdigest()[:10]


ROSTER = []  # [{slug, alias}] of the players, for the "who are you?" picker; set by build_site
ACE = {}     # data/ace_league.json; set by build_site


def _e(x):
    return escape(str(x), quote=True)


def _date(s):
    y, m, d = map(int, s.split("-"))
    return date(y, m, d)


def page(cfg, title, body, rel, edition=None, description="", pagina="", image=None):
    if edition:
        top = (f'<div class="topline"><span>{_e(long_date(_date(edition["date"])).capitalize())}</span>'
               f'<span>Año I · Edición nº {edition["number"]}</span><span>Precio: 1 LP</span></div>')
    else:
        top = ('<div class="topline"><span>Fundado en la Grieta del Invocador</span><span>Año I</span>'
               '<span>Precio: 1 LP</span></div>')
    feeder = json.dumps({"url": cfg.get("supabase_url", ""), "key": cfg.get("supabase_anon_key", ""),
                         "jugadores": ROSTER}, ensure_ascii=False)
    if edition:
        pagina = pagina or f"edicion:{edition['date']}"
    marks = (f' data-edicion="{_e(edition["date"])}"' if edition else "") + (f' data-pagina="{_e(pagina)}"' if pagina else "")
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<meta name="description" content="{_e(description or cfg['site_tagline'])}">
<meta property="og:site_name" content="{_e(cfg['site_title'])}">
<meta property="og:title" content="{_e(title)}">
<meta property="og:description" content="{_e(description or cfg['site_tagline'])}">
<meta property="og:type" content="article">
{f'<meta property="og:image" content="{_e(image)}"><meta name="twitter:card" content="summary_large_image">' if image else ""}
{FONTS}
<link rel="stylesheet" href="{rel}style.css?v={ASSET_VERSION}">
</head>
<body{marks}>
<div class="wrap"><div class="paper">
<header class="mast">
{top}
<a class="title" href="{rel}index.html">{_e(cfg['site_title'])}</a>
<p class="tagline">{_e(cfg['site_tagline'])}</p>
<div class="rules"></div>
<nav class="menu"><a href="{rel}index.html">Portada</a><a href="{rel}archivo.html">Hemeroteca</a><a href="{rel}jugadores.html">Jugadores</a><a href="{rel}sagas.html">Sagas</a><a class="cta" href="{rel}proponer.html">Proponer noticia</a><a href="#" class="yo" id="yo-btn">¿Quién eres?</a></nav>
</header>
{body}
</div></div>
<footer>{_e(LEGAL.format(title=cfg['site_title']))}</footer>
<script>window.FEEDER={feeder};</script>
<script src="{rel}lectores.js?v={ASSET_VERSION}" defer></script>
</body>
</html>
"""


# --------------------------------------------------------------------------- tables
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
            f'<td class="num">{r["d"]}</td><td class="num">{dmg}</td></tr>')
    return ('<div class="tablewrap"><table><thead><tr><th>#</th><th>Jugador</th><th class="num">V–D</th>'
            '<th class="num">KDA</th><th class="num">Muertes</th><th class="num">Daño</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>"
            '<p class="small" style="margin-top:6px">De peor a mejor. «Daño»: cuota media del daño a campeones de su equipo.</p>')


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
            '<p class="small" style="margin-top:6px">El peor del día suma 5 puntos, el segundo 3, el tercero 2 y el cuarto 1.</p>')


def _market_table(games):
    """'Cotizaciones de la Lonja': gold share vs damage share per player (non-support games)."""
    agg = defaultdict(lambda: [0, 0.0, 0.0])
    for g in games:
        if g.get("support"):
            continue
        a = agg[g["alias"]]
        a[0] += 1; a[1] += g["gold_share"]; a[2] += g["dmg_share"]
    if not agg:
        return ""
    rows = []
    for alias, (n, gold, dmg) in sorted(agg.items(), key=lambda kv: (kv[1][2] - kv[1][1]) / kv[1][0]):
        gold, dmg = gold / n, dmg / n
        diff = (dmg - gold) * 100
        cls, arrow = ("up", "▲") if diff >= 0 else ("down", "▼")
        rows.append(f'<tr><td>{_e(alias)}</td><td class="num">{fmt_pct(gold)}</td><td class="num">{fmt_pct(dmg)}</td>'
                    f'<td class="num {cls}">{arrow} {fmt_num(abs(diff), 1)}</td></tr>')
    return ('<div class="board"><h4 class="kicker">Cotizaciones del día</h4><div class="tablewrap"><table><thead><tr>'
            '<th>Valor</th><th class="num">Oro cobrado</th><th class="num">Daño entregado</th><th class="num">Balance</th>'
            '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div></div>')


def _weather(ranking, forecasts=None):
    if not ranking:
        return ""
    forecasts = forecasts or {}
    cards = []
    for r in sorted(ranking, key=lambda r: -r["dead"]):
        m = r["dead"] / 60
        ic, txt = (("☀", "Despejado") if m < 3 else ("⛅", "Nubes y claros") if m < 8 else
                   ("☁", "Cubierto") if m < 15 else ("☂", "Niebla espesa") if m < 25 else ("☠", "Niebla Negra"))
        fc = f'<p class="prevision">{_e(forecasts[r["slug"]])}</p>' if forecasts.get(r.get("slug")) else ""
        cards.append(f'<div><div class="ic">{ic}</div><b>{_e(r["alias"])}</b><span>{txt} · {int(m)} min en gris</span>{fc}</div>')
    return f'<div class="board weather{" con-prevision" if forecasts else ""}">' + "".join(cards) + '</div>'


# --------------------------------------------------------------------------- articles
def _saga(it, rel=""):
    sg = it.get("saga")
    if not sg:
        return ""
    cap = "Último capítulo" if sg.get("estado") == "cerrado" else f"Capítulo {sg['capitulo']}"
    return f'<a class="saga" href="{rel}sagas.html#{_e(sg["id"])}">{_e(sg["titulo"])} · {cap}</a>'


def _kicker(it, rel=""):
    section = "EL FARO DE LA ESPERANZA" if it.get("section") == "MENCIÓN" else it["section"]  # older editions
    desk = it.get("desk") or DESKS.get(section, "")
    return (_saga(it, rel) + f'<div class="kicker">{_e(section)}'
            + (f'<span class="desk"> · {_e(desk)}</span>' if desk else "") + '</div>')


# Official champion art from Riot's Data Dragon CDN (allowed for free fan projects that carry
# Riot's legal notice). Display names ("Kai'Sa") are turned back into Data Dragon ids.
DDRAGON_IDS = {"wukong": "MonkeyKing", "nunu & willump": "Nunu", "nunu y willump": "Nunu",
               "renata glasc": "Renata", "kog'maw": "KogMaw", "rek'sai": "RekSai", "k'sante": "KSante",
               "leblanc": "Leblanc", "dr. mundo": "DrMundo", "jarvan iv": "JarvanIV", "bel'veth": "Belveth"}

CAPTIONS = [
    "{champ}, en una imagen de archivo, minutos antes de que le tocara a {alias}.",
    "Fotografía de {champ} tomada por los Centinelas de la Luz como prueba del delito.",
    "{champ}, con cara de decepción tras la partida de {alias}.",
    "Retrato oficial de {champ}. Sus abogados piden que no se le relacione con {alias}.",
    "{champ}, ayer, preguntando quién le había hecho esto.",
    "La Comisaría de Piltover difunde esta imagen de {champ} por si alguien reconoce al culpable.",
    "{champ} posa para la portada sin saber todavía lo que le esperaba.",
    "Imagen de {champ} recuperada de entre la Niebla Negra.",
]

# Classic top/bottom meme text for the automatic champion pictures, by kind of story.
MEMES = {
    "portada": [("este es {alias}", "hoy ha hecho {wl}"), ("nadie:", "{alias}: {wl}")],
    "sucesos": [("cuando juegas {champ}", "y mueres {d} veces"), ("solo una pelea más", "{d} muertes después")],
    "economia": [("cobrar el {gold} del oro", "y hacer el {share} del daño"), ("el equipo invirtió en mí", "yo: {share} del daño")],
    "dano": [("¿daño?", "no sé qué es eso"), ("yo buscando el daño", "de {alias}")],
    "tiempo": [("{dead_mins} minutos en gris", "todo según el plan"), ("la pantalla gris", "mi segunda casa")],
    "racha": [("solo una más", "{n} derrotas después")],
    "pleno": [("solo una más", "{wl}")],
    "maldito": [("{champ} otra vez", "0–{n}")],
}


def _ddragon_id(name):
    key = name.strip().lower()
    if key in DDRAGON_IDS:
        return DDRAGON_IDS[key]
    if "'" in name or "." in name or " " in name:
        clean = "".join(ch for ch in name if ch.isalnum())
        return clean[0].upper() + clean[1:].lower() if "'" in name else clean
    return name


def _pick(options, seed):
    return options[sum(map(ord, seed)) % len(options)]


def _meme_text(it):
    top, bot = it.get("meme_arriba"), it.get("meme_abajo")
    if top or bot:
        return top or "", bot or ""
    if it.get("imagen"):
        return "", ""
    options = MEMES.get(it.get("kind"))
    if not options:
        return "", ""
    facts = dict(it.get("facts") or {})
    facts.setdefault("alias", it.get("alias") or "")
    try:
        t, b = _pick(options, it["headline"])
        return t.format(**facts), b.format(**facts)
    except (KeyError, IndexError):
        return "", ""


def _figure(it, rel):
    """Picture for a story: one the group sent (docs/img/) or the champion's official art as a meme."""
    size = ""
    if it.get("imagen"):
        src = f"{rel}img/{it['imagen']}"
        caption = it.get("pie") or ""
    else:
        size = ' width="1215" height="717"'  # Data Dragon splash size: keeps the page from jumping while it loads
        champ = it.get("campeon") or (it.get("facts") or {}).get("champ")
        if not champ:
            return ""
        src = f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{_ddragon_id(champ)}_0.jpg"
        caption = it.get("pie") or _pick(CAPTIONS, it["headline"]).format(
            champ=champ_name(champ), alias=it.get("alias") or "el grupo")
    top, bot = _meme_text(it)
    meme = (f'<div class="meme"><span>{_e(top)}</span><span>{_e(bot)}</span></div>' if top or bot else "")
    return (f'<figure><div class="ph"><img src="{_e(src)}"{size} alt="{_e(caption)}" loading="lazy" '
            f'onerror="this.closest(\'figure\').remove()">{meme}</div>'
            + (f'<figcaption>{_e(caption)}</figcaption>' if caption else "") + '</figure>')


def _has_picture(it):
    return bool(it.get("imagen") or it.get("campeon") or (it.get("facts") or {}).get("champ"))


def _stat(it):
    return (f'<div class="stat"><span class="n">{_e(it["stat"])}</span>'
            f'<span class="l">{_e(it["stat_label"])}</span></div>')


def _paras_html(text):
    return "".join(f"<p>{_e(p)}</p>" for p in str(text).split("\n\n") if p.strip())


PLAIN_FORMATS = ("noticia", "breve", "")


def _article(it, rel, image=False, cls="", attrs="", placard=False):
    who = ""
    if it.get("replica_de"):
        who = f'<div class="byline">Réplica de {_e(it["replica_de"])}, con la respuesta de la redacción</div>'
    elif it.get("lector"):
        who = f'<div class="byline">Enviado por {_e(it["lector"])}</div>'
    elif it.get("player"):
        who = (f'<div class="byline">Sobre <a href="{rel}jugadores/{_e(it["player"])}.html">'
               f'{_e(it["alias"])}</a></div>')
    stat = _stat(it) if it.get("stat") else ""
    fig = _figure(it, rel) if image else ""
    if placard and not fig and it.get("stat"):
        # Stories without a picture get their figure as a big printed placard where the photo would go.
        stat = (f'<div class="cartel"><div class="o">✦ ✦ ✦</div><div class="n">{_e(it["stat"])}</div>'
                f'<div class="l">{_e(it["stat_label"])}</div></div>')
        cls = (cls + " con-cartel").strip()
    formato = it.get("formato") or ""
    if it.get("peso"):
        cls = f'{cls} pieza-{it["peso"]} f-{slugify(formato)}'.strip()
    ante = f'<div class="ante">{_e(formato.capitalize())}</div>' if formato not in PLAIN_FORMATS else ""
    sub = f'<p class="sub">{_e(it["subtitulo"])}</p>' if it.get("subtitulo") else ""
    if it.get("id") is not None:
        attrs += f' data-pieza="{_e(it["id"])}" id="p-{_e(it["id"])}"'
    if it.get("player"):
        attrs += f' data-jugador="{_e(it["player"])}"'
    return (f'<article class="{cls}"{attrs}>{_kicker(it, rel)}{ante}'
            f'<h3>{_e(it["headline"])}</h3>{sub}{fig}{stat}<div class="txt">{_paras_html(it["body"])}</div>{who}</article>')


# --------------------------------------------------------------------------- sections
# key, title, desk, item sections it collects
BLOCKS = [
    ("sucesos", "Sucesos", "Comisaría de Piltover", {"SUCESOS"}),
    ("deportes", "Deportes", "Arena de Noxus", {"DEPORTES", "DERBI"}),
    ("economia", "Economía", "Lonja de Aguasturbias", {"ECONOMÍA", "AGRICULTURA"}),
    ("ciencia", "Ciencia y Daño", "Instituto Hextech de Piltover", {"DAÑO", "CIENCIA", "VAR"}),
    ("tiempo", "El Tiempo", "Islas de la Sombra", {"EL TIEMPO"}),
    ("sociedad", "Sociedad", "Ecos de Jonia", {"SOCIEDAD", "SALUD", "AUSENTES"}),
    ("politica", "Política y Radio", "Corte de Demacia · Radio Zaun", {"POLÍTICA", "COMUNICACIÓN"}),
    ("cultura", "Cultura", "Biblioteca de Shurima", {"CULTURA"}),
    ("reportajes", "Reportajes", "Corresponsales por toda Runeterra", set()),  # everything else
    ("voz", "La Voz de Runeterra", "Las noticias que mandan los lectores", {"LA VOZ DE RUNETERRA"}),
    ("opinion", "Opinión", "Tribuna libre", {"OPINIÓN", "CARTA DEL DIRECTOR", "CARTAS", "EDITORIAL"}),
    ("faro", "El Faro de la Esperanza", "Centinelas de la Luz", {"EL FARO DE LA ESPERANZA", "MENCIÓN"}),
]


def _block_of(section):
    for key, _, _, members in BLOCKS:
        if section in members:
            return key
    return "reportajes"


def _sections(ed, rest, rel, v2=False):
    groups = defaultdict(list)
    for it in rest:
        groups[_block_of(it.get("section", ""))].append(it)
    pics = {"left": 8 if v2 else 6}

    def arts(items, key):
        out = []
        if v2:
            items = sorted(items, key=lambda it: it.get("peso") != "grande")
        for i, it in enumerate(items):
            image = pics["left"] > 0 and (i < 2 or v2) and _has_picture(it)
            if image:
                pics["left"] -= 1
            cls, attrs = "", ""
            if key == "sucesos":
                attrs = f' data-exp="Expediente nº {ed["number"]}-{i + 1}"'
            elif key == "politica" and it.get("section") == "COMUNICACIÓN":
                cls = "radio"
            out.append(_article(it, rel, image=image, cls=cls, attrs=attrs, placard=True))
        return "".join(out)

    html, row = [], []

    def flush():
        html.append(row[0] if len(row) == 1 else
                    f'<div class="sec-row n{len(row)}">' + "".join(row) + '</div>')
        row.clear()

    for key, title, desk, _ in BLOCKS:
        items = groups.get(key, [])
        widget = ""
        if key == "deportes" and ed.get("ranking"):
            widget = '<div class="board"><h4 class="kicker">Resultados del día</h4>' + _ranking_table(ed["ranking"], rel) + '</div>'
        elif key == "economia" and items:
            widget = _market_table(ed.get("games", []))
        elif key == "tiempo" and items:
            widget = _weather(ed.get("ranking", []))
        elif key == "voz":
            widget = (f'<div class="voz-cta">¿Ha pasado algo que merezca portada? '
                      f'<a href="{rel}proponer.html">Envía tu noticia a la redacción</a> y saldrá aquí en la próxima edición.</div>')
        col = ed.get("columna") if key == "opinion" else None
        if not items and not col and not (key in ("deportes", "voz") and widget):
            continue
        body = arts(items, key)
        if col:
            paras = "".join(f"<p>{_e(p)}</p>" for p in col["cuerpo"])
            body = (f'<article class="wide column"><div class="kicker">La columna</div><h3>{_e(col["titulo"])}</h3>'
                    f'<div class="byline">Por {_e(col["autor"])}</div><div class="cbody">{paras}</div></article>') + body
        block = (f'<section class="secblock sec-{key}"><header class="sec-head"><h3 class="sec-name">{_e(title)}</h3>'
                 f'<span class="sec-desk">{_e(desk)}</span></header>{widget}<div class="sec-grid">{body}</div></section>')
        # Sections with a single story (or none) share a row, like the small pieces of a printed page.
        small = len(items) + (1 if col else 0) <= 1 and not any(it.get("peso") == "grande" for it in items)
        if small and key not in ("deportes", "economia", "tiempo"):
            row.append(block)
            if len(row) == 3:
                flush()
        else:
            if row:
                flush()
            html.append(block)
    if row:
        flush()
    return "".join(html)


OPINION_SECTIONS = {"OPINIÓN", "EDITORIAL", "CARTAS", "CARTA DEL DIRECTOR", "DERECHO DE RÉPLICA"}


def _sections_v2(ed, rest, rel):
    """Format-2 editions: Claude already chose what matters, so stories are not split into one
    section per topic (that left one story per section and rows full of holes). They share one
    news well, each with its own section label; the day's tables get a band of their own."""
    html = []
    games = ed.get("games") or []
    if ed.get("ranking"):
        market = _market_table(games)
        html.append(
            '<section class="secblock sec-datos" id="sec-datos"><header class="sec-head"><h3 class="sec-name">Resultados</h3>'
            '<span class="sec-desk">Arena de Noxus · Lonja de Aguasturbias · Islas de la Sombra</span></header>'
            f'<div class="datos-grid"><div class="board"><h4 class="kicker">Resultados del día</h4>'
            f'{_ranking_table(ed["ranking"], rel)}</div>{market}</div>{_bolsa(ed)}</section>')
    voz_items = [it for it in rest if it.get("lector")]
    opinion = [it for it in rest if not it.get("lector") and it.get("section") in OPINION_SECTIONS]
    weather_items = [it for it in rest if not it.get("lector") and it.get("section") == "EL TIEMPO"]
    ace_items = [it for it in rest if not it.get("lector") and it.get("section") == "ACE LEAGUE"]
    well = [it for it in rest if not it.get("lector") and it.get("section") not in OPINION_SECTIONS
            and it.get("section") not in ("EL TIEMPO", "ACE LEAGUE")]
    pics = {"left": 8}

    def card(it, i):
        image = pics["left"] > 0 and _has_picture(it)
        if image:
            pics["left"] -= 1
        sec = it.get("section", "")
        cls, attrs = f"s-{slugify(sec)}", ""
        if sec == "SUCESOS":
            attrs = f' data-exp="Expediente nº {ed["number"]}-{i + 1}"'
        elif sec == "COMUNICACIÓN":
            cls += " radio"
        return _article(it, rel, image=image, cls=cls, attrs=attrs, placard=True)

    if well:
        well = sorted(well, key=lambda it: it.get("peso") != "grande")
        html.append('<section class="secblock sec-actualidad" id="sec-actualidad"><header class="sec-head">'
                    '<h3 class="sec-name">Actualidad</h3><span class="sec-desk">Corresponsales por toda Runeterra</span>'
                    '</header><div class="sec-grid pozo">' + "".join(card(it, i) for i, it in enumerate(well))
                    + '</div></section>')
    if ace_items or _ace_matches():
        rows = "".join(f'<tr><td>{_e(m.get("fecha", ""))}</td><td>{_e(m.get("rival", ""))}</td>'
                       f'<td class="{"win" if m.get("resultado") == "victoria" else "loss" if m.get("resultado") == "derrota" else ""}">'
                       f'{_e((m.get("resultado") or "pendiente").capitalize())}</td><td>{_e(m.get("marcador", ""))}</td></tr>'
                       for m in _ace_matches(8))
        table = ('<div class="board"><h4 class="kicker">Calendario y resultados</h4><div class="tablewrap"><table><thead><tr>'
                 '<th>Fecha</th><th>Rival</th><th>Resultado</th><th>Marcador</th></tr></thead><tbody>' + rows
                 + '</tbody></table></div></div>') if rows else ""
        html.append(f'<section class="secblock sec-ace" id="sec-ace"><header class="sec-head"><h3 class="sec-name">'
                    f'{_e(ACE.get("competicion", "ACE League"))}</h3><span class="sec-desk">{_e(ACE.get("equipo", ""))} · '
                    f'{_e(ACE.get("division", ""))}</span></header>{table}'
                    + ('<div class="sec-grid pozo">' + "".join(card(it, i) for i, it in enumerate(ace_items)) + '</div>'
                       if ace_items else "") + '</section>')
    if ed.get("ranking"):
        forecasts = {t["jugador"]: t["texto"] for t in ed.get("tiempo") or []}
        html.append('<section class="secblock sec-tiempo" id="sec-tiempo"><header class="sec-head"><h3 class="sec-name">'
                    'El Tiempo</h3><span class="sec-desk">Islas de la Sombra · previsión de Madame Niebla</span></header>'
                    + _weather(ed["ranking"], forecasts)
                    + ('<div class="sec-grid pozo">' + "".join(card(it, i) for i, it in enumerate(weather_items)) + '</div>'
                       if weather_items else "") + '</section>')
    if voz_items:
        html.append('<section class="secblock sec-voz" id="sec-voz"><header class="sec-head"><h3 class="sec-name">'
                    'La Voz de Runeterra</h3><span class="sec-desk">Las noticias que mandan los lectores</span></header>'
                    '<div class="sec-grid pozo">' + "".join(card(it, i) for i, it in enumerate(voz_items)) + '</div></section>')
    col = ed.get("columna")
    if col or opinion:
        body = ""
        if col:
            paras = "".join(f"<p>{_e(p)}</p>" for p in col["cuerpo"])
            body = (f'<article class="{"wide2" if opinion else "wide"} column"><div class="kicker">La columna</div>'
                    f'<h3>{_e(col["titulo"])}</h3><div class="byline">Por {_e(col["autor"])}</div>'
                    f'<div class="cbody">{paras}</div></article>')
        body += "".join(card(it, i) for i, it in enumerate(opinion))
        html.append('<section class="secblock sec-opinion" id="sec-opinion"><header class="sec-head"><h3 class="sec-name">'
                    'Opinión</h3><span class="sec-desk">Tribuna libre</span></header>'
                    f'<div class="sec-grid">{body}</div></section>')
    return "".join(html)


# --------------------------------------------------------------------------- fillers
# Old newspapers never left a hole: they filled it with small ads, notices and odds and ends.
# The page script drops these into whatever gaps the stories leave, so they are built from the
# day's data but only the ones that fit end up on the page.
HOROSCOPO = {
    "top": ["Una isla desierta te espera. Nadie vendrá a ayudarte, como siempre.",
            "Los astros te aconsejan teleport. Tu equipo, que lo uses alguna vez."],
    "jungle": ["Marte en conjunción con el dragón: hoy tampoco llegarás a tiempo.",
               "Tus gankeos serán recordados. Sobre todo por el rival."],
    "mid": ["Saturno te pide que mires el minimapa. Tú, como siempre, no.",
            "Día propicio para el roaming. Tu torre opina lo contrario."],
    "adc": ["Venus te protege de todo menos del primer asesino que te vea.",
            "Un soporte entrará en tu vida. Y saldrá a los diez minutos."],
    "support": ["Tu generosidad será premiada con cero oro y ninguna gratitud.",
                "Los astros ven un ward en tu futuro. Uno."],
}
ROLE_NAMES = {"top": "Top", "jungle": "Jungla", "mid": "Mid", "adc": "Tirador", "support": "Soporte"}
MAX_ADS = 5   # small ads per edition; the page script always shows at least 3
SIGNOS = [("Top", "top", "♈"), ("Jungla", "jungle", "♏"), ("Mid", "mid", "♌"), ("Tirador", "adc", "♐"),
          ("Soporte", "support", "♓")]


def _horoscopo(ed):
    """Claude writes it in AI editions; otherwise the stock lines, rotating by date."""
    texts = {h["signo"]: h["texto"] for h in ed.get("horoscopo") or []}
    seed = sum(map(ord, ed["date"]))
    lis = "".join(
        f'<li><span class="glifo">{g}</span><b>{name}.</b> '
        f'{_e(texts.get(name) or HOROSCOPO[key][(seed + i) % len(HOROSCOPO[key])])}</li>'
        for i, (name, key, g) in enumerate(SIGNOS))
    return f'<div class="horoscopo"><h4>Horóscopo de Runeterra</h4><ul>{lis}</ul></div>'


def _sorteo(ed, rel, latest):
    from .sorteo import combination
    res = ed.get("sorteo")
    if not res:
        combo, origin = combination(ed)
        res = {"combinacion": combo, "origen": origin, "participantes": 0, "acertantes": [], "segundos": [], "bote": 0}
    bolas = "".join(f'<span>{n}</span>' for n in res["combinacion"])
    origen = ", ".join(res.get("origen") or [])
    if res["acertantes"]:
        verdict = ("¡Premio! Acertaron los tres números: <b>" + ", ".join(_e(a["nombre"]) for a in res["acertantes"])
                   + "</b>. Su nombre queda grabado como Oráculo de la Grieta.")
    elif res["participantes"]:
        verdict = (f'{res["participantes"]} boleto{"s" if res["participantes"] != 1 else ""} y ningún pleno. '
                   f'El bote sube a <b>{fmt_int(res.get("bote", 0))} LP</b>.')
    else:
        verdict = "Nadie jugó a este sorteo. El bote sigue esperando a alguien con valor."
    if res.get("segundos"):
        verdict += " Con dos aciertos: " + ", ".join(_e(a["nombre"]) for a in res["segundos"]) + "."
    form = ""
    if latest:
        desde = datetime.fromtimestamp(ed.get("generated_at", ed["window"][1]) / 1000, timezone.utc).isoformat()
        form = f"""<form class="papel boleto" id="boleto" data-desde="{_e(desde)}">
  <p class="small">Juega para el sorteo de mañana: tres números del 0 al 99. La combinación serán las muertes de los
  tres que más mueran. Boletos ya sellados: <b id="boletos-cuenta">0</b>.</p>
  <label>Tu nombre de invocador<input type="text" name="nombre" maxlength="40" required></label>
  <div class="nums"><input type="number" name="n1" min="0" max="99" required aria-label="Primer número">
  <input type="number" name="n2" min="0" max="99" required aria-label="Segundo número">
  <input type="number" name="n3" min="0" max="99" required aria-label="Tercer número"></div>
  <input class="hp" type="text" name="web" tabindex="-1" autocomplete="off" aria-hidden="true">
  <button type="submit">Sellar boleto</button><span class="msg"></span>
</form>"""
    return (f'<div class="sorteo"><h4>Sorteo de la Grieta · nº {ed["number"]}</h4><div class="bolas">{bolas}</div>'
            f'<p class="origen">Combinación ganadora: {_e(origen)}.</p><p>{verdict}</p>{form}</div>')


def _porra(ed, latest, seers):
    res = ed.get("porra") or {}
    lines = []
    if res.get("peor"):
        hits = ", ".join(_e(a["nombre"]) for a in res.get("acertantes", []))
        lines.append(f'<p>El peor de esta edición fue <b>{_e(res["peor"])}</b>. '
                     + (f'Lo vieron venir: <b>{hits}</b>.' if hits else
                        ("Nadie acertó." if res.get("participantes") else "Nadie apostó.")) + '</p>')
        if res.get("votos"):
            lines.append('<p class="small">Votos: ' + ", ".join(f'{_e(k)} ({n})' for k, n in res["votos"].items()) + '</p>')
    form = ""
    if latest:
        opts = "".join(f'<option value="{_e(r["slug"])}">{_e(r["alias"])}</option>' for r in ROSTER)
        desde = datetime.fromtimestamp(ed.get("generated_at", ed["window"][1]) / 1000, timezone.utc).isoformat()
        form = (f'<form class="papel porra" id="porra" data-desde="{_e(desde)}"><p class="small">¿Quién será el peor del '
                f'grupo en la próxima edición? Sin dinero: solo gloria. Apuestas ya hechas: <b id="porra-cuenta">0</b>.</p>'
                f'<label>Tu nombre de invocador<input type="text" name="nombre" maxlength="40" required></label>'
                f'<label>El peor será<select name="prediccion" required><option value="">Elige…</option>{opts}</select></label>'
                f'<input class="hp" type="text" name="web" tabindex="-1" autocomplete="off" aria-hidden="true">'
                f'<button type="submit">Apostar</button><span class="msg"></span></form>')
    rank = ""
    if seers:
        rank = ('<p class="small"><b>Videntes:</b> ' + ", ".join(f'{_e(n)} ({k})' for n, k in seers) + '</p>')
    return f'<div class="porra-box"><h4>La porra</h4>{"".join(lines)}{rank}{form}</div>'


def _pasatiempos(ed, rel, latest, seers=None):
    return (f'<section class="secblock sec-pasatiempos" id="sorteo"><header class="sec-head">'
            f'<h3 class="sec-name">Pasatiempos</h3><span class="sec-desk">Sorteo, porra y horóscopo</span></header>'
            f'<div class="pasa-grid">{_sorteo(ed, rel, latest)}{_porra(ed, latest, seers or [])}{_horoscopo(ed)}</div></section>')


def _bolsa(ed):
    b = ed.get("bolsa") or {}
    if not b.get("filas"):
        return ""

    def cell(e):
        if not e:
            return '<td>–</td><td class="num">–</td>'
        d = e.get("delta")
        cls, arrow = ("up", "▲") if (d or 0) > 0 else ("down", "▼") if (d or 0) < 0 else ("", "=")
        tag = f' <i>({_e(e["cambio"])})</i>' if e.get("cambio") else ""
        return (f'<td>{_e(e["posicion"])}{tag}</td><td class="num {cls}">'
                + (f'{arrow} {abs(d)}' if d is not None else "nuevo") + '</td>')
    rows = "".join(f'<tr><td>{_e(r["alias"])}</td>{cell(r.get("solo"))}{cell(r.get("flex"))}</tr>' for r in b["filas"])
    since = f' (frente al {short_date(_date(b["desde"]))})' if b.get("desde") else ""
    return (f'<div class="board bolsa"><h4 class="kicker">Bolsa de LP{_e(since)}</h4><div class="tablewrap"><table><thead><tr>'
            '<th>Valor</th><th>SoloQ</th><th class="num">LP</th><th>Flex</th><th class="num">LP</th></tr></thead><tbody>'
            + rows + '</tbody></table></div></div>')


def _ace_matches(limit=6):
    ms = sorted(ACE.get("partidos") or [], key=lambda m: m.get("fecha", ""))
    return ms[-limit:]


def _ace_box(rel):
    if not ACE:
        return ""
    ms = _ace_matches(4)
    if ms:
        lis = "".join(f'<li><span class="small">{_e(short_date(_date(m["fecha"])) if m.get("fecha") else "")}</span> '
                      f'vs <b>{_e(m.get("rival", "?"))}</b> · <span class="{"win" if m.get("resultado") == "victoria" else "loss" if m.get("resultado") == "derrota" else ""}">'
                      f'{_e((m.get("resultado") or "pendiente").capitalize())}</span>'
                      + (f' {_e(m["marcador"])}' if m.get("marcador") else "") + '</li>' for m in ms)
        inner = f'<ul class="ace">{lis}</ul>'
    else:
        inner = (f'<p class="small">{_e(ACE.get("historia", ""))} El calendario de la temporada saldrá aquí en cuanto '
                 'se apunten los partidos.</p>')
    return (f'<div class="box ace-box"><h4>{_e(ACE.get("competicion", "ACE League"))}</h4>'
            f'<p class="small" style="text-align:center"><b>{_e(ACE.get("equipo", ""))}</b> · {_e(ACE.get("division", ""))}</p>'
            f'{inner}</div>')


def _readers_boxes(ed, rel):
    out = []
    fb = ed.get("lectores_ayer") or {}
    top = (fb.get("mas_reaccionadas") or [])[:3]
    if top:
        lis = "".join(f'<li><a href="{rel}ediciones/{_e(fb["edicion"])}.html#p-{_e(t["pieza"])}">{_e(t["titular"])}</a>'
                      f'<span class="emojis">{"".join(f"{e}{n}" for e, n in t["emojis"].items())}</span></li>' for t in top)
        out.append(f'<div class="box mas-reido"><h4>Lo más reído de ayer</h4><ol>{lis}</ol></div>')
    cot = [c for c in (ed.get("cotillas") or []) if c["veces"] >= 1][:4]
    if cot:
        lis = "".join(f'<li><b>{_e(c["cotilla"])}</b> '
                      + ("se miró a sí mismo" if c["se_mira_a_si_mismo"] else f'miró la ficha de <b>{_e(c["ficha"])}</b>')
                      + f' {c["veces"]} {"vez" if c["veces"] == 1 else "veces"}</li>' for c in cot)
        out.append(f'<div class="box cotilla"><h4>El cotilla del día</h4><ul>{lis}</ul></div>')
    return "".join(out)


def _breves(items, rel):
    if not items:
        return ""
    out = []
    for it in items:
        who = (f' <a href="{rel}jugadores/{_e(it["player"])}.html">{_e(it["alias"])}</a>'
               if it.get("player") and it.get("alias") else "")
        out.append(f'<div class="breve f-{slugify(it.get("formato") or "")}" data-pieza="{_e(it["id"])}"><div class="bk">{_e(it["section"])}</div>'
                   f'<h5>{_e(it["headline"])}</h5>{_paras_html(it["body"])}'
                   + (f'<div class="byline">Sobre{who}</div>' if who else "") + '</div>')
    return '<div class="box breves"><h4>Breves</h4>' + "".join(out) + '</div>'


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def _fillers(ed):
    rk = ed.get("ranking") or []
    games = ed.get("games") or []
    if not rk:
        return ""
    day = short_date(_date(ed["date"]))
    by_d = max(rk, key=lambda r: r["d"])
    by_grey = max(rk, key=lambda r: r["dead"])
    by_kda = min(rk, key=lambda r: r["kda"])
    best = rk[-1]
    second = rk[1] if len(rk) > 1 else rk[0]
    seed = sum(map(ord, ed["date"]))
    out = []

    def add(kind, inner, wide=False):
        if inner:
            out.append(f'<div class="anuncio k-{kind}"' + (' data-wide="1"' if wide else '') + f'>{inner}</div>')

    add("busca", f'<div class="t">Se busca</div><div class="who">{_e(by_d["alias"])}</div>'
                 f'<p>Por alimentar al enemigo {by_d["d"]} veces en un solo día.</p>'
                 '<div class="rec">Recompensa: 1 LP</div><div class="pie">Comisaría de Piltover</div>')
    add("esquela", f'<div class="cruz">†</div><div class="t">El KDA de {_e(by_kda["alias"])}</div>'
                   f'<div class="n">{fmt_num(by_kda["kda"], 2)}</div>'
                   f'<p>Nos dejó el {_e(day)} tras {_plural(by_kda["losses"], "derrota")}. '
                   'Sus compañeros de equipo ruegan una oración y una partida menos.</p>')
    m = int(ed["totals"]["dead_seconds"] // 60)
    if m:
        add("dato", f'<div class="t">El dato</div><div class="n">{m}</div><div class="l">minutos en la pantalla gris</div>'
                    f'<p>Lo que duran {fmt_num(m / 45, 1)} capítulos de una serie. El grupo prefirió verlos en gris.</p>')
    if games:
        champ, n = Counter(g["champ"] for g in games).most_common(1)[0]
        deaths = sum(g["d"] for g in games if g["champ"] == champ)
        add("taller", f'<div class="t">Taller de Zaun</div><div class="s">Reparación de {_e(champ_name(champ))}</div>'
                      f'<p>¿Su campeón llega con {_plural(deaths, "muerte")} en {_plural(n, "partida")}? '
                      'Chapa, pintura y dignidad. Presupuesto sin compromiso.</p><div class="pie">Barrio de los Barones · Zaun</div>')
    add("clasif", '<div class="t">Anuncios por palabras</div><ul>'
                  f'<li><b>Se vende</b> pantalla gris, muy usada. Preguntar por {_e(by_grey["alias"])}.</li>'
                  f'<li><b>Se busca</b> dúo con paciencia infinita. Razón: {_e(second["alias"])}.</li>'
                  f'<li><b>Se ofrecen</b> clases de supervivencia. Profesor: {_e(best["alias"])}.</li></ul>', wide=True)
    add("aviso", f'<div class="t">Aviso</div><p>Se ruega a quien encuentre la dignidad de <b>{_e(second["alias"])}</b> '
                 'que la entregue en la Comisaría de Piltover. Se gratificará.</p>')
    add("publi", '<div class="t">¿Cansado de perder?</div><div class="s">Botón de rendición a domicilio</div>'
                 '<p>Rápido, discreto y sin esperar al minuto 15. Demacia no lo aprueba.</p>')
    if games:
        g = max(games, key=lambda g: g["d"])
        add("cartelera", f'<div class="t">Cartelera</div><div class="s">Teatro de Piltover</div>'
                         f'<p>Hoy, en sesión continua: <b>«{_e(champ_name(g["champ"]))} y las {g["d"]} muertes»</b>, '
                         f'con {_e(g["alias"])} en el papel principal. Final trágico.</p>')
    add("farmacia", f'<div class="t">Farmacia de guardia</div><div class="s">Dr. Mundo · Zaun</div>'
                    f'<p>Pociones de vida a granel. Atención preferente a {_e(by_d["alias"])}, '
                    f'que ayer gastó {by_d["d"]} vidas.</p>')
    worst = rk[0]
    add("alquila", f'<div class="t">Se alquila</div><p>Fuente de nexo, muy frecuentada, vistas a la pantalla gris. '
                   f'Razón: {_e(worst["alias"])}, que se pasa el día allí.</p>')
    add("erratas", f'<div class="t">Fe de erratas</div><p>En una edición anterior, donde decía «{_e(best["alias"])} jugó bien», '
                   f'debía decir «{_e(best["alias"])} jugó». Pedimos disculpas a los lectores.</p>')
    k = seed % len(out)
    return '<template id="relleno">' + "".join((out[k:] + out[:k])[:MAX_ADS]) + '</template>'


def _comments(ed):
    return f"""<section class="secblock comentarios" id="comentarios" data-edicion="{_e(ed['date'])}">
<header class="sec-head"><h3 class="sec-name">Cartas al director</h3><span class="sec-desk">Comentarios de los lectores sobre esta edición</span></header>
<div class="lista"><p class="small">Cargando comentarios…</p></div>
<form class="papel">
  <label>Tu nombre de invocador<input type="text" name="nombre" maxlength="40" required></label>
  <label>Tu comentario<textarea name="texto" maxlength="1000" required placeholder="Defiéndete, acusa o echa sal en la herida…"></textarea></label>
  <input class="hp" type="text" name="web" tabindex="-1" autocomplete="off" aria-hidden="true">
  <button type="submit">Enviar al periódico</button><span class="msg"></span>
</form>
</section>"""


def render_edition(cfg, ed, editions_until, rel, latest=False):
    items = ed["items"]
    lead = items[0] if items else None
    v2 = (ed.get("ai") or {}).get("formato") == 2
    rest = [it for it in items[1:] if not (v2 and it.get("peso") == "breve")]
    breves = [it for it in items[1:] if v2 and it.get("peso") == "breve"]
    ticker = " ".join(f"<span>{_e(i['headline'])}</span>" for i in items[:8])
    t = ed["totals"]
    lead_html = ""
    if lead:
        who = (f'<div class="who"><a href="{rel}jugadores/{_e(lead["player"])}.html">{_e(lead["alias"])}</a></div>'
               if lead.get("player") else "")
        sent = f'<div class="byline">Enviado por {_e(lead["lector"])}</div>' if lead.get("lector") else ""
        stat_box = (f'<div class="bigstat"><div class="n">{_e(lead["stat"])}</div>'
                    f'<div class="l">{_e(lead["stat_label"])}</div>{who}</div>') if lead.get("stat") else ""
        sub = f'<p class="sub">{_e(lead["subtitulo"])}</p>' if lead.get("subtitulo") else ""
        lead_html = (f'<section class="lead{" lead-v2" if v2 else ""}" data-pieza="{_e(lead.get("id", 0))}"><div>{_kicker(lead, rel)}'
                     f'<h2>{_e(lead["headline"])}</h2>{sub}<div class="txt">{_paras_html(lead["body"])}</div>{sent}</div>'
                     f'<div>{_figure(lead, rel)}{stat_box}</div></section><div class="orn">✦ ✦ ✦</div>')
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
<div class="cols edicion">
  <main>{_sections_v2(ed, rest, rel) if v2 else _sections(ed, rest, rel)}{_pasatiempos(ed, rel, latest, seers(editions_until))}{_comments(ed)}</main>{_fillers(ed)}
  <aside>
    <div class="box"><h4>General de la vergüenza</h4>{_general_table(board, rel)}</div>
    <div class="box"><h4>Frase del día</h4><p class="quote">«{_e(ed["frase"])}»</p></div>
    <div class="box"><h4>El día en cifras</h4>{totals}{writer}</div>
    {_readers_boxes(ed, rel)}
    {_breves(breves, rel)}
    {_ace_box(rel)}
    <div class="box"><h4>Quién ha leído esta edición</h4><p class="small visitas" data-visitas="edicion:{_e(ed["date"])}">Cargando…</p></div>
    <div class="anuncios-extra"></div>
    <div class="box"><h4>Buzón del lector</h4><p class="small" style="text-align:center">¿Tienes una noticia, una foto o un meme?
      <br><a href="{rel}proponer.html">Envíala a La Voz de Runeterra</a>.</p></div>
  </aside>
</div>"""
    title = f"{cfg['site_title']} · {short_date(_date(ed['date']))}"
    desc = lead["headline"] if lead else cfg["site_tagline"]
    image = None
    if lead and lead.get("imagen") and cfg.get("site_url"):
        image = cfg["site_url"].rstrip("/") + "/img/" + lead["imagen"]
    elif lead and (lead.get("campeon") or (lead.get("facts") or {}).get("champ")):
        image = ("https://ddragon.leagueoflegends.com/cdn/img/champion/splash/"
                 f"{_ddragon_id(lead.get('campeon') or lead['facts']['champ'])}_0.jpg")
    return page(cfg, title, body, rel, edition=ed, description=desc, image=image)


def render_sagas(cfg, canon, editions):
    """Every story thread of the newspaper, with its chapters."""
    dates = {e["date"] for e in editions}
    names = {s: p.get("alias", s) for s, p in canon["personajes"].items()}
    blocks = []
    hilos = sorted(canon["hilos"], key=lambda h: (canon_mod.hilo_estado(h) == "cerrado", h.get("abierto", "")))
    for h in hilos:
        est = canon_mod.hilo_estado(h)
        prot = ", ".join(f'<a href="jugadores/{_e(x)}.html">{_e(names.get(x, x))}</a>' for x in h.get("protagonistas", []))
        caps = "".join(
            f'<li><span class="small">{_e(short_date(_date(c["fecha"])))}</span> '
            + (f'<a href="ediciones/{c["fecha"]}.html">' if c["fecha"] in dates else "<span>")
            + _e(c.get("titulares", [None])[0] if c.get("titulares") else c["resumen"])
            + ("</a>" if c["fecha"] in dates else "</span>")
            + (f'<p>{_e(c["resumen"])}</p>' if c.get("titulares") else "") + '</li>'
            for c in h.get("capitulos", []))
        blocks.append(f'<article class="saga-ficha est-{est}" id="{_e(h["id"])}"><div class="kicker">{_e(est.upper())}'
                      f'<span class="desk"> · desde el {_e(short_date(_date(h["abierto"])))}</span></div>'
                      f'<h3>{_e(h["titulo"])}</h3><p>{_e(h.get("resumen", ""))}</p>'
                      + (f'<p class="small">Protagonistas: {prot}</p>' if prot else "")
                      + (f'<ol class="capitulos">{caps}</ol>' if caps else "") + '</article>')
    cast = "".join(f'<li><b>{_e(e["nombre"])}</b>, {_e(e["cargo"])}. <i>{_e(e.get("rasgo", ""))}</i></li>'
                   for e in canon["elenco"])
    body = (f'<section class="secblock"><header class="sec-head"><h3 class="sec-name">Sagas</h3>'
            f'<span class="sec-desk">Las historias que el periódico no deja de contar</span></header>'
            f'<div class="sec-grid sagas">{"".join(blocks) or "<p>Aún no hay sagas.</p>"}</div></section>'
            f'<section class="secblock"><header class="sec-head"><h3 class="sec-name">El elenco</h3>'
            f'<span class="sec-desk">Personajes fijos de la redacción</span></header><ul class="elenco">{cast}</ul></section>')
    return page(cfg, f"Sagas · {cfg['site_title']}", body, "", pagina="sagas")


def render_proponer(cfg):
    body = """
<section class="secblock" style="margin-top:20px">
<header class="sec-head"><h3 class="sec-name">La Voz de Runeterra</h3><span class="sec-desk">Buzón de noticias de los lectores</span></header>
<p style="max-width:760px;margin-bottom:16px">¿Alguien del grupo ha hecho algo que merece salir en el periódico? Cuéntalo aquí,
con foto o meme si quieres. La redacción lo convertirá en noticia y saldrá en la sección <i>La Voz de Runeterra</i>
de la próxima edición. Que sea sobre el LoL y sin pasarse: lo que no sea publicable, no se publica.</p>
<form class="papel" id="proponer">
<fieldset style="border:0;display:grid;gap:10px">
  <label>Tu nombre de invocador<input type="text" name="nombre" maxlength="40" required></label>
  <label>Titular propuesto<input type="text" name="titulo" maxlength="140" minlength="3" required placeholder="Ej.: Wôlf rompe el teclado tras la quinta derrota"></label>
  <label>¿Qué pasó?<textarea name="texto" maxlength="2000" minlength="10" required placeholder="Cuenta la historia con todo detalle. Cuanto más jugosa, mejor."></textarea></label>
  <label>Foto o meme (opcional, máx. 5 MB)<input type="file" name="imagen" accept="image/jpeg,image/png,image/gif,image/webp"></label>
  <input class="hp" type="text" name="web" tabindex="-1" autocomplete="off" aria-hidden="true">
  <button type="submit">Enviar a la redacción</button>
</fieldset>
<p class="msg"></p>
</form>
</section>"""
    return page(cfg, f"Proponer noticia · {cfg['site_title']}", body, "", pagina="proponer")


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


def _logros(slug, alias, games, editions):
    """Achievements (good and mostly bad) earned in the archive."""
    out = []
    portadas = sum(1 for e in editions if e.get("ranking") and e["ranking"][0]["slug"] == slug)
    if portadas:
        out.append(("💀", f"Portada de la vergüenza ×{portadas}"))
    faros = sum(1 for e in editions for it in e["items"] if it.get("player") == slug
                and it.get("section") in ("EL FARO DE LA ESPERANZA", "MENCIÓN"))
    if faros:
        out.append(("☼", f"Iluminado por el Faro ×{faros}"))
    if games:
        worst = max(games, key=lambda x: x["d"])
        out.append(("⚰", f"Récord de muertes: {worst['d']} con {champ_name(worst['champ'])}"))
        best = max(games, key=lambda x: ((x["k"] + x["a"]) / max(x["d"], 1)))
        out.append(("👑", f"Mejor partida: {best['k']}/{best['d']}/{best['a']} con {champ_name(best['champ'])}"))
        champs = Counter(champ_name(x["champ"]) for x in games)
        fav, n = champs.most_common(1)[0]
        if n >= 3:
            out.append(("♥", f"Fiel a {fav} ({n} partidas)"))
        for c, n in champs.items():
            if n >= 3 and not any(x["win"] for x in games if champ_name(x["champ"]) == c):
                out.append(("☠", f"Maldito con {c} (0–{n})"))
    porras = sum(1 for e in editions if alias in [a["nombre"] for a in (e.get("porra") or {}).get("acertantes", [])])
    if porras:
        out.append(("🔮", f"Vidente de la porra ×{porras}"))
    return out


def _ficha_runeterra(p, slug, canon):
    if not p:
        return ""
    title = canon_mod.current_title(p)
    rows = []
    for label, key in (("Apodos", "apodos"), ("Rasgos", "rasgos"), ("Maldiciones", "maldiciones"), ("Rivales", "rivales")):
        vals = canon_mod.texts(p.get(key))
        if vals:
            rows.append(f'<li><b>{label}:</b> {_e(" · ".join(vals))}</li>')
    hilos = [h for h in canon["hilos"] if slug in h.get("protagonistas", [])]
    if hilos:
        rows.append('<li><b>Sagas:</b> ' + ", ".join(f'<a href="../sagas.html#{_e(h["id"])}">{_e(h["titulo"])}</a>'
                                                   for h in hilos) + '</li>')
    return (f'<div class="box ficha-rt"><h4>Ficha de Runeterra</h4>'
            + (f'<p class="titulo-rt">{_e(title)}</p>' if title else "")
            + (f'<p class="small faccion">{_e(p["faccion"])}</p>' if p.get("faccion") else "")
            + f'<ul>{"".join(rows)}</ul></div>')


def render_player(cfg, friend, editions, canon=None):
    slug = friend["slug"]
    canon = canon or canon_mod.empty()
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
        f'<h3>{_e(it["headline"])}</h3>{_stat(it) if it.get("stat") else ""}<p>{_e(it["body"])}</p></article>'
        for it in reversed(items[-20:]))
    rows = "".join(
        f'<tr><td>{_e(short_date(_date(x["date"])))}</td><td>{_e(champ_name(x["champ"]))}</td><td>{_e(x["role"])}</td>'
        f'<td>{_e(x["queue_name"])}</td><td class="{"win" if x["win"] else "loss"}">{"V" if x["win"] else "D"}</td>'
        f'<td class="num">{x["k"]}/{x["d"]}/{x["a"]}</td>'
        f'<td class="num">{fmt_pct(x["dmg_share"], 0)}</td></tr>' for x in reversed(games[-25:]))
    table = ('<div class="tablewrap"><table><thead><tr><th>Día</th><th>Campeón</th><th>Rol</th><th>Cola</th><th></th>'
             '<th class="num">KDA</th><th class="num">Daño</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
             ) if rows else '<p class="small">Sin partidas todavía.</p>'
    logros = _logros(slug, friend["alias"], games, editions)
    logros_html = ('<div class="box logros"><h4>Logros (y deshonras)</h4><ul>'
                   + "".join(f'<li><span>{i}</span>{_e(t)}</li>' for i, t in logros) + '</ul></div>') if logros else ""
    body = f"""
<section class="profile">
  <div><div class="kicker">Ficha policial</div><h2>{_e(friend["alias"])}</h2>
    <p class="small">{_e(friend["riot_id"])} · {g} partidas registradas</p>
    <div style="margin-top:16px">{_sparkline(scores[-30:])}</div></div>
  <div class="kpis">{kpi_html}</div>
</section>
<div class="cols">
  <section class="secblock"><header class="sec-head"><h3 class="sec-name">Su hemeroteca</h3><span class="sec-desk">Todo lo publicado sobre {_e(friend["alias"])}</span></header>
    <div class="sec-grid">{news or '<p class="small">Todavía no ha salido en el periódico.</p>'}</div></section>
  <aside>{_ficha_runeterra(canon["personajes"].get(slug), slug, canon)}
    {logros_html}
    <div class="box"><h4>Quién cotillea esta ficha</h4><p class="small visitas" data-visitas="jugador:{_e(slug)}">Cargando…</p></div>
    <div class="box"><h4>Últimas partidas</h4>{table}</div></aside>
</div>"""
    return page(cfg, f"{friend['alias']} · {cfg['site_title']}", body, "../", pagina=f"jugador:{slug}",
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
    body = (f'<section class="secblock"><header class="sec-head"><h3 class="sec-name">Hemeroteca</h3>'
            f'<span class="sec-desk">Todas las ediciones</span></header>'
            f'<ul class="archive">{lis or "<li>Aún no hay ediciones.</li>"}</ul></section>')
    return page(cfg, f"Hemeroteca · {cfg['site_title']}", body, "", pagina="hemeroteca")


def render_players_index(cfg, friends, editions):
    board = {t["slug"]: t for t in general_leaderboard(editions)}
    cards = "".join(
        f'<article><div class="kicker">{_e(f["riot_id"])}</div><h3><a href="jugadores/{_e(f["slug"])}.html">'
        f'{_e(f["alias"])}</a></h3><p class="small">{board.get(f["slug"], {}).get("points", 0)} puntos de vergüenza · '
        f'{board.get(f["slug"], {}).get("portadas", 0)} portadas</p></article>' for f in friends)
    body = (f'<section class="secblock"><header class="sec-head"><h3 class="sec-name">Jugadores</h3>'
            f'<span class="sec-desk">Fichas policiales del grupo</span></header><div class="sec-grid">{cards}</div></section>')
    return page(cfg, f"Jugadores · {cfg['site_title']}", body, "", pagina="jugadores")


def build_site(cfg, friends, editions, out_dir, canon=None):
    out = Path(out_dir)
    (out / "ediciones").mkdir(parents=True, exist_ok=True)
    (out / "jugadores").mkdir(parents=True, exist_ok=True)
    (out / "img").mkdir(parents=True, exist_ok=True)
    (out / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (out / "lectores.js").write_text(LECTORES_JS, encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    editions = sorted(editions, key=lambda e: e["date"])

    known = {f["slug"]: f for f in friends}
    for ed in editions:
        for r in ed.get("ranking", []):
            known.setdefault(r["slug"], {"slug": r["slug"], "alias": r["alias"], "riot_id": r.get("riot_id", "")})
    friends_all = list(known.values())
    ROSTER[:] = [{"slug": f["slug"], "alias": f["alias"]} for f in friends_all]
    ACE.clear()
    ACE.update(load_json(ROOT / "data" / "ace_league.json", None) or {})

    for i, ed in enumerate(editions):
        html = render_edition(cfg, ed, editions[:i + 1], "../", latest=i == len(editions) - 1)
        (out / "ediciones" / f"{ed['date']}.html").write_text(html, encoding="utf-8")
    if editions:
        index = render_edition(cfg, editions[-1], editions, "", latest=True)
    else:
        index = page(cfg, cfg["site_title"],
                     '<section class="secblock"><h2 class="kicker">Próximamente</h2>'
                     '<p>La primera edición saldrá en cuanto se ejecute el robot.</p></section>', "")
    (out / "index.html").write_text(index, encoding="utf-8")
    (out / "archivo.html").write_text(render_archive(cfg, editions), encoding="utf-8")
    (out / "jugadores.html").write_text(render_players_index(cfg, friends_all, editions), encoding="utf-8")
    (out / "proponer.html").write_text(render_proponer(cfg), encoding="utf-8")
    canon = canon if canon is not None else canon_mod.load()
    (out / "sagas.html").write_text(render_sagas(cfg, canon, editions), encoding="utf-8")
    for f in friends_all:
        (out / "jugadores" / f"{f['slug']}.html").write_text(render_player(cfg, f, editions, canon), encoding="utf-8")
    return out
