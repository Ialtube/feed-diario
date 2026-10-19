"""Static site generator: a daily old-style newspaper, an archive, player pages,
reader comments and the "propose a story" page."""
import json
from collections import defaultdict
from datetime import date
from html import escape
from pathlib import Path

from .roasts import DESKS
from .util import champ_name, fmt_int, fmt_num, fmt_pct, long_date, short_date

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
  font-family:"Libre Caslon Text",Georgia,serif;line-height:1.55;font-size:18px}
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
/* front page: lead story + figures + contents on the left, the boxes on the right */
.front{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:0 36px;border-bottom:3px double var(--ink);padding-bottom:24px}
.front aside{border-left:1px solid var(--rule);padding-left:28px}
.lead h2{font-family:"Old Standard TT",Georgia,serif;font-weight:700;font-size:clamp(2.2rem,4.4vw,4rem);line-height:1.02;margin:6px 0 16px}
.lead-grid{display:grid;grid-template-columns:1.25fr 1fr;gap:28px;align-items:start}
.lead-grid figure{margin:0}
.lead-text p{font-size:1.14rem;line-height:1.6;text-align:justify;hyphens:auto}
.lead-text p.dc::first-letter,.flow>article:first-child>p.dc::first-letter,.feature p.dc::first-letter,.solo>p.dc::first-letter{
  font-family:"Old Standard TT",serif;font-weight:700;float:left;font-size:3.9em;line-height:.8;padding:5px 8px 0 0;color:var(--ink)}
.lead.nofig .lead-grid{grid-template-columns:1fr}
.lead.nofig .lead-text p{column-count:2;column-gap:30px;column-rule:1px solid var(--rule)}
.cifras{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--ink);border-bottom:1px solid var(--ink);margin:22px 0 0}
.cifras div{text-align:center;padding:10px 6px;border-left:1px solid var(--rule)}
.cifras div:first-child{border-left:0}
.cifras b{display:block;font-family:"Old Standard TT",serif;font-size:clamp(1.7rem,3vw,2.4rem);line-height:1.05;color:var(--accent)}
.cifras span{font-family:"IM Fell English SC",serif;font-size:.95rem;color:var(--muted)}
.sumario{margin-top:18px}
.sumario h4{font-family:"IM Fell English SC",serif;font-weight:400;font-size:1.1rem;letter-spacing:.08em;margin-bottom:6px}
.sumario ol{list-style:none;column-count:2;column-gap:30px;column-rule:1px solid var(--rule)}
.sumario li{break-inside:avoid;padding:7px 0;border-bottom:1px dotted var(--rule);line-height:1.3}
.sumario li a{text-decoration:none}
.sumario li b{display:block;font-family:"IM Fell English SC",serif;font-weight:400;font-size:.9rem;color:var(--accent);letter-spacing:.05em}
.sumario li span{font-family:"Old Standard TT",serif;font-weight:700;font-size:1.05rem}
.sumario li a:hover span{text-decoration:underline}
.bigstat{border:4px double var(--ink);padding:16px;text-align:center;margin-top:16px}
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
.lead .meme span{font-size:clamp(1.3rem,2.6vw,2.1rem)}
.feature .meme span{font-size:clamp(1.2rem,2.3vw,1.9rem)}
figcaption{font-family:"Old Standard TT",serif;font-style:italic;font-size:.9rem;color:var(--muted);margin-top:5px;text-align:center}
/* layout */
.cols{display:grid;grid-template-columns:1fr 320px;gap:34px;margin-top:6px}
.cols>*,.front>*,.lead-grid>*,.profile>*,.sec-grid>*,.sec-row>*,.with-board>*,.feature>*,.op-grid>*,.cgrid>*{min-width:0}
/* sections */
.secblock{margin-top:34px}
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:6px 16px;flex-wrap:wrap;
  border-top:4px double var(--ink);border-bottom:1px solid var(--ink);padding:6px 0 4px;margin-bottom:16px}
