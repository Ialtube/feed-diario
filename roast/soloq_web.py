"""The SoloQ Challenge page (docs/soloq/), a tab of the newspaper's website: an old wooden notice
board with the standings nailed in the middle on a sheet of parchment, the LP chart of every player
on another sheet below, and around them carved plaques, a wanted poster, clippings of El Rincón del
Feeder and notes nailed by «somebody» (the robot, the newspaper's AI newsroom and the readers).
Static HTML built by the robot; the browser only signs people up, pins readers' notes, counts down
and notices when the table changes."""
import hashlib
import json
import random
import urllib.parse
from datetime import datetime
from html import escape
from pathlib import Path

from . import soloq
from .rangos import TIER_ES, TIERS
from .util import fmt_int, fmt_num, long_date, short_date

PLATFORM_OPGG = {"euw1": "euw", "eun1": "eune", "na1": "na", "kr": "kr", "br1": "br", "la1": "lan", "la2": "las",
                 "oc1": "oce", "tr1": "tr", "ru": "ru", "jp1": "jp"}
TIER_COLORS = {  # wax seal and crest: light, dark
    "IRON": ("#8a807c", "#3b3330"), "BRONZE": ("#c98a5e", "#5e3a24"), "SILVER": ("#d5dee5", "#6f7f8b"),
    "GOLD": ("#f5d68a", "#a8782b"), "PLATINUM": ("#8fe3d6", "#2a7d78"), "EMERALD": ("#5fe8aa", "#138a55"),
    "DIAMOND": ("#b9c7ff", "#4a5bd1"), "MASTER": ("#dc9cf7", "#7b2fb3"), "GRANDMASTER": ("#ff8a7a", "#a31d24"),
    "CHALLENGER": ("#fff3c4", "#3fa7ff"), "NONE": ("#9b948a", "#4b453e"),
}
TIER_INK = {"IRON": "#4b4340", "BRONZE": "#7a4527", "SILVER": "#56656f", "GOLD": "#8a6114", "PLATINUM": "#1f6b66",
            "EMERALD": "#11704a", "DIAMOND": "#3546a8", "MASTER": "#6b2399", "GRANDMASTER": "#93161f",
            "CHALLENGER": "#1f6fb8", "NONE": "#6b5d4a"}
INKS = ["#8b1e1e", "#1f3f7a", "#2e6b2e", "#6a2c7a", "#b0601a", "#1a1a1a", "#0f6b6b", "#9c2a63", "#5b4a12", "#3f5f8f",
        "#7a3b10", "#2b7a4b"]
DASHES = ["", "7 4", "2 4", "10 4 2 4"]
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Almendra:ital,wght@0,400;0,700;1,400'
         '&family=Caveat:wght@500;700&family=IM+Fell+English:ital@0;1&family=MedievalSharp&family=Pirata+One'
         '&display=swap" rel="stylesheet">')
LEGAL = ("{name} es un juego entre amigos de {site} y no está avalado por Riot Games ni refleja las opiniones de "
         "Riot Games ni de nadie implicado oficialmente en la producción o gestión de League of Legends. League of "
         "Legends y Riot Games son marcas registradas de Riot Games, Inc. Datos de la API oficial de Riot; "
         "la mala leche es nuestra.")


def _svg_url(svg):
    return "url(\"data:image/svg+xml;utf8," + svg.replace("#", "%23").replace('"', "'") + "\")"


PLANKS = _svg_url(
    "<svg xmlns='http://www.w3.org/2000/svg' width='520' height='132'>"
    "<filter id='g'><feTurbulence type='fractalNoise' baseFrequency='0.005 0.21' numOctaves='3' seed='8' stitchTiles='stitch'/>"
    "<feColorMatrix values='0 0 0 0 0.07  0 0 0 0 0.04  0 0 0 0 0.02  0 0 0 1.5 -0.45'/></filter>"
    "<rect width='520' height='66' fill='#5c3e27'/><rect y='66' width='520' height='66' fill='#523621'/>"
    "<rect width='520' height='132' filter='url(#g)'/>"
    "<path d='M0 65H520M0 131H520M188 0V65M430 66V131' stroke='#160d07' stroke-width='3.5'/>"
    "<path d='M0 67.5H520M0 1.5H520M190.5 0V65M432.5 66V131' stroke='#8a6644' stroke-width='1' opacity='.35'/>"
    "<g fill='#191512'><circle cx='176' cy='12' r='2.6'/><circle cx='176' cy='53' r='2.6'/><circle cx='202' cy='12' r='2.6'/>"
    "<circle cx='202' cy='53' r='2.6'/><circle cx='418' cy='78' r='2.6'/><circle cx='418' cy='119' r='2.6'/>"
    "<circle cx='444' cy='78' r='2.6'/><circle cx='444' cy='119' r='2.6'/></g>"
    "<g fill='#8d8a84' opacity='.55'><circle cx='175.3' cy='11.3' r='1'/><circle cx='175.3' cy='52.3' r='1'/>"
    "<circle cx='201.3' cy='11.3' r='1'/><circle cx='201.3' cy='52.3' r='1'/><circle cx='417.3' cy='77.3' r='1'/>"
    "<circle cx='417.3' cy='118.3' r='1'/><circle cx='443.3' cy='77.3' r='1'/><circle cx='443.3' cy='118.3' r='1'/></g></svg>")
BEAM = _svg_url(
    "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='120'>"
    "<filter id='g'><feTurbulence type='fractalNoise' baseFrequency='0.006 0.16' numOctaves='3' seed='3' stitchTiles='stitch'/>"
    "<feColorMatrix values='0 0 0 0 0.09  0 0 0 0 0.05  0 0 0 0 0.02  0 0 0 1.3 -0.4'/></filter>"
    "<rect width='400' height='120' fill='#6a4529'/><rect width='400' height='120' filter='url(#g)'/></svg>")
PAPER = _svg_url(
    "<svg xmlns='http://www.w3.org/2000/svg' width='260' height='260'>"
    "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/>"
    "<feColorMatrix values='0 0 0 0 .38  0 0 0 0 .26  0 0 0 0 .1  0 0 0 .2 0'/></filter>"
    "<rect width='260' height='260' filter='url(#n)'/></svg>")

