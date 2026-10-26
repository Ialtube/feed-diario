"""Static site generator: a daily old-style newspaper, an archive, player pages,
reader comments and the "propose a story" page."""
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

from . import canon as canon_mod
from . import coronas
from .porra import seers
from .roasts import DESKS
from .soloq_web import pestanas
from .util import (ROOT, champ_name, fmt_int, fmt_num, fmt_pct, get_tz, load_json, long_date, ms_to_local,
                   short_date, slugify)

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
figure .ph{position:relative;border:1px solid var(--ink);padding:4px;background:var(--paper2);container-type:inline-size}
figure img{display:block;width:100%;height:auto;filter:grayscale(1) sepia(.45) contrast(1.15) brightness(.88)}
.meme{position:absolute;inset:4px;display:flex;flex-direction:column;justify-content:space-between;align-items:center;
  pointer-events:none;padding:6px 8px;text-align:center}
.meme span{font-family:"Anton",Impact,sans-serif;text-transform:uppercase;color:#fff;font-size:clamp(.62rem,7.5cqw,2.3rem);
  line-height:1.05;letter-spacing:.02em;-webkit-text-stroke:1.2px #000;paint-order:stroke fill;
  text-shadow:2px 2px 0 #000,-1px -1px 0 #000,1px -1px 0 #000,-1px 1px 0 #000}
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
/* interviews, turn by turn: who speaks in small capitals, the paper's questions in bold */
.dialogo{margin:6px 0 8px}
.turno{display:block;padding:3px 0;text-align:left;hyphens:auto}
.turno::before{content:attr(data-quien) ". ";font-family:"IM Fell English SC",serif;font-weight:400;font-style:normal;
  letter-spacing:.04em;color:var(--accent)}
.turno.pregunta{font-weight:700}
.turno.respuesta::before{color:var(--ink)}
.raya{font-size:0}
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
/* tabs at the very top: the newspaper and the SoloQ Challenge board */
.pestanas{display:flex;justify-content:center;gap:6px;padding:10px 12px 0;background:#1a120c;border-bottom:3px solid #3a2a1c}
.pestanas a{position:relative;top:3px;display:flex;align-items:center;gap:8px;padding:8px 20px 7px;text-decoration:none;
  font:19px/1 "IM Fell English SC",serif;color:#e0cfa8;background:linear-gradient(180deg,#4a3422,#2e2015);border:2px solid #5a4029;
  border-bottom:0;border-radius:10px 10px 0 0}
.pestanas a:hover{color:#fff4d8}
.pestanas a.on{background:var(--paper);color:var(--ink);border-color:var(--rule)}
.pestanas small{font:italic 12px/1 "Libre Caslon Text",serif;opacity:.8}
@media (max-width:520px){.pestanas a{padding:7px 12px 6px;font-size:16px}.pestanas small{display:none}}
.yo-dialog{border:3px double var(--ink);background:var(--paper);color:var(--ink);padding:18px 22px;max-width:min(560px,92vw)}
.yo-dialog::backdrop{background:rgba(20,14,8,.6)}
.yo-dialog h4{font-family:"UnifrakturMaguntia",serif;font-weight:400;font-size:1.8rem}
.yo-lista{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:4px 12px;margin:6px 0}
.yo-op{font-family:"IM Fell English SC",serif;font-size:1.02rem;cursor:pointer}
.yo-op small{display:block;margin-left:22px;font-family:"Old Standard TT",serif;font-style:italic;font-size:.8rem;color:var(--muted)}
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
.reglamento{max-width:820px}
.reglamento h4{font-family:"IM Fell English SC",serif;font-weight:400;font-size:1.2rem;margin:16px 0 6px}
.reglamento ul{margin:6px 0 6px 22px}
.reglamento li{padding:3px 0}
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
/* pastimes in rows: three games of the same size, then the Lonja and the horoscope across the page */
.pasa-grid.pasa-3{grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px}
.pasa-grid>*{min-width:0}
.sorteo .nums input{flex:1;min-width:0;width:auto}
.sec-pasatiempos .lonja,.sec-pasatiempos .horoscopo{margin-top:24px}
.lonja .mercados{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:0 26px}
.lonja .pie-lonja{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:0 26px;border-top:1px dashed var(--ink);margin-top:6px}
.lonja .pie-lonja h5{margin-top:12px}
.horoscopo ul{columns:2 340px;column-gap:28px;column-rule:1px solid var(--rule)}
.horoscopo li{break-inside:avoid}
.bolsa{margin-top:14px}
.bolsa table{font-size:.84rem}
.bolsa td{white-space:nowrap}
.bolsa tbody.persona{border-top:2px solid var(--ink)}
.bolsa tbody.persona:last-child{border-bottom:2px solid var(--ink)}
.bolsa th.jug{font-family:"IM Fell English SC",serif;font-size:1.05rem;color:var(--ink);vertical-align:top;
  border-right:1px solid var(--ink);border-bottom:0;padding:7px 6px 5px 2px;white-space:nowrap}
.bolsa tbody.persona tr:first-child td{padding-top:7px}
.bolsa tbody.persona tr:last-child td{border-bottom:0}
.bolsa td.cuenta{padding-left:7px}
.bolsa td.smurf{font-style:italic;color:var(--muted)}
.bolsa .tipo{font-family:"IM Fell English SC",serif;font-style:normal;font-size:.78rem;letter-spacing:.04em;margin-left:4px}
@media (max-width:560px){
  .bolsa thead{display:none}
  .bolsa table,.bolsa tbody.persona{display:block}
  .bolsa tbody.persona{padding:4px 0 6px}
  .bolsa tr{display:grid;grid-template-columns:1fr auto;column-gap:8px}
  .bolsa th.jug{display:block;grid-column:1/-1;border-right:0;padding:4px 0 2px}
  .bolsa td{display:block;border-bottom:0;padding:1px 0}
  .bolsa td.cuenta{grid-column:1/-1;padding:4px 0 0 10px}
  .bolsa td:not(.cuenta):not(.num){padding-left:10px}
  .bolsa tr>td:nth-last-child(4)::before{content:"SoloQ · ";color:var(--muted)}
  .bolsa tr>td:nth-last-child(2)::before{content:"Flex · ";color:var(--muted)}
}
.bolsa-nota{margin-top:6px;line-height:1.35}
.rx .rx-share{margin-left:4px}
.rx-rep{display:flex;gap:6px;align-items:center;font-size:.85rem}

/* boxed stories hug their content and line up with their neighbours (no half-empty frames) */
.pozo article.s-sucesos,.pozo article.s-el-faro-de-la-esperanza,.pozo article.radio,
.sec-grid>article.f-esquela,.sec-grid>article.f-telegrama,.sec-grid>article.f-anuncio-por-palabras,
.sec-opinion .sec-grid>article.column{margin:0;align-self:start}
.celda-anuncios{align-self:start;display:flex;flex-direction:column;gap:16px;padding-top:12px}
.celda-anuncios .anuncio{margin:0}
/* admin edit mode */
body.editando [data-campo]{outline:2px dashed var(--accent);outline-offset:3px;cursor:text}
body.editando [data-campo]:focus{outline-style:solid;background:rgba(255,248,225,.35)}
.admin-bar{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:50;display:flex;flex-wrap:wrap;gap:8px;align-items:center;
  width:min(920px,94vw);background:var(--ink);color:var(--paper);padding:10px 14px;border:3px double var(--paper);box-shadow:0 10px 30px rgba(0,0,0,.5)}
.admin-bar .nota{flex:1;min-width:220px;font:inherit;font-size:.9rem;padding:5px 8px;border:1px solid var(--paper);background:rgba(255,248,225,.1);color:var(--paper)}
.admin-bar button{font-family:"IM Fell English SC",serif;background:var(--paper);color:var(--ink);border:0;padding:5px 12px;cursor:pointer}
.admin-bar .small{color:#d8ccae}
/* test version banner */
.aviso-prueba{background:#7a2416;color:#f3e9d2;text-align:center;font-family:"IM Fell English SC",serif;padding:7px 12px;
  letter-spacing:.05em;font-size:.95rem}
/* «Tu edición»: what the paper says about the reader */
/* it lives in a drawer behind a tab on the right edge, not on the front page */
.tu-pestana{position:fixed;right:0;top:50%;transform:translateY(-50%);z-index:40;writing-mode:vertical-rl;
  font-family:"IM Fell English SC",serif;font-size:1rem;letter-spacing:.08em;background:var(--ink);color:var(--paper);border:0;
  border-radius:6px 0 0 6px;padding:16px 8px;cursor:pointer;box-shadow:-3px 3px 12px rgba(0,0,0,.35)}
.tu-pestana:hover{background:var(--accent)}
.tu-pestana b{display:inline-block;margin-top:8px;writing-mode:horizontal-tb;background:var(--accent);color:var(--paper);
  border-radius:50%;min-width:1.5em;line-height:1.5em;text-align:center;font-family:"Old Standard TT",serif;font-size:.85rem}
.tu-pestana:hover b{background:var(--ink)}
.tu-edicion{position:fixed;top:0;right:0;bottom:0;width:min(360px,88vw);z-index:45;overflow:auto;padding:18px 18px 26px;
  background:var(--noise),var(--paper);border-left:3px double var(--ink);box-shadow:-12px 0 30px rgba(0,0,0,.45);
  transform:translateX(110%);transition:transform .25s ease;visibility:hidden}
.tu-edicion.abierto{transform:none;visibility:visible}
.tu-edicion .cerrar{float:right;font-size:1.5rem;line-height:1;background:transparent;color:var(--ink);padding:0 4px}
.tu-edicion ol.tus-piezas{margin:6px 0 2px 20px}
.tu-edicion ol.tus-piezas li{border:0;padding:2px 0}
@media (prefers-reduced-motion:reduce){.tu-edicion{transition:none}}
@media (max-width:700px){   /* on a phone the tab is a pill in the corner, not a strip over the text */
  .tu-pestana{top:auto;bottom:14px;right:12px;transform:none;writing-mode:horizontal-tb;border-radius:20px;padding:8px 14px}
  .tu-pestana b{margin:0 0 0 6px}
}
/* on a phone the front page story shows its opening and folds the rest */
.seguir{display:none;font-family:"IM Fell English SC",serif;background:var(--ink);color:var(--paper);border:0;padding:5px 14px;margin-top:8px;cursor:pointer}
@media (max-width:700px){
  .lead .txt.plegado p:nth-child(n+2){display:none}
  .lead .txt.plegado+.seguir,.lead .txt.plegado~.seguir{display:inline-block}
}
.tu-edicion h4{font-family:"IM Fell English SC",serif;font-weight:400;font-size:1.15rem;letter-spacing:.04em}
.tu-edicion ul{list-style:none;margin-top:6px}
.tu-edicion li{padding:4px 0;border-bottom:1px dotted var(--rule);font-size:.95rem}
.tu-edicion li:last-child{border-bottom:0}
.tu-edicion button{font-family:"IM Fell English SC",serif;background:var(--ink);color:var(--paper);border:0;padding:4px 12px;cursor:pointer}
/* the strip under the front page: popular jury, yesterday's verdict and promises */
.franja{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:20px;margin:20px 0 6px}
.jurado,.veredicto,.promesas,.quienfue,.lonja{border:3px double var(--ink);padding:14px 16px;background:rgba(255,248,225,.1)}
.jurado h4,.veredicto h4,.promesas h4,.quienfue h4,.lonja h4{font-family:"UnifrakturMaguntia",serif;font-weight:400;font-size:1.6rem;
  text-align:center;border-bottom:1px solid var(--ink);padding-bottom:6px;margin-bottom:10px}
.preg{font-family:"Old Standard TT",serif;font-weight:700;font-size:1.2rem;line-height:1.25;text-align:center;margin:2px 0 10px}
.jurado-op{display:block;width:100%;text-align:left;font:inherit;font-size:.98rem;background:transparent;border:1px solid var(--ink);
  padding:7px 10px;margin:6px 0;cursor:pointer;position:relative;color:var(--ink);overflow:hidden}
.jurado-op:disabled{cursor:default}
.jurado-op .barra{position:absolute;left:0;top:0;bottom:0;width:0;background:rgba(122,36,22,.16);transition:width .5s}
.jurado-op span{position:relative}
.jurado-op .n{float:right;font-family:"Old Standard TT",serif;font-weight:700}
.jurado-op.mia{border:2px solid var(--accent)}
.veredicto .fallo{font-style:italic;margin-top:8px}
.promesas li{list-style:none;padding:6px 0;border-bottom:1px dotted var(--rule);font-size:.94rem}
.promesas li:last-child{border-bottom:0}
.promesas li b{display:block;font-family:"IM Fell English SC",serif;font-weight:400;color:var(--accent)}
/* «La jornada en 30 segundos» */
.jornada .resumen{font-style:italic;color:var(--muted);margin-bottom:8px}
.jornada ol{list-style:none;columns:2 380px;column-gap:28px;column-rule:1px solid var(--rule)}
.jornada li{break-inside:avoid;display:grid;grid-template-columns:3.1em 1fr auto;gap:0 10px;padding:5px 0;
  border-bottom:1px dotted var(--rule);font-size:.92rem;line-height:1.35}
.jornada time{font-family:"Old Standard TT",serif;font-weight:700}
.jornada .cola{display:block;font-family:"IM Fell English SC",serif;font-size:.82rem;color:var(--accent);letter-spacing:.03em}
.jornada .res{font-family:"Old Standard TT",serif;font-weight:700;font-size:1.05rem}
/* La Gaceta de Noxus: the rival tabloid */
.gaceta{border:4px solid #7c1414;outline:1px solid #7c1414;outline-offset:-9px;padding:18px 20px 16px;
  background:repeating-linear-gradient(135deg,rgba(124,20,20,.04) 0 6px,transparent 6px 12px),rgba(255,248,225,.14);position:relative}
.gaceta .cab{font-family:"Anton",Impact,sans-serif;color:#7c1414;font-size:clamp(1.9rem,4.4vw,2.8rem);text-transform:uppercase;
  letter-spacing:.05em;line-height:1;text-align:center}
.gaceta .lema{text-align:center;font-family:"Courier Prime","Courier New",monospace;font-size:.82rem;text-transform:uppercase;
  border-top:2px solid #7c1414;border-bottom:2px solid #7c1414;padding:3px 0;margin:6px 0 12px;letter-spacing:.08em}
.gaceta h3{font-family:"Anton",Impact,sans-serif;font-weight:400;text-transform:uppercase;font-size:clamp(1.5rem,3.4vw,2.1rem);
  line-height:1.05;letter-spacing:.01em;margin-bottom:10px}
.gaceta .txt{column-count:2;column-gap:24px;column-rule:1px solid rgba(124,20,20,.4)}
.gaceta .txt p{font-family:"Courier Prime","Courier New",monospace;font-size:.95rem;line-height:1.45}
.gaceta .sello{position:absolute;top:14px;right:16px;transform:rotate(9deg);font-family:"Anton",Impact,sans-serif;color:#7c1414;
  border:3px solid #7c1414;padding:2px 8px;font-size:.95rem;letter-spacing:.06em;opacity:.85}
.gaceta .byline{font-family:"Courier Prime","Courier New",monospace}
/* «¿Quién fue?» */
.quienfue ol{margin:4px 0 10px 20px}
.quienfue li{padding:3px 0;font-size:.95rem}
.quienfue li.oculta{color:var(--muted);font-style:italic;list-style:none;margin-left:-20px}
.qf-ops{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:6px}
.qf-ops button{font-family:"IM Fell English SC",serif;font-size:1rem;background:transparent;color:var(--ink);border:1px solid var(--ink);
  padding:5px 6px;cursor:pointer}
.qf-ops button:hover{background:rgba(255,248,225,.3)}
.qf-ops button.mal{text-decoration:line-through;opacity:.45;cursor:default}
.qf-ops button.bien{background:var(--good);color:var(--paper)}
.qf-fin{font-style:italic;margin-top:10px}
.qf-detectives{margin-top:8px}
/* La Lonja de Coronas */
.lonja .saldo{text-align:center;font-family:"Old Standard TT",serif;font-size:1.1rem;margin-bottom:6px}
.lonja .saldo b{color:var(--accent);font-size:1.4rem}
.mercado{border-top:1px dashed var(--ink);padding:10px 0}
.mercado p{font-family:"Old Standard TT",serif;font-weight:700;margin-bottom:6px;line-height:1.25}
.mercado .ops{display:flex;flex-wrap:wrap;gap:6px}
.mercado label.op{border:1px solid var(--ink);padding:3px 8px;cursor:pointer;font-size:.92rem;display:inline-flex;gap:6px;align-items:center}
.mercado label.op b{color:var(--accent);font-family:"Old Standard TT",serif}
.mercado label.op:has(input:checked){background:var(--ink);color:var(--paper)}
.mercado label.op:has(input:checked) b{color:#f0c27a}
.mercado label.op input{position:absolute;opacity:0;pointer-events:none}
.mercado .apostar{display:flex;gap:8px;align-items:center;margin-top:8px;flex-wrap:wrap}
.mercado .apostar input{width:6em;font:inherit;color:var(--ink);background:rgba(255,248,225,.25);border:1px solid var(--ink);padding:4px 6px}
.mercado .apostar button{font-family:"IM Fell English SC",serif;background:var(--ink);color:var(--paper);border:0;padding:5px 12px;cursor:pointer}
.mercado .mias{font-size:.85rem;color:var(--muted);font-style:italic;margin-top:4px}
.lonja table{font-size:.86rem}
.lonja .resuelto{font-size:.9rem;padding:5px 0;border-bottom:1px dotted var(--rule)}
/* «Mañana en El Rincón» */
.manana ul{list-style:none}
.manana li{padding:8px 0 8px 34px;border-bottom:1px dotted var(--rule);position:relative;font-family:"Old Standard TT",serif;font-size:1.08rem}
.manana li::before{content:"\2316";position:absolute;left:4px;top:4px;font-size:1.4rem;color:var(--accent)}
/* the full LP market folds away; only the accounts that moved stay in sight */
details.bolsa-todo summary{cursor:pointer;font-family:"IM Fell English SC",serif;margin:6px 0}
/* sagas page: the cast's secrets are printed blacked out */
.secreto{background:var(--ink);color:var(--ink);padding:0 3px;cursor:help;transition:color .2s}
.secreto:hover,.secreto:focus{color:var(--paper)}
.etiqueta{display:inline-block;font-family:"IM Fell English SC",serif;font-size:.78rem;border:1px solid var(--ink);padding:0 6px;margin-left:6px;letter-spacing:.04em}
ul.sindicato{list-style:none}
ul.sindicato li{padding:6px 0;border-bottom:1px dotted var(--rule);font-size:.94rem}
.arco{font-family:"IM Fell English SC",serif;color:var(--accent)}
@media (max-width:980px){
  .cols,.lead,.profile{grid-template-columns:1fr}
  .lead .txt,.sec-opinion article.column .cbody{column-count:1}
}
@media (max-width:700px){
  .sec-grid>article.pieza-grande{grid-column:auto}
  .pieza-grande .txt{column-count:1}
  .pasa-grid,.datos-grid{grid-template-columns:1fr}
  .gaceta .txt{column-count:1}
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
  var EMOJIS = ['😂', '💀', '🔥', '🤡'];
  function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function when(t){try{return new Date(t).toLocaleString('es-ES',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});}catch(e){return '';}}
  function api(path, opts){opts=opts||{};var h=Object.assign({},H,opts.headers||{});
    return fetch(C.url.replace(/\/$/,'')+path,Object.assign({},opts,{headers:h})).then(function(r){
      if(!r.ok) return r.text().then(function(t){var e=new Error(t||r.status);e.status=r.status;throw e;}); return r;});}
  // In the test version only the new games write to the database: comments, reactions and the rest
  // would land on the official paper.
  var NUEVAS = ['jurado', 'quienfue', 'apuestas'];
  function post(table, row){
    if (C.prueba && NUEVAS.indexOf(table) < 0) { alert('Versión de prueba: esto no se guarda para no mezclarlo con la edición oficial.'); var e = new Error('prueba'); e.status = 0; return Promise.reject(e); }
    return api('/rest/v1/'+table,{method:'POST',headers:{'Content-Type':'application/json',Prefer:'return=minimal'},body:JSON.stringify(row)});}
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
      Yo.listeners.forEach(function(f){ try { f(Yo.get()); } catch(e){} });
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
          return '<label class="yo-op"><input type="checkbox" value="'+esc(j.slug)+'" data-alias="'+esc(j.alias)+'"> '+esc(j.alias)+
            ((j.cuentas || []).length ? '<small>'+(j.cuentas || []).map(esc).join(' · ')+'</small>' : '')+'</label>';
        }).join('');
        d.innerHTML = '<form method="dialog" class="papel"><h4>¿Quién eres?</h4>'+
          '<p class="small">Marca quién eres. Debajo de cada nombre salen sus cuentas, smurfs incluidos. '+
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
    remember: function(nombre){ if (!Yo.get() && nombre) Yo.set({nombre: nombre.slice(0, 40), cuentas: []}); },
    listeners: [],
    // the reader's name as the Lonja de Coronas keys its accounts
    key: function(){ var y = Yo.get(); return y ? y.nombre.trim().replace(/\s+/g, ' ').toLowerCase() : ''; }
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
        '<button type="button" class="rx-share" title="Compartir el recorte de esta noticia">↗</button>' +
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
        recorte(el).then(function(blob){
          var file = blob && window.File ? new File([blob], 'rincon-del-feeder.png', {type: 'image/png'}) : null;
          if (file && navigator.canShare && navigator.canShare({files: [file]}))
            return navigator.share({files: [file], title: t, text: t + ' ' + url});
          if (blob) { var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'rincon-del-feeder.png';
                      document.body.appendChild(a); a.click(); a.remove(); }
          if (navigator.clipboard) navigator.clipboard.writeText(t + ' ' + url).catch(function(){});
        }).catch(function(){
          if (navigator.share) navigator.share({title: t, url: url}).catch(function(){});
          else window.open('https://wa.me/?text=' + encodeURIComponent(t + ' ' + url), '_blank', 'noopener');
        });
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
  if (ok && PAGINA && !C.prueba) {
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


  // ------------------------------------------------------------------ admin: corrections and edit mode
  // Everyone sees the latest corrections at once; only the admin (with the key) can make them.
  var FIELD_LIST = ['body', 'columna.cuerpo'];
  var piezaOf = function(el){ var h = el.closest('[data-pieza],[data-ed]');
    return h ? Number(h.getAttribute('data-pieza') || h.getAttribute('data-ed')) : 0; };
  var textOf = function(el){
    if (FIELD_LIST.indexOf(el.getAttribute('data-campo')) >= 0) {
      var kids = Array.prototype.filter.call(el.children, function(c){ return /^(P|DIV)$/.test(c.tagName); });
      if (kids.length) return kids.map(function(c){ return c.innerText.trim(); }).filter(Boolean).join('\n\n');
    }
    return el.innerText.trim();
  };
  // an interview keeps its turns after a correction (same rule as the server: a dash that opens a sentence)
  var dialogo = function(el, t){
    var g = el.querySelector('.turno.respuesta'), guest = g ? g.getAttribute('data-quien') : 'El entrevistado', n = 0;
    return t.split(/\n\s*\n/).map(function(p){
      p = p.trim(); if (!p) return '';
      if (p.charAt(0) !== '—') return '<p>' + esc(p) + '</p>';
      return '<div class="dialogo">' + p.split(/\s+(?=—[¿¡«"A-ZÁÉÍÓÚÑ0-9])/).map(function(x){
        x = x.trim().replace(/^—\s*/, ''); if (!x) return '';
        var q = n++ % 2 === 0;
        return '<span class="turno ' + (q ? 'pregunta' : 'respuesta') + '" data-quien="' + esc(q ? 'El Rincón' : guest) +
               '"><span class="raya">—</span>' + esc(x) + '</span>';
      }).join('') + '</div>';
    }).join('');
  };
  var setText = function(el, t){
    if (el.getAttribute('data-campo') === 'body' && el.closest('.f-entrevista')) el.innerHTML = dialogo(el, t);
    else if (FIELD_LIST.indexOf(el.getAttribute('data-campo')) >= 0)
      el.innerHTML = t.split(/\n\s*\n/).map(function(p){ return '<p>' + esc(p.trim()) + '</p>'; }).join('');
    else el.textContent = t;
  };
  var fields = function(){ return Array.prototype.slice.call(document.querySelectorAll('[data-campo]')); };
  if (ok && EDICION) {
    api('/rest/v1/correcciones?select=pieza,campo,despues&edicion=eq.' + EDICION + '&order=created_at.asc')
      .then(function(r){ return r.json(); }).then(function(rows){
        var last = {}; rows.forEach(function(c){ last[c.pieza + '|' + c.campo] = c.despues; });
        fields().forEach(function(el){ var k = piezaOf(el) + '|' + el.getAttribute('data-campo'); if (last[k] != null) setText(el, last[k]); });
      }).catch(function(){});
  }
  var editing = false, originals = new Map(), bar = null;
  var rpc = function(fn, args){ return api('/rest/v1/rpc/' + fn, {method: 'POST', headers: {'Content-Type': 'application/json'},
                                                                   body: JSON.stringify(args)}).then(function(r){ return r.json(); }); };
  var changed = function(){ return fields().filter(function(el){ return originals.has(el) && textOf(el) !== originals.get(el); }); };
  var stop = function(discard){
    fields().forEach(function(el){ if (discard && originals.has(el)) setText(el, originals.get(el)); el.removeAttribute('contenteditable'); });
    originals = new Map(); editing = false; document.body.classList.remove('editando'); if (bar) bar.remove(); bar = null;
  };
  var start = function(){
    if (!ok || !EDICION) { alert('El modo edición solo funciona en las páginas de una edición.'); return; }
    var key = remember('feeder-admin') || prompt('Clave de administrador:');
    if (!key) return;
    rpc('es_admin', {clave: key}).then(function(isAdmin){
      if (isAdmin !== true) { remember('feeder-admin', ''); alert('Clave incorrecta.'); return; }
      remember('feeder-admin', key);
      editing = true; document.body.classList.add('editando');
      fields().forEach(function(el){ originals.set(el, textOf(el)); el.setAttribute('contenteditable', 'true'); });
      bar = document.createElement('div'); bar.className = 'admin-bar';
      bar.innerHTML = '<b>Modo edición</b> <span class="small">Cambia titulares, entradillas, textos, la columna o la frase. ' +
        'Ctrl+Mayús+E para salir.</span><input type="text" class="nota" maxlength="500" placeholder="¿Por qué lo cambias? (opcional, ayuda a la redacción a aprender)">' +
        '<button type="button" data-a="save">Guardar cambios</button><button type="button" data-a="discard">Descartar</button><span class="msg"></span>';
      document.body.appendChild(bar);
      bar.querySelector('[data-a=discard]').onclick = function(){ stop(true); };
      bar.querySelector('[data-a=save]').onclick = function(){
        var list = changed(), note = bar.querySelector('.nota').value.trim(), msgEl = bar.querySelector('.msg');
        if (!list.length) { msgEl.textContent = 'No has cambiado nada.'; return; }
        msgEl.textContent = 'Guardando…';
        list.reduce(function(prev, el){
          return prev.then(function(){
            return rpc('guardar_correccion', {clave: key, p_edicion: EDICION, p_pieza: piezaOf(el), p_campo: el.getAttribute('data-campo'),
                                              p_antes: originals.get(el), p_despues: textOf(el), p_nota: note || null})
              .then(function(){ originals.set(el, textOf(el)); });
          });
        }, Promise.resolve()).then(function(){ msgEl.textContent = 'Guardadas ' + list.length + ' correcciones. La redacción las estudiará.'; })
          .catch(function(){ msgEl.textContent = 'No se pudo guardar. ¿La clave sigue siendo válida?'; });
      };
    }).catch(function(){ alert('No se pudo comprobar la clave.'); });
  };
  document.addEventListener('keydown', function(e){
    if (e.ctrlKey && e.shiftKey && e.code === 'KeyE') {
      e.preventDefault();
      if (!editing) start();
      else if (!changed().length || confirm('Hay cambios sin guardar. ¿Salir y descartarlos?')) stop(true);
    }
  });
  document.addEventListener('paste', function(e){   // paste plain text only while editing
    if (!editing || !e.target.closest('[contenteditable]')) return;
    e.preventDefault(); document.execCommand('insertText', false, (e.clipboardData || window.clipboardData).getData('text'));
  });
  if (location.hash === '#editar') start();

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


  // ------------------------------------------------------------------ a clipping of a story, as a picture to share
  function recorte(el){
    var W = 1080, H = 1350, c = document.createElement('canvas'); c.width = W; c.height = H;
    var x = c.getContext('2d'); if (!x || !c.toBlob) return Promise.reject(new Error('sin canvas'));
    var pick = function(sel){ var n = el.querySelector(sel); return n ? n.textContent.trim() : ''; };
    var head = pick('h2,h3,h5'), sub = pick('p.sub'), kick = pick('.kicker').replace(/\s+/g, ' ');
    var body = Array.prototype.map.call(el.querySelectorAll('.txt p'), function(p){ return p.textContent.trim(); }).join(' ');
    var fonts = ['72px UnifrakturMaguntia', '700 64px "Old Standard TT"', 'italic 36px "Old Standard TT"', '30px "Libre Caslon Text"', '28px "IM Fell English SC"'];
    var ready = document.fonts ? Promise.all(fonts.map(function(f){ return document.fonts.load(f); })) : Promise.resolve();
    return ready.then(function(){
      x.fillStyle = '#d8ccae'; x.fillRect(0, 0, W, H);
      var g = x.createRadialGradient(W/2, H/2, W*.3, W/2, H/2, W*.8); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(70,48,18,.35)');
      x.fillStyle = g; x.fillRect(0, 0, W, H);
      x.strokeStyle = '#2a2017'; x.lineWidth = 3; x.strokeRect(30, 30, W - 60, H - 60); x.lineWidth = 1; x.strokeRect(42, 42, W - 84, H - 84);
      x.fillStyle = '#2a2017'; x.textAlign = 'center';
      x.font = '84px UnifrakturMaguntia'; x.fillText(document.querySelector('.title') ? document.querySelector('.title').textContent : 'El Rincón del Feeder', W/2, 150);
      x.font = '26px "IM Fell English SC"'; x.fillText((document.querySelector('.topline span') || {}).textContent || '', W/2, 196);
      x.fillRect(80, 220, W - 160, 5); x.fillRect(80, 232, W - 160, 1.5);
      var wrap = function(text, font, lh, y, maxLines, align){
        x.font = font; x.textAlign = align || 'left'; var words = text.split(/\s+/), line = '', n = 0, X = align === 'center' ? W/2 : 90;
        for (var i = 0; i < words.length; i++) {
          var test = line ? line + ' ' + words[i] : words[i];
          if (x.measureText(test).width > W - 180 && line) {
            n++; if (n === maxLines) { x.fillText(line.replace(/[,.;:]?$/, '…'), X, y); return y + lh; }
            x.fillText(line, X, y); y += lh; line = words[i];
          } else line = test;
        }
        if (line) { x.fillText(line, X, y); y += lh; } return y;
      };
      x.fillStyle = '#7a2416'; var y = wrap(kick.toUpperCase(), '28px "IM Fell English SC"', 36, 300, 2, 'center');
      x.fillStyle = '#2a2017'; y = wrap(head, '700 66px "Old Standard TT"', 74, y + 40, 5, 'center');
      if (sub) { x.fillStyle = '#5a4a37'; y = wrap(sub, 'italic 36px "Old Standard TT"', 46, y + 20, 3, 'center'); }
      x.fillStyle = '#7b6850'; x.fillRect(W/2 - 120, y + 10, 240, 2);
      x.fillStyle = '#2a2017'; wrap(body, '30px "Libre Caslon Text"', 44, y + 70, Math.max(3, Math.floor((H - 160 - y - 70) / 44)));
      x.font = '24px "IM Fell English SC"'; x.textAlign = 'center'; x.fillStyle = '#5a4a37';
      x.fillText(location.host + location.pathname.replace(/index\.html$/, ''), W/2, H - 70);
      return new Promise(function(res){ c.toBlob(res, 'image/png'); });
    });
  }

  var DATOS = (function(){ var n = document.getElementById('ed-datos'); try { return n ? JSON.parse(n.textContent) : {}; } catch(e){ return {}; } })();

  // ------------------------------------------------------------------ «Tu edición»: what today's paper says about you
  // It lives in a drawer behind a tab on the edge of the page, so the front page stays a front page.
  var tu = document.getElementById('tu-edicion'), tab = document.getElementById('tu-pestana');
  var cajon = function(open){
    if (!tu) return;
    tu.classList.toggle('abierto', open); tu.setAttribute('aria-hidden', open ? 'false' : 'true');
    if (tab) tab.setAttribute('aria-expanded', open ? 'true' : 'false');
  };
  if (tab) tab.addEventListener('click', function(){ cajon(!tu.classList.contains('abierto')); });
  if (tu) tu.addEventListener('click', function(e){ if (e.target.closest('a,[data-a=cerrar]')) cajon(false); });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') cajon(false); });
  document.addEventListener('click', function(e){
    if (tu && tu.classList.contains('abierto') && !e.target.closest('#tu-edicion,#tu-pestana,dialog')) cajon(false);
  });
  var cabecera = function(t){ return '<button type="button" class="cerrar" data-a="cerrar" aria-label="Cerrar">×</button><h4>' + t + '</h4>'; };
  function pintaTu(){
    if (!tu) return;
    var y = Yo.get(), J = DATOS.jugadores || {}, li = [];
    if (tab) tab.hidden = false;
    if (!y) {
      tu.innerHTML = cabecera('Tu edición') + '<p class="small">Dinos quién eres y te enseñamos lo que el periódico dice hoy de ti.</p>' +
        '<p style="margin-top:8px"><button type="button" class="yo-cajon">¿Quién eres?</button></p>';
      tu.querySelector('.yo-cajon').onclick = function(){ cajon(false); Yo.open(); };
      if (tab) tab.innerHTML = 'Tu edición';
      return;
    }
    var slug = (y.cuentas || [])[0], me = slug ? J[slug] : null;
    if (me && me.piezas.length) li.push('Hoy sales en <b>' + me.piezas.length + '</b> pieza' + (me.piezas.length > 1 ? 's' : '') + ':<ol class="tus-piezas">' +
      me.piezas.map(function(p){ return '<li><a href="#p-' + esc(p[0]) + '">' + esc(p[1]) + '</a></li>'; }).join('') + '</ol>');
    else if (slug) li.push('Hoy no sales en el periódico. Disfrútalo: no durará.');
    if (me && me.puesto) li.push('Tu día: <b>' + esc(me.dia) + '</b>, puesto ' + me.puesto + ' de ' + me.de + ' en la tabla de la vergüenza' +
      (me.puesto === 1 ? ' (sí, el peor)' : '') + '.');
    if (me && me.tiempo) li.push('Tu tiempo, según Madame Niebla: <i>' + esc(me.tiempo) + '</i>');
    if (tab) tab.innerHTML = 'Tu edición' + (me && me.piezas.length ? ' <b>' + me.piezas.length + '</b>' : '');
    var saldo = (DATOS.saldos || {})[Yo.key()];
    li.push('Lonja de Coronas: ' + (saldo != null ? '<b>' + saldo + '</b> coronas.' : 'aún no tienes cuenta; empiezas con 100 coronas.') + ' <a href="#lonja">Apostar</a>');
    if (document.getElementById('jurado')) li.push(remember('feeder-jurado-' + EDICION) ? 'Ya has votado en el jurado popular.' : 'El jurado popular espera <a href="#jurado">tu voto</a>.');
    if (document.getElementById('quienfue')) {
      var q = {}; try { q = JSON.parse(remember('feeder-qf-' + EDICION) || '{}'); } catch(e){}
      li.push(q.fin ? '¿Quién fue?: ' + (q.acierto ? 'resuelto en ' + q.intentos + ' intento' + (q.intentos > 1 ? 's' : '') + '.' : 'hoy no lo sacaste.')
                    : '<a href="#quienfue">¿Quién fue?</a> sigue sin resolver.');
    }
    tu.innerHTML = cabecera('Tu edición, ' + esc(y.nombre)) + '<ul>' + li.map(function(t){ return '<li>' + t + '</li>'; }).join('') + '</ul>';
  }
  pintaTu(); Yo.listeners.push(pintaTu);

  // the front page story, folded on a phone after its opening
  var lt = document.querySelector('.lead .txt');
  if (lt && lt.children.length > 1) {
    lt.classList.add('plegado');
    var sb = document.createElement('button'); sb.type = 'button'; sb.className = 'seguir'; sb.textContent = 'Seguir leyendo';
    sb.onclick = function(){ lt.classList.remove('plegado'); sb.remove(); };
    lt.parentNode.insertBefore(sb, lt.nextSibling);
  }

  // ------------------------------------------------------------------ the popular jury
  var jb = document.getElementById('jurado');
  if (jb) {
    var JED = jb.getAttribute('data-edicion'), jopen = jb.getAttribute('data-abierto') === '1';
    var jops = jb.querySelectorAll('.jurado-op'), jmsg = jb.querySelector('.msg'), jvotes = [];
    var jmine = remember('feeder-jurado-' + JED);
    var jpaint = function(){
      var counts = [], total = 0; for (var i = 0; i < jops.length; i++) counts.push(0);
      jvotes.forEach(function(v){ if (v.opcion >= 0 && v.opcion < counts.length) { counts[v.opcion]++; total++; } });
      var show = !!jmine || !jopen;
      Array.prototype.forEach.call(jops, function(b, i){
        b.querySelector('.barra').style.width = show && total ? Math.round(100 * counts[i] / total) + '%' : '0';
        b.querySelector('.n').textContent = show ? counts[i] + (total ? ' · ' + Math.round(100 * counts[i] / total) + ' %' : '') : '';
        b.classList.toggle('mia', String(i) === jmine); b.disabled = show;
      });
      jmsg.textContent = !ok ? 'El jurado se abrirá en cuanto se configure la base de datos.' :
        show ? total + ' voto' + (total !== 1 ? 's' : '') + (jopen ? '. El veredicto sale mañana.' : '. Votación cerrada.') : 'Vota para ver cómo va.';
    };
    var jload = function(){
      if (!ok) return jpaint();
      api('/rest/v1/jurado?select=opcion,nombre&edicion=eq.' + JED).then(function(r){ return r.json(); })
        .then(function(rows){ jvotes = rows; jpaint(); }).catch(function(){ jmsg.textContent = 'El jurado aún no está abierto (falta crear su tabla).'; });
    };
    Array.prototype.forEach.call(jops, function(b, i){
      b.addEventListener('click', function(){
        if (!ok || jmine || !jopen) return;
        var y = Yo.get(); jmine = String(i); remember('feeder-jurado-' + JED, jmine);
        jvotes.push({opcion: i}); jpaint(); pintaTu();
        post('jurado', {edicion: JED, opcion: i, lector: Yo.lector(), nombre: y ? y.nombre : null})
          .catch(function(err){ if (err.status !== 409) { jmsg.textContent = 'No se pudo guardar tu voto.'; } });
      });
    });
    jload();
  }

  // ------------------------------------------------------------------ ¿Quién fue?
  var qf = document.getElementById('quienfue');
  if (qf) {
    var QD = JSON.parse(qf.querySelector('script').textContent), QED = qf.getAttribute('data-edicion');
    var qopen = qf.getAttribute('data-abierto') === '1', qkey = 'feeder-qf-' + QED;
    var answer = (function(){ try { return atob(QD.clave).split('').reverse().join(''); } catch(e){ return ''; } })();
    var st = {}; try { st = JSON.parse(remember(qkey) || '{}'); } catch(e){}
    st.mal = st.mal || [];
    var qpaint = function(){
      var shown = st.fin ? QD.pistas.length : Math.min(QD.pistas.length, 1 + st.mal.length);
      qf.querySelector('ol').innerHTML = QD.pistas.map(function(p, i){
        return i < shown ? '<li>' + esc(p) + '</li>' : '<li class="oculta">Pista ' + (i + 1) + ': se destapa si fallas.</li>'; }).join('');
      qf.querySelector('.qf-ops').innerHTML = QD.opciones.map(function(o){
        var cls = st.mal.indexOf(o.slug) >= 0 ? 'mal' : (st.fin && o.slug === answer ? 'bien' : '');
        return '<button type="button" data-s="' + esc(o.slug) + '" class="' + cls + '"' + (st.fin || cls ? ' disabled' : '') + '>' + esc(o.alias) + '</button>';
      }).join('');
      var racha = {}; try { racha = JSON.parse(remember('feeder-qf-racha') || '{}'); } catch(e){}
      qf.querySelector('.qf-fin').innerHTML = st.fin ? (st.acierto ?
        '¡Era ' + esc(QD.alias) + ' con ' + esc(QD.campeon) + '! Lo has sacado en ' + st.intentos + ' intento' + (st.intentos > 1 ? 's' : '') + '.' :
        'Era <b>' + esc(QD.alias) + '</b>, con ' + esc(QD.campeon) + '. Mañana, más suerte.') +
        (racha.n ? ' Racha: ' + racha.n + ' día' + (racha.n > 1 ? 's' : '') + ' seguido' + (racha.n > 1 ? 's' : '') + '.' : '') : '';
      Array.prototype.forEach.call(qf.querySelectorAll('.qf-ops button:not([disabled])'), function(b){
        b.addEventListener('click', function(){ guess(b.getAttribute('data-s')); });
      });
    };
    var guess = function(slug){
      if (st.fin) return;
      if (slug === answer) { st.fin = true; st.acierto = true; st.intentos = st.mal.length + 1; }
      else { st.mal.push(slug); if (st.mal.length >= QD.pistas.length) { st.fin = true; st.acierto = false; st.intentos = st.mal.length; } }
      if (st.fin) {
        var r = {}; try { r = JSON.parse(remember('feeder-qf-racha') || '{}'); } catch(e){}
        if (st.acierto) { r.n = (r.ultima && r.ultima < QED && (new Date(QED) - new Date(r.ultima)) <= 86400000 ? (r.n || 0) : 0) + 1; r.ultima = QED; }
        else r = {n: 0, ultima: QED};
        remember('feeder-qf-racha', JSON.stringify(r));
        if (ok && qopen) { var y = Yo.get();
          post('quienfue', {edicion: QED, lector: Yo.lector(), nombre: y ? y.nombre : null, intentos: st.intentos, acierto: st.acierto})
            .then(qload).catch(function(){}); }
      }
      remember(qkey, JSON.stringify(st)); qpaint(); pintaTu();
    };
    var qload = function(){
      var box = qf.querySelector('.qf-detectives'); if (!ok || !box) return;
      api('/rest/v1/quienfue?select=nombre,intentos,acierto&edicion=eq.' + QED + '&order=intentos.asc').then(function(r){ return r.json(); })
        .then(function(rows){
          var good = rows.filter(function(r){ return r.acierto; });
          box.innerHTML = rows.length ? '<b>Detectives de hoy:</b> ' + (good.length ? good.slice(0, 8).map(function(r){
            return esc(r.nombre || 'anónimo') + ' (' + r.intentos + ')'; }).join(', ') : 'nadie lo ha sacado todavía') +
            ' · ' + rows.length + ' han jugado.' : 'Nadie ha jugado todavía.';
        }).catch(function(){});
    };
    qpaint(); qload();
  }

  // ------------------------------------------------------------------ La Lonja de Coronas
  var lj = document.getElementById('lonja');
  if (lj) {
    var LD = JSON.parse(lj.querySelector('script').textContent);
    var closed = !lj.getAttribute('data-abierto') || Date.now() > new Date(LD.cierre).getTime();
    var lsaldo = lj.querySelector('.saldo'), mine = [];
    var available = function(){ var base = (LD.saldos || {})[Yo.key()]; base = base != null ? base : LD.inicial;
      return base - mine.filter(function(b){ return b.created_at > LD.corte; }).reduce(function(a, b){ return a + b.importe; }, 0); };
    var lpaint = function(){
      var y = Yo.get();
      lsaldo.innerHTML = !y ? 'Para apostar, <a href="#" class="lj-yo">dinos quién eres</a>. Todos empiezan con ' + LD.inicial + ' coronas.' :
        'Saldo de ' + esc(y.nombre) + ': <b>' + available() + '</b> coronas';
      var a = lsaldo.querySelector('.lj-yo'); if (a) a.onclick = function(e){ e.preventDefault(); Yo.open(); };
      Array.prototype.forEach.call(lj.querySelectorAll('.mercado'), function(m){
        var id = m.getAttribute('data-id'), bets = mine.filter(function(b){ return b.mercado === id; });
        m.querySelector('.mias').textContent = bets.length ? 'Tus apuestas: ' + bets.map(function(b){
          var o = m.querySelector('input[value="' + b.opcion + '"]'); return b.importe + ' a ' + (o ? o.getAttribute('data-t') : b.opcion); }).join(', ') : '';
        var f = m.querySelector('.apostar'); if (f) f.hidden = closed;
      });
      var cl = lj.querySelector('.lj-cerrado'); if (cl) cl.hidden = !closed;
    };
    var lload = function(){
      var y = Yo.get(); if (!ok || !y) return lpaint();
      var ids = LD.mercados.map(function(m){ return '"' + m + '"'; }).join(',');
      api('/rest/v1/apuestas?select=mercado,opcion,importe,created_at&nombre=ilike.' + encodeURIComponent(y.nombre) + '&mercado=in.(' + encodeURIComponent(ids) + ')')
        .then(function(r){ return r.json(); }).then(function(rows){ mine = rows; lpaint(); }).catch(function(){ lpaint(); });
    };
    Array.prototype.forEach.call(lj.querySelectorAll('.mercado .apostar'), function(f){
      f.addEventListener('submit', function(ev){
        ev.preventDefault();
        var m = f.closest('.mercado'), msg = f.querySelector('.msg'), y = Yo.get();
        if (!ok) { msg.textContent = 'La Lonja abrirá en cuanto se configure la base de datos.'; return; }
        if (!y) { Yo.open(function(){ lload(); }); return; }
        var op = m.querySelector('input[type=radio]:checked'), imp = parseInt(f.importe.value, 10);
        if (!op) { msg.textContent = 'Elige una respuesta.'; return; }
        if (!(imp >= 1)) { msg.textContent = 'Apuesta al menos 1 corona.'; return; }
        if (imp > available()) { msg.textContent = 'No te llega: tienes ' + available() + '.'; return; }
        if (Date.now() > new Date(LD.cierre).getTime()) { closed = true; lpaint(); return; }
        f.querySelector('button').disabled = true; msg.textContent = 'Firmando el boleto…';
        var row = {nombre: y.nombre, lector: Yo.lector(), mercado: m.getAttribute('data-id'), opcion: op.value, importe: imp};
        post('apuestas', row).then(function(){
          mine.push({mercado: row.mercado, opcion: row.opcion, importe: imp, created_at: new Date().toISOString()});
          msg.textContent = 'Apuesta registrada. Se paga mañana.'; f.importe.value = ''; lpaint(); pintaTu();
        }).catch(function(){ msg.textContent = 'No se pudo apostar (¿está creada la tabla de la Lonja?).'; })
          .then(function(){ f.querySelector('button').disabled = false; });
      });
    });
    Yo.listeners.push(lload); lload();
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
    Array.prototype.forEach.call(document.querySelectorAll('.sec-grid .celda-anuncios, .sec-grid .anuncio, .anuncios-extra .anuncio'),
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
      var lastTop = -1e9, taken = 0, rowH = 0;
      Array.prototype.forEach.call(g.children, function(c){ lastTop = Math.max(lastTop, Math.round(c.getBoundingClientRect().top)); });
      Array.prototype.forEach.call(g.children, function(c){
        var b = c.getBoundingClientRect();
        if (Math.abs(Math.round(b.top) - lastTop) <= 2) {
          taken += Math.max(1, Math.round((b.width + gap) / (cw + gap)));
          rowH = Math.max(rowH, b.height);
        }
      });
      var rem = Math.max(0, cols - taken);
      // each empty cell gets small ads stacked at their own size, never one ad stretched to the row
      while (rem > 0 && used < pool.length) {
        var cell = document.createElement('div'); cell.className = 'celda-anuncios';
        g.appendChild(cell); rem -= 1;
        do { cell.appendChild(pool[used++].cloneNode(true)); }
        while (used < pool.length && rowH - cell.getBoundingClientRect().height > 220);
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
LEDGER = {}  # balances of the Lonja de Coronas (coronas.ledger); set by build_site


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
                         "jugadores": ROSTER, "prueba": bool(cfg.get("prueba"))}, ensure_ascii=False)
    banner = ('<div class="aviso-prueba">Versión de prueba · no es la edición oficial · aquí solo se guardan el jurado, '
              '«¿Quién fue?» y la Lonja de Coronas</div>' if cfg.get("prueba") else "")
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
{pestanas(rel, rel + "soloq/", "periodico")}
{banner}
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


MIN_SHAME = 0.0  # only a genuinely bad day scores: a good day never takes points
ALONE_SHAME = 5.0  # playing alone there is nobody to compare with: only a disaster scores
_SEASON = {}


def season_start():
    """First edition of the current season of the General (config 'general_desde'); None = all of them."""
    if "desde" not in _SEASON:
        from .util import load_config
        _SEASON["desde"] = load_config().get("general_desde")
    return _SEASON["desde"]


def day_points(ranking):
    """Shame points of one day: 5, 3, 2 and 1 for the four worst, but only among those whose day was
    really bad (shame score above zero). Playing alone with good games scores nothing."""
    floor = ALONE_SHAME if len(ranking) == 1 else MIN_SHAME
    bad = [r for r in ranking if (r.get("score") or 0) > floor]
    return {r["slug"]: POINTS[i] for i, r in enumerate(bad[:len(POINTS)])}


def general_leaderboard(editions, since="temporada"):
    since = season_start() if since == "temporada" else since
    tot = {}
    for ed in editions:
        if since and ed["date"] < since:
            continue
        pts = day_points(ed.get("ranking", []))
        for r in ed.get("ranking", []):
            t = tot.setdefault(r["slug"], {"slug": r["slug"], "alias": r["alias"], "points": 0,
                                           "portadas": 0, "games": 0, "wins": 0, "losses": 0})
            t["alias"] = r["alias"]
            t["points"] += pts.get(r["slug"], 0)
            t["portadas"] += 1 if pts.get(r["slug"]) == POINTS[0] else 0
            t["games"] += r["games"]
            t["wins"] += r["wins"]
            t["losses"] += r["losses"]
    return sorted(tot.values(), key=lambda t: (-t["points"], -t["portadas"]))


def _general_table(board, rel, since=None):
    season = (f'<p class="small" style="text-align:center">Temporada desde el {_e(short_date(_date(since)))}</p>'
              if since else "")
    if not board:
        return season + f'<p class="small">Aún no hay puntos esta temporada. <a href="{rel}puntuacion.html">Cómo se puntúa</a>.</p>'
    rows = "".join(
        f'<tr class="{"top" if i == 0 else ""}"><td>{i + 1}</td>'
        f'<td><a href="{rel}jugadores/{_e(t["slug"])}.html">{_e(t["alias"])}</a></td>'
        f'<td class="num">{t["points"]}</td><td class="num">{t["portadas"]}</td></tr>'
        for i, t in enumerate(board))
    return (season + '<div class="tablewrap"><table><thead><tr><th>#</th><th>Jugador</th><th class="num">Puntos</th>'
            '<th class="num">Portadas</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
            '<p class="small" style="margin-top:6px">Cada día puntúan solo los que tuvieron un día malo de verdad: '
            f'el peor 5, el segundo 3, el tercero 2 y el cuarto 1. <a href="{rel}puntuacion.html">Cómo se calcula</a>.</p>')


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


def _firma(lector):
    """Reader credit: newer editions store the whole line ("Según varias fuentes: …"), older ones a name."""
    return lector if lector.startswith(("Enviado por", "Según", "Con información")) else f"Enviado por {lector}"


def _paras_html(text):
    return "".join(f"<p>{_e(p)}</p>" for p in str(text).split("\n\n") if p.strip())


# a new turn of an interview: a dash that opens a sentence (not a dash that opens an aside, «—dice—»)
TURN = re.compile(r"\s+(?=—[¿¡«\"A-ZÁÉÍÓÚÑ0-9])")


def _dialogue_html(text, guest):
    """An interview printed turn by turn: the paper's questions in bold, the answers in roman, each
    on its own line with the speaker's name in front. The dashes stay in the text (invisible), so
    the admin's corrections keep the format the editor writes in."""
    out, turn = [], 0
    for para in str(text).split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if not para.startswith("—"):
            out.append(f"<p>{_e(para)}</p>")
            continue
        lines = []
        for t in TURN.split(para):
            t = t.strip().lstrip("—").strip()
            if not t:
                continue
            who, cls = ("El Rincón", "pregunta") if turn % 2 == 0 else (guest, "respuesta")
            lines.append(f'<span class="turno {cls}" data-quien="{_e(who)}"><span class="raya">—</span>{_e(t)}</span>')
            turn += 1
        out.append(f'<div class="dialogo">{"".join(lines)}</div>')
    return "".join(out)


def _body_html(it):
    if it.get("formato") == "entrevista":
        guest = it.get("entrevistado") or (champ_name(it["campeon"]) if it.get("campeon") else "El entrevistado")
        return _dialogue_html(it["body"], guest)
    return _paras_html(it["body"])


PLAIN_FORMATS = ("noticia", "breve", "")


def _article(it, rel, image=False, cls="", attrs="", placard=False):
    who = ""
    if it.get("replica_de"):
        who = f'<div class="byline">Réplica de {_e(it["replica_de"])}, con la respuesta de la redacción</div>'
    elif it.get("lector"):
        who = f'<div class="byline">{_e(_firma(it["lector"]))}</div>'
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
    sub = f'<p class="sub" data-campo="subtitulo">{_e(it["subtitulo"])}</p>' if it.get("subtitulo") else ""
    if it.get("id") is not None:
        attrs += f' data-pieza="{_e(it["id"])}" id="p-{_e(it["id"])}"'
    if it.get("player"):
        attrs += f' data-jugador="{_e(it["player"])}"'
    return (f'<article class="{cls}"{attrs}>{_kicker(it, rel)}{ante}'
            f'<h3 data-campo="headline">{_e(it["headline"])}</h3>{sub}{fig}{stat}<div class="txt" data-campo="body">{_body_html(it)}</div>{who}</article>')


# --------------------------------------------------------------------------- sections
# key, title, desk, item sections it collects
BLOCKS = [
    ("sucesos", "Sucesos", "Comisaría de Piltover", {"SUCESOS"}),
    ("deportes", "Deportes", "Arena de Noxus", {"DEPORTES", "DERBI", "SOLOQ CHALLENGE"}),
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
    datos = ""
    if ed.get("ranking"):
        market = _market_table(games)
        datos = (
            '<section class="secblock sec-datos" id="sec-datos"><header class="sec-head"><h3 class="sec-name">Resultados</h3>'
            '<span class="sec-desk">Arena de Noxus · Lonja de Aguasturbias · Islas de la Sombra</span></header>'
            f'<div class="datos-grid"><div class="board"><h4 class="kicker">Resultados del día</h4>'
            f'{_ranking_table(ed["ranking"], rel)}</div>{market}</div>{_bolsa(ed)}</section>')
    voz_items = [it for it in rest if it.get("section") == "LA VOZ DE RUNETERRA"]
    rest = [it for it in rest if it.get("section") != "LA VOZ DE RUNETERRA"]   # proposals told elsewhere stay in their section
    opinion = [it for it in rest if it.get("section") in OPINION_SECTIONS]
    weather_items = [it for it in rest if it.get("section") == "EL TIEMPO"]
    ace_items = [it for it in rest if it.get("section") == "ACE LEAGUE"]
    soloq_items = [it for it in rest if it.get("section") == "SOLOQ CHALLENGE"] if ed.get("soloq") else []
    well = [it for it in rest if it.get("section") not in OPINION_SECTIONS
            and it.get("section") not in ("EL TIEMPO", "ACE LEAGUE") and it not in soloq_items]
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
    html.append(_gaceta(ed))
    html.append(datos)
    if ed.get("soloq"):
        html.append(_soloq(ed, rel) + ('<div class="sec-grid pozo">' + "".join(card(it, i) for i, it in enumerate(soloq_items))
                                        + '</div>' if soloq_items else "") + '</section>')
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
            body = (f'<article class="{"wide2" if opinion else "wide"} column" data-ed="0"><div class="kicker">La columna</div>'
                    f'<h3 data-campo="columna.titulo">{_e(col["titulo"])}</h3><div class="byline">Por {_e(col["autor"])}</div>'
                    f'<div class="cbody" data-campo="columna.cuerpo">{paras}</div></article>')
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


def _pasatiempos(ed, rel, latest, seers=None, editions_until=()):
    return (f'<section class="secblock sec-pasatiempos" id="sorteo"><header class="sec-head">'
            f'<h3 class="sec-name">Pasatiempos</h3><span class="sec-desk">¿Quién fue?, la Lonja de Coronas, sorteo, porra y horóscopo</span></header>'
            f'<div class="pasa-grid pasa-3">{_quienfue(ed, latest)}{_sorteo(ed, rel, latest)}{_porra(ed, latest, seers or [])}</div>'
            f'{_lonja(ed, list(editions_until), latest)}{_horoscopo(ed)}</section>')


def _bolsa(ed):
    b = ed.get("bolsa") or {}
    rows = [r for r in b.get("filas") or [] if r.get("cuenta")]     # older editions mixed smurfs: not shown
    if not rows:
        return ""

    def cell(e):
        if not e:
            return '<td>–</td><td class="num">–</td>'
        d = e.get("delta")
        cls, arrow = ("up", "▲") if (d or 0) > 0 else ("down", "▼") if (d or 0) < 0 else ("", "=")
        tag = f' <i>({_e(e["cambio"])})</i>' if e.get("cambio") else ""
        if d is not None:
            change = f'{arrow} {abs(d)}' if d else "="
        else:
            change = "?" if e.get("dudoso") else "nuevo"
        return f'<td>{_e(e["posicion"])}{tag}</td><td class="num {cls}">{change}</td>'

    people = {}
    for r in rows:      # already in order: each person with the main account first and the smurfs below
        people.setdefault(r["slug"], []).append(r)

    def account(r):
        smurf = "" if r.get("principal", True) else ' <span class="tipo">smurf</span>'
        return f'<td class="cuenta{"" if r.get("principal", True) else " smurf"}">{_e(r["cuenta"])}{smurf}</td>'

    def person(accs):
        name = f'<th scope="rowgroup" rowspan="{len(accs)}" class="jug">{_e(accs[0]["alias"])}</th>'
        return ('<tbody class="persona">' + "".join(
            f'<tr>{name if i == 0 else ""}{account(r)}{cell(r.get("solo"))}{cell(r.get("flex"))}</tr>'
            for i, r in enumerate(accs)) + '</tbody>')
    def moved(r):
        return any((r.get(q) or {}).get("delta") or (r.get(q) or {}).get("cambio") for q in ("solo", "flex"))
    head = ('<div class="tablewrap"><table><thead><tr><th>Jugador</th><th>Cuenta</th><th>SoloQ</th><th class="num">LP</th>'
            '<th>Flex</th><th class="num">LP</th></tr></thead>')
    movers = {}
    for slug, accs in people.items():
        if any(moved(r) for r in accs):
            movers[slug] = [r for r in accs if moved(r)]
    body = "".join(person(accs) for accs in people.values())
    since = f' (frente al {short_date(_date(b["desde"]))})' if b.get("desde") else ""
    top = (head + "".join(person(accs) for accs in movers.values()) + '</table></div>' if movers else
           '<p class="small">Ninguna cuenta se ha movido desde la última vez. Ni para arriba ni, milagro, para abajo.</p>')
    return (f'<div class="board bolsa"><h4 class="kicker">Bolsa de LP{_e(since)}</h4>{top}'
            f'<details class="bolsa-todo"><summary>Ver todas las cuentas</summary>{head}{body}</table></div>'
            '<p class="small bolsa-nota">Cada cuenta se compara solo consigo misma, con la última vez que la miramos '
            '(normalmente el día anterior); los smurfs van aparte, en la fila de su dueño. La cifra es la diferencia en LP '
            'contando 100 por división y 400 por liga: pasar de Oro IV con 20 LP a Plata I con 80 LP son ▼ 40. '
            '«nuevo»: es la primera vez que vemos esa cuenta en esa cola. «?»: el cambio no cuadra con las partidas '
            'jugadas y no se cuenta.</p></details></div>')


def _soloq(ed, rel):
    """The SoloQ Challenge as the edition closed: the table (or, before the starting gun, who signed
    up) and a link to the board. Returns an open <section> so the day's stories about the race can
    go inside it."""
    sq = ed["soloq"]
    rows = sq.get("clasificacion") or []

    def name(x):
        n = x.get("nombre") or x.get("apodo")
        return f'<a href="{rel}jugadores/{_e(x["jugador"])}.html">{_e(n)}</a>' if x.get("jugador") else _e(n)

    def move(x):
        c = x.get("cambio_de_puesto")
        if c is None:
            return '<span class="small">nuevo</span>'
        return '=' if not c else f'<span class="{"up" if c > 0 else "down"}">{"▲" if c > 0 else "▼"} {abs(c)}</span>'

    def lp(n):
        return "–" if n is None else ("=" if not n else f'<span class="{"up" if n > 0 else "down"}">{n:+d}</span>')

    fase = sq.get("fase")
    days = sq.get("dias_restantes")
    when = ("Terminado" if fase == "finalizado" else "Inscripciones abiertas" if fase == "inscripcion" else
            f'Día {sq.get("dia_del_reto")}' + (f' · quedan {days} {"día" if days == 1 else "días"}' if days is not None else ""))
    head = (f'<section class="secblock sec-soloq" id="sec-soloq"><header class="sec-head"><h3 class="sec-name">'
            f'{_e(sq.get("nombre") or "SoloQ Challenge")}</h3><span class="sec-desk">Enviado especial a la cola de Solo/Dúo · '
            f'{_e(when)}</span></header>')
    if not rows:
        return head
    if fase == "inscripcion":
        body = "".join(f'<tr><td class="num">{i}</td><td>{name(x)}</td><td>{_e(x.get("mote") or "")}</td>'
                       f'<td>{_e(x.get("objetivo_declarado") or "–")}</td></tr>' for i, x in enumerate(rows, 1))
        table = ('<div class="board"><h4 class="kicker">Inscritos con su cuenta de cero</h4><div class="tablewrap"><table>'
                 '<thead><tr><th class="num">#</th><th>Jugador</th><th>Mote</th><th>Promete</th></tr></thead>'
                 f'<tbody>{body}</tbody></table></div>')
    else:
        body = "".join(
            f'<tr><td class="num">{x["puesto"]}</td><td class="num">{move(x)}</td><td>{name(x)}</td><td>{_e(x["liga"])}</td>'
            f'<td class="num">{lp(x.get("lp_en_el_dia"))}</td><td class="num">{x["victorias_dia"]}–{x["derrotas_dia"]}</td>'
            f'<td class="num">{x["victorias_reto"]}–{x["derrotas_reto"]}</td></tr>' for x in rows[:12])
        table = ('<div class="board"><h4 class="kicker">La clasificación al cierre de esta edición</h4><div class="tablewrap"><table>'
                 '<thead><tr><th class="num">#</th><th class="num">±</th><th>Jugador</th><th>Liga</th><th class="num">LP del día</th>'
                 '<th class="num">Día</th><th class="num">Reto</th></tr></thead>'
                 f'<tbody>{body}</tbody></table></div>')
    return head + table + (f'<p class="small">La gráfica, las notas clavadas y la inscripción, en '
                           f'<a href="{rel}soloq/index.html">el tablón del SoloQ Challenge</a>.</p></div>')


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
        out.append(f'<div class="breve f-{slugify(it.get("formato") or "")}" data-pieza="{_e(it["id"])}" id="p-{_e(it["id"])}"><div class="bk">{_e(it["section"])}</div>'
                   f'<h5 data-campo="headline">{_e(it["headline"])}</h5><div class="txt" data-campo="body">{_paras_html(it["body"])}</div>'
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


# --------------------------------------------------------------------------- the day at a glance and the newsroom's extras
SHORT_QUEUE = {"Ranked Flex": "Flex", "Ranked Solo/Dúo": "SoloQ", "Normal Draft": "Normal"}


def _jornada(ed, cfg, rel):
    """«La jornada en 30 segundos»: every game of the day in order, so the stories never have to list them."""
    games = ed.get("games") or []
    if not games:
        return ""
    tz = get_tz(cfg.get("timezone", "Europe/Madrid"))
    by_match = defaultdict(list)
    for g in games:
        by_match[g["match"]].append(g)
    rows = []
    flex_w = flex_l = solo_w = solo_l = 0
    for mid, gs in by_match.items():
        start = min(g["end"] - g["dur"] * 1000 for g in gs)
        q = SHORT_QUEUE.get(gs[0]["queue_name"], gs[0]["queue_name"])
        sides = defaultdict(list)
        for g in gs:
            sides[g["win"]].append(g)
        for won, team in sorted(sides.items(), key=lambda kv: not kv[0]):
            if q == "Flex" and len(team) >= 2:
                label = f"Flex del grupo ({len(team)})"
                flex_w, flex_l = flex_w + won, flex_l + (not won)
            elif q == "SoloQ" and len(team) >= 2:
                label = "DuoQ"
            else:
                label = q
            if q == "SoloQ":
                solo_w, solo_l = solo_w + won * len(team), solo_l + (not won) * len(team)
            if len(sides) == 2:
                label += " · derbi"
            who = " · ".join(f'<a href="{rel}jugadores/{_e(g["slug"])}.html">{_e(g["alias"])}</a> '
                             f'<span class="small">{_e(champ_name(g["champ"]))} {g["k"]}/{g["d"]}/{g["a"]}</span>'
                             for g in sorted(team, key=lambda g: g["alias"].lower()))
            rows.append((start, f'<li><time>{ms_to_local(start, tz):%H:%M}</time><div><span class="cola">{_e(label)}</span>{who}</div>'
                                f'<span class="res {"win" if won else "loss"}">{"V" if won else "D"}</span></li>'))
    rows.sort(key=lambda r: r[0])
    t = ed["totals"]
    bits = [f'{len(ed.get("ranking") or [])} jugaron', f'{t["games"]} partidas del grupo']
    if flex_w + flex_l:
        bits.append(f"Flex del grupo: {flex_w}–{flex_l}")
    if solo_w + solo_l:
        bits.append(f"SoloQ/DuoQ: {solo_w}–{solo_l}")
    return ('<section class="secblock jornada" id="jornada"><header class="sec-head"><h3 class="sec-name">La jornada en 30 segundos</h3>'
            '<span class="sec-desk">Todas las partidas de ayer, en orden</span></header>'
            f'<p class="resumen">{" · ".join(bits)}.</p><ol>{"".join(r for _, r in rows)}</ol></section>')


def _gaceta(ed):
    g = ed.get("gaceta")
    if not g:
        return ""
    return ('<section class="secblock sec-gaceta" id="gaceta"><header class="sec-head"><h3 class="sec-name">Lo que dice la competencia</h3>'
            '<span class="sec-desk">Reproducido sin permiso y sin ganas</span></header>'
            '<article class="gaceta" data-ed="0"><div class="sello">¡EXCLUSIVA!</div><div class="cab">La Gaceta de Noxus</div>'
            '<div class="lema">El diario que no se arrodilla · Sale cuando el Rincón miente</div>'
            f'<h3>{_e(g["titular"])}</h3><div class="txt">{_paras_html(g["cuerpo"])}</div>'
            f'<div class="byline">Firma: {_e(g["firma"])}</div></article></section>')


def _franja(ed, latest):
    """Under the front page: today's question for the popular jury, yesterday's verdict and how the
    things the paper promised to watch ended."""
    boxes = []
    abierto = ' data-abierto="1"' if latest else ""
    j = ed.get("jurado")
    if j:
        ops = "".join(f'<button type="button" class="jurado-op" data-i="{i}"><span class="barra"></span>'
                      f'<span>{_e(o)}</span><span class="n"></span></button>' for i, o in enumerate(j["opciones"]))
        boxes.append(f'<div class="jurado" id="jurado" data-edicion="{_e(ed["date"])}"{abierto}>'
                     f'<h4>{"El Juicio del Mes" if j.get("juicio") else "El jurado popular"}</h4>'
                     f'<p class="preg">{_e(j["pregunta"])}</p>{ops}<p class="small msg"></p></div>')
    prev = ed.get("jurado_ayer")
    if prev and (prev.get("total") or ed.get("jurado_veredicto")):
        total = prev.get("total") or 0
        bars = "".join(
            f'<button type="button" class="jurado-op" disabled><span class="barra" style="width:{round(100 * o["votos"] / total) if total else 0}%"></span>'
            f'<span>{_e(o["texto"])}</span><span class="n">{o["votos"]}</span></button>' for o in prev["opciones"])
        boxes.append(f'<div class="veredicto"><h4>Veredicto de ayer</h4><p class="preg">{_e(prev["pregunta"])}</p>{bars}'
                     + (f'<p class="fallo">{_e(ed["jurado_veredicto"])}</p>' if ed.get("jurado_veredicto") else "")
                     + f'<p class="small">{total} voto{"s" if total != 1 else ""}.</p></div>')
    if ed.get("promesas"):
        lis = "".join(f'<li><b>{_e(p["pregunta"])}</b>{_e(p["texto"])}</li>' for p in ed["promesas"])
        boxes.append(f'<div class="promesas"><h4>Lo que prometimos ayer</h4><ul>{lis}</ul></div>')
    return f'<div class="franja">{"".join(boxes)}</div>' if boxes else ""


def _manana(ed):
    if not ed.get("manana"):
        return ""
    lis = "".join(f'<li>{_e(m["texto"])}</li>' for m in ed["manana"])
    return ('<section class="secblock manana" id="manana"><header class="sec-head"><h3 class="sec-name">Mañana en El Rincón</h3>'
            f'<span class="sec-desk">Lo que la redacción vigila esta noche</span></header><ul>{lis}</ul></section>')


def _quienfue(ed, latest):
    q = ed.get("quien_fue")
    if not q:
        return ""
    data = {k: q[k] for k in ("pistas", "opciones", "clave", "campeon", "alias")}
    abierto = ' data-abierto="1"' if latest else ""
    return (f'<div class="quienfue" id="quienfue" data-edicion="{_e(ed["date"])}"{abierto}>'
            '<h4>¿Quién fue?</h4><p class="small">Una partida de ayer, sin nombre. Cada fallo destapa una pista más.</p>'
            f'<ol></ol><div class="qf-ops"></div><p class="qf-fin"></p><p class="small qf-detectives"></p>'
            f'<script type="application/json">{_json_script(data)}</script></div>')


def _json_script(data):
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def _lonja(ed, editions_until, latest):
    mk = ed.get("mercados")
    if not mk:
        return ""
    markets = []
    for m in mk["lista"]:
        ops = "".join(f'<label class="op"><input type="radio" name="op-{_e(m["id"])}" value="{_e(o["id"])}" data-t="{_e(o["texto"])}">'
                      f'{_e(o["texto"])} <b>×{fmt_num(o["cuota"], 1)}</b></label>' for o in m["opciones"])
        form = ('<form class="apostar"><input type="number" name="importe" min="1" step="1" placeholder="Coronas" aria-label="Coronas">'
                '<button type="submit">Apostar</button><span class="small msg"></span></form>') if latest else ""
        markets.append(f'<div class="mercado" data-id="{_e(m["id"])}"><p>{_e(m["pregunta"])}</p><div class="ops">{ops}</div>'
                       f'{form}<div class="mias"></div></div>')
    prev = editions_until[-2]["date"] if len(editions_until) > 1 else None
    results = [r for r in (LEDGER.get("resultados") or {}).values() if r["edicion"] == prev]
    res_html = ""
    if results:
        def line(r):
            if r["nula"]:
                return f'<div class="resuelto">{_e(r["pregunta"])} <i>Anulada: se devuelve lo apostado.</i></div>'
            won = [a for a in r["apuestas"] if a["premio"]]
            return (f'<div class="resuelto">{_e(r["pregunta"])} <b>{_e(", ".join(r["ganadoras"]) or "—")}</b>. '
                    + (("Cobran: " + ", ".join(f'{_e(a["nombre"])} ({a["premio"]})' for a in won)) if won else
                       ("Nadie acertó." if r["apuestas"] else "Nadie apostó.")) + '</div>')
        res_html = '<h5 class="kicker" style="margin-top:12px">Así acabaron los mercados de ayer</h5>' + "".join(line(r) for r in results)
    board = (LEDGER.get("cuentas") or [])[:8]
    rank = ""
    if board:
        rank = ('<h5 class="kicker" style="margin-top:12px">Los más ricos de la Lonja</h5><div class="tablewrap"><table><tbody>'
                + "".join(f'<tr><td>{i + 1}</td><td>{_e(a["nombre"])}</td><td class="num">{a["saldo"]}</td>'
                          f'<td class="small">{"rescatado ×" + str(a["rescates"]) if a["rescates"] else ""}</td></tr>'
                          for i, a in enumerate(board)) + '</tbody></table></div>')
    corte = datetime.fromtimestamp((ed.get("generated_at") or ed["window"][1]) / 1000, timezone.utc).isoformat()
    if LEDGER.get("hasta"):
        corte = LEDGER["hasta"]
    data = {"cierre": mk["cierre"], "mercados": [m["id"] for m in mk["lista"]], "inicial": coronas.SALDO_INICIAL,
            "saldos": {a["nombre"].lower(): a["saldo"] for a in LEDGER.get("cuentas") or []}, "corte": corte}
    tz_close = datetime.fromisoformat(mk["cierre"].replace("Z", "+00:00"))
    abierto = ' data-abierto="1"' if latest else ""
    return (f'<div class="lonja" id="lonja"{abierto}><h4>La Lonja de Coronas</h4>'
            '<p class="saldo"></p><p class="small" style="text-align:center">Apuesta coronas sobre la próxima edición. Se paga según la cuota; '
            f'las apuestas cierran a las {tz_close.astimezone(get_tz("Europe/Madrid")):%H:%M} y se resuelven mañana.</p>'
            '<p class="small lj-cerrado" hidden><b>Apuestas cerradas.</b> Se resuelven en la próxima edición.</p>'
            + '<div class="mercados">' + "".join(markets) + '</div>'
            + ('<div class="pie-lonja">' + (f'<div>{res_html}</div>' if res_html else "") + (f'<div>{rank}</div>' if rank else "")
               + '</div>' if res_html or rank else "")
            + f'<script type="application/json">{_json_script(data)}</script></div>')


def _ed_datos(ed):
    """What «Tu edición» needs for each player: the stories about them, their day and their forecast."""
    rk = ed.get("ranking") or []
    pos = {r["slug"]: (i + 1, f'{r["wins"]}–{r["losses"]}') for i, r in enumerate(rk)}
    tiempo = {t["jugador"]: t["texto"] for t in ed.get("tiempo") or []}
    alias = {r["slug"]: r["alias"] for r in rk}
    alias.update({f["slug"]: f["alias"] for f in ROSTER})
    players = {}
    for it in ed.get("items") or []:
        text = f'{it["headline"]} {it.get("subtitulo") or ""} {it["body"]}'.lower()
        for slug, name in alias.items():       # the stories about them, and the ones that name them
            if it.get("player") == slug or name.lower() in text:
                players.setdefault(slug, []).append([it.get("id"), it["headline"]])
    out = {}
    for slug in sorted(set(players) | set(pos) | set(tiempo)):   # sorted: the same page every build
        p, dia = pos.get(slug, (None, None))
        out[slug] = {"piezas": players.get(slug, []), "puesto": p, "de": len(rk), "dia": dia, "tiempo": tiempo.get(slug)}
    data = {"jugadores": out, "saldos": {a["nombre"].lower(): a["saldo"] for a in LEDGER.get("cuentas") or []}}
    return f'<script type="application/json" id="ed-datos">{_json_script(data)}</script>'


IMPRENTA_DESDE = "2026-10-20"   # from here on, the robot's template stories are never published


def en_imprenta(ed):
    """An edition Claude has not written yet: the page shows only the day's data."""
    return not ed.get("ai") and ed["date"] >= IMPRENTA_DESDE


def render_edition(cfg, ed, editions_until, rel, latest=False):
    imprenta = en_imprenta(ed)
    items = [] if imprenta else ed["items"]
    lead = items[0] if items else None
    v2 = (ed.get("ai") or {}).get("formato") == 2 or imprenta
    rest = [it for it in items[1:] if not (v2 and it.get("peso") == "breve")]
    breves = [it for it in items[1:] if v2 and it.get("peso") == "breve"]
    ticker = " ".join(f"<span>{_e(i['headline'])}</span>" for i in items[:8])
    t = ed["totals"]
    lead_html = ""
    if lead:
        who = (f'<div class="who"><a href="{rel}jugadores/{_e(lead["player"])}.html">{_e(lead["alias"])}</a></div>'
               if lead.get("player") else "")
        sent = f'<div class="byline">{_e(_firma(lead["lector"]))}</div>' if lead.get("lector") else ""
        stat_box = (f'<div class="bigstat"><div class="n">{_e(lead["stat"])}</div>'
                    f'<div class="l">{_e(lead["stat_label"])}</div>{who}</div>') if lead.get("stat") else ""
        sub = f'<p class="sub" data-campo="subtitulo">{_e(lead["subtitulo"])}</p>' if lead.get("subtitulo") else ""
        lead_html = (f'<section class="lead{" lead-v2" if v2 else ""}" data-pieza="{_e(lead.get("id", 0))}"><div>{_kicker(lead, rel)}'
                     f'<h2 data-campo="headline">{_e(lead["headline"])}</h2>{sub}<div class="txt" data-campo="body">{_body_html(lead)}</div>{sent}</div>'
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
    since = season_start()
    since = since if since and ed["date"] >= since else None     # older pages keep their own standings
    board = general_leaderboard(editions_until, since=since)
    writer = ""
    if ed.get("written_by"):
        version = (ed.get("ai") or {}).get("version")
        writer = (f'<p class="small" style="margin-top:10px">Redacción: {_e(ed["written_by"])}'
                  + (f' (versión {version})' if version and version > 1 else "") + '.</p>')
    if imprenta:
        special = ('<section class="special t-negro"><div class="kicker">En imprenta</div>'
                   '<h2>La redacción está escribiendo la edición de hoy</h2>'
                   '<p>Sale a lo largo de la mañana. Mientras tanto, los números fríos del día, que no mienten '
                   'aunque duelan.</p></section>')
    body = f"""
<div class="ticker"><b>ÚLTIMA HORA</b><div class="run">{ticker}</div></div>
{'<button type="button" class="tu-pestana" id="tu-pestana" aria-controls="tu-edicion" aria-expanded="false" hidden>Tu edición</button><aside class="tu-edicion" id="tu-edicion" aria-hidden="true" aria-label="Tu edición"></aside>' if latest and not imprenta else ""}
{special}
{lead_html}
{_franja(ed, latest)}
<div class="cols edicion">
  <main>{_jornada(ed, cfg, rel)}{_sections_v2(ed, rest, rel) if v2 else _sections(ed, rest, rel)}{_pasatiempos(ed, rel, latest, seers(editions_until), editions_until)}{_manana(ed)}{_comments(ed)}</main>{_fillers(ed)}{_ed_datos(ed)}
  <aside>
    <div class="box"><h4>General de la vergüenza</h4>{_general_table(board, rel, since)}</div>
    {"" if imprenta else f'<div class="box" data-ed="0"><h4>Frase del día</h4><p class="quote">«<span data-campo="frase">{_e(ed["frase"])}</span>»</p></div>'}
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
        reparto = ", ".join(_e(n) for n in h.get("reparto", []))
        tag = '<span class="etiqueta">La redacción</span>' if canon_mod.is_redaccion(h) else ""
        blocks.append(f'<article class="saga-ficha est-{est}" id="{_e(h["id"])}"><div class="kicker">{_e(est.upper())}'
                      f'<span class="desk"> · desde el {_e(short_date(_date(h["abierto"])))}</span>{tag}</div>'
                      f'<h3>{_e(h["titulo"])}</h3><p>{_e(h.get("resumen", ""))}</p>'
                      + (f'<p class="small">Protagonistas: {prot}</p>' if prot else "")
                      + (f'<p class="small">Reparto: {reparto}</p>' if reparto else "")
                      + (f'<ol class="capitulos">{caps}</ol>' if caps else "") + '</article>')
    def member(e):
        v = canon_mod.cast_view(e)
        bits = [f'<b>{_e(v["nombre"])}</b>, {_e(v.get("cargo", ""))}.']
        if v.get("rasgo"):
            bits.append(f'<i>{_e(v["rasgo"])}</i>')
        if v.get("estado"):
            bits.append(f'<br><span class="small"><b>Situación:</b> {_e(v["estado"])}</span>')
        if v.get("deseo"):
            bits.append(f'<br><span class="small"><b>Quiere:</b> {_e(v["deseo"])}</span>')
        if v.get("relacion"):
            bits.append(f'<br><span class="small"><b>Con los demás:</b> {_e(v["relacion"])}</span>')
        if v.get("secreto"):
            bits.append(f'<br><span class="small"><b>Secreto:</b> <span class="secreto" tabindex="0" '
                        f'title="Pasa por encima si te atreves">{_e(v["secreto"])}</span></span>')
        return "<li>" + " ".join(bits) + "</li>"
    cast = "".join(member(e) for e in canon["elenco"])
    names = {s: p.get("alias", s) for s, p in canon["personajes"].items()}
    union = "".join(f'<li><span class="small">{_e(short_date(_date(d["fecha"])))}</span> <b>{_e(d["campeon"])}</b> denuncia a '
                    f'<a href="jugadores/{_e(d["jugador"])}.html">{_e(names.get(d["jugador"], d["jugador"]))}</a>: {_e(d["motivo"])}</li>'
                    for d in reversed(canon.get("sindicato") or []))
    body = (f'<section class="secblock"><header class="sec-head"><h3 class="sec-name">Sagas</h3>'
            f'<span class="sec-desk">Las historias que el periódico no deja de contar</span></header>'
            f'<div class="sec-grid sagas">{"".join(blocks) or "<p>Aún no hay sagas.</p>"}</div></section>'
            f'<section class="secblock"><header class="sec-head"><h3 class="sec-name">El elenco</h3>'
            f'<span class="sec-desk">Personajes fijos de la redacción, con lo que quieren y lo que esconden</span></header>'
            f'<ul class="elenco">{cast}</ul></section>'
            + (f'<section class="secblock" id="sindicato"><header class="sec-head"><h3 class="sec-name">El Sindicato de Campeones Maltratados</h3>'
               f'<span class="sec-desk">Registro de denuncias</span></header><ul class="sindicato">{union}</ul></section>' if union else ""))
    return page(cfg, f"Sagas · {cfg['site_title']}", body, "", pagina="sagas")


def render_puntuacion(cfg):
    since = season_start()
    body = f"""
<section class="secblock" style="margin-top:20px">
<header class="sec-head"><h3 class="sec-name">Cómo se puntúa la vergüenza</h3><span class="sec-desk">Reglamento oficial de la General</span></header>
<div class="reglamento">
<h4>1. La vergüenza de cada partida</h4>
<p>Cada partida da una nota de vergüenza. Cuanto más alta, peor. Se calcula así:</p>
<ul>
<li><b>+1,2</b> por cada muerte.</li>
<li><b>−0,5</b> por cada asesinato y <b>−0,3</b> por cada asistencia (lo bueno resta).</li>
<li>Si no juegas de soporte: <b>+0,5</b> por cada punto que te falte para llegar al 20 % del daño de tu equipo,
y <b>+3</b> si fuiste el que menos daño hizo.</li>
<li><b>+2,5</b> si perdiste.</li>
<li><b>+3</b> si moriste 10 veces o más.</li>
<li><b>+0,12</b> por cada punto que te falte para participar en el 40 % de los asesinatos de tu equipo.</li>
<li><b>−2</b> si ganaste con un KDA de 5 o más.</li>
</ul>
<h4>2. La vergüenza del día</h4>
<p>Es la media de tus partidas del día, más <b>0,5</b> por cada derrota. Con eso se ordena la tabla de
resultados de cada edición, de peor a mejor.</p>
<h4>3. Los puntos de la General</h4>
<p>Cada día, de los que tuvieron un día <b>malo de verdad</b> (vergüenza del día por encima de cero), el peor
se lleva <b>5 puntos</b>, el segundo <b>3</b>, el tercero <b>2</b> y el cuarto <b>1</b>. Si te sale un buen día,
no sumas nada. Si eres el único que ha jugado ese día, no hay con quién compararte: solo puntúas si tu
día ha sido un desastre (vergüenza de 5 o más). Si nadie la lía, nadie puntúa. Llevarse los 5 puntos
cuenta como una <b>portada</b>.</p>
<h4>4. Temporadas</h4>
<p>{f"La temporada actual empezó el {_e(long_date(_date(since)))}, cuando se puso a cero la General para corregir un error de la fórmula anterior, que daba puntos a quien jugaba solo aunque hiciera buenas partidas." if since else "La General cuenta desde la primera edición."}</p>
</div>
</section>"""
    return page(cfg, f"Cómo se puntúa · {cfg['site_title']}", body, "", pagina="puntuacion")


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


def _logros(slug, alias, games, editions, owner=None):
    """Achievements (good and mostly bad) earned in the archive."""
    out = []
    portadas = sum(1 for e in editions for s, pts in day_points(e.get("ranking", [])).items()
                   if pts == POINTS[0] and _owner_of(e, owner)(s) == slug)
    if portadas:
        out.append(("💀", f"Portada de la vergüenza ×{portadas}"))
    faros = sum(1 for e in editions for it in e["items"] if it.get("player") and _owner_of(e, owner)(it["player"]) == slug
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
    arc = canon_mod.current_arc(p)
    if arc:
        rows.insert(0, f'<li><b>Su historia:</b> <span class="arco">{_e(arc["tipo"].capitalize())}</span>. {_e(arc["texto"])}</li>')
    union = [d for d in canon.get("sindicato") or [] if d["jugador"] == slug]
    if union:
        rows.append('<li><b>Denuncias del Sindicato:</b> ' + " · ".join(f'{_e(d["campeon"])} ({_e(d["motivo"])})'
                                                                         for d in union[-4:]) + '</li>')
    hilos = [h for h in canon["hilos"] if slug in h.get("protagonistas", [])]
    if hilos:
        rows.append('<li><b>Sagas:</b> ' + ", ".join(f'<a href="../sagas.html#{_e(h["id"])}">{_e(h["titulo"])}</a>'
                                                   for h in hilos) + '</li>')
    return (f'<div class="box ficha-rt"><h4>Ficha de Runeterra</h4>'
            + (f'<p class="titulo-rt">{_e(title)}</p>' if title else "")
            + (f'<p class="small faccion">{_e(p["faccion"])}</p>' if p.get("faccion") else "")
            + f'<ul>{"".join(rows)}</ul></div>')


def _owner_of(ed, owner):
    """In an old edition, who each name really was (by account): a smurf counts for its owner."""
    rid = {r["slug"]: (r.get("riot_id") or "").lower() for r in ed.get("ranking", [])}
    return lambda s: (owner or {}).get(rid.get(s), s)


def render_player(cfg, friend, editions, canon=None, owner=None):
    slug = friend["slug"]
    canon = canon or canon_mod.empty()
    games, items, scores = [], [], []
    portadas = 0
    for ed in editions:
        who = _owner_of(ed, owner)
        for i, r in enumerate(ed.get("ranking", [])):
            if who(r["slug"]) == slug:
                scores.append(r["score"])
                portadas += 1 if i == 0 else 0
        games += [dict(g, date=ed["date"]) for g in ed.get("games", []) if who(g["slug"]) == slug]
        items += [dict(it, date=ed["date"]) for it in ed["items"] if it.get("player") and who(it["player"]) == slug]
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
    logros = _logros(slug, friend["alias"], games, editions, owner)
    logros_html = ('<div class="box logros"><h4>Logros (y deshonras)</h4><ul>'
                   + "".join(f'<li><span>{i}</span>{_e(t)}</li>' for i, t in logros) + '</ul></div>') if logros else ""
    body = f"""
<section class="profile">
  <div><div class="kicker">Ficha policial</div><h2>{_e(friend["alias"])}</h2>
    <p class="small">{_e(" · ".join(friend.get("cuentas") or [friend["riot_id"]]))} · {g} partidas registradas</p>
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
        if en_imprenta(ed):
            return "En imprenta"
        return ed["items"][0]["headline"] if ed["items"] else "Sin noticias"
    lis = "".join(
        f'<li><span class="small">{_e(long_date(_date(ed["date"])).capitalize())}<br>Edición nº {ed["number"]}</span>'
        f'<a href="ediciones/{ed["date"]}.html">{_e(title(ed))}</a></li>'
        for ed in reversed(editions))
    body = (f'<section class="secblock"><header class="sec-head"><h3 class="sec-name">Hemeroteca</h3>'
            f'<span class="sec-desk">Todas las ediciones</span></header>'
            f'<ul class="archive">{lis or "<li>Aún no hay ediciones.</li>"}</ul></section>')
    return page(cfg, f"Hemeroteca · {cfg['site_title']}", body, "", pagina="hemeroteca")


def _redirect_page(cfg, old_alias, person):
    body = (f'<section class="secblock"><header class="sec-head"><h3 class="sec-name">{_e(old_alias)}</h3></header>'
            f'<p>{_e(old_alias)} es una cuenta de <a href="{_e(person["slug"])}.html">{_e(person["alias"])}</a>. '
            'Su ficha está ahí.</p></section>')
    html = page(cfg, f"{old_alias} · {cfg['site_title']}", body, "../")
    return html.replace("<head>", f'<head>\n<meta http-equiv="refresh" content="0; url={_e(person["slug"])}.html">', 1)


def render_players_index(cfg, friends, editions):
    board = {t["slug"]: t for t in general_leaderboard(editions)}
    cards = "".join(
        f'<article><div class="kicker">{_e(" · ".join(f.get("cuentas") or [f["riot_id"]]))}</div><h3><a href="jugadores/{_e(f["slug"])}.html">'
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

    # people: the accounts in friends.json grouped by alias (a smurf shares its owner's alias)
    people = {}
    for f in friends:
        person = people.setdefault(f["slug"], {"slug": f["slug"], "alias": f["alias"], "riot_id": f["riot_id"], "cuentas": []})
        person["cuentas"].append(f["riot_id"])
    owner = {f["riot_id"].lower(): f["slug"] for f in friends}
    redirects = {}
    for ed in editions:
        for r in ed.get("ranking", []):
            rid = (r.get("riot_id") or "").lower()
            if rid in owner:
                if owner[rid] != r["slug"] and r["slug"] not in people:
                    redirects[r["slug"]] = (r["alias"], owner[rid])   # an old name that is now someone's smurf
                continue
            people.setdefault(r["slug"], {"slug": r["slug"], "alias": r["alias"], "riot_id": r.get("riot_id", ""),
                                          "cuentas": [r.get("riot_id", "")], "antiguo": True})
    friends_all = list(people.values())
    ROSTER[:] = [{"slug": f["slug"], "alias": f["alias"], "cuentas": f["cuentas"]} for f in friends_all if not f.get("antiguo")]
    ACE.clear()
    ACE.update(load_json(ROOT / "data" / "ace_league.json", None) or {})
    LEDGER.clear()
    LEDGER.update(coronas.ledger(editions, coronas.stored_bets()))
    LEDGER["hasta"] = datetime.now(timezone.utc).isoformat()

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
    (out / "puntuacion.html").write_text(render_puntuacion(cfg), encoding="utf-8")
    canon = canon if canon is not None else canon_mod.load()
    (out / "sagas.html").write_text(render_sagas(cfg, canon, editions), encoding="utf-8")
    for f in friends_all:
        (out / "jugadores" / f"{f['slug']}.html").write_text(render_player(cfg, f, editions, canon, owner), encoding="utf-8")
    for old, (alias, slug) in redirects.items():
        (out / "jugadores" / f"{old}.html").write_text(_redirect_page(cfg, alias, people[slug]), encoding="utf-8")
    # profiles of names that no longer exist (renamed or turned into smurfs) are removed
    wanted = {f"{f['slug']}.html" for f in friends_all} | {f"{old}.html" for old in redirects}
    for stale in (out / "jugadores").glob("*.html"):
        if stale.name not in wanted:
            stale.unlink()
    return out