.sec-name{font-family:"UnifrakturMaguntia",serif;font-weight:400;font-size:clamp(1.8rem,3.2vw,2.6rem);line-height:1}
.sec-desk{font-family:"Old Standard TT",serif;font-style:italic;color:var(--muted);font-size:1.02rem}
.sec-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:0 28px}
.sec-grid article{border-top:1px solid var(--rule);padding:12px 0 16px}
article h3{font-family:"Old Standard TT",Georgia,serif;font-weight:700;font-size:1.48rem;line-height:1.14;margin:4px 0 9px}
article p{text-align:justify;hyphens:auto;line-height:1.6}
.stat{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;border-top:1px solid var(--ink);border-bottom:1px solid var(--ink);
  padding:4px 0;margin:2px 0 10px}
.stat .n{font-family:"Old Standard TT",serif;font-weight:700;font-size:1.9rem;line-height:1;color:var(--accent)}
.stat .l{font-family:"Old Standard TT",serif;font-style:italic;font-size:.95rem;color:var(--muted);line-height:1.2}
.byline{font-family:"Old Standard TT",serif;font-style:italic;font-size:.92rem;color:var(--muted);margin-top:9px}
.byline a{text-decoration:none;border-bottom:1px dotted var(--muted)}
/* newspaper columns: stories flow down the columns like in print, with rules between them */
.flow{column-gap:34px;column-rule:1px solid var(--rule)}
.flow.c2{column-count:2}.flow.c3{column-count:3}
.flow.c2>article figure{float:left;width:48%;margin:4px 20px 8px 0}
.flow.c2>article .stat{overflow:hidden}
.flow>article{break-inside:avoid;padding-bottom:16px;margin-bottom:18px;border-bottom:1px solid var(--rule)}
.flow>article:first-child h3{font-size:1.72rem;line-height:1.08}
.flow>article.it h3{font-style:italic;font-weight:400;font-size:1.6rem}
.flow>article.boxed{background:rgba(255,248,225,.16);border:1px solid var(--rule);border-top:4px solid var(--ink);padding:12px 16px 14px}
.flow>article.boxed h3{text-align:center}
/* the photo story of a section: picture and text side by side */
.feature{display:grid;grid-template-columns:1.15fr 1fr;gap:30px;align-items:start;padding-bottom:20px;margin-bottom:20px;border-bottom:1px solid var(--ink)}
.feature figure{margin:0;grid-row:1/span 9}
.feature h3{font-size:clamp(1.8rem,2.8vw,2.5rem);line-height:1.05}
.feature p{font-size:1.08rem}
.feature .stat .n{font-size:2.4rem}
.feature.rev figure{grid-column:2}
.feature.rev>:not(figure){grid-column:1}
/* a table next to the section's first story */
.with-board{display:grid;grid-template-columns:1.1fr 1fr;gap:34px;align-items:start;padding-bottom:20px;margin-bottom:20px;border-bottom:1px solid var(--ink)}
.with-board>article{border-left:1px solid var(--rule);padding-left:30px}
.with-board>article h3{font-size:clamp(1.6rem,2.4vw,2.1rem);line-height:1.08}
/* a section with a single story: headline on the left, text in columns on the right */
.solo{display:grid;grid-template-columns:1fr 1.7fr;gap:0 34px;align-items:start}
.solo>*{grid-column:1}
.solo>p{grid-column:2;grid-row:1/span 9;column-count:2;column-gap:30px;column-rule:1px solid var(--rule);font-size:1.06rem}
.solo h3{font-size:clamp(1.7rem,2.6vw,2.3rem);line-height:1.06}
/* small sections share a row */
.sec-row{display:grid;gap:0 34px;margin-top:34px}
.sec-row.n2{grid-template-columns:1fr 1fr}.sec-row.n3{grid-template-columns:repeat(3,1fr)}
.sec-row>.secblock{margin-top:0}
.sec-row>.secblock+.secblock{position:relative}
.sec-row>.secblock+.secblock::before{content:"";position:absolute;left:-17px;top:0;bottom:0;border-left:1px solid var(--rule)}
.sec-row .flow>article:last-child{border-bottom:0}
/* section flavours */
.sec-sucesos .flow>article{position:relative;border:1px dashed var(--ink);padding:16px 16px 14px;background:rgba(255,248,225,.08)}
.sec-sucesos .feature,.sec-sucesos .with-board>article{position:relative}
.sec-sucesos article::after{content:attr(data-exp);position:absolute;top:10px;right:-4px;transform:rotate(8deg);
  font-family:"IM Fell English SC",serif;font-size:.82rem;color:var(--accent);border:2px solid var(--accent);padding:1px 6px;opacity:.8}