CSS = r"""
:root{
  color-scheme:light;
  --wall:#1b1310; --ink:#2b1d10; --ink2:#5a4630; --ink3:#7d6a50; --red:#8b1a1a; --green:#2f5d1f; --blue:#1f3f7a;
  --parch:#ead7a8; --parch2:#dcc28a; --slate:#c7c497; --slate2:#a9a675; --frame:#8e4a22; --frame2:#5f2f14;
  --carve:"MedievalSharp","Pirata One",serif; --script:"Almendra","IM Fell English",Georgia,serif;
  --hand:"Caveat","Segoe Print","Comic Sans MS",cursive; --news:"IM Fell English",Georgia,serif; --wanted:"Pirata One","MedievalSharp",serif;
  --planks:PLANKS; --beam:BEAM; --paper:PAPER;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--wall);color:var(--ink);font:17px/1.45 var(--script);overflow-x:hidden;
  background-image:radial-gradient(1100px 500px at 50% -120px,rgba(255,190,110,.18),transparent 70%)}
a{color:inherit}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}

/* ---------------------------------------------------------------- back to the newspaper */
.volver{display:flex;justify-content:space-between;align-items:center;gap:10px;max-width:1400px;margin:0 auto;padding:12px 14px 0}
.volver a{display:inline-flex;align-items:center;gap:8px;padding:8px 16px;text-decoration:none;font:19px/1 var(--carve);color:#f3e6c4;
  background-image:var(--beam);background-color:#5c3e27;border:2px solid #2e1d10;border-radius:4px;box-shadow:0 3px 0 #1c110a}
.volver a:hover{color:#fff;filter:brightness(1.12)}
.volver .jefe{font-size:16px;padding:7px 12px;cursor:pointer;background-color:#3a271a}

/* ---------------------------------------------------------------- frame + board */
.marco{position:relative;display:block;max-width:1400px;margin:18px auto 0;padding:30px;background-image:var(--beam);background-color:#6a4529;
  box-shadow:0 30px 80px rgba(0,0,0,.75),inset 0 0 0 3px #1c110a,inset 0 0 30px rgba(0,0,0,.6);border-radius:6px}
.marco>.perno{position:absolute;width:16px;height:16px;border-radius:50%;
  background:radial-gradient(circle at 35% 35%,#e9e4d8 0 2px,#9a958b 3px,#4a4640 6px,#1d1a17 8px);box-shadow:0 2px 3px rgba(0,0,0,.7)}
.tablon{position:relative;background-image:var(--planks);background-color:#563a24;padding:34px 30px 40px;
  box-shadow:inset 0 0 0 3px #150c06,inset 0 0 60px rgba(0,0,0,.75),inset 0 18px 30px rgba(0,0,0,.45)}
@media (max-width:760px){.marco{padding:12px;margin-top:10px;border-radius:0}.tablon{padding:22px 12px 30px}.marco>.perno{display:none}}

/* ---------------------------------------------------------------- shared pinned things */
.cosa{position:relative;transform:rotate(var(--r,0deg));transition:transform .2s;filter:drop-shadow(0 10px 10px rgba(0,0,0,.55))}
.cosa:hover{transform:rotate(calc(var(--r,0deg) * .3)) scale(1.01);z-index:3}
.clavo{position:absolute;z-index:4;width:15px;height:15px;border-radius:50%;
  background:radial-gradient(circle at 35% 35%,#f2efe8 0 1.5px,#b3aea4 2.5px,#6b665d 5px,#2a2622 7.5px);
  box-shadow:1px 3px 3px rgba(0,0,0,.65)}
.chincheta{position:absolute;z-index:4;width:18px;height:18px;border-radius:50%;left:calc(50% - 9px);top:-6px;
  background:radial-gradient(circle at 35% 30%,#ffb3a6 0 2px,#c0281c 4px,#7d1009 9px);box-shadow:2px 4px 4px rgba(0,0,0,.6)}
.hoja{background-color:var(--parch);background-image:var(--paper),
    radial-gradient(circle at 18% 22%,rgba(150,95,30,.16),transparent 22%),
    radial-gradient(circle at 82% 70%,rgba(150,95,30,.14),transparent 25%),
    radial-gradient(ellipse at 50% 50%,transparent 55%,rgba(120,72,20,.38) 100%);
  color:var(--ink)}
h2.tit,h3.tit{margin:0 0 6px;text-align:center;font:30px/1.1 var(--carve);letter-spacing:.04em;color:var(--ink)}
h3.tit{font-size:22px}
.sub{margin:0 0 14px;text-align:center;font-style:italic;color:var(--ink2);font-size:15px}

/* scroll: rolled top and bottom */
.perg .rollo{display:block;position:relative;z-index:2;height:24px;margin:0 -12px;border-radius:12px;
  background:linear-gradient(180deg,#5d4220 0%,#c9a866 22%,#f0dcaa 42%,#d1b072 62%,#8a6a3c 85%,#4e3619 100%);
  box-shadow:0 3px 4px rgba(0,0,0,.35)}
.perg .rollo:before,.perg .rollo:after{content:"";position:absolute;top:3px;width:18px;height:18px;border-radius:50%;
  background:radial-gradient(circle at 50% 50%,#6e5228 0 3px,#c9a866 4px 6px,#8a6a3c 7px)}
.perg .rollo:before{left:-2px}.perg .rollo:after{right:-2px}
.perg .hoja{margin:-6px 0;padding:26px 26px 24px}
@media (max-width:760px){.perg .hoja{padding:22px 14px 20px}}

/* carved plaque in a wooden frame */
.placa{padding:13px;background-image:var(--beam);background-color:var(--frame);
  box-shadow:inset 0 0 0 2px var(--frame2),inset 0 0 12px rgba(0,0,0,.5),0 0 0 2px #2a1408}
.placa .in{position:relative;padding:16px 18px;text-align:center;
  background-image:var(--paper),radial-gradient(ellipse at 50% 40%,var(--slate),var(--slate2));
  box-shadow:inset 0 0 22px rgba(60,55,20,.65),inset 0 0 0 1px rgba(0,0,0,.35)}
.tallado{font-family:var(--carve);text-transform:uppercase;color:#4a3d22;letter-spacing:.04em;
  text-shadow:0 1px 0 rgba(255,253,230,.6),0 -1px 0 rgba(0,0,0,.4)}
.placa .clavo{width:11px;height:11px}

/* small notes */
.nota{max-width:300px;padding:22px 18px 14px;font:24px/1.12 var(--hand);color:#2a1d12}
.nota .firma{display:block;margin-top:8px;text-align:right;font-size:19px;color:var(--ink2)}
.nota.amarilla{background-color:#efd98a}.nota.rosa{background-color:#e9b8a6}.nota.verde{background-color:#c9d39a}
.nota.ia .firma:after{content:" · redacción del Rincón";font-size:15px}
.nota.lector{font-size:22px}

/* newspaper clipping */
.recorte{max-width:330px;padding:22px 18px 14px;background-color:#e9e3d1;background-image:var(--paper);font-family:var(--news)}
.recorte .k{font:italic 13px/1.2 var(--news);color:#5b5246;border-bottom:1px solid #8d8474;padding-bottom:4px;margin-bottom:6px}
.recorte h4{margin:0 0 6px;font:700 21px/1.12 var(--news);color:#1f1a14}
.recorte p{margin:0 0 8px;font-size:15px;line-height:1.35;color:#3b342b}
.recorte a.leer{font:italic 15px var(--news);color:var(--red)}

/* ---------------------------------------------------------------- header sign */
.cartel{display:flex;justify-content:center;margin:0 auto 34px;max-width:860px}
.cartel .placa{padding:16px;width:100%}
.cartel .in{padding:22px 20px 18px}
.cartel h1{margin:0;font:clamp(38px,7vw,78px)/1 var(--carve)}
.cartel .lema{margin:8px 0 0;font:italic 19px/1.3 var(--script);color:#4a3d22}
.cartel .estado{display:inline-block;margin-top:12px;padding:4px 14px;font:16px/1.2 var(--carve);letter-spacing:.08em;
  color:#f7e9c9;background:#7d1d14;border-radius:3px;box-shadow:inset 0 0 0 2px #4a0d07;transform:rotate(-1.5deg)}
.cartel .estado.inscripcion{background:#5b4a12}.cartel .estado.finalizado{background:#2b2b2b}

/* ---------------------------------------------------------------- layout */
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2.7fr) minmax(0,1fr);gap:30px;align-items:start}
.col{display:flex;flex-direction:column;gap:34px;align-items:center}
.col>*{width:100%}
.col>.nota,.col>.recorte,.o9>.recorte{width:auto;max-width:300px}
.centro{gap:40px}
.fila-notas,.dispersas{display:flex;flex-wrap:wrap;gap:26px 30px;justify-content:center;align-items:flex-start}
.fila-notas>.nota,.dispersas>.nota{flex:0 1 270px}
.dispersas{margin-top:40px}
.dispersas:empty{display:none}
.bajo{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr) minmax(0,1fr);gap:34px;margin-top:44px;align-items:start}
.bajo>.col{gap:34px}
.notas-lectores{display:flex;flex-wrap:wrap;gap:26px;justify-content:center;margin-top:40px}
.notas-lectores:empty{display:none}
@media (max-width:1100px){.grid{grid-template-columns:minmax(0,1fr) minmax(0,1.8fr)}
  .col.der{grid-column:1/-1;flex-direction:row;flex-wrap:wrap;justify-content:center;align-items:flex-start}
  .col.der>*{width:auto;flex:0 1 300px}.bajo{grid-template-columns:1fr 1fr}.bajo>.bando{grid-column:1/-1}}
@media (max-width:820px){.grid,.bajo{display:flex;flex-direction:column;align-items:center;gap:30px}.col,.col.der,.fila-notas{display:contents}
  .grid>*,.col>*,.bajo>*,.col.der>*{width:100%;max-width:640px;flex:none}.col>.nota,.col>.recorte,.o9>.recorte{max-width:330px}
  .o1{order:1}.o2{order:2}.o3{order:3}.o4{order:4}.o5{order:5}.o6{order:6}.o7{order:7}.o8{order:8}.o9{order:9}}

/* ---------------------------------------------------------------- countdown + figures plaques */
.reloj .n{display:flex;justify-content:center;gap:14px;align-items:flex-end;margin-top:6px}
.reloj .n div{text-align:center}
.reloj b{display:block;font:44px/1 var(--carve)}
.reloj span{font:13px/1 var(--carve);letter-spacing:.08em}
.reloj .peq{margin-top:8px;font:17px/1.2 var(--carve);letter-spacing:.04em}
.cifras{display:grid;grid-template-columns:1fr 1fr;gap:12px 8px}
.cifras b{display:block;font:30px/1 var(--carve)}
.cifras span{font:12px/1.15 var(--carve);letter-spacing:.04em}
.cifras .neg b{color:#7d1d14}

/* ---------------------------------------------------------------- the standings */
.clasif .hoja{padding-top:28px;container-type:inline-size}
.cab,.fila>summary{display:grid;grid-template-columns:34px 38px minmax(150px,2.2fr) minmax(130px,1.5fr) 62px minmax(96px,1fr) 46px 96px;
  gap:8px;align-items:center}
.cab{padding:0 8px 6px;border-bottom:2px solid var(--ink);font:13px/1 var(--carve);letter-spacing:.06em;text-transform:uppercase;color:var(--ink2)}
.fila{border-bottom:1px dashed rgba(60,40,20,.45)}
.fila>summary{list-style:none;cursor:pointer;padding:10px 8px;transition:background .15s}
.fila>summary::-webkit-details-marker{display:none}
.fila>summary:hover,.fila[open]>summary{background:rgba(120,80,20,.1)}
.fila.yo>summary{background:rgba(31,63,122,.1);box-shadow:inset 4px 0 0 var(--blue)}
.pos{font:30px/1 var(--carve);text-align:center}
.top1 .pos{color:#9a6a08}
.dl{font:700 15px/1 var(--script);text-align:center}
.up{color:var(--green)}.down{color:var(--red)}.eq{color:var(--ink3)}.dl.new{font:12px var(--carve);color:var(--blue)}
.quien{min-width:0}
.quien .nm{font:700 20px/1.1 var(--script);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.quien .nm i{font-weight:400;font-size:15px;color:var(--ink2)}
.quien .nm .tu{font:12px var(--carve);color:#f3e8cc;background:var(--blue);padding:1px 5px;margin-left:6px;font-style:normal}
.quien .rid{font-size:13px;color:var(--ink3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.quien .ver{font:20px/1.05 var(--hand);color:#5a2a14;margin-top:3px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.lg{display:flex;align-items:center;gap:9px;min-width:0}
.sello{flex:none;display:grid;place-items:center;width:40px;height:40px;border-radius:50%;font:14px/1 var(--carve);color:#fffaf0;
  text-shadow:0 1px 1px rgba(0,0,0,.6);box-shadow:inset 0 -3px 6px rgba(0,0,0,.35),inset 0 3px 5px rgba(255,255,255,.35);
  clip-path:polygon(50% 0,61% 6%,74% 3%,80% 14%,93% 17%,93% 30%,100% 40%,95% 52%,100% 63%,91% 72%,90% 85%,77% 88%,69% 98%,57% 94%,
  45% 100%,35% 92%,22% 96%,16% 85%,4% 80%,7% 67%,0 56%,6% 45%,1% 33%,10% 25%,10% 12%,23% 9%,31% 1%,42% 5%)}
.lg b{display:block;font:700 17px/1.05 var(--script)}
.lg span{font-size:14px;color:var(--ink2)}
.lg .nq{display:block;font:17px/1 var(--hand);color:var(--red)}
.hoy{text-align:right;font:700 17px/1.05 var(--script)}
.hoy small{display:block;font:400 12px/1.3 var(--script);color:var(--ink3)}
.wr .n{display:flex;justify-content:space-between;font-size:15px}
.wr .barra{height:7px;margin-top:4px;border:1px solid var(--ink2);background:repeating-linear-gradient(45deg,rgba(139,26,26,.25) 0 3px,transparent 3px 6px)}
.wr .barra i{display:block;height:100%;background:rgba(47,93,31,.75)}
.racha{font:700 17px/1 var(--script);text-align:center}
.ult{display:flex;gap:3px;justify-content:flex-end;font:700 21px/1 var(--hand)}
.ult .v{color:var(--green)}.ult .d{color:var(--red)}
.ult .nada{font:15px var(--hand);color:var(--ink3)}
.vacia{padding:30px 10px;text-align:center;font:26px/1.2 var(--hand)}
.leyenda-fila{margin:12px 0 0;font:19px/1.2 var(--hand);color:var(--ink2);text-align:center}
@container (max-width:800px){.cab,.fila>summary{grid-template-columns:30px 34px minmax(130px,2fr) minmax(120px,1.4fr) 56px minmax(86px,1fr) 42px}.c-ult{display:none!important}}
@container (max-width:560px){
  .cab{display:none}
  .fila>summary{grid-template-columns:30px 1fr auto;grid-template-areas:"pos quien hoy" "dl lg lg" ". wr racha";row-gap:8px}
  .fila>summary .pos{grid-area:pos}.fila>summary .dl{grid-area:dl}.fila>summary .quien{grid-area:quien}.fila>summary .lg{grid-area:lg}
  .fila>summary .hoy{grid-area:hoy}.fila>summary .wr{grid-area:wr}.fila>summary .racha{grid-area:racha}}

/* the sign-up sheet (before the starting gun) */
.lista{list-style:none;margin:0;padding:0}
.lista li{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:10px;align-items:baseline;padding:9px 4px;border-bottom:1px dashed rgba(60,40,20,.45)}
.lista .n{font:24px/1 var(--carve)}
.lista b{font-size:19px}.lista i{color:var(--ink2)}
.lista small{display:block;color:var(--ink3);font-size:13px}
.lista .meta{text-align:right;font-size:14px;color:var(--ink2)}
.lista .lema{display:block;font:20px/1.1 var(--hand);color:#5a2a14}

/* row detail */
.det{padding:6px 8px 20px 80px;display:grid;grid-template-columns:1.3fr 1fr;gap:18px}
@container (max-width:700px){.det{padding:4px 4px 16px;grid-template-columns:1fr}}
.recuadro{border:1px solid rgba(60,40,20,.5);padding:10px 12px;background:rgba(255,248,225,.25)}
.recuadro h4{margin:0 0 6px;font:15px/1 var(--carve);letter-spacing:.06em;text-transform:uppercase;color:var(--ink2)}
.kv{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}
.kv>div{border-bottom:1px dotted var(--ink3);padding-bottom:4px}
.kv>div>span{display:block;font:12px/1.2 var(--carve);letter-spacing:.04em;color:var(--ink3);text-transform:uppercase}
.kv b{font-size:16px}
.obj .track{height:9px;border:1px solid var(--ink2);margin:8px 0 6px;background:rgba(255,255,255,.2)}
.obj .track i{display:block;height:100%;background:repeating-linear-gradient(90deg,var(--ink2) 0 4px,transparent 4px 6px)}
.obj p{margin:0;font:19px/1.15 var(--hand)}
.champ{display:flex;align-items:center;gap:9px;margin-bottom:6px;font-size:15px}
.champ .wrc{margin-left:auto;color:var(--ink2)}
.ch{position:relative;flex:none;width:32px;height:32px;border:2px solid var(--ink2);display:grid;place-items:center;
  font:12px var(--carve);color:var(--ink2);background:rgba(255,255,255,.25);filter:sepia(.35)}
.ch:before{content:attr(data-i)}
.ch img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.partidas{display:flex;flex-wrap:wrap;gap:6px}
.partida{display:flex;align-items:center;gap:6px;padding:2px 7px 2px 2px;font-size:14px;border:1px solid}
.partida.v{border-color:var(--green);color:var(--green)}.partida.d{border-color:var(--red);color:var(--red)}
.partida .ch{width:24px;height:24px;font-size:10px;border-width:1px}
.lema-fila{margin:10px 0 0;font:22px/1.1 var(--hand);color:#5a2a14}
.enl{display:flex;gap:14px;flex-wrap:wrap;margin-top:10px;font-size:15px}
.enl a{color:var(--red)}
.chart{width:100%;height:auto;display:block}
.chart .rej line{stroke:rgba(60,40,20,.22);stroke-width:1}
.chart .rej text{fill:var(--ink2);font:12px var(--script)}
.chart .tinta{fill:none;stroke-width:2.6;stroke-linejoin:round;stroke-linecap:round}
.chart .lbl{font:700 14px var(--script);paint-order:stroke;stroke:#ead7a8;stroke-width:4px}

/* ---------------------------------------------------------------- the big chart */
.grafica .lienzo{overflow-x:auto;-webkit-overflow-scrolling:touch}
@media (max-width:640px){.grafica svg.big{min-width:620px}}
.chart.big .rej text{font-size:15px}
.chart.big .lbl{font-size:16px}
.grafica .leyenda{display:flex;flex-wrap:wrap;gap:6px 16px;justify-content:center;margin:10px 0 0;padding:0;list-style:none}
.grafica .leyenda li{display:flex;align-items:center;gap:6px;font-size:16px;cursor:pointer}
.grafica .leyenda svg{width:30px;height:8px}
.grafica svg.big .linea{transition:opacity .15s}
.grafica svg.big.foco .linea{opacity:.13}
.grafica svg.big.foco .linea.on{opacity:1}
.grafica svg.big.foco .linea.on .tinta{stroke-width:4}

/* ---------------------------------------------------------------- side pieces */
.rey .in{padding:14px 12px}
.rey svg.crest{width:96px;height:96px;display:block;margin:6px auto}
.rey .nombre{font-size:30px;line-height:1.05;word-break:break-word}
.rey .liga{font-size:17px;margin-top:6px}
.rey .frase{margin:10px 0 0;font:21px/1.1 var(--hand);color:#3b2b14}
.sebusca .hoja{text-align:center}
.sebusca h3{margin:0;font:56px/.9 var(--wanted);letter-spacing:.02em;color:#2b1a0b}
.sebusca .por{font:italic 15px var(--script);color:var(--ink2)}
.sebusca svg.crest{width:110px;height:110px;margin:6px auto;display:block;filter:sepia(.5)}
.sebusca .nm{font:34px/1 var(--wanted);margin:4px 0;word-break:break-word}
.sebusca .delito{font:20px/1.15 var(--hand);margin:6px 0}
.sebusca .recompensa{font:22px/1 var(--wanted);border-top:2px solid var(--ink);border-bottom:2px solid var(--ink);padding:6px 0;margin-top:10px}
.registro ol{list-style:none;margin:0;padding:0}
.registro li{padding:8px 2px;border-bottom:1px dashed rgba(60,40,20,.45);font-size:15px;line-height:1.3}
.registro li:last-child{border-bottom:0}
.registro .q{font-weight:700}
.registro .t{display:block;font:italic 13px var(--script);color:var(--ink3)}
.registro .lp{float:right;font-weight:700;margin-left:8px}
.muro .premio{padding:8px 2px 9px;border-bottom:1px dashed rgba(60,40,20,.45)}
.muro .premio:last-child{border-bottom:0}
.muro .pt{font:18px/1.1 var(--carve)}
.muro .pc{font:italic 12px var(--script);color:var(--ink3)}
.muro .pw{font:700 18px/1.2 var(--script)}
.muro .px{font:19px/1.1 var(--hand);color:#5a2a14}

/* ---------------------------------------------------------------- forms */
.bando form{margin:0}
.bando label{display:block;margin:0 0 14px;font:15px/1.2 var(--carve);letter-spacing:.04em;color:var(--ink2);text-transform:uppercase}
.bando input[type=text],.bando select,.clava textarea,.clava input{display:block;width:100%;margin-top:4px;padding:6px 2px;border:0;
  border-bottom:2px solid var(--ink2);background:transparent;color:var(--ink);font:24px/1.1 var(--hand);border-radius:0;appearance:none}
.bando select{background-image:linear-gradient(45deg,transparent 50%,var(--ink2) 50%),linear-gradient(135deg,var(--ink2) 50%,transparent 50%);
  background-position:calc(100% - 14px) 16px,calc(100% - 8px) 16px;background-size:6px 6px;background-repeat:no-repeat}
.bando input:focus,.bando select:focus,.clava textarea:focus,.clava input:focus{outline:none;border-bottom-color:var(--red);background-color:rgba(255,255,255,.18)}
.bando .hint{display:block;margin-top:4px;font:italic 14px/1.3 var(--script);letter-spacing:0;text-transform:none;color:var(--ink3)}
.bando .fila2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:600px){.bando .fila2{grid-template-columns:1fr}}
.bando .check{display:flex;gap:10px;align-items:flex-start;font:17px/1.3 var(--script);letter-spacing:0;text-transform:none;color:var(--ink)}
.bando .check input{margin-top:4px;width:18px;height:18px;accent-color:var(--red)}
.boton{display:inline-block;cursor:pointer;padding:10px 22px;font:21px/1 var(--carve);letter-spacing:.04em;color:#f6e7c4;
  background:linear-gradient(180deg,#8f2a1c,#5e150c);border:2px solid #3a0b05;border-radius:4px;box-shadow:0 3px 0 #2a0703,0 6px 10px rgba(0,0,0,.35)}
.boton:hover{filter:brightness(1.1)}
.boton[disabled]{opacity:.5;cursor:not-allowed}
.msg{min-height:22px;margin:12px 0 0;font:21px/1.15 var(--hand)}
.msg.ok{color:var(--green)}.msg.err{color:var(--red)}
.cerrado{padding:10px 12px;border:2px dashed var(--ink2);font:21px/1.15 var(--hand);margin-bottom:14px}
.clava textarea{min-height:90px;resize:vertical}
.jefe-dialog{border:0;padding:0;background:transparent;max-width:min(560px,94vw)}
.jefe-dialog h4{margin:18px 0 8px;font:19px/1.1 var(--carve);border-top:1px dashed var(--ink3);padding-top:14px}
.jefe-dialog .permiso{padding:8px 0;border-bottom:1px dashed rgba(60,40,20,.4);font-size:15px}
.jefe-dialog .permiso p{margin:0 0 4px}
.jefe-dialog .permiso .por{font:italic 13px var(--script);color:var(--ink3)}
.jefe-dialog .permiso .boton{font-size:14px;padding:5px 10px;margin:4px 6px 0 0}

/* ---------------------------------------------------------------- what the readers asked for */
.tarjetas-zona{margin-top:44px}
.tarjetas-zona>.cartelito{display:flex;justify-content:center;margin-bottom:26px}
.tarjetas-zona>.cartelito .placa{width:auto}
.tarjetas{display:flex;flex-wrap:wrap;gap:34px;justify-content:center;align-items:flex-start}
.tarjetas>.cosa{flex:0 1 330px}
.tarjeta h3{margin:0 0 4px;text-align:center;font:22px/1.1 var(--carve)}
.tarjeta .st{margin:0 0 10px;text-align:center;font:italic 14px/1.3 var(--script);color:var(--ink2)}
.tarjeta .gran{text-align:center;font:52px/1 var(--carve);margin:6px 0}
.tarjeta .gran-l{text-align:center;font:19px/1.2 var(--hand)}
.tarjeta ol{margin:0;padding-left:22px}
.tarjeta li{display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-bottom:1px dotted rgba(60,40,20,.35);font-size:15px}
.tarjeta li b{font-weight:700}
.tarjeta .bar{margin:6px 0}
.tarjeta .bar span{display:flex;justify-content:space-between;font-size:14px}
.tarjeta .bar i{display:block;height:9px;margin-top:2px;background:repeating-linear-gradient(90deg,var(--ink2) 0 5px,rgba(90,70,48,.6) 5px 7px)}
.tarjeta table{width:100%;border-collapse:collapse;font-size:14px}
.tarjeta th{font:12px var(--carve);text-transform:uppercase;letter-spacing:.04em;text-align:left;border-bottom:2px solid var(--ink2);padding:3px 4px}
.tarjeta td{border-bottom:1px dotted rgba(60,40,20,.35);padding:3px 4px}
.tarjeta .tx{margin:0;font-size:16px}
.tarjeta .pie{margin:10px 0 0;font:italic 13px/1.3 var(--script);color:var(--ink3);text-align:center}
.buzon form textarea{min-height:80px}
.buzon .lista-s{list-style:none;margin:14px 0 0;padding:0}
.buzon .lista-s li{padding:8px 0;border-bottom:1px dashed rgba(60,40,20,.4);font-size:15px}
.buzon .lista-s li small{display:block;font:italic 13px var(--script);color:var(--ink3)}
.sello-s{display:inline-block;margin-right:6px;padding:1px 6px;font:12px/1.4 var(--carve);letter-spacing:.04em;text-transform:uppercase;
  border:2px solid currentColor;border-radius:3px;transform:rotate(-2deg)}
.sello-s.hecha,.sello-s.aprobada{color:var(--green)}.sello-s.descartada,.sello-s.rechazada{color:var(--red)}
.sello-s.permiso,.sello-s.programar{color:#8a5a00}.sello-s.pendiente{color:var(--blue)}
.jefe-dialog::backdrop{background:rgba(10,6,3,.72)}
.jefe-dialog .perg .hoja{padding:24px 24px 20px}
.jefe-dialog label{display:block;margin:0 0 14px;font:15px/1.2 var(--carve);letter-spacing:.04em;color:var(--ink2);text-transform:uppercase}
.jefe-dialog input{display:block;width:100%;margin-top:4px;padding:6px 2px;border:0;border-bottom:2px solid var(--ink2);background:transparent;
  color:var(--ink);font:22px/1.1 var(--hand);border-radius:0}
.jefe-dialog input:focus{outline:none;border-bottom-color:var(--red)}
.jefe-dialog .hint{display:block;margin-top:4px;font:italic 14px/1.3 var(--script);text-transform:none;letter-spacing:0;color:var(--ink3)}
.jefe-dialog .botones{display:flex;gap:10px;flex-wrap:wrap}
.jefe-dialog .boton.sec{background:linear-gradient(180deg,#6b5a43,#3f3324);border-color:#2a2015}
.clava .boton{font-size:18px;padding:8px 16px;margin-top:10px}
.lado ul{list-style:none;margin:0;padding:0}
.lado li{padding:5px 0;border-bottom:1px dashed rgba(60,40,20,.4);font-size:16px}
.lado li span{display:block;font:italic 13px var(--script);color:var(--ink3)}
.reglas ol{margin:0;padding-left:22px}
.reglas li{margin:0 0 10px;font-size:16px}
.reglas li b{font:17px var(--carve);letter-spacing:.02em}

/* ---------------------------------------------------------------- footer + toast */
footer{max-width:1100px;margin:0 auto;padding:26px 20px 40px;color:#a68e6c;font:14px/1.5 var(--script);text-align:center}
footer a{color:#e2c48d}
.aviso{position:fixed;left:50%;bottom:20px;z-index:30;display:flex;gap:14px;align-items:center;padding:12px 16px;
  transform:translate(-50%,160%);opacity:0;pointer-events:none;transition:transform .3s,opacity .3s;
  background:var(--parch);background-image:var(--paper);border:2px solid var(--ink2);box-shadow:0 10px 30px rgba(0,0,0,.6);font:24px var(--hand)}
.aviso.on{transform:translate(-50%,0);opacity:1;pointer-events:auto}
.aviso .boton{font-size:16px;padding:7px 12px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}html{scroll-behavior:auto}}
""".replace("PLANKS", PLANKS).replace("BEAM", BEAM).replace("PAPER", PAPER)

JS = r"""(function(){
var S=window.SOLOQ||{};
function $(s,r){return (r||document).querySelector(s)}
function $$(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))}
function store(k,v){try{if(v===undefined)return localStorage.getItem(k);if(v===null)localStorage.removeItem(k);else localStorage.setItem(k,v)}catch(e){return null}}
function esc(t){return String(t==null?"":t).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}

// countdown carved on the plaque
var cd=$("#reloj");
if(cd){var target=+cd.getAttribute("data-target");
  var tick=function(){var s=Math.max(0,Math.floor((target-Date.now())/1000));
    var v={d:Math.floor(s/86400),h:("0"+Math.floor(s%86400/3600)).slice(-2),m:("0"+Math.floor(s%3600/60)).slice(-2)};
    for(var k in v){var el=cd.querySelector('[data-u="'+k+'"]');if(el)el.textContent=v[k]}};
  tick();setInterval(tick,15000)}

// the date the boss set on this page, before the robot has picked it up
function fecha(ms){return new Date(ms).toLocaleString("es-ES",{weekday:"long",day:"numeric",month:"long",hour:"2-digit",minute:"2-digit"})}
function clock(target,label){var box=$(".reloj");if(!box)return;
  box.innerHTML='<div style="font-size:18px">'+esc(label)+'</div><div class="n" id="reloj" data-target="'+target+'">'+
    '<div><b data-u="d">--</b><span>días</span></div><div><b data-u="h">--</b><span>horas</span></div><div><b data-u="m">--</b><span>min</span></div></div>'+
    '<div class="peq">'+esc(fecha(target))+'</div>';
  var el=$("#reloj"),tick=function(){var s=Math.max(0,Math.floor((target-Date.now())/1000));
    var v={d:Math.floor(s/86400),h:("0"+Math.floor(s%86400/3600)).slice(-2),m:("0"+Math.floor(s%3600/60)).slice(-2)};
    for(var k in v){var u=el.querySelector('[data-u="'+k+'"]');if(u)u.textContent=v[k]}};tick();setInterval(tick,15000)}

// relative times
function rel(ts){var m=Math.round((Date.now()-ts)/60000);if(m<1)return "ahora mismo";if(m<60)return "hace "+m+" min";
  var h=Math.round(m/60);if(h<24)return "hace "+h+" h";var d=Math.round(h/24);return "hace "+d+(d===1?" día":" días")}
function times(){$$("[data-ts]").forEach(function(el){el.textContent=rel(+el.getAttribute("data-ts"))})}
times();setInterval(times,60000);

// «tú»: the account this browser signed up
var yo=store("soloq-yo");
if(yo){$$('.fila[data-key]').forEach(function(f){if(f.getAttribute("data-key")===yo){f.classList.add("yo");
  var nm=f.querySelector(".quien .nm");if(nm&&!nm.querySelector(".tu"))nm.insertAdjacentHTML("beforeend",'<span class="tu">TÚ</span>')}})}
if(location.hash&&location.hash.indexOf("#j-")===0){var f=$(location.hash);if(f&&f.tagName==="DETAILS")f.open=true}

// the big chart: point at a name to follow its line, click it to open the player's row
var big=$("svg.big");
$$(".leyenda li").forEach(function(li){var k=li.getAttribute("data-k");
  function on(){if(!big)return;big.classList.add("foco");$$(".linea",big).forEach(function(g){g.classList.toggle("on",g.getAttribute("data-k")===k)})}
  function off(){if(big)big.classList.remove("foco")}
  li.addEventListener("mouseenter",on);li.addEventListener("mouseleave",off);li.addEventListener("focus",on);li.addEventListener("blur",off);
  li.addEventListener("click",function(){var f=document.getElementById(li.getAttribute("data-fila"));if(f){f.open=true;f.scrollIntoView({behavior:"smooth",block:"center"})}})});

// who is reading (shared with the newspaper)
var me=null;try{me=JSON.parse(localStorage.getItem("feeder-yo")||"null")}catch(e){}

// Supabase
var ok=S.url&&S.key;
function api(path,opts){opts=opts||{};opts.headers=Object.assign({apikey:S.key,Authorization:"Bearer "+S.key},opts.headers||{});
  return fetch(S.url.replace(/\/$/,"")+"/rest/v1/"+path,opts)}
var known={};(S.conocidos||[]).forEach(function(k){known[k]=1});

// the locker room: signed up on the web, waiting for the robot
var vest=$("#vestuario");
function loadVestuario(){if(!ok||!vest)return;
  api("soloq_inscritos?select=riot_id,apodo,created_at&order=id.desc&limit=60").then(function(r){return r.ok?r.json():[]}).then(function(rows){
    var seen={},items=[];rows.forEach(function(x){var k=String(x.riot_id||"").trim().toLowerCase();if(!k||known[k]||seen[k])return;seen[k]=1;items.push(x)});
    if(!items.length){vest.innerHTML='<p style="margin:0">Nadie esperando: todos los apuntados ya están en el tablón.</p>';return}
    vest.innerHTML='<ul>'+items.slice(0,10).map(function(x){return '<li><b>'+esc(x.apodo)+'</b><span>'+esc(x.riot_id)+'</span></li>'}).join("")+'</ul>'+
      '<p style="margin:6px 0 0">Entran en la próxima pasada del robot (cada 30 minutos).</p>'}).catch(function(){})}
loadVestuario();

// sign-up form
var form=$("#alta");
if(form){
  var msg=$("#alta-msg"),btn=form.querySelector("button");
  if(!ok){$$("input,select,button",form).forEach(function(el){el.disabled=true})}
  if(me&&me.cuentas&&me.cuentas.length&&form.jugador){form.jugador.value=me.cuentas[0]}
  form.addEventListener("submit",function(ev){ev.preventDefault();if(!ok)return;
    var rid=form.riot_id.value.trim().replace(/\s*#\s*/,"#"),apodo=form.apodo.value.trim();
    msg.className="msg";
    if(!/^[^#]{3,16}#[^#\s]{2,5}$/.test(rid)){msg.className="msg err";msg.textContent="Eso no es un Riot ID. Formato: Nombre#TAG (lo de después de la almohadilla).";return}
    if(!form.jugador.value){msg.className="msg err";msg.textContent="Di quién eres. Las cuentas compradas no se apuntan solas.";return}
    if(!apodo){msg.className="msg err";msg.textContent="Ponte un mote. Uno que no te dé vergüenza ver en último lugar.";return}
    if(!form.acepto.checked){msg.className="msg err";msg.textContent="Sin aceptar el escarnio público no hay reto. Son las normas.";return}
    if(known[rid.toLowerCase()]){msg.className="msg err";msg.textContent="Esa cuenta ya está clavada en el tablón. Ni apuntándote dos veces subes.";return}
    btn.disabled=true;msg.textContent="Clavando tu nombre…";
    var j=form.jugador.value==="fuera"?null:form.jugador.value;
    var body={riot_id:rid,apodo:apodo.slice(0,24),jugador:j,objetivo:form.objetivo.value||null,
      lema:form.lema.value.trim().slice(0,120)||null,lector:store("feeder-lector")||null};
    api("soloq_inscritos",{method:"POST",headers:{"Content-Type":"application/json",Prefer:"return=minimal"},body:JSON.stringify(body)})
      .then(function(r){if(!r.ok)throw new Error(r.status);store("soloq-yo",rid.toLowerCase());
        msg.className="msg ok";msg.textContent="Apuntado. En media hora como mucho estás clavado en el tablón. Ve calentando el dedo del /ff.";
        form.reset();loadVestuario()})
      .catch(function(){msg.className="msg err";msg.textContent="No se ha podido apuntar. Prueba en un rato (o échale la culpa al jungla)."})
      .then(function(){btn.disabled=false})});
}

// the boss's schedule: shown at once, even before the robot picks it up
if(ok&&S.fase==="inscripcion"){api("soloq_control?select=id,inicio,fin&order=id.desc&limit=1").then(function(r){return r.ok?r.json():[]})
  .then(function(rows){var c=rows[0];if(c&&c.id>(S.control||0)){var t=Date.parse(c.inicio);if(t>Date.now())clock(t,"Empieza en")}}).catch(function(){})}

// the boss sets the starting date (the password is checked by the database, never here)
var jd=$("#jefe-dialog"),jb=$("#jefe-btn");
if(jd&&jb){var jf=$("#jefe"),jm=$("#jefe-msg");
  jb.addEventListener("click",function(ev){ev.preventDefault();if(jd.showModal)jd.showModal();else jd.setAttribute("open","")});
  $("#jefe-cerrar").addEventListener("click",function(){jd.close()});
  jf.addEventListener("submit",function(ev){ev.preventDefault();
    if(!ok){jm.className="msg err";jm.textContent="El tablón aún no tiene base de datos.";return}
    var ini=jf.inicio.value,fin=jf.fin.value,clave=jf.clave.value;
    if(!ini){jm.className="msg err";jm.textContent="Pon fecha y hora de salida.";return}
    if(!clave){jm.className="msg err";jm.textContent="Sin contraseña no hay pistoletazo.";return}
    var a=new Date(ini),b=fin?new Date(fin):null;
    if(b&&b<=a){jm.className="msg err";jm.textContent="El final tiene que ir después de la salida. Por lógica.";return}
    jm.className="msg";jm.textContent="Comprobando la contraseña…";
    api("rpc/soloq_programar",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({clave:clave,p_inicio:a.toISOString(),p_fin:b?b.toISOString():null})})
      .then(function(r){if(r.status===401||r.status===403||r.status===400){return r.json().then(function(e){throw new Error((e&&e.message)||"no")})}
        if(!r.ok)throw new Error("red");return r.json()})
      .then(function(){jm.className="msg ok";jm.textContent="Hecho. Salida el "+fecha(a.getTime())+(b?" y final el "+fecha(b.getTime()):"")+
        ". El tablón y Discord se enteran en la próxima pasada del robot (media hora como mucho).";jf.clave.value="";
        if(a.getTime()>Date.now())clock(a.getTime(),"Empieza en")})
      .catch(function(e){jm.className="msg err";jm.textContent=/Contrase/.test(e.message)?"Contraseña incorrecta. Aquí no entra cualquiera.":
        /final/.test(e.message)?e.message:"No se ha podido guardar. Prueba otra vez en un rato."})})}

// the suggestion box
var bz=$("#buzon"),bzl=$("#buzon-lista");
function loadBuzon(){if(!ok||!bzl)return;var seen={};(S.sugerencias||[]).forEach(function(i){seen[i]=1});
  api("soloq_sugerencias?select=id,nombre,texto&order=id.desc&limit=10").then(function(r){return r.ok?r.json():[]}).then(function(rows){
    var nuevas=rows.filter(function(x){return !seen[x.id]});
    nuevas.reverse().forEach(function(x){bzl.insertAdjacentHTML("afterbegin",'<li><span class="sello-s pendiente">En el buzón</span>'+esc(x.texto)+
      '<small>'+esc(x.nombre)+' · la redacción la revisa mañana</small></li>')})}).catch(function(){})}
loadBuzon();
if(bz){var bm=$("#buzon-msg");
  if(!ok){$$("input,textarea,button",bz).forEach(function(el){el.disabled=true})}
  if(me&&me.nombre&&bz.nombre)bz.nombre.value=me.nombre;
  bz.addEventListener("submit",function(ev){ev.preventDefault();if(!ok)return;
    var t=bz.texto.value.trim(),n=bz.nombre.value.trim();
    if(t.length<10){bm.className="msg err";bm.textContent="Explica un poco más qué quieres ver. Diez letras, mínimo.";return}
    if(!n){bm.className="msg err";bm.textContent="Firma la sugerencia, que luego hay que darte las gracias (o las culpas).";return}
    api("soloq_sugerencias",{method:"POST",headers:{"Content-Type":"application/json",Prefer:"return=minimal"},
      body:JSON.stringify({nombre:n.slice(0,40),texto:t.slice(0,400),lector:store("feeder-lector")||null})})
      .then(function(r){if(!r.ok)throw new Error(r.status);bm.className="msg ok";
        bm.textContent="Al buzón. Mañana la redacción la revisa: si se puede, sale como tarjeta en el tablón.";
        bz.texto.value="";loadBuzon()})
      .catch(function(){bm.className="msg err";bm.textContent="El buzón está atascado. Prueba en un rato."})})}

// the boss answers the suggestions that wait for permission
$$(".permiso [data-decision]").forEach(function(b){b.addEventListener("click",function(){
  var jfm=$("#jefe"),pm=$("#permiso-msg"),clave=jfm?jfm.clave.value:"";
  if(!clave){pm.className="msg err";pm.textContent="Pon la contraseña arriba.";return}
  var row=b.closest(".permiso"),nota=row.querySelector("input")?row.querySelector("input").value.trim():"";
  api("rpc/soloq_decidir",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({clave:clave,p_sugerencia:+row.getAttribute("data-id"),p_decision:b.getAttribute("data-decision"),p_nota:nota||null})})
    .then(function(r){if(!r.ok)return r.json().then(function(e){throw new Error((e&&e.message)||"no")});
      row.innerHTML='<p><b>'+(b.getAttribute("data-decision")==="aprobada"?"Aprobada":"Rechazada")+'.</b> La redacción se entera mañana.</p>'})
    .catch(function(e){pm.className="msg err";pm.textContent=/Contrase/.test(e.message)?"Contraseña incorrecta.":"No se ha podido guardar."})})});

// readers' notes nailed to the board
var wall=$("#notas-lectores"),colors=["amarilla","rosa","verde",""];
function pin(n,i){var r=((i*37)%9-4)*0.8;return '<div class="cosa nota lector hoja '+colors[i%4]+'" style="--r:'+r+'deg"><i class="chincheta"></i>'+
  esc(n.texto)+'<span class="firma">— '+esc(n.nombre)+'</span></div>'}
function loadNotas(){if(!ok||!wall)return;
  api("soloq_notas?select=nombre,texto,created_at&order=id.desc&limit=12").then(function(r){return r.ok?r.json():[]}).then(function(rows){
    wall.innerHTML=rows.map(pin).join("")}).catch(function(){})}
loadNotas();
var clava=$("#clava");
if(clava){var cm=$("#clava-msg");
  if(!ok){$$("input,textarea,button",clava).forEach(function(el){el.disabled=true})}
  if(me&&me.nombre&&clava.nombre)clava.nombre.value=me.nombre;
  clava.addEventListener("submit",function(ev){ev.preventDefault();if(!ok)return;
    var t=clava.texto.value.trim(),n=clava.nombre.value.trim();
    if(t.length<4){cm.className="msg err";cm.textContent="Escribe algo. Aunque sea un insulto bien puesto.";return}
    if(!n){cm.className="msg err";cm.textContent="Firma la nota. Aquí se insulta con nombre y apellidos.";return}
    api("soloq_notas",{method:"POST",headers:{"Content-Type":"application/json",Prefer:"return=minimal"},
      body:JSON.stringify({nombre:n.slice(0,40),texto:t.slice(0,180),lector:store("feeder-lector")||null})})
      .then(function(r){if(!r.ok)throw new Error(r.status);cm.className="msg ok";cm.textContent="Clavada. Ya la puede leer todo el mundo.";
        clava.texto.value="";loadNotas()})
      .catch(function(){cm.className="msg err";cm.textContent="El martillo ha fallado. Prueba otra vez."})})}

// the board changed while the page was open
var toast=$("#aviso");
if(toast&&S.actualizado){setInterval(function(){
  fetch("datos.json?t="+Date.now(),{cache:"no-store"}).then(function(r){return r.ok?r.json():null}).then(function(d){
    if(d&&d.actualizado&&d.actualizado!==S.actualizado)toast.classList.add("on")}).catch(function(){})},180000);
  toast.querySelector("button").addEventListener("click",function(){location.reload()})}
})();
"""