.sec-sucesos .feature::after{right:6px;top:-4px}
.sec-economia .board,.sec-deportes .board,.sec-tiempo .board{margin-bottom:12px}
.with-board .board{margin-bottom:0}
.secblock>.board.alone{max-width:900px;margin:0 auto 8px}
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
.op-grid{display:grid;grid-template-columns:2fr 1fr;gap:34px;align-items:start}
.op-grid .flow>article:last-child{border-bottom:0}
.sec-opinion article.column{background:rgba(255,248,225,.12);border:1px solid var(--ink);outline:1px solid var(--ink);outline-offset:-6px;padding:22px 28px 14px}
.sec-opinion article.column h3{font-style:italic;text-align:center;font-size:2.1rem}
.sec-opinion article.column p{font-size:1.06rem}
.sec-opinion article.column .kicker,.sec-opinion article.column .byline{text-align:center}
.sec-opinion article.column .cbody{column-count:2;column-gap:28px;column-rule:1px solid var(--rule)}
.sec-opinion article.column p{margin-bottom:10px}
.sec-opinion article.column p:first-of-type::first-letter{font-family:"Old Standard TT",serif;font-weight:700;float:left;font-size:2.7rem;line-height:.85;padding:4px 6px 0 0}
/* aside */
aside .box{border:3px double var(--ink);padding:14px 16px;margin-bottom:20px;background:rgba(255,248,225,.08)}
aside h4{font-family:"IM Fell English SC",serif;font-weight:400;font-size:1.14rem;letter-spacing:.05em;text-align:center;
  border-bottom:1px solid var(--ink);padding-bottom:6px;margin-bottom:10px}