ASSET_VERSION = hashlib.sha1((CSS + JS).encode("utf-8")).hexdigest()[:10]


def _e(x):
    return escape(str(x), quote=True)


def _initials(name):
    letters = [w[0] for w in str(name).replace("#", " ").split() if w]
    return ("".join(letters[:2]) or "?").upper()


def _rot(seed, spread=2.6):
    """A small, stable tilt for each pinned thing."""
    n = int(hashlib.sha1(str(seed).encode("utf-8")).hexdigest(), 16)
    return f"{(n % 1000) / 1000 * 2 * spread - spread:.2f}deg"


def _torn(seed, jag=1.2, n=18):
    """A clip-path with ragged edges, like hand-torn paper."""
    rng = random.Random(str(seed))
    right = [f"{100 - rng.uniform(0, jag):.1f}% {i * 100 / n:.1f}%" for i in range(n + 1)]
    left = [f"{rng.uniform(0, jag):.1f}% {100 - i * 100 / n:.1f}%" for i in range(n + 1)]
    top = [f"{x}% {rng.uniform(0, jag * .5):.1f}%" for x in (25, 50, 75)]
    bottom = [f"{x}% {100 - rng.uniform(0, jag * .5):.1f}%" for x in (75, 50, 25)]
    return "polygon(" + ",".join([left[-1]] + top + right + bottom + left) + ")"


def _nails(spots):
    return "".join(f'<i class="clavo" style="{s}"></i>' for s in spots)


def _perg(inner, seed, cls="", extra=""):
    """A scroll of parchment, rolled at both ends and nailed to the board."""
    nail = _nails(["left:9%;top:4px", "right:9%;top:4px", "left:9%;bottom:4px", "right:9%;bottom:4px"])
    return (f'<section class="cosa perg {cls}" style="--r:{_rot(seed, .7)}" {extra}><i class="rollo"></i>'
            f'<div class="hoja" style="clip-path:{_torn(seed, .7, 30)}">{inner}</div><i class="rollo"></i>{nail}</section>')


def _placa(inner, seed, cls=""):
    nail = _nails(["left:3px;top:3px", "right:3px;top:3px", "left:3px;bottom:3px", "right:3px;bottom:3px"])
    return f'<div class="cosa placa {cls}" style="--r:{_rot(seed, 1.2)}"><div class="in">{inner}</div>{nail}</div>'


def _nota(texto, firma, seed, cls=""):
    color = ["amarilla", "", "rosa", "verde", ""][int(hashlib.sha1(seed.encode()).hexdigest(), 16) % 5]
    return (f'<div class="cosa nota hoja {color} {cls}" style="--r:{_rot(seed, 4)};clip-path:{_torn(seed, 2.2, 8)}">'
            f'<i class="clavo" style="left:calc(50% - 7px);top:5px"></i>{_e(texto)}<span class="firma">— {_e(firma)}</span></div>')


# --------------------------------------------------------------------------- pictures
def _gradients():
    stops = "".join(f'<radialGradient id="g-{t.lower()}" cx=".4" cy=".35" r=".8"><stop offset="0" stop-color="{a}"/>'
                    f'<stop offset="1" stop-color="{b}"/></radialGradient>' for t, (a, b) in TIER_COLORS.items())
    return f'<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>{stops}</defs></svg>'


def crest(tier, cls="crest"):
    """A league crest drawn in SVG (no external images): a shield in the tier's colours with a gem."""
    t = tier if tier in TIERS else "NONE"
    crown = ('<path d="M19 12 L23 3 L28 9 L32 1 L36 9 L41 3 L45 12" fill="none" stroke="#3b2a12" stroke-width="2.2" '
             'stroke-linejoin="round"/>' if soloq.apex(t) else "")
    return (f'<svg class="{cls}" viewBox="0 0 64 64" aria-hidden="true">'
            f'<path d="M32 6 L54 15 L54 35 C54 48 44 56 32 61 C20 56 10 48 10 35 L10 15 Z" fill="url(#g-{t.lower()})" '
            'stroke="#3b2a12" stroke-width="2.4"/>'
            '<path d="M32 16 L44 32 L32 51 L20 32 Z" fill="rgba(255,255,255,.2)" stroke="rgba(40,25,10,.55)" stroke-width="1.4"/>'
            '<path d="M32 22 L38.5 32 L32 44 L25.5 32 Z" fill="rgba(255,255,255,.38)"/>'
            f'{crown}</svg>')


def _sello(x):
    """The league as a wax seal: the tier's colour with its division pressed in."""
    t = x["tier"] if x["tier"] in TIERS else "NONE"
    txt = "–" if t == "NONE" else {"MASTER": "M", "GRANDMASTER": "GM", "CHALLENGER": "C"}.get(t, x["division"])
    a, b = TIER_COLORS[t]
    return (f'<span class="sello" title="{_e(x["liga"])}" style="background:radial-gradient(circle at 40% 35%,{a},{b})">'
            f'{_e(txt)}</span>')


def _champ_img(cid, champ, ver):
    if not cid:
        return f'<span class="ch" data-i="{_e(_initials(champ))}"></span>'
    src = (f"{soloq.DDRAGON}/cdn/{ver}/img/champion/{urllib.parse.quote(cid)}.png" if ver else
           f"https://cdn.communitydragon.org/latest/champion/{urllib.parse.quote(cid)}/square")
    return (f'<span class="ch" data-i="{_e(_initials(champ))}"><img src="{_e(src)}" alt="{_e(champ)}" loading="lazy" '
            'onerror="this.remove()"></span>')