.anteriores ol{list-style:none}
.anteriores li{padding:7px 0;border-bottom:1px dotted var(--rule);line-height:1.3}
.anteriores li:last-child{border-bottom:0}
.anteriores a{text-decoration:none}
.anteriores b{display:block;font-family:"IM Fell English SC",serif;font-weight:400;font-size:.88rem;color:var(--accent)}
.anteriores span{font-family:"Old Standard TT",serif;font-size:.98rem}
.anteriores a:hover span{text-decoration:underline}
.quote{font-family:"Old Standard TT",serif;font-style:italic;font-size:1.18rem;line-height:1.35;text-align:center}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th{text-align:left;font-family:"IM Fell English SC",serif;font-weight:400;color:var(--muted);font-size:.9rem;border-bottom:1px solid var(--ink);padding:4px}
td{padding:5px 4px;border-bottom:1px dotted var(--rule)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr.top td{color:var(--accent);font-weight:700}
.win{color:var(--good);font-weight:700}.loss{color:var(--accent);font-weight:700}
.tablewrap{overflow-x:auto}
/* comments and forms */
.cgrid{display:grid;grid-template-columns:1.2fr 1fr;gap:36px;align-items:start}
.cgrid form.papel{border-left:1px solid var(--rule);padding-left:30px}
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
@media (max-width:1180px){
  .flow.c3{column-count:2}
  .sec-row.n3{grid-template-columns:1fr 1fr}
  .sec-row.n3>.secblock:nth-child(3)::before{display:none}
}
@media (max-width:980px){
  .cols,.front,.lead-grid,.profile,.feature,.with-board,.solo,.op-grid,.cgrid,.sec-row.n2,.sec-row.n3{grid-template-columns:1fr}
  .front aside{border-left:0;padding-left:0;margin-top:24px}
  .feature figure,.feature.rev figure,.feature.rev>:not(figure),.solo>*,.solo>p{grid-column:auto;grid-row:auto}
  .with-board>article,.cgrid form.papel{border-left:0;padding-left:0}
  .sec-row>.secblock+.secblock{margin-top:34px}
  .sec-row>.secblock+.secblock::before{display:none}
  .lead.nofig .lead-text p,.sec-opinion article.column .cbody,.solo>p{column-count:1}
}
@media (max-width:700px){
  .flow.c2,.flow.c3,.sumario ol{column-count:1}
  .flow.c2>article figure{float:none;width:auto;margin:8px 0 12px}
  .cifras{grid-template-columns:repeat(2,1fr)}
  .cifras div:nth-child(3){border-left:0}
  .cifras div:nth-child(n+3){border-top:1px solid var(--rule)}
}
@media (max-width:560px){
  body{font-size:16.5px}
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
  function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function when(t){try{return new Date(t).toLocaleString('es-ES',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});}catch(e){return '';}}
  function api(path, opts){opts=opts||{};var h=Object.assign({},H,opts.headers||{});
    return fetch(C.url.replace(/\/$/,'')+path,Object.assign({},opts,{headers:h})).then(function(r){
      if(!r.ok) return r.text().then(function(t){throw new Error(t||r.status);}); return r;});}
  function remember(k,v){try{if(v===undefined)return localStorage.getItem(k)||'';localStorage.setItem(k,v);}catch(e){return '';}}

  var box = document.getElementById('comentarios');
  if (box) {
    var lista = box.querySelector('.lista'), form = box.querySelector('form'), msg = box.querySelector('.msg');
    var ed = box.getAttribute('data-edicion');
    if (!ok) { lista.innerHTML = '<p class="small">Los comentarios se activarán en cuanto se configure la base de datos.</p>'; form.hidden = true; }
    else {
      var load = function(){
        api('/rest/v1/comentarios?select=nombre,texto,created_at&edicion=eq.'+ed+'&order=created_at.asc')
          .then(function(r){return r.json();}).then(function(rows){
            lista.innerHTML = rows.length ? rows.map(function(c){return '<div class="comentario"><b>'+esc(c.nombre)+
              '</b><time>'+when(c.created_at)+'</time><p>'+esc(c.texto)+'</p></div>';}).join('')
              : '<p class="small">Nadie ha comentado todavía. Sé el primero en hurgar en la herida.</p>';
          }).catch(function(){lista.innerHTML='<p class="small">No se han podido cargar los comentarios.</p>';});
      };
      load();
      form.nombre.value = remember('feeder-nombre');
      form.addEventListener('submit', function(ev){
        ev.preventDefault(); if (form.web.value) return;
        var nombre = form.nombre.value.trim(), texto = form.texto.value.trim();
        if (!nombre || !texto) return;
        form.querySelector('button').disabled = true; msg.textContent = 'Enviando…';
        remember('feeder-nombre', nombre);
        api('/rest/v1/comentarios',{method:'POST',headers:{'Content-Type':'application/json',Prefer:'return=minimal'},
          body:JSON.stringify({edicion:ed,nombre:nombre.slice(0,40),texto:texto.slice(0,1000)})})
          .then(function(){form.texto.value='';msg.textContent='Publicado.';load();})
          .catch(function(){msg.textContent='No se pudo enviar. Inténtalo de nuevo.';})
          .then(function(){form.querySelector('button').disabled=false;});
      });
    }
  }

  var pf = document.getElementById('proponer');
  if (pf) {
    var pmsg = pf.querySelector('.msg');
    if (!ok) { pf.querySelector('fieldset').disabled = true; pmsg.textContent = 'El buzón se abrirá en cuanto se configure la base de datos.'; }
    else {
      pf.nombre.value = remember('feeder-nombre');
      pf.addEventListener('submit', function(ev){
        ev.preventDefault(); if (pf.web.value) return;
        var file = pf.imagen.files[0], btn = pf.querySelector('button');
        if (file && file.size > 5*1024*1024) { pmsg.textContent = 'La imagen pesa más de 5 MB.'; return; }
        btn.disabled = true; pmsg.textContent = 'Enviando a la redacción…';
        remember('feeder-nombre', pf.nombre.value.trim());
        var up = Promise.resolve(null);
        if (file) {
          var ext = (file.name.split('.').pop()||'jpg').toLowerCase().replace(/[^a-z0-9]/g,'');
          var path = Date.now()+'-'+Math.random().toString(36).slice(2,8)+'.'+ext;
          up = api('/storage/v1/object/propuestas/'+path,{method:'POST',headers:{'Content-Type':file.type||'image/jpeg'},body:file})
            .then(function(){return path;});
        }
        up.then(function(path){
          return api('/rest/v1/propuestas',{method:'POST',headers:{'Content-Type':'application/json',Prefer:'return=minimal'},
            body:JSON.stringify({nombre:pf.nombre.value.trim().slice(0,40),titulo:pf.titulo.value.trim().slice(0,140),
              texto:pf.texto.value.trim().slice(0,2000),imagen:path})});
        }).then(function(){pf.reset();pf.nombre.value=remember('feeder-nombre');
          pmsg.textContent='¡Recibida! La redacción la revisará y saldrá en La Voz de Runeterra de la próxima edición.';})
          .catch(function(){pmsg.textContent='No se pudo enviar. Revisa los campos e inténtalo de nuevo.';})
          .then(function(){btn.disabled=false;});
      });
    }
  }
})();
"""


def _e(x):
    return escape(str(x), quote=True)


def _date(s):
    y, m, d = map(int, s.split("-"))
    return date(y, m, d)


def page(cfg, title, body, rel, edition=None, description=""):
    if edition:
        top = (f'<div class="topline"><span>{_e(long_date(_date(edition["date"])).capitalize())}</span>'
               f'<span>Año I · Edición nº {edition["number"]}</span><span>Precio: 1 LP</span></div>')
    else:
        top = ('<div class="topline"><span>Fundado en la Grieta del Invocador</span><span>Año I</span>'
               '<span>Precio: 1 LP</span></div>')
    feeder = json.dumps({"url": cfg.get("supabase_url", ""), "key": cfg.get("supabase_anon_key", "")})
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
<nav class="menu"><a href="{rel}index.html">Portada</a><a href="{rel}archivo.html">Hemeroteca</a><a href="{rel}jugadores.html">Jugadores</a><a class="cta" href="{rel}proponer.html">Proponer noticia</a></nav>
</header>
{body}
</div></div>
<footer>{_e(LEGAL.format(title=cfg['site_title']))}</footer>
<script>window.FEEDER={feeder};</script>
<script src="{rel}lectores.js" defer></script>
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


def _weather(ranking):
    if not ranking:
        return ""
    cards = []
    for r in sorted(ranking, key=lambda r: -r["dead"]):
        m = r["dead"] / 60
        ic, txt = (("☀", "Despejado") if m < 3 else ("⛅", "Nubes y claros") if m < 8 else
                   ("☁", "Cubierto") if m < 15 else ("☂", "Niebla espesa") if m < 25 else ("☠", "Niebla Negra"))
        cards.append(f'<div><div class="ic">{ic}</div><b>{_e(r["alias"])}</b><span>{txt} · {int(m)} min en gris</span></div>')
    return '<div class="board weather">' + "".join(cards) + '</div>'


# --------------------------------------------------------------------------- articles
def _kicker(it):
    section = "EL FARO DE LA ESPERANZA" if it.get("section") == "MENCIÓN" else it["section"]  # older editions
    desk = it.get("desk") or DESKS.get(section, "")
    return (f'<div class="kicker">{_e(section)}'
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
    if it.get("imagen"):
        src = f"{rel}img/{it['imagen']}"
        caption = it.get("pie") or ""
    else:
        champ = it.get("campeon") or (it.get("facts") or {}).get("champ")
        if not champ:
            return ""
        src = f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{_ddragon_id(champ)}_0.jpg"
        caption = it.get("pie") or _pick(CAPTIONS, it["headline"]).format(
            champ=champ_name(champ), alias=it.get("alias") or "el grupo")
    top, bot = _meme_text(it)
    meme = (f'<div class="meme"><span>{_e(top)}</span><span>{_e(bot)}</span></div>' if top or bot else "")
    return (f'<figure><div class="ph"><img src="{_e(src)}" alt="{_e(caption)}" loading="lazy" '
            f'onerror="this.closest(\'figure\').remove()">{meme}</div>'
            + (f'<figcaption>{_e(caption)}</figcaption>' if caption else "") + '</figure>')


def _has_picture(it):
    return bool(it.get("imagen") or it.get("campeon") or (it.get("facts") or {}).get("champ"))


def _stat(it):
    return (f'<div class="stat"><span class="n">{_e(it["stat"])}</span>'
            f'<span class="l">{_e(it["stat_label"])}</span></div>')


def _dc(text):
    """Drop capitals only look right on a letter, not on '4/17/23'."""
    return ' class="dc"' if text[:1].isalpha() else ""


def _article(it, rel, image=False, cls="", attrs=""):
    who = ""
    if it.get("lector"):
        who = f'<div class="byline">Enviado por {_e(it["lector"])}</div>'
    elif it.get("player"):
        who = (f'<div class="byline">Sobre <a href="{rel}jugadores/{_e(it["player"])}.html">'
               f'{_e(it["alias"])}</a></div>')
    stat = _stat(it) if it.get("stat") else ""
    fig = _figure(it, rel) if image else ""
    return (f'<article class="{cls}"{attrs}>{_kicker(it)}'
            f'<h3>{_e(it["headline"])}</h3>{fig}{stat}<p{_dc(it["body"])}>{_e(it["body"])}</p>{who}</article>')


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


PACKABLE_MAX = 2  # sections with this many stories or fewer share a row with their neighbours
NOT_PACKABLE = {"deportes", "economia", "tiempo", "opinion"}


def _sections(ed, rest, rel):
    groups = defaultdict(list)
    for it in rest:
        groups[_block_of(it.get("section", ""))].append(it)
    pics = {"left": 8}

    def picture(it):
        if pics["left"] > 0 and _has_picture(it):
            pics["left"] -= 1
            return True
        return False

    def one(b, it, i, image=False, cls=""):
        attrs = f' data-exp="Expediente nº {ed["number"]}-{i + 1}"' if b["key"] == "sucesos" else ""
        if b["key"] == "politica" and it.get("section") == "COMUNICACIÓN":
            cls += " radio"
        return _article(it, rel, image=image, cls=cls.strip(), attrs=attrs)

    def flow(b, items, start, cols, allow_pic=True):
        """Stories running down newspaper columns; text-only ones alternate between looks."""
        out, plain = [], 0
        # One story per column: pictures for all of them or for none, so the columns stay level.
        # More stories than columns: a single picture, the columns balance themselves.
        if 1 < len(items) <= cols:
            every = allow_pic and pics["left"] >= len(items) and all(_has_picture(it) for it in items)
            wants = [every] * len(items)
        else:
            first = next((j for j, it in enumerate(items) if _has_picture(it)), None) if allow_pic else None
            wants = [j == first for j in range(len(items))]
        for j, it in enumerate(items):
            image = wants[j] and picture(it)
            cls = ""
            if not image and j > 0 and b["key"] not in ("sucesos", "politica"):
                plain += 1
                cls = "boxed" if plain % 3 == 2 else "it" if plain % 3 == 0 else ""
            out.append(one(b, it, start + j, image, cls))
        return f'<div class="flow c{cols}">' + "".join(out) + '</div>'

    def head(b):
        return (f'<header class="sec-head"><h3 class="sec-name">{_e(b["title"])}</h3>'
                f'<span class="sec-desk">{_e(b["desk"])}</span></header>')

    def wrap(b, inner):
        return f'<section class="secblock sec-{b["key"]}" id="sec-{b["key"]}">{head(b)}{inner}</section>'

    def full(b):
        items, inner, start = list(b["items"]), "", 0
        if b["col"]:
            col = b["col"]
            paras = "".join(f"<p>{_e(p)}</p>" for p in col["cuerpo"])
            column = (f'<article class="column"><div class="kicker">La columna</div><h3>{_e(col["titulo"])}</h3>'
                      f'<div class="byline">Por {_e(col["autor"])}</div><div class="cbody">{paras}</div></article>')
            if items:
                return wrap(b, f'<div class="op-grid">{column}{flow(b, items, 0, 1)}</div>')
            return wrap(b, column)
        if b["board"]:
            if items:
                first = items.pop(0)
                inner = f'<div class="with-board">{b["widget"]}{one(b, first, 0, picture(first))}</div>'
                start = 1
            else:
                inner = b["widget"].replace('class="board"', 'class="board alone"', 1)
        else:
            inner = b["widget"]
            if items and _has_picture(items[0]) and pics["left"] > 0:
                first = items.pop(0)
                rev = " rev" if b["index"] % 2 else ""
                inner += one(b, first, 0, picture(first), "feature" + rev)
                start = 1
        if len(items) == 1:
            inner += one(b, items[0], start, picture(items[0]), "solo")
        elif items:
            inner += flow(b, items, start, min(len(items), 3))
        return wrap(b, inner)

    def packed(b):
        return wrap(b, b["widget"] + (flow(b, b["items"], 0, 1) if b["items"] else ""))

    blocks = []
    for key, title, desk, _ in BLOCKS:
        items = groups.get(key, [])
        widget, board = "", False
        if key == "deportes" and ed.get("ranking"):
            widget, board = ('<div class="board"><h4 class="kicker">Resultados del día</h4>'
                             + _ranking_table(ed["ranking"], rel) + '</div>'), True
        elif key == "economia" and items:
            widget = _market_table(ed.get("games", []))
            board = bool(widget)
        elif key == "tiempo" and items:
            widget = _weather(ed.get("ranking", []))
        elif key == "voz":
            widget = (f'<div class="voz-cta">¿Ha pasado algo que merezca portada? '
                      f'<a href="{rel}proponer.html">Envía tu noticia a la redacción</a> y saldrá aquí en la próxima edición.</div>')
        col = ed.get("columna") if key == "opinion" else None
        if not items and not col and not (key in ("deportes", "voz") and widget):
            continue
        blocks.append({"key": key, "title": title, "desk": desk, "items": items, "widget": widget,
                       "board": board, "col": col, "index": len(blocks)})

    html, row = [], []

    def flush():
        if len(row) == 1:
            html.append(full(row[0]))
        elif row:
            html.append(f'<div class="sec-row n{len(row)}">' + "".join(packed(b) for b in row) + '</div>')
        row.clear()

    for b in blocks:
        if b["key"] not in NOT_PACKABLE and len(b["items"]) <= PACKABLE_MAX:
            row.append(b)
            if len(row) == 3:
                flush()
        else:
            flush()
            html.append(full(b))
    flush()
    return "".join(html), blocks


def _comments(ed):
    return f"""<section class="secblock comentarios" id="comentarios" data-edicion="{_e(ed['date'])}">