def _value_name(v):
    tier = TIERS[min(int(v // 400), TIERS.index("MASTER"))]
    if soloq.apex(tier):
        return f"{TIER_ES[tier]} {int(v - 2800)}"
    return f"{TIER_ES[tier]} {['IV', 'III', 'II', 'I'][int(v % 400 // 100)]}"


def _scale(lo, hi):
    lo, hi = (lo // 100) * 100, (hi // 100 + 1) * 100
    if hi - lo > 1200:   # long falls and climbs: one line per tier instead of per division
        return (lo // 400) * 400, (hi // 400 + 1) * 400, 400
    return lo, hi, 100


def _steps(pts):
    """LP only change when a game ends: draw steps, not slopes."""
    out = [pts[0]]
    for t, v in pts[1:]:
        out += [(t, out[-1][1]), (t, v)]
    return out


def _chart(x, r):
    """One player's LP since the starting gun, in ink."""
    pts = [(t, v) for t, v in x.get("serie") or [] if v is not None]
    if len(pts) < 2:
        return '<p class="obj" style="margin:0"><span style="font:19px var(--hand)">La gráfica sale en cuanto se mueva de su sitio.</span></p>'
    W, H, L, R, T, B = 560, 170, 96, 12, 10, 22
    t0, t1 = pts[0][0], max(pts[-1][0], pts[0][0] + 1)
    lo, hi, step = _scale(min(v for _, v in pts), max(v for _, v in pts))

    def X(t):
        return L + (t - t0) / (t1 - t0) * (W - L - R)

    def Y(v):
        return T + (hi - v) / (hi - lo) * (H - T - B)

    grid = "".join(f'<line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                   f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{_e(_value_name(v))}</text>'
                   for v in range(int(lo), int(hi) + 1, step))
    path = " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in _steps(pts))
    ink = TIER_INK.get(x["tier"] or "NONE", "#2b1d10")
    return (f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="LP de {_e(x["nombre"])}">'
            f'<g class="rej">{grid}</g><polyline class="tinta" style="stroke:{ink}" points="{path}"/></svg>')


def _big_chart(rows, r, at_ms, ids):
    """Every player's line on one sheet: who climbs, who sinks and when."""
    series = [(x, [(t, v) for t, v in x.get("serie") or [] if v is not None]) for x in rows]
    series = [(x, pts) for x, pts in series if pts]
    if not series:
        return ('<p class="vacia">La gráfica se empieza a dibujar en cuanto alguien termine sus partidas de '
                'clasificación. De momento, papel en blanco y mucha fe.</p>')
    W, H, L, R, T, B = 760, 380, 112, 118, 14, 30
    t0 = min(pts[0][0] for _, pts in series)
    t1 = max(at_ms, t0 + 3600 * 1000)
    vals = [v for _, pts in series for _, v in pts]
    lo, hi, step = _scale(min(vals), max(vals))

    def X(t):
        return L + (t - t0) / (t1 - t0) * (W - L - R)

    def Y(v):
        return T + (hi - v) / (hi - lo) * (H - T - B)

    grid = "".join(f'<line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                   f'<text x="{L - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{_e(_value_name(v))}</text>'
                   for v in range(int(lo), int(hi) + 1, step))
    days = max(1, int((t1 - t0) / 86400000))       # one tick a day (fewer if the race is long)
    every = max(1, days // 8)
    d0 = datetime.fromtimestamp(t0 / 1000, r["tz"]).replace(hour=0, minute=0, second=0, microsecond=0)
    ticks = []
    for i in range(0, days + 2, every):
        t = int(d0.timestamp() * 1000) + i * 86400000
        if t0 <= t <= t1:
            d = datetime.fromtimestamp(t / 1000, r["tz"]).date()
            ticks.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{T}" y2="{H - B}" style="stroke-dasharray:2 5"/>'
                         f'<text x="{X(t):.1f}" y="{H - 8}" text-anchor="middle">{d.day}/{d.month}</text>')
    lines, labels = [], []
    for i, (x, pts) in enumerate(series):
        ink, dash = INKS[i % len(INKS)], DASHES[(i // len(INKS)) % len(DASHES)]
        pts = pts + [(at_ms, pts[-1][1])]
        path = " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in _steps(pts))
        style = f"stroke:{ink}" + (f";stroke-dasharray:{dash}" if dash else "")
        lines.append(f'<g class="linea" data-k="{_e(x["key"])}"><polyline class="tinta" style="{style}" points="{path}"/>'
                     f'<circle cx="{X(pts[-1][0]):.1f}" cy="{Y(pts[-1][1]):.1f}" r="4" fill="{ink}"/></g>')
        labels.append([Y(pts[-1][1]), x["nombre"], ink])
    labels.sort()
    for i in range(1, len(labels)):            # names at the end of the lines must not overlap
        labels[i][0] = max(labels[i][0], labels[i - 1][0] + 18)
    lab = "".join(f'<text class="lbl" x="{W - R + 8}" y="{y + 4:.1f}" fill="{ink}">{_e(n)}</text>' for y, n, ink in labels)
    legend = "".join(
        f'<li tabindex="0" data-k="{_e(x["key"])}" data-fila="{_e(ids[x["key"]])}"><svg viewBox="0 0 30 8">'
        f'<line x1="0" y1="4" x2="30" y2="4" stroke="{INKS[i % len(INKS)]}" stroke-width="3" '
        f'stroke-dasharray="{DASHES[(i // len(INKS)) % len(DASHES)]}"/></svg>{_e(x["nombre"])}</li>'
        for i, (x, _) in enumerate(series))
    height = max(H, int(labels[-1][0]) + 10)
    return (f'<div class="lienzo"><svg class="chart big" viewBox="0 0 {W} {height}" role="img" '
            f'aria-label="Evolución de LP de todos los jugadores"><g class="rej">{grid}{"".join(ticks)}</g>'
            f'{"".join(lines)}{lab}</svg></div><ul class="leyenda">{legend}</ul>')


def _signed(n, unit=" LP"):
    if n is None:
        return '<span class="eq">–</span>'
    if n == 0:
        return '<span class="eq">=</span>'
    return f'<span class="{"up" if n > 0 else "down"}">{"+" if n > 0 else "−"}{abs(n)}{unit}</span>'


def _delta(x):
    if "cambio" not in x:
        return '<div class="dl eq">·</div>'
    c = x["cambio"]
    if c is None:
        return '<div class="dl new" title="Nuevo en la tabla desde las 07:00">NUEVO</div>'
    if c == 0:
        return '<div class="dl eq" title="Mismo puesto que a las 07:00">=</div>'
    return (f'<div class="dl {"up" if c > 0 else "down"}" title="{"Sube" if c > 0 else "Baja"} {abs(c)} '
            f'{"puesto" if abs(c) == 1 else "puestos"} desde las 07:00">{"▲" if c > 0 else "▼"}{abs(c)}</div>')


def _opgg(cfg, riot_id):
    region = PLATFORM_OPGG.get(cfg.get("platform", "euw1"), "euw")
    name, tag = riot_id.rsplit("#", 1)
    return f"https://www.op.gg/summoners/{region}/{urllib.parse.quote(name)}-{urllib.parse.quote(tag)}"


def _fila(cfg, r, x, ver, rel_paper, row_id, noticias):
    wr = x["winrate"]
    top = f' top{x["puesto"]}' if x["puesto"] <= 3 and x["valor"] is not None else ""
    if x["valor"] is not None:
        lg = (f'<div class="lg">{_sello(x)}<div><b>{_e(x["liga_corta"])}</b><span>{x["lp"]} LP</span>'
              + ('' if x["partidas"] >= r["min_partidas"] else
                 f'<span class="nq">le faltan {r["min_partidas"] - x["partidas"]} partidas</span>') + '</div></div>')
    else:
        lg = (f'<div class="lg">{_sello(x)}<div><b>Sin clasificar</b>'
              f'<span>{"en las de clasificación" if x["partidas"] else "sin estrenar"}</span></div></div>')
    hoy = x["hoy"]
    hoy_html = (f'<div class="hoy">{_signed(x.get("lp_hoy"))}'
                + (f'<small>{hoy[0]}V {hoy[1]}D hoy</small>' if sum(hoy) else '<small>hoy, nada</small>') + '</div>')
    wr_html = (f'<div class="wr"><div class="n"><span>{x["victorias"]}V {x["derrotas"]}D</span><b>{round(wr * 100)} %</b></div>'
               f'<div class="barra"><i style="width:{wr * 100:.1f}%"></i></div></div>' if wr is not None else
               '<div class="wr"><div class="n"><span>0 partidas</span><b>–</b></div><div class="barra"></div></div>')
    rk = x["racha"]
    racha = (f'<div class="racha {"up" if rk > 0 else "down"}" title="Racha actual">{abs(rk)}{"V" if rk > 0 else "D"}</div>'
             if rk else '<div class="racha eq">–</div>')
    ult = "".join(f'<span class="{"v" if g["win"] else "d"}" title="{_e(g["champ"])} {g["k"]}/{g["d"]}/{g["a"]}">'
                  f'{"✓" if g["win"] else "✗"}</span>' for g in reversed(x["ultimas"][:5]))
    ult = f'<div class="ult c-ult">{ult or "<span class=nada>sin partidas</span>"}</div>'
    mote = f' <i>«{_e(x["apodo"])}»</i>' if x["apodo"] != x["nombre"] else ""
    summary = (f'<summary><div class="pos">{x["puesto"]}</div>{_delta(x)}'
               f'<div class="quien"><div class="nm">{_e(x["nombre"])}{mote}</div>'
               f'<div class="rid">{_e(x["riot_id"])}{" · nivel " + str(x["nivel"]) if x.get("nivel") else ""}</div>'
               f'<div class="ver">{_e(x["veredicto"])}</div></div>'
               f'{lg}{hoy_html}{wr_html}{racha}{ult}</summary>')
    kv = [("Empezó en", x["inicio"]), ("Pico", x["pico"] or "–"), ("LP en el reto", None),
          ("KDA", fmt_num(x["kda"], 2) if x["kda"] is not None else "–"), ("Horas jugadas", fmt_num(x["horas"], 1)),
          ("Temporada", f'{x["temporada"][0]}V {x["temporada"][1]}D')]
    kv_html = "".join(f'<div><span>{_e(k)}</span><b>{_signed(x["lp_reto"]) if v is None else _e(v)}</b></div>' for k, v in kv)
    obj = ""
    if x.get("objetivo"):
        gv = soloq.target_value(x["objetivo"])
        base = (x.get("serie") or [(0, x["valor"] or 0)])[0][1] or 0
        pct = 100 if x["cumplido"] else max(0, min(100, ((x["valor"] or 0) - base) / max(gv - base, 1) * 100)) if gv else 0
        txt = ("Objetivo cumplido. Ahora, a no tirarlo." if x["cumplido"] else
               f'Le faltan {x["falta"]} LP. Lo dijo en voz alta, que conste.' if x.get("falta") is not None else
               "Primero tendrá que acabar las de clasificación.")
        obj = (f'<div class="recuadro obj" style="margin-top:12px"><h4>Prometió llegar a {_e(x["objetivo_es"])}</h4>'
               f'<div class="track"><i style="width:{pct:.0f}%"></i></div><p>{_e(txt)}</p></div>')
    champs = "".join(f'<div class="champ">{_champ_img(c.get("cid"), c["champ"], ver)}<span>{_e(c["champ"])}</span>'
                     f'<span class="wrc">{c["partidas"]} partidas · {round(c["victorias"] / c["partidas"] * 100)} %</span></div>'
                     for c in x["campeones"]) or '<p style="margin:0;color:var(--ink3)">Aún sin partidas en el reto.</p>'
    games = "".join(f'<span class="partida {"v" if g["win"] else "d"}" title="{_e(g["champ"])}">'
                    f'{_champ_img(g.get("cid"), g["champ"], ver)}{g["k"]}/{g["d"]}/{g["a"]}</span>' for g in x["ultimas"])
    lema = f'<p class="lema-fila">«{_e(x["lema"])}»</p>' if x.get("lema") else ""
    links = [f'<a href="{_e(_opgg(cfg, x["riot_id"]))}" target="_blank" rel="noopener">OP.GG ↗</a>']
    if x.get("jugador"):
        links.append(f'<a href="{rel_paper}jugadores/{_e(x["jugador"])}.html">Su ficha en El Rincón del Feeder</a>')
    news = [n for n in noticias if x.get("jugador") and n.get("player") == x["jugador"]][:3]
    news_html = "".join(f'<li><a href="{_e(n["href"])}">{_e(n["headline"])}</a><span>{_e(n["fecha"])}</span></li>' for n in news)
    news_html = (f'<div class="recuadro lado" style="margin-top:12px"><h4>Sale en El Rincón</h4><ul>{news_html}</ul></div>'
                 if news_html else "")
    det = (f'<div class="det"><div><div class="recuadro"><h4>Sus LP, a tinta</h4>{_chart(x, r)}</div>'
           f'<div class="kv">{kv_html}</div>{obj}</div>'
           f'<div><div class="recuadro"><h4>Campeones del reto</h4>{champs}</div>'
           f'<div class="recuadro" style="margin-top:12px"><h4>Últimas partidas</h4><div class="partidas">'
           f'{games or "<span style=color:var(--ink3)>Ni una todavía.</span>"}</div>{lema}'
           f'<div class="enl">{"".join(links)}</div></div>{news_html}</div></div>')
    return f'<details class="fila{top}" id="{_e(row_id)}" data-key="{_e(x["key"])}">{summary}{det}</details>'


def _lista(rows, rel_paper):
    """Before the starting gun: the sign-up sheet."""
    if not rows:
        return ('<p class="vacia">Nadie se ha apuntado todavía. El tablón está más vacío que el chat de tu equipo '
                'cuando pides ayuda.</p>')
    lis = []
    for i, x in enumerate(rows, 1):
        who = (f'<a href="{rel_paper}jugadores/{_e(x["jugador"])}.html">{_e(x["nombre"])}</a>' if x.get("jugador")
               else _e(x["nombre"]))
        mote = f' <i>«{_e(x["apodo"])}»</i>' if x["apodo"] != x["nombre"] else ""
        meta = (f'Nivel {x["nivel"]}<br>' if x.get("nivel") else "") + (
            '<span class="up">sin estrenar ✓</span>' if x["valor"] is None else
            f'<span class="down">ya tiene liga: {_e(x["liga_corta"])}</span>')
        goal = f' · promete {_e(x["objetivo_es"])}' if x.get("objetivo_es") else ""
        lema = f'<span class="lema">«{_e(x["lema"])}»</span>' if x.get("lema") else ""
        lis.append(f'<li><span class="n">{i}</span><div><b>{who}</b>{mote}<small>{_e(x["riot_id"])}{goal}</small>{lema}</div>'
                   f'<div class="meta">{meta}</div></li>')
    return f'<ol class="lista">{"".join(lis)}</ol>'


def _registro(moves):
    if not moves:
        return '<p style="font:21px var(--hand);margin:0">Ni un movimiento. La tabla está más quieta que un tirador sin soporte.</p>'
    lis = []
    for m in moves:
        lp = f'<span class="lp">{_signed(m.get("delta"))}</span>' if m.get("delta") else ""
        lis.append(f'<li>{lp}<span class="q">{_e(m["nombre"])}</span>: {_e(m["texto"])}'
                   f'<span class="t" data-ts="{m["ts"]}"></span></li>')
    return f'<ol>{"".join(lis)}</ol>'


def _muro(awards):
    if not awards:
        return '<p style="font:21px var(--hand);margin:0">Los premios se reparten en cuanto alguien juegue. Material no va a faltar.</p>'
    return "".join(f'<div class="premio"><div class="pt">{_e(a["titulo"])}</div><div class="pc">{_e(a["criterio"])}</div>'
                   f'<div class="pw">{_e(a["nombre"])}</div><div class="px">{_e(a["texto"])}</div></div>' for a in awards)


def noticias(editions, rows, rel_paper, since_ms=None, limit=12):
    """Stories of El Rincón del Feeder about the race, or about its people once it started, newest first."""
    slugs = {x["jugador"] for x in rows if x.get("jugador")}
    out = []
    for ed in sorted(editions or [], key=lambda e: e["date"], reverse=True):
        if not ed.get("ai"):
            continue          # only what the newsroom published, never the robot's draft
        for it in ed.get("items") or []:
            about = it.get("section") == "SOLOQ CHALLENGE" or str(it.get("clave") or "").startswith("soloq")
            if about or (it.get("player") in slugs and since_ms and ed["window"][1] >= since_ms):
                d = datetime.fromisoformat(ed["date"]).date()
                out.append({"headline": it["headline"], "body": it.get("body") or "", "player": it.get("player"),
                            "section": it.get("section"), "fecha": short_date(d),
                            "href": f'{rel_paper}ediciones/{ed["date"]}.html#p-{it.get("id", 0)}', "reto": about})
        if len(out) >= limit * 3:
            break
    out.sort(key=lambda n: not n["reto"])       # stable: the race's own stories first, newest first
    return out[:limit]


def _recorte(n, seed, cls=""):
    body = n["body"].split("\n\n")[0]
    body = body if len(body) <= 220 else body[:217].rsplit(" ", 1)[0] + "…"
    return (f'<article class="cosa recorte {cls}" style="--r:{_rot(seed, 3)};clip-path:{_torn(seed, 1.6, 10)}">'
            f'<i class="clavo" style="left:calc(50% - 7px);top:5px"></i>'
            f'<div class="k">El Rincón del Feeder · {_e(n["fecha"])} · {_e((n["section"] or "").capitalize())}</div>'
            f'<h4>{_e(n["headline"])}</h4><p>{_e(body)}</p><a class="leer" href="{_e(n["href"])}">Leer en El Rincón →</a></article>')


def _tarjeta(c, buzon, fecha):
    """A card the newsroom made from a reader's suggestion."""
    d, t = c["datos"], c["tipo"]
    if t == "cifra":
        body = (f'<div class="gran">{_e(d["valor"])}</div><div class="gran-l">{_e(d["etiqueta"])}'
                + (f' · <b>{_e(d["quien"])}</b>' if d.get("quien") else "") + '</div>')
    elif t == "lista":
        body = "<ol>" + "".join(f'<li><span>{_e(f["nombre"])}</span><b>{_e(f["valor"])}</b></li>' for f in d["filas"]) + "</ol>"
    elif t == "barras":
        top = max((abs(f["valor"]) for f in d["filas"]), default=1) or 1
        body = "".join(f'<div class="bar"><span><b>{_e(f["nombre"])}</b><span>{_e(f.get("texto") or fmt_num(f["valor"], 0 if float(f["valor"]).is_integer() else 1))}</span></span>'
                       f'<i style="width:{abs(f["valor"]) / top * 100:.0f}%"></i></div>' for f in d["filas"])
    elif t == "tabla":
        body = ("<table><thead><tr>" + "".join(f"<th>{_e(h)}</th>" for h in d["columnas"]) + "</tr></thead><tbody>"
                + "".join("<tr>" + "".join(f"<td>{_e(x)}</td>" for x in row) + "</tr>" for row in d["filas"]) + "</tbody></table>")
    else:
        body = f'<p class="tx">{_e(d["texto"])}</p>'
    who = next((b["nombre"] for b in buzon if b["id"] == c.get("sugerencia")), None)
    pie = " · ".join(x for x in (c.get("pie"), f"Sugerida por {who}" if who else None, f"Datos del {fecha}" if fecha else None) if x)
    sub = f'<p class="st">{_e(c["subtitulo"])}</p>' if c.get("subtitulo") else ""
    return _perg(f'<div class="tarjeta"><h3>{_e(c["titulo"])}</h3>{sub}{body}<p class="pie">{_e(pie)}</p></div>', "t" + c["id"])


def _date_es(ms, r):
    return long_date(datetime.fromtimestamp(ms / 1000, r["tz"]).date())


def render(cfg, datos, now_ms, roster=(), ver=None, rel_paper="../", editions=(), cast=(), buzon=None):
    """The whole page as HTML, plus the small JSON the open pages poll to notice changes."""
    r = soloq.reto_de(cfg, datos)
    ph = soloq.fase(r, now_ms)
    at = min(now_ms, r["fin_ms"] or now_ms)
    ref = soloq.ultimo_corte(r, at) if ph == "en_juego" else None
    rows = soloq.puesta_al_dia(datos, r, at, ref)
    day = datetime.fromtimestamp(at / 1000, r["tz"]).date().isoformat()
    started = ph != "inscripcion"
    ranked = [x for x in rows if x["valor"] is not None] if started else []
    ids = {x["key"]: "j-" + soloq.slug_key(x["key"]) for x in rows}
    awards = soloq.premios(rows) if started else []
    moves = soloq.movimientos(datos, r, (r["inicio_ms"] or 0) - 7 * 86400000, at, limit=12)
    _, rejected = soloq.activos(datos, r)
    title = r["nombre"]
    site_title = cfg.get("site_title", "El Rincón del Feeder")
    news = noticias(editions, rows, rel_paper, r["inicio_ms"])
    latest_ai = next((e for e in sorted(editions or [], key=lambda e: e["date"], reverse=True) if e.get("tablon")), None)
    pinned = ([(n["texto"], n["firma"], "ia") for n in (latest_ai or {}).get("tablon") or []]
              + [(n["texto"], n["firma"], "") for n in soloq.notas(rows, ph, day, cast)])
    notes = [_nota(t, f, f"{day}{i}", f"{cls} o9") for i, (t, f, cls) in enumerate(pinned)]
    buzon = buzon or []
    with_cards = next((e for e in sorted(editions or [], key=lambda e: e["date"], reverse=True) if e.get("tarjetas") is not None), None)
    cards = (with_cards or {}).get("tarjetas") or []
    fecha_cards = short_date(datetime.fromisoformat(with_cards["date"]).date()) if with_cards else None

    # ---- the carved sign
    estado = {"inscripcion": "Inscripciones abiertas", "finalizado": "Terminado",
              "en_juego": f'En juego · día {(at - (r["inicio_ms"] or at)) // 86400000 + 1}'}[ph]
    cartel = ('<header class="cartel">' + _placa(f'<h1 class="tallado">{_e(title)}</h1><p class="lema">{_e(r["lema"])}</p>'
                                                 f'<span class="estado {ph}">{_e(estado)}</span>', "cartel") + '</header>')

    # ---- the clock and the figures, carved
    if ph == "en_juego" and r["fin_ms"]:
        units = "".join(f'<div><b data-u="{k}">--</b><span>{n}</span></div>' for k, n in (("d", "días"), ("h", "horas"), ("m", "min")))
        reloj = (f'<div style="font-size:18px">Quedan</div><div class="n" id="reloj" data-target="{r["fin_ms"]}">{units}</div>'
                 f'<div class="peq">Acaba el {_e(_date_es(r["fin_ms"] - 1, r).split(", ")[1])}</div>')
    elif ph == "en_juego":
        reloj = (f'<div style="font-size:18px">Día</div><div class="n"><div><b>{(at - r["inicio_ms"]) // 86400000 + 1}</b>'
                 '<span>del reto</span></div></div><div class="peq">Hasta que el jefe diga basta</div>')
    elif ph == "finalizado":
        reloj = (f'<div style="font-size:20px">Se acabó</div><div class="peq">{_e(_date_es(r["fin_ms"] - 1, r))}</div>'
                 '<div class="peq">Ya hay culpables</div>')
    elif r["inicio_ms"]:
        units = "".join(f'<div><b data-u="{k}">--</b><span>{n}</span></div>' for k, n in (("d", "días"), ("h", "horas"), ("m", "min")))
        reloj = (f'<div style="font-size:18px">Empieza en</div><div class="n" id="reloj" data-target="{r["inicio_ms"]}">{units}</div>'
                 f'<div class="peq">{_e(soloq.cuando(r["inicio_ms"], r["tz"]))}</div>')
    else:
        reloj = ('<div style="font-size:20px">Inscripciones abiertas</div><div class="peq">La salida la da el jefe.</div>'
                 '<div class="peq">Hasta entonces, nadie juega.</div>')
    reloj = _placa(f'<div class="reloj tallado">{reloj}</div>', "reloj", "o3")
    lost = (sum(-m["delta"] for m in soloq.movimientos(datos, r, r["inicio_ms"], at) if m.get("delta") and m["delta"] < 0)
            if started else 0)
    cifras = _placa(
        '<div class="cifras tallado">'
        f'<div><b>{len(rows)}</b><span>valientes</span></div><div><b>{fmt_int(sum(x["partidas"] for x in rows))}</b>'
        f'<span>partidas</span></div><div><b>{fmt_num(sum(x["horas"] for x in rows), 0)}</b><span>horas tiradas</span></div>'
        f'<div class="neg"><b>{fmt_int(lost)}</b><span>LP al vacío</span></div></div>', "cifras", "o6")

    # ---- the standings, nailed in the middle
    upd = datos.inscritos.get("actualizado")
    when = f'Última novedad <span data-ts="{upd}"></span>; se mira cada 30 minutos.' if upd else "Se mira cada 30 minutos."
    if started:
        head = ('<div class="cab"><span>#</span><span title="Puestos desde las 07:00">±</span><span>Jugador</span><span>Liga</span>'
                '<span style="text-align:right">Hoy</span><span>Reto</span><span style="text-align:center">Racha</span>'
                '<span class="c-ult" style="text-align:right">Últimas</span></div>')
        body = "".join(_fila(cfg, r, x, ver, rel_paper, ids[x["key"]], news) for x in rows) or (
            '<p class="vacia">Nadie en la tabla. Ni para hacer el ridículo ha venido nadie.</p>')
        sheet = (f'<h2 class="tit">Clasificación oficial</h2><p class="sub">Manda la liga, luego la división y luego los LP. '
                 f'Pulsa en un jugador para ver su ficha. {when}</p>{head}{body}'
                 '<p class="leyenda-fila">± = puestos ganados o perdidos desde las 07:00 · «Hoy» = LP desde las 07:00</p>')
        chart = _big_chart(rows, r, at, ids)
    else:
        sheet = (f'<h2 class="tit">Lista de inscritos</h2><p class="sub">Cuentas de cero, una por cabeza. La clasificación se '
                 f'clava aquí en cuanto suene el pistoletazo. {when}</p>{_lista(rows, rel_paper)}')
        chart = '<p class="vacia">Aquí se dibujarán las subidas y las caídas de cada uno. De momento, papel en blanco.</p>'
    clasif = _perg(sheet, "clasif", "clasif o1")
    grafica = _perg('<h2 class="tit">La gráfica</h2><p class="sub">Los LP de cada jugador desde el pistoletazo, a tinta. '
                    'Pasa por un nombre para seguir su línea; púlsalo para abrir su ficha.</p>' + chart, "grafica", "grafica o2")

    # ---- around it
    rey = busca = ""
    if ranked:
        lead = ranked[0]
        rey = _placa(f'<div class="tallado" style="font-size:16px">{"Campeón del reto" if ph == "finalizado" else "Rey de la Grieta"}'
                     f'</div>{crest(lead["tier"])}<div class="nombre tallado">{_e(lead["nombre"])}</div>'
                     f'<div class="liga tallado">{_e(lead["liga"])}</div><p class="frase">{_e(lead["veredicto"])}</p>',
                     "rey", "rey o4")
    if len(ranked) > 2:
        last = ranked[-1]
        busca = _perg(f'<h3>Se busca</h3><div class="por">por destrozar su propio MMR</div>{crest(last["tier"])}'
                      f'<div class="nm">{_e(last["nombre"])}</div><div class="delito">Visto por última vez en '
                      f'{_e(last["liga"])}, con {last["derrotas"]} derrotas a la espalda.</div>'
                      '<div class="recompensa">Recompensa: 1 LP</div>', "sebusca", "sebusca o5")
    registro = _perg('<h3 class="tit">Registro de la Guardia</h3><p class="sub">Quién sube, quién baja y quién se hunde.</p>'
                     + _registro(moves), "registro", "registro o7")
    muro = (_perg('<h3 class="tit">Muro de la vergüenza</h3><p class="sub">Premios que nadie quiere ganar.</p>' + _muro(awards),
                  "muro", "muro o8") if started else "")
    recortes = [_recorte(n, n["href"], "o9") for n in news[:3]] or [
        _nota("Aquí se clavan los recortes de El Rincón del Feeder sobre el reto. Todavía no ha escrito nada: "
              "ni la prensa os hace caso.", "El repartidor del periódico", "recortes", "o9")]
    left = [reloj, cifras] + notes[0:2] + ([muro] if muro else notes[2:4])
    rest = notes[2:] if muro else notes[4:]
    right = [x for x in (rey, busca) if x] + recortes + [registro]
    grid = (f'<div class="grid"><div class="col izq">{"".join(left)}</div>'
            f'<div class="col centro">{clasif}{grafica}<div class="fila-notas">{"".join(rest[:3])}</div></div>'
            f'<div class="col der">{"".join(right)}</div></div><div class="dispersas">{"".join(rest[3:])}</div>')

    # ---- sign-up sheet, readers' notes and the laws
    configured = bool(cfg.get("supabase_url") and cfg.get("supabase_anon_key"))
    closed = ph == "finalizado"
    tiers = "".join(f'<option value="{t}">{_e(TIER_ES[t])}</option>' for t in TIERS)
    who = "".join(f'<option value="{_e(p["slug"])}">{_e(p["alias"])}</option>' for p in roster)
    off = ('<div class="cerrado">El reto ha terminado. Las inscripciones vuelven en la próxima temporada.</div>' if closed else
           "" if configured else '<div class="cerrado">El formulario se abre en cuanto la web tenga su base de datos. '
           'Mientras, pide al jefe que te apunte a mano.</div>')
    late = ('<p class="sub">El reto ya ha empezado: quien se apunte ahora juega con desventaja, y sus LP cuentan desde '
            'que el robot le vea.</p>' if ph == "en_juego" else "")
    bando = _perg(
        '<h2 class="tit">Bando de inscripción</h2><p class="sub">Se buscan valientes con cuenta recién comprada. '
        f'Una por cabeza. Lo peor que puede pasar es que El Rincón del Feeder escriba sobre ti cada mañana.</p>{late}'
        f'<form id="alta" novalidate>{off}'
        '<div class="fila2"><label>Riot ID de la cuenta del reto<input type="text" name="riot_id" placeholder="Nombre#EUW" '
        'maxlength="23" autocomplete="off"><span class="hint">La cuenta nueva, con el tag después de la #.</span></label>'
        '<label>¿Quién eres?<select name="jugador"><option value="">Elige…</option>'
        f'{who}<option value="fuera">No salgo en el periódico</option></select>'
        '<span class="hint">La cuenta queda asociada a tu nombre del Rincón.</span></label></div>'
        '<div class="fila2"><label>Mote para el tablón<input type="text" name="apodo" maxlength="24" placeholder="El Manco de Zaun">'
        '<span class="hint">Elige bien: va a salir en el periódico.</span></label>'
        f'<label>¿Hasta dónde llegas?<select name="objetivo"><option value="">Prefiero no comprometerme</option>{tiers}</select>'
        '<span class="hint">Lo que digas se usará en tu contra.</span></label></div>'
        '<label>Grito de guerra<input type="text" name="lema" maxlength="120" placeholder="«Este mes salgo de Plata o desinstalo»">'
        '<span class="hint">Opcional. Cuando falles, saldrá en los titulares.</span></label>'
        '<label class="check"><input type="checkbox" name="acepto"> Acepto que el tablón y El Rincón del Feeder se rían de cómo '
        'juego, en público y cada mañana.</label>'
        '<button class="boton" type="submit">Clavar mi nombre</button><p class="msg" id="alta-msg" role="status"></p></form>',
        "bando", "bando")
    rej = [(k, c, why) for k, c, why in rejected if why in ("no_encontrado", "duplicado", "lleno")][:8]
    why_txt = {"no_encontrado": "no existe en Riot (revisa el tag, genio)", "duplicado": "ya tiene otra cuenta en el reto",
               "lleno": "reto completo: lista de espera"}
    rej_html = ("<ul>" + "".join(f'<li>{_e(c["riot_id"])}<span>{_e(why_txt[why])}</span></li>' for _, c, why in rej) + "</ul>"
                if rej else "<p style='margin:0'>Nadie. De momento todo el mundo sabe escribir su Riot ID.</p>")
    lado = _perg(f'<h3 class="tit">En el vestuario</h3><div id="vestuario" class="lado"><p style="margin:0">'
                 f'{"Mirando quién espera…" if configured else "Sin base de datos todavía."}</p></div>'
                 f'<h3 class="tit" style="margin-top:16px">Rechazados</h3><div class="lado">{rej_html}</div>', "lado", "lado")
    clava = _perg(
        '<h3 class="tit">Clava tu nota</h3><p class="sub">Para el que va primero, para el que se hunde o para tu jungla. '
        'Contra cómo juegan, no contra quién son.</p><form id="clava" class="clava" novalidate>'
        '<textarea name="texto" maxlength="180" placeholder="Lo que tengas que decir…"></textarea>'
        '<input type="text" name="nombre" maxlength="40" placeholder="Firma">'
        '<button class="boton" type="submit">Clavar</button><p class="msg" id="clava-msg" role="status"></p></form>',
        "clava", "clava")
    rules = [
        ("Cuentas de cero", "Cada uno juega con una cuenta nueva y sin clasificar, comprada para el reto. Una por cabeza, "
                            "asociada a su nombre del Rincón."),
        ("El pistoletazo", "Lo da el jefe. Lo que se juegue antes no cuenta, aunque se apunta para la burla."),
        ("La cola", "Solo cuenta Solo/Dúo en EUW. Flex, normales y ARAM no existen para el reto. Las remakes tampoco."),
        ("Cómo se gana", "Manda quien esté más arriba al acabar: liga, luego división, luego LP. A igualdad, quien "
                         "haya necesitado menos partidas."),
        ("Mínimo de partidas", f'Para optar al trono hay que jugar al menos {r["min_partidas"]} partidas del reto.'),
        ("Juego limpio", "Nada de pagar a nadie para que te suba la cuenta. Además de prohibido, da una vergüenza ajena que flipas."),
    ]
    if r.get("premio"):
        rules.append(("Premio", r["premio"]))
    if r.get("castigo"):
        rules.append(("Castigo", r["castigo"]))
    reglas = _perg('<h3 class="tit">Las leyes del tablón</h3><ol>'
                   + "".join(f'<li><b>{_e(k)}.</b> {_e(v)}</li>' for k, v in rules) + '</ol>'
                   '<p class="sub" style="margin:10px 0 0">Datos de la API oficial de Riot, cada 30 minutos.</p>', "reglas", "reglas")
    lis = "".join(f'<li><span class="sello-s {_e(b["estado"])}">{_e(b["sello"])}</span>{_e(b["texto"])}'
                  f'<small>{_e(b["nombre"])}' + (f' · {_e(b["motivo"])}' if b.get("motivo") else "") + '</small></li>'
                  for b in buzon[:12])
    buzon_html = _perg(
        '<h3 class="tit">Buzón de sugerencias</h3><p class="sub">¿Qué quieres ver en el tablón? Una tarjeta, un dato, un '
        'ranking… Cada mañana la redacción las revisa: lo que se pueda hacer con los datos del reto, sale clavado; lo raro, '
        'lo pesado o lo que no pinte nada aquí, se le consulta al jefe.</p>'
        '<form id="buzon" class="clava" novalidate><textarea name="texto" maxlength="400" '
        'placeholder="Ej.: quién muere más por partida, el campeón maldito del reto, quién juega más de madrugada…"></textarea>'
        '<input type="text" name="nombre" maxlength="40" placeholder="Firma"><button class="boton" type="submit">Al buzón</button>'
        f'<p class="msg" id="buzon-msg" role="status"></p></form><ul class="lista-s" id="buzon-lista">{lis}</ul>', "buzon", "buzon")
    zona = ""
    if cards:
        zona = ('<div class="tarjetas-zona"><div class="cartelito">' + _placa(
            '<div class="tallado" style="font-size:22px">Lo que pidió la gente</div>', "pidio") + '</div><div class="tarjetas">'
            + "".join(_tarjeta(c, buzon, fecha_cards) for c in cards) + '</div></div>')
    bajo = (f'{zona}<div class="bajo">{bando}<div class="col">{lado}{clava}</div><div class="col">{buzon_html}{reglas}</div></div>'
            '<div class="notas-lectores" id="notas-lectores" aria-live="polite"></div>')

    waiting = [b for b in buzon if b["estado"] == "permiso"]
    permisos = ('<h4>Sugerencias que esperan tu permiso</h4>' + "".join(
        f'<div class="permiso" data-id="{b["id"]}"><p>«{_e(b["texto"])}»</p><p class="por">{_e(b["nombre"])} · la redacción '
        f'pregunta: {_e(b.get("motivo") or "")}</p><input type="text" maxlength="200" placeholder="Nota para la redacción (opcional)">'
        '<button class="boton" type="button" data-decision="aprobada">Aprobar</button>'
        '<button class="boton sec" type="button" data-decision="rechazada">Rechazar</button></div>' for b in waiting)
        + '<p class="msg" id="permiso-msg" role="status"></p>') if waiting else ""
    jefe = ('<dialog class="jefe-dialog" id="jefe-dialog">' + _perg(
        '<h3 class="tit">El pistoletazo</h3><p class="sub">Solo para el jefe. Fecha y hora de salida y, si quieres, de final '
        f'(si no, dura {r.get("duracion_dias") or "hasta nueva orden"}{" días" if r.get("duracion_dias") else ""}). '
        'Se puede volver a poner para retrasarlo o para acabarlo antes.</p>'
        '<form id="jefe" novalidate><label>Contraseña<input type="password" name="clave" autocomplete="off"></label>'
        '<label>Salida<input type="datetime-local" name="inicio" required></label>'
        '<label>Final (opcional)<input type="datetime-local" name="fin"></label>'
        '<div class="botones"><button class="boton" type="submit">Dar el pistoletazo</button>'
        '<button class="boton sec" type="button" id="jefe-cerrar">Cerrar</button></div>'
        '<p class="msg" id="jefe-msg" role="status"></p></form>' + permisos, "jefe") + '</dialog>')
    feeder = json.dumps({"url": cfg.get("supabase_url", "") if not closed else "", "key": cfg.get("supabase_anon_key", ""),
                         "fase": ph, "control": datos.inscritos.get("control_id", 0), "sugerencias": [b["id"] for b in buzon],
                         "conocidos": sorted({x["key"] for x in rows} | {k for k, _, _ in rejected}),
                         "actualizado": upd}, ensure_ascii=False)
    desc = f'{r["lema"]}. La clasificación clavada en el tablón, la gráfica de LP y las notas de la vergüenza.'
    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)} · {_e(site_title)}</title>
<meta name="description" content="{_e(desc)}">
<meta property="og:title" content="{_e(title)} · {_e(site_title)}">
<meta property="og:description" content="{_e(desc)}">
<meta property="og:type" content="website">
<meta name="theme-color" content="#1b1310">
{FONTS}
<link rel="stylesheet" href="soloq.css?v={ASSET_VERSION}">
</head>
<body>
{_gradients()}
<nav class="volver"><a href="{rel_paper}index.html">← Volver a El Rincón del Feeder</a><a href="#" class="jefe" id="jefe-btn" role="button" title="Solo para el jefe">🔒 El pistoletazo</a></nav>
<main class="marco">
<i class="perno" style="left:8px;top:8px"></i><i class="perno" style="right:8px;top:8px"></i>
<i class="perno" style="left:8px;bottom:8px"></i><i class="perno" style="right:8px;bottom:8px"></i>
<div class="tablon">
{cartel}
{grid}
{bajo}
</div>
</main>
<footer><p>{_e(LEGAL.format(name=title, site=site_title))}</p>
<p><a href="{rel_paper}index.html">Leer El Rincón del Feeder</a>, el periódico que cuenta cada mañana lo que pasa en este tablón.</p></footer>
{jefe}
<div class="aviso" id="aviso" role="status"><span>Alguien ha movido el tablón</span><button class="boton" type="button">Mirar</button></div>
<script>window.SOLOQ={feeder};</script>
<script src="soloq.js?v={ASSET_VERSION}" defer></script>
</body>
</html>
"""
    public = {"nombre": title, "fase": ph, "actualizado": upd, "clasificacion": [
        {k: x[k] for k in ("puesto", "nombre", "apodo", "riot_id", "liga", "lp_hoy", "partidas", "victorias", "derrotas", "racha")}
        for x in rows]}
    return html, public


def build(cfg, datos, out_dir, now_ms, roster=(), ver=None, rel_paper="../", editions=(), cast=(), buzon=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    html, public = render(cfg, datos, now_ms, roster, ver, rel_paper, editions, cast, buzon)
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "soloq.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (out / "soloq.js").write_text(JS, encoding="utf-8")
    (out / "datos.json").write_text(json.dumps(public, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out