<header class="sec-head"><h3 class="sec-name">Cartas al director</h3><span class="sec-desk">Comentarios de los lectores sobre esta edición</span></header>
<div class="cgrid">
<div class="lista"><p class="small">Cargando comentarios…</p></div>
<form class="papel">
  <label>Tu nombre de invocador<input type="text" name="nombre" maxlength="40" required></label>
  <label>Tu comentario<textarea name="texto" maxlength="1000" required placeholder="Defiéndete, acusa o echa sal en la herida…"></textarea></label>
  <input class="hp" type="text" name="web" tabindex="-1" autocomplete="off" aria-hidden="true">
  <button type="submit">Enviar al periódico</button><span class="msg"></span>
</form>
</div>
</section>"""


def _previous(editions_until, rel, n=2):
    prev = [e for e in reversed(editions_until[:-1]) if e.get("items")][:n]
    if not prev:
        return ""
    lis = "".join(f'<li><a href="{rel}ediciones/{e["date"]}.html"><b>{_e(short_date(_date(e["date"])))}</b>'
                  f'<span>{_e(e["items"][0]["headline"])}</span></a></li>' for e in prev)
    return f'<div class="box anteriores"><h4>Ediciones anteriores</h4><ol>{lis}</ol></div>'


def render_edition(cfg, ed, editions_until, rel):
    items = ed["items"]
    lead = items[0] if items else None
    rest = items[1:]
    ticker = " ".join(f"<span>{_e(i['headline'])}</span>" for i in items[:8])
    t = ed["totals"]
    sections, blocks = _sections(ed, rest, rel)
    lead_html = ""
    if lead:
        who = (f'<div class="who"><a href="{rel}jugadores/{_e(lead["player"])}.html">{_e(lead["alias"])}</a></div>'
               if lead.get("player") else "")
        stat_box = (f'<div class="bigstat"><div class="n">{_e(lead["stat"])}</div>'
                    f'<div class="l">{_e(lead["stat_label"])}</div>{who}</div>') if lead.get("stat") else ""
        fig = _figure(lead, rel)
        lead_html = (f'<section class="lead{"" if fig else " nofig"}">{_kicker(lead)}<h2>{_e(lead["headline"])}</h2>'
                     f'<div class="lead-grid">{fig}<div class="lead-text"><p{_dc(lead["body"])}>{_e(lead["body"])}</p>{stat_box}</div></div>'
                     '</section>')
    special = ""
    esp = ed.get("especial")
    if esp:
        special = (f'<section class="special t-{_e(esp["tema"])}"><div class="kicker">{_e(esp["antetitulo"])}</div>'
                   f'<h2>{_e(esp["titulo"])}</h2>'
                   + (f'<p>{_e(esp["subtitulo"])}</p>' if esp.get("subtitulo") else "") + '</section>')
    cifras = "".join(f'<div><b>{_e(n)}</b><span>{_e(l)}</span></div>' for n, l in [
        (t["games"], "partidas del grupo"), (fmt_int(t["deaths"]), "muertes"),
        (int(t["dead_seconds"] // 60), "minutos en gris"), (int(t["play_seconds"] // 60), "minutos jugados")])
    sumario = "".join(
        f'<li><a href="#sec-{b["key"]}"><b>{_e(b["title"])}</b><span>{_e(b["items"][0]["headline"])}</span></a></li>'
        for b in blocks if b["items"])
    board = general_leaderboard(editions_until)
    writer = ""
    if ed.get("written_by"):
        version = (ed.get("ai") or {}).get("version")
        writer = (f'<p class="small" style="text-align:center;margin-top:10px">Redacción: {_e(ed["written_by"])}'
                  + (f' (versión {version})' if version and version > 1 else "") + '.</p>')
    body = f"""
<div class="ticker"><b>ÚLTIMA HORA</b><div class="run">{ticker}</div></div>
{special}
<div class="front">
  <div class="front-main">
    {lead_html}
    <div class="cifras">{cifras}</div>
    {f'<nav class="sumario"><h4>En esta edición</h4><ol>{sumario}</ol></nav>' if sumario else ""}
  </div>
  <aside>
    <div class="box"><h4>General de la vergüenza</h4>{_general_table(board, rel)}</div>
    <div class="box"><h4>Frase del día</h4><p class="quote">«{_e(ed["frase"])}»</p>{writer}</div>
    {_previous(editions_until, rel)}
  </aside>
</div>
{sections}
{_comments(ed)}"""
    title = f"{cfg['site_title']} · {short_date(_date(ed['date']))}"
    desc = lead["headline"] if lead else cfg["site_tagline"]
    return page(cfg, title, body, rel, edition=ed, description=desc)


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
    return page(cfg, f"Proponer noticia · {cfg['site_title']}", body, "")


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
  <aside><div class="box"><h4>Últimas partidas</h4>{table}</div></aside>
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
    body = (f'<section class="secblock"><header class="sec-head"><h3 class="sec-name">Hemeroteca</h3>'
            f'<span class="sec-desk">Todas las ediciones</span></header>'
            f'<ul class="archive">{lis or "<li>Aún no hay ediciones.</li>"}</ul></section>')
    return page(cfg, f"Hemeroteca · {cfg['site_title']}", body, "")


def render_players_index(cfg, friends, editions):
    board = {t["slug"]: t for t in general_leaderboard(editions)}
    cards = "".join(
        f'<article><div class="kicker">{_e(f["riot_id"])}</div><h3><a href="jugadores/{_e(f["slug"])}.html">'
        f'{_e(f["alias"])}</a></h3><p class="small">{board.get(f["slug"], {}).get("points", 0)} puntos de vergüenza · '
        f'{board.get(f["slug"], {}).get("portadas", 0)} portadas</p></article>' for f in friends)
    body = (f'<section class="secblock"><header class="sec-head"><h3 class="sec-name">Jugadores</h3>'
            f'<span class="sec-desk">Fichas policiales del grupo</span></header><div class="sec-grid">{cards}</div></section>')
    return page(cfg, f"Jugadores · {cfg['site_title']}", body, "")


def build_site(cfg, friends, editions, out_dir):
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

    for i, ed in enumerate(editions):
        html = render_edition(cfg, ed, editions[:i + 1], "../")
        (out / "ediciones" / f"{ed['date']}.html").write_text(html, encoding="utf-8")
    if editions:
        index = render_edition(cfg, editions[-1], editions, "")
    else:
        index = page(cfg, cfg["site_title"],
                     '<section class="secblock"><h2 class="kicker">Próximamente</h2>'
                     '<p>La primera edición saldrá en cuanto se ejecute el robot.</p></section>', "")
    (out / "index.html").write_text(index, encoding="utf-8")
    (out / "archivo.html").write_text(render_archive(cfg, editions), encoding="utf-8")
    (out / "jugadores.html").write_text(render_players_index(cfg, friends_all, editions), encoding="utf-8")
    (out / "proponer.html").write_text(render_proponer(cfg), encoding="utf-8")
    for f in friends_all:
        (out / "jugadores" / f"{f['slug']}.html").write_text(render_player(cfg, f, editions), encoding="utf-8")
    return out
