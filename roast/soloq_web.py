"""The SoloQ Challenge website (docs/soloq/): a Riot-style leaderboard, the sign-up form, the day's
movements, the wall of shame and the rules. Static HTML built by the robot; the browser only signs
people up (Supabase), counts down and notices when the table changes."""
import hashlib
import json
import urllib.parse
from datetime import datetime
from html import escape
from pathlib import Path

from . import soloq
from .rangos import TIER_ES, TIERS
from .util import fmt_int, fmt_num, long_date

PLATFORM_OPGG = {"euw1": "euw", "eun1": "eune", "na1": "na", "kr": "kr", "br1": "br", "la1": "lan", "la2": "las",
                 "oc1": "oce", "tr1": "tr", "ru": "ru", "jp1": "jp"}
TIER_COLORS = {  # light, dark (crest gradient)
    "IRON": ("#8a807c", "#3b3330"), "BRONZE": ("#c98a5e", "#5e3a24"), "SILVER": ("#d5dee5", "#6f7f8b"),
    "GOLD": ("#f5d68a", "#a8782b"), "PLATINUM": ("#8fe3d6", "#2a7d78"), "EMERALD": ("#5fe8aa", "#138a55"),
    "DIAMOND": ("#b9c7ff", "#4a5bd1"), "MASTER": ("#dc9cf7", "#7b2fb3"), "GRANDMASTER": ("#ff8a7a", "#a31d24"),
    "CHALLENGER": ("#fff3c4", "#3fa7ff"), "NONE": ("#6b6a66", "#1e2328"),
}
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700'
         '&family=Barlow:wght@400;500;600&family=Cinzel:wght@600;700;800&display=swap" rel="stylesheet">')
LEGAL = ("{name} es un juego entre amigos de {site} y no está avalado por Riot Games ni refleja las opiniones de "
         "Riot Games ni de nadie implicado oficialmente en la producción o gestión de League of Legends. League of "
         "Legends y Riot Games son marcas registradas de Riot Games, Inc. Datos de la API oficial de Riot; "
         "la mala leche es nuestra.")

CSS = r"""
:root{
  color-scheme:dark;
  --bg0:#010a13; --bg1:#0a1428; --bg2:#091428; --panel:#0b1a2e; --panel2:#0e2036; --line:#1e2d3d; --line2:#2b3c4f;
  --gold1:#f0e6d2; --gold2:#c8aa6e; --gold3:#c89b3c; --gold4:#785a28; --gold5:#463714;
  --blue1:#cdfafa; --blue2:#0ac8b9; --blue3:#0397ab; --blue4:#005a82;
  --grey1:#a09b8c; --grey2:#7c7a72; --grey3:#3c3c41;
  --win:#0acbe6; --win-bg:rgba(10,203,230,.12); --loss:#e84057; --loss-bg:rgba(232,64,87,.12);
  --up:#38d39f; --down:#e84057;
  --display:"Cinzel","Times New Roman",serif; --cond:"Barlow Condensed","Arial Narrow",sans-serif;
  --body:"Barlow","Segoe UI",system-ui,sans-serif;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg0);color:var(--gold1);font:16px/1.5 var(--body);overflow-x:hidden;
  background-image:radial-gradient(1200px 600px at 75% -10%,rgba(0,90,130,.35),transparent 60%),
    radial-gradient(900px 500px at -10% 30%,rgba(200,155,60,.08),transparent 60%),
    linear-gradient(180deg,#010a13 0%,#04101e 40%,#010a13 100%);background-attachment:fixed}
a{color:var(--gold2);text-decoration:none}
a:hover{color:var(--gold1)}
img{max-width:100%}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.wrap{max-width:1240px;margin:0 auto;padding:0 20px}

/* ---------------------------------------------------------------- top bar */
.top{position:sticky;top:0;z-index:20;background:rgba(1,10,19,.88);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--gold5);box-shadow:0 1px 0 rgba(200,170,110,.08)}
.top .wrap{display:flex;align-items:center;gap:22px;height:64px}
.logo{display:flex;align-items:center;gap:10px;color:var(--gold1);font:800 18px/1 var(--display);letter-spacing:.08em}
.logo svg{width:34px;height:34px;flex:none}
.logo small{display:block;font:600 10px/1 var(--cond);letter-spacing:.32em;color:var(--gold3);margin-top:4px}
.nav{display:flex;gap:4px;margin-left:auto;align-items:center}
.nav a{font:600 13px/1 var(--cond);letter-spacing:.14em;text-transform:uppercase;color:var(--grey1);padding:10px 12px;
  border-bottom:2px solid transparent}
.nav a:hover{color:var(--gold1);border-bottom-color:var(--gold3)}
.nav a.cta{color:var(--bg0);background:linear-gradient(180deg,#e6c983,#c89b3c);border:1px solid #f0e6d2;padding:9px 14px;
  margin-left:8px;box-shadow:0 0 18px rgba(200,155,60,.25)}
.nav a.cta:hover{filter:brightness(1.08);color:var(--bg0)}
.nav a.ext{color:var(--blue2)}
@media (max-width:900px){.nav a:not(.cta):not(.ext){display:none}.top .wrap{gap:10px}}
@media (max-width:520px){.nav a.ext{display:none}.logo{font-size:15px}}

/* ---------------------------------------------------------------- hero */
.hero{position:relative;padding:56px 0 40px;overflow:hidden}
.hero:before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.5;
  background:repeating-linear-gradient(115deg,transparent 0 46px,rgba(200,170,110,.035) 46px 47px)}
.hero .wrap{position:relative;display:grid;grid-template-columns:1.25fr .9fr;gap:40px;align-items:center}
.kicker{font:600 13px/1 var(--cond);letter-spacing:.3em;text-transform:uppercase;color:var(--blue2)}
.hero h1{margin:14px 0 10px;font:800 clamp(40px,7vw,84px)/.95 var(--display);letter-spacing:.02em;
  background:linear-gradient(180deg,#f0e6d2 0%,#e2c785 45%,#a8782b 100%);-webkit-background-clip:text;background-clip:text;
  color:transparent;filter:drop-shadow(0 4px 24px rgba(200,155,60,.25))}
.hero .lema{font-size:19px;color:var(--grey1);max-width:560px;margin:0 0 22px}
.estado{display:inline-flex;align-items:center;gap:8px;font:700 12px/1 var(--cond);letter-spacing:.22em;text-transform:uppercase;
  padding:7px 12px;border:1px solid var(--line2);background:rgba(10,20,40,.7)}
.estado i{width:8px;height:8px;border-radius:50%;background:var(--blue2);box-shadow:0 0 0 0 rgba(10,200,185,.7);animation:pulse 2s infinite}
.estado.previa i{background:var(--gold3);animation:none}.estado.finalizado i{background:var(--loss);animation:none}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(10,200,185,.6)}70%{box-shadow:0 0 0 10px rgba(10,200,185,0)}100%{box-shadow:0 0 0 0 rgba(10,200,185,0)}}
.countdown{display:flex;gap:10px;margin:22px 0 26px;flex-wrap:wrap}
.countdown .u{position:relative;min-width:84px;padding:12px 10px 10px;text-align:center;background:linear-gradient(180deg,#0e2036,#091428);
  border:1px solid var(--gold4)}
.countdown .u:before,.countdown .u:after{content:"";position:absolute;width:8px;height:8px;border:2px solid var(--gold2)}
.countdown .u:before{top:-2px;left:-2px;border-right:0;border-bottom:0}.countdown .u:after{bottom:-2px;right:-2px;border-left:0;border-top:0}
.countdown b{display:block;font:700 38px/1 var(--cond);color:var(--gold1);font-variant-numeric:tabular-nums}
.countdown span{font:600 11px/1 var(--cond);letter-spacing:.24em;color:var(--grey1);text-transform:uppercase}
.countdown-label{font:600 12px/1 var(--cond);letter-spacing:.2em;color:var(--grey1);text-transform:uppercase;margin-top:22px}
.btns{display:flex;gap:12px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:46px;padding:0 26px;cursor:pointer;
  font:700 15px/1 var(--cond);letter-spacing:.16em;text-transform:uppercase;border:2px solid var(--gold3);color:var(--gold1);
  background:linear-gradient(180deg,#1e2328,#0a1428);transition:filter .15s, box-shadow .15s}
.btn:hover{color:#fff;box-shadow:0 0 22px rgba(200,155,60,.35),inset 0 0 12px rgba(200,155,60,.25)}
.btn.primary{border-color:var(--blue2);color:var(--blue1);background:linear-gradient(180deg,#0b3a4a,#0a1428);
  box-shadow:inset 0 0 14px rgba(10,200,185,.25)}
.btn.primary:hover{box-shadow:0 0 24px rgba(10,200,185,.45),inset 0 0 18px rgba(10,200,185,.35)}
.btn[disabled]{opacity:.45;cursor:not-allowed;filter:grayscale(.6)}

.rey{position:relative;padding:28px 26px 24px;background:linear-gradient(160deg,rgba(14,32,54,.95),rgba(1,10,19,.95));
  border:1px solid var(--gold4);box-shadow:0 30px 80px rgba(0,0,0,.55),inset 0 0 0 1px rgba(200,170,110,.08);text-align:center}
.rey:before{content:"";position:absolute;inset:6px;border:1px solid rgba(200,170,110,.15);pointer-events:none}
.rey .titulo{font:700 12px/1 var(--cond);letter-spacing:.34em;color:var(--gold3);text-transform:uppercase}
.rey .crest{width:150px;height:150px;margin:12px auto 4px;display:block;filter:drop-shadow(0 10px 30px rgba(0,0,0,.6))}
.rey .nombre{font:800 30px/1.1 var(--display);color:var(--gold1);margin:6px 0 2px;word-break:break-word}
.rey .rid{font:500 14px/1 var(--cond);color:var(--grey2);letter-spacing:.06em}
.rey .liga{font:700 22px/1.2 var(--cond);letter-spacing:.06em;margin-top:12px;text-transform:uppercase}
.rey .mini{display:flex;justify-content:center;gap:18px;margin-top:12px;font:600 14px/1 var(--cond);color:var(--grey1);letter-spacing:.06em}
.rey .mini b{color:var(--gold1);font-size:18px}
.rey .frase{margin:16px 0 0;font-style:italic;color:var(--grey1);font-size:14px}
@media (max-width:900px){.hero .wrap{grid-template-columns:1fr}.hero{padding-top:36px}}
@media (max-width:520px){.countdown{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.countdown .u{min-width:0;padding:10px 4px 8px}
  .countdown b{font-size:30px}.countdown span{font-size:10px;letter-spacing:.14em}.estado{font-size:11px;letter-spacing:.14em}}

/* ---------------------------------------------------------------- stats strip */
.strip{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line2);background:rgba(9,20,40,.75);margin:0 0 46px}
.strip div{padding:18px 20px;border-right:1px solid var(--line)}
.strip div:last-child{border-right:0}
.strip b{display:block;font:700 34px/1 var(--cond);color:var(--gold1);font-variant-numeric:tabular-nums}
.strip span{font:600 12px/1.3 var(--cond);letter-spacing:.18em;text-transform:uppercase;color:var(--grey1)}
.strip .neg b{color:var(--loss)}
@media (max-width:720px){.strip{grid-template-columns:1fr 1fr}.strip div:nth-child(2){border-right:0}
  .strip div:nth-child(-n+2){border-bottom:1px solid var(--line)}}

/* ---------------------------------------------------------------- section heads */
.sec{margin:0 0 54px;scroll-margin-top:80px}
.sec-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:18px;
  border-bottom:1px solid var(--gold5);padding-bottom:12px}
.sec-head h2{margin:0;font:700 clamp(24px,3.4vw,34px)/1 var(--display);color:var(--gold1);letter-spacing:.04em}
.sec-head p{margin:6px 0 0;color:var(--grey1);font-size:15px}
.sec-head .meta{font:600 12px/1.4 var(--cond);letter-spacing:.14em;text-transform:uppercase;color:var(--grey2);text-align:right}
@media (max-width:640px){.sec-head{flex-direction:column;align-items:flex-start}.sec-head .meta{text-align:left}}

/* ---------------------------------------------------------------- podium */
.podio{display:grid;grid-template-columns:1fr 1.15fr 1fr;gap:16px;align-items:end;margin-bottom:26px}
.podio .p{position:relative;text-align:center;padding:22px 16px 18px;background:linear-gradient(180deg,rgba(14,32,54,.9),rgba(9,20,40,.9));
  border:1px solid var(--line2)}
.podio .p.n1{border-color:var(--gold3);padding-top:30px;box-shadow:0 0 40px rgba(200,155,60,.15)}
.podio .num{position:absolute;top:-14px;left:50%;transform:translateX(-50%);width:30px;height:30px;line-height:28px;
  font:700 16px var(--cond);background:var(--bg1);border:1px solid var(--gold3);color:var(--gold2);rotate:45deg}
.podio .num span{display:inline-block;rotate:-45deg}
.podio .crest{width:84px;height:84px}
.podio .n1 .crest{width:110px;height:110px}
.podio .nm{font:700 20px/1.15 var(--display);margin-top:6px;word-break:break-word}
.podio .lg{font:600 15px/1.3 var(--cond);letter-spacing:.08em;text-transform:uppercase;margin-top:4px}
.podio .wl{font:500 13px/1 var(--cond);color:var(--grey1);margin-top:8px;letter-spacing:.06em}
@media (max-width:640px){.podio{display:none}}

/* ---------------------------------------------------------------- leaderboard */
.tabla{border:1px solid var(--line2);background:rgba(9,20,40,.82)}
.tabla .cab,.fila>summary{display:grid;grid-template-columns:46px 44px minmax(190px,2.1fr) minmax(170px,1.5fr) 74px minmax(132px,1fr) 66px 140px;
  align-items:center;gap:10px;padding:0 16px}
.tabla .cab{height:40px;font:600 11px/1 var(--cond);letter-spacing:.2em;text-transform:uppercase;color:var(--grey2);
  border-bottom:1px solid var(--line2);background:rgba(1,10,19,.6)}
.fila{border-bottom:1px solid var(--line)}
.fila:last-child{border-bottom:0}
.fila>summary{list-style:none;cursor:pointer;min-height:76px;padding-top:10px;padding-bottom:10px;transition:background .15s}
.fila>summary::-webkit-details-marker{display:none}
.fila>summary:hover{background:rgba(200,170,110,.05)}
.fila[open]>summary{background:rgba(200,170,110,.07)}
.fila.yo>summary{box-shadow:inset 3px 0 0 var(--blue2);background:rgba(10,200,185,.06)}
.fila.top1>summary{box-shadow:inset 3px 0 0 var(--gold3)}
.pos{font:700 26px/1 var(--cond);color:var(--grey1);text-align:center;font-variant-numeric:tabular-nums}
.top1 .pos{color:var(--gold2)}.top2 .pos,.top3 .pos{color:var(--gold1)}
.delta{font:700 13px/1 var(--cond);text-align:center;letter-spacing:.04em}
.delta.up{color:var(--up)}.delta.down{color:var(--down)}.delta.eq{color:var(--grey3)}.delta.new{color:var(--blue2);font-size:10px;letter-spacing:.14em}
.inv{display:flex;align-items:center;gap:12px;min-width:0}
.pi{position:relative;flex:none;width:48px;height:48px;border-radius:50%;border:2px solid var(--gold4);background:#1e2328;
  display:grid;place-items:center;font:700 15px var(--cond);color:var(--gold2)}
.pi:before{content:attr(data-i)}
.pi img{position:absolute;inset:0;width:100%;height:100%;border-radius:50%;object-fit:cover}
.pi em{position:absolute;bottom:-7px;left:50%;transform:translateX(-50%);font:600 10px/1 var(--cond);font-style:normal;padding:2px 5px;
  background:var(--bg0);border:1px solid var(--gold4);color:var(--gold2);letter-spacing:.04em}
.inv .t{min-width:0}
.inv .nm{font:700 17px/1.15 var(--body);color:var(--gold1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.inv .nm .tu{font:700 10px/1 var(--cond);letter-spacing:.16em;color:var(--bg0);background:var(--blue2);padding:2px 5px;margin-left:6px;vertical-align:2px}
.inv .rid{font:500 13px/1.2 var(--cond);color:var(--grey2);letter-spacing:.04em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.inv .ver{font-size:13px;line-height:1.3;color:var(--grey1);font-style:italic;margin-top:3px;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden}
.lg{display:flex;align-items:center;gap:10px;min-width:0}
.lg .crest{width:44px;height:44px;flex:none}
.lg b{display:block;font:700 16px/1.1 var(--cond);letter-spacing:.06em;text-transform:uppercase}
.lg span{font:600 14px/1.2 var(--cond);color:var(--grey1);letter-spacing:.04em}
.lg .nq{font-size:11px;color:var(--gold3);letter-spacing:.12em;text-transform:uppercase}
.hoy{font:700 16px/1 var(--cond);text-align:right;font-variant-numeric:tabular-nums}
.hoy small{display:block;font:500 11px/1.4 var(--cond);color:var(--grey2);letter-spacing:.06em}
.up{color:var(--up)}.down{color:var(--down)}.zero{color:var(--grey2)}
.wr .n{display:flex;justify-content:space-between;font:600 14px/1 var(--cond);letter-spacing:.04em;color:var(--grey1)}
.wr .n b{color:var(--gold1)}
.bar{height:6px;margin-top:7px;background:var(--loss-bg);border:1px solid rgba(232,64,87,.35);position:relative;overflow:hidden}
.bar i{position:absolute;inset:0 auto 0 0;background:linear-gradient(90deg,#0397ab,#0acbe6)}
.racha{font:700 15px/1 var(--cond);text-align:center;letter-spacing:.04em}
.racha.w{color:var(--win)}.racha.l{color:var(--loss)}
.ult{display:flex;gap:4px;justify-content:flex-end}
.ult i{width:24px;height:24px;display:grid;place-items:center;font:700 11px/1 var(--cond);font-style:normal}
.ult i.w{background:var(--win-bg);color:var(--win);border:1px solid rgba(10,203,230,.4)}
.ult i.l{background:var(--loss-bg);color:var(--loss);border:1px solid rgba(232,64,87,.4)}
.ult .none{font:500 12px var(--cond);color:var(--grey2);letter-spacing:.08em}
.vacia{padding:46px 20px;text-align:center;color:var(--grey1)}
.vacia b{display:block;font:700 22px/1.3 var(--display);color:var(--gold1);margin-bottom:8px}

@media (max-width:1060px){
  .tabla .cab,.fila>summary{grid-template-columns:40px 36px minmax(160px,2fr) minmax(150px,1.4fr) 64px minmax(110px,1fr) 56px}
  .c-ult{display:none!important}
}
@media (max-width:760px){
  .tabla .cab{display:none}
  .fila>summary{grid-template-columns:34px 1fr auto;grid-template-areas:"pos inv hoy" "dl lg lg" ". wr racha";row-gap:10px;padding:14px 12px}
  .fila>summary .pos{grid-area:pos}.fila>summary .delta{grid-area:dl}.fila>summary .inv{grid-area:inv}
  .fila>summary .lg{grid-area:lg}.fila>summary .hoy{grid-area:hoy}.fila>summary .wr{grid-area:wr}.fila>summary .racha{grid-area:racha}
  .pos{font-size:22px}
}

/* ---------------------------------------------------------------- row detail */
.det{padding:6px 16px 22px 106px;display:grid;grid-template-columns:1.35fr 1fr;gap:22px}
@media (max-width:900px){.det{padding:4px 12px 18px;grid-template-columns:1fr}}
.panel{background:rgba(1,10,19,.55);border:1px solid var(--line);padding:14px 16px}
.panel h4{margin:0 0 10px;font:700 12px/1 var(--cond);letter-spacing:.24em;text-transform:uppercase;color:var(--gold3)}
.chart{width:100%;height:auto;display:block}
.chart .grid line{stroke:rgba(160,155,140,.13);stroke-width:1}
.chart .grid text{fill:var(--grey2);font:600 10px var(--cond);letter-spacing:.06em}
.chart .area{fill:url(#lp-area)}
.chart .line{fill:none;stroke:var(--gold2);stroke-width:2.2;stroke-linejoin:round;stroke-linecap:round}
.chart .dot{fill:var(--gold1);stroke:var(--bg0);stroke-width:2}
.kv{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}
.kv div{background:rgba(14,32,54,.6);border:1px solid var(--line);padding:9px 10px}
.kv>div>span{display:block;font:600 10px/1.2 var(--cond);letter-spacing:.18em;text-transform:uppercase;color:var(--grey2)}
.kv b{font:700 16px/1.3 var(--cond);letter-spacing:.03em;color:var(--gold1)}
.obj .track{height:10px;background:rgba(30,35,40,.9);border:1px solid var(--line2);margin:10px 0 6px;position:relative}
.obj .track i{position:absolute;inset:0 auto 0 0;background:linear-gradient(90deg,var(--gold4),var(--gold2))}
.obj p{margin:0;font-size:14px;color:var(--grey1)}
.champs{display:flex;flex-direction:column;gap:8px}
.champ{display:flex;align-items:center;gap:10px;font:600 14px/1.2 var(--cond);letter-spacing:.03em}
.champ .wrc{margin-left:auto;color:var(--grey1)}
.ch{position:relative;flex:none;width:34px;height:34px;border:1px solid var(--gold4);background:#1e2328;display:grid;place-items:center;
  font:700 12px var(--cond);color:var(--gold2)}
.ch:before{content:attr(data-i)}
.ch img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.games{display:flex;flex-wrap:wrap;gap:6px}
.game{display:flex;align-items:center;gap:7px;padding:4px 8px 4px 4px;font:600 13px/1 var(--cond);letter-spacing:.03em;border:1px solid}
.game.w{border-color:rgba(10,203,230,.35);background:var(--win-bg)}.game.l{border-color:rgba(232,64,87,.35);background:var(--loss-bg)}
.game .ch{width:26px;height:26px;font-size:10px}
.lema{margin:12px 0 0;padding-left:12px;border-left:2px solid var(--gold4);font-style:italic;color:var(--grey1)}
.enl{display:flex;gap:14px;flex-wrap:wrap;margin-top:14px;font:600 13px/1 var(--cond);letter-spacing:.14em;text-transform:uppercase}

/* ---------------------------------------------------------------- feed + shame */
.dos{display:grid;grid-template-columns:1fr 1.1fr;gap:26px}
@media (max-width:900px){.dos{grid-template-columns:1fr}}
.feed{list-style:none;margin:0;padding:0;border:1px solid var(--line2);background:rgba(9,20,40,.82)}
.feed li{display:grid;grid-template-columns:34px 1fr auto;gap:12px;align-items:center;padding:12px 14px;border-bottom:1px solid var(--line)}
.feed li:last-child{border-bottom:0}
.feed .ic{width:30px;height:30px;display:grid;place-items:center;font:700 14px var(--cond);border:1px solid var(--line2);rotate:45deg}
.feed .ic span{rotate:-45deg}
.feed .ascenso .ic,.feed .sube .ic,.feed .liga .ic{color:var(--up);border-color:rgba(56,211,159,.45)}
.feed .descenso .ic,.feed .baja .ic{color:var(--down);border-color:rgba(232,64,87,.45)}
.feed .inscripcion .ic{color:var(--blue2);border-color:rgba(10,200,185,.45)}
.feed .q{font:700 15px/1.2 var(--body);color:var(--gold1)}
.feed .q small{font:600 12px var(--cond);color:var(--grey2);letter-spacing:.08em;margin-left:6px}
.feed .x{font-size:14px;color:var(--grey1);line-height:1.35}
.feed .lp{font:700 15px/1 var(--cond);text-align:right;white-space:nowrap}
.feed .lp small{display:block;font:500 11px var(--cond);color:var(--grey2);margin-top:3px;letter-spacing:.06em}
.muro{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:520px){.muro{grid-template-columns:1fr}}
.premio{position:relative;padding:16px 16px 14px;background:linear-gradient(160deg,rgba(14,32,54,.95),rgba(9,20,40,.95));border:1px solid var(--line2)}
.premio:after{content:"";position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--gold3),transparent)}
.premio .tt{font:700 16px/1.2 var(--display);color:var(--gold2)}
.premio .cr{font:600 10px/1.3 var(--cond);letter-spacing:.18em;text-transform:uppercase;color:var(--grey2);margin-top:4px}
.premio .who{font:700 20px/1.2 var(--body);color:var(--gold1);margin:10px 0 4px;word-break:break-word}
.premio p{margin:0;font-size:14px;color:var(--grey1);font-style:italic;line-height:1.4}

/* ---------------------------------------------------------------- sign-up */
.alta{display:grid;grid-template-columns:1.2fr .8fr;gap:26px}
@media (max-width:900px){.alta{grid-template-columns:1fr}}
.form{position:relative;padding:26px;background:linear-gradient(160deg,rgba(14,32,54,.95),rgba(1,10,19,.95));border:1px solid var(--gold4)}
.form:before{content:"";position:absolute;inset:6px;border:1px solid rgba(200,170,110,.12);pointer-events:none}
.form .row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:600px){.form .row{grid-template-columns:1fr}}
.form label{display:block;margin-bottom:14px;font:600 12px/1 var(--cond);letter-spacing:.2em;text-transform:uppercase;color:var(--gold3)}
.form input[type=text],.form select{display:block;width:100%;margin-top:8px;height:46px;padding:0 14px;background:#010a13;color:var(--gold1);
  border:1px solid var(--line2);font:500 16px var(--body);letter-spacing:0;text-transform:none;border-radius:0;appearance:none}
.form select{background-image:linear-gradient(45deg,transparent 50%,var(--gold2) 50%),linear-gradient(135deg,var(--gold2) 50%,transparent 50%);
  background-position:calc(100% - 20px) 20px,calc(100% - 14px) 20px;background-size:6px 6px;background-repeat:no-repeat}
.form input:focus,.form select:focus{outline:none;border-color:var(--gold2);box-shadow:0 0 0 3px rgba(200,155,60,.18)}
.form .hint{display:block;margin-top:6px;font:400 13px/1.35 var(--body);letter-spacing:0;text-transform:none;color:var(--grey2)}
.form .check{display:flex;gap:10px;align-items:flex-start;font:400 14px/1.4 var(--body);letter-spacing:0;text-transform:none;color:var(--grey1)}
.form .check input{margin-top:3px;accent-color:var(--gold3);width:16px;height:16px}
.form .msg{min-height:22px;margin:14px 0 0;font-size:15px}
.form .msg.ok{color:var(--blue2)}.form .msg.err{color:var(--loss)}
.form .off{padding:12px 14px;border:1px dashed var(--gold4);color:var(--grey1);font-size:14px;margin-bottom:16px}
.lado .panel{margin-bottom:16px}
.lado ul{list-style:none;margin:0;padding:0}
.lado li{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-bottom:1px solid var(--line);font-size:14px}
.lado li:last-child{border-bottom:0}
.lado li span{color:var(--grey2);font:500 13px var(--cond);letter-spacing:.04em}
.lado p{margin:0;color:var(--grey1);font-size:14px}

/* ---------------------------------------------------------------- rules */
.reglas{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media (max-width:900px){.reglas{grid-template-columns:1fr 1fr}}@media (max-width:560px){.reglas{grid-template-columns:1fr}}
.regla{padding:18px;background:rgba(9,20,40,.82);border:1px solid var(--line2)}
.regla b{display:block;font:700 13px/1.2 var(--cond);letter-spacing:.2em;text-transform:uppercase;color:var(--gold2);margin-bottom:8px}
.regla p{margin:0;color:var(--grey1);font-size:15px}
.regla.premio-r{border-color:var(--gold4)}.regla.castigo-r{border-color:rgba(232,64,87,.4)}

/* ---------------------------------------------------------------- footer + toast */
footer{border-top:1px solid var(--gold5);padding:26px 0 40px;color:var(--grey2);font-size:13px;margin-top:20px}
footer .wrap{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}
footer p{margin:0;max-width:760px}
.toast{position:fixed;left:50%;bottom:22px;transform:translate(-50%,140%);z-index:30;opacity:0;pointer-events:none;display:flex;gap:14px;align-items:center;
  padding:12px 14px 12px 18px;background:#0a1428;border:1px solid var(--blue2);box-shadow:0 10px 40px rgba(0,0,0,.6);transition:transform .3s}
.toast.on{transform:translate(-50%,0);opacity:1;pointer-events:auto}
.toast span{font:600 15px var(--cond);letter-spacing:.08em}
.toast .btn{min-height:36px;padding:0 14px;font-size:13px}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}html{scroll-behavior:auto}}
"""

JS = r"""(function(){
var S=window.SOLOQ||{};
function $(s,r){return (r||document).querySelector(s)}
function $$(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))}
function store(k,v){try{if(v===undefined)return localStorage.getItem(k);if(v===null)localStorage.removeItem(k);else localStorage.setItem(k,v)}catch(e){return null}}
function esc(t){return String(t==null?"":t).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}

// countdown
var cd=$("#countdown");
if(cd){var target=+cd.getAttribute("data-target");
  var tick=function(){var s=Math.max(0,Math.floor((target-Date.now())/1000));
    var v={d:Math.floor(s/86400),h:Math.floor(s%86400/3600),m:Math.floor(s%3600/60),s:s%60};
    for(var k in v){var el=cd.querySelector('[data-u="'+k+'"]');if(el)el.textContent=(k==="d"?v[k]:("0"+v[k]).slice(-2))}
    if(s===0&&cd.getAttribute("data-reload")!=="no"){cd.setAttribute("data-reload","no")}};
  tick();setInterval(tick,1000)}

// relative times
function rel(ts){var m=Math.round((Date.now()-ts)/60000);if(m<1)return "ahora mismo";if(m<60)return "hace "+m+" min";
  var h=Math.round(m/60);if(h<24)return "hace "+h+" h";var d=Math.round(h/24);return "hace "+d+(d===1?" día":" días")}
function times(){$$("[data-ts]").forEach(function(el){el.textContent=rel(+el.getAttribute("data-ts"))})}
times();setInterval(times,60000);

// «tú»: the account this browser signed up
var yo=store("soloq-yo");
if(yo){$$('.fila[data-key]').forEach(function(f){if(f.getAttribute("data-key")===yo){f.classList.add("yo");
  var nm=f.querySelector(".inv .nm");if(nm&&!nm.querySelector(".tu"))nm.insertAdjacentHTML("beforeend",'<span class="tu">TÚ</span>')}})}
if(location.hash&&location.hash.indexOf("#j-")===0){var f=$(location.hash);if(f&&f.tagName==="DETAILS")f.open=true}

// Supabase
var ok=S.url&&S.key;
function api(path,opts){opts=opts||{};opts.headers=Object.assign({apikey:S.key,Authorization:"Bearer "+S.key},opts.headers||{});
  return fetch(S.url.replace(/\/$/,"")+"/rest/v1/"+path,opts)}
var known={};(S.conocidos||[]).forEach(function(k){known[k]=1});

// the locker room: signed up on the web, waiting for the next update
var vest=$("#vestuario");
function loadVestuario(){if(!ok||!vest)return;
  api("soloq_inscritos?select=riot_id,apodo,created_at&order=id.desc&limit=60").then(function(r){return r.ok?r.json():[]}).then(function(rows){
    var seen={},items=[];rows.forEach(function(x){var k=String(x.riot_id||"").trim().toLowerCase();if(!k||known[k]||seen[k])return;seen[k]=1;items.push(x)});
    if(!items.length){vest.innerHTML='<p>Nadie esperando. Todos los inscritos ya están en la tabla.</p>';return}
    vest.innerHTML='<ul>'+items.slice(0,12).map(function(x){return '<li><b>'+esc(x.apodo)+'</b><span>'+esc(x.riot_id)+'</span></li>'}).join("")+'</ul>'+
      '<p style="margin-top:10px">Entran en la tabla en la próxima actualización.</p>'}).catch(function(){})}
loadVestuario();

// sign-up form
var form=$("#alta");
if(form){
  var msg=$("#alta-msg"),btn=form.querySelector("button");
  if(!ok){$$("input,select,button",form).forEach(function(el){el.disabled=true})}
  form.addEventListener("submit",function(ev){ev.preventDefault();if(!ok)return;
    var rid=form.riot_id.value.trim().replace(/\s*#\s*/,"#"),apodo=form.apodo.value.trim();
    msg.className="msg";
    if(!/^[^#]{3,16}#[^#\s]{2,5}$/.test(rid)){msg.className="msg err";msg.textContent="Eso no es un Riot ID. Formato: Nombre#TAG (el tag es lo que va después de la almohadilla).";return}
    if(!apodo){msg.className="msg err";msg.textContent="Ponte un apodo. Uno que no te dé vergüenza ver en último lugar.";return}
    if(!form.acepto.checked){msg.className="msg err";msg.textContent="Sin aceptar el escarnio público no hay reto. Son las normas.";return}
    if(known[rid.toLowerCase()]){msg.className="msg err";msg.textContent="Esa cuenta ya está en la tabla. Ni apuntándote dos veces subes.";return}
    btn.disabled=true;msg.textContent="Entrando en la cola…";
    var body={riot_id:rid,apodo:apodo.slice(0,24),jugador:form.jugador.value||null,objetivo:form.objetivo.value||null,
      lema:form.lema.value.trim().slice(0,120)||null,lector:store("feeder-lector")||null};
    api("soloq_inscritos",{method:"POST",headers:{"Content-Type":"application/json",Prefer:"return=minimal"},body:JSON.stringify(body)})
      .then(function(r){if(!r.ok)throw new Error(r.status);store("soloq-yo",rid.toLowerCase());
        msg.className="msg ok";msg.textContent="Dentro. Apareces en la tabla en la próxima actualización (cada 30 minutos). Ve calentando el dedo del /ff.";
        form.reset();loadVestuario()})
      .catch(function(){msg.className="msg err";msg.textContent="No se ha podido apuntar. Prueba otra vez en un rato (o échale la culpa al jungla)."})
      .then(function(){btn.disabled=false})});
}

// the table changed while the page was open
var toast=$("#toast");
if(toast&&S.actualizado!==undefined){setInterval(function(){
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


# --------------------------------------------------------------------------- pictures
def _gradients():
    stops = "".join(f'<linearGradient id="g-{t.lower()}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/>'
                    f'<stop offset="1" stop-color="{b}"/></linearGradient>' for t, (a, b) in TIER_COLORS.items())
    return ('<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>' + stops +
            '<linearGradient id="lp-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c8aa6e" stop-opacity=".35"/>'
            '<stop offset="1" stop-color="#c8aa6e" stop-opacity="0"/></linearGradient></defs></svg>')


def crest(tier, cls="crest"):
    """A league crest drawn in SVG (no external images): a shield in the tier's colours with a gem."""
    t = tier if tier in TIERS else "NONE"
    crown = ('<path d="M19 12 L23 3 L28 9 L32 1 L36 9 L41 3 L45 12" fill="none" stroke="#f0e6d2" stroke-width="2.2" '
             'stroke-linejoin="round"/>' if soloq.apex(t) else "")
    wings = ('<path d="M10 20 L2 16 L6 30 L10 34 Z M54 20 L62 16 L58 30 L54 34 Z" fill="url(#g-{0})" stroke="#c8aa6e" '
             'stroke-width="1.2"/>'.format(t.lower()) if t in ("DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER") else "")
    return (f'<svg class="{cls}" viewBox="0 0 64 64" aria-hidden="true">{wings}'
            f'<path d="M32 6 L54 15 L54 35 C54 48 44 56 32 61 C20 56 10 48 10 35 L10 15 Z" fill="url(#g-{t.lower()})" '
            'stroke="#c8aa6e" stroke-width="2"/>'
            '<path d="M32 16 L44 32 L32 51 L20 32 Z" fill="rgba(255,255,255,.16)" stroke="rgba(255,255,255,.55)" stroke-width="1.2"/>'
            '<path d="M32 22 L38.5 32 L32 44 L25.5 32 Z" fill="rgba(255,255,255,.38)"/>'
            f'{crown}</svg>')


def _tier_color(tier):
    return TIER_COLORS.get(tier if tier in TIERS else "NONE")[0]


def _champ_img(cid, champ, ver):
    if not cid:
        return f'<span class="ch" data-i="{_e(_initials(champ))}"></span>'
    src = (f"{soloq.DDRAGON}/cdn/{ver}/img/champion/{urllib.parse.quote(cid)}.png" if ver else
           f"https://cdn.communitydragon.org/latest/champion/{urllib.parse.quote(cid)}/square")
    return (f'<span class="ch" data-i="{_e(_initials(champ))}"><img src="{_e(src)}" alt="{_e(champ)}" loading="lazy" '
            'onerror="this.remove()"></span>')


def _profile(x, ver):
    img = ""
    if x.get("icono") is not None:
        src = (f"{soloq.DDRAGON}/cdn/{ver}/img/profileicon/{int(x['icono'])}.png" if ver else
               f"https://cdn.communitydragon.org/latest/profile-icon/{int(x['icono'])}")
        img = f'<img src="{_e(src)}" alt="" loading="lazy" onerror="this.remove()">'
    lvl = f'<em>{int(x["nivel"])}</em>' if x.get("nivel") else ""
    return f'<span class="pi" data-i="{_e(_initials(x["apodo"]))}">{img}{lvl}</span>'


def _chart(x, r):
    """The LP curve since the account entered the race, with a line at every division."""
    pts = [(t, v) for t, v in x.get("serie") or [] if v is not None]
    if len(pts) < 2:
        return '<p class="small" style="color:var(--grey2);margin:0">La gráfica sale en cuanto se mueva de su sitio.</p>'
    W, H, L, R, T, B = 560, 170, 92, 10, 10, 22
    t0, t1 = pts[0][0], max(pts[-1][0], pts[0][0] + 1)
    lo, hi = min(v for _, v in pts), max(v for _, v in pts)
    lo, hi = (lo // 100) * 100, (hi // 100 + 1) * 100
    if hi - lo > 1200:   # long falls/climbs: one line per tier instead of per division
        lo, hi, step = (lo // 400) * 400, (hi // 400 + 1) * 400, 400
    else:
        step = 100

    def X(t):
        return L + (t - t0) / (t1 - t0) * (W - L - R)

    def Y(v):
        return T + (hi - v) / (hi - lo) * (H - T - B)

    grid = []
    for v in range(int(lo), int(hi) + 1, step):
        name = _value_name(v)
        grid.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                    f'<text x="{L - 6}" y="{Y(v) + 3:.1f}" text-anchor="end">{_e(name)}</text>')
    path = " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in pts)
    # a step line: LP only change when a game ends
    steps = [pts[0]]
    for t, v in pts[1:]:
        steps += [(t, steps[-1][1]), (t, v)]
    path = " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in steps)
    area = f"{X(steps[0][0]):.1f},{H - B} " + path + f" {X(steps[-1][0]):.1f},{H - B}"
    d0 = datetime.fromtimestamp(t0 / 1000, r["tz"]).strftime("%d/%m")
    d1 = datetime.fromtimestamp(t1 / 1000, r["tz"]).strftime("%d/%m %H:%M")
    return (f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="Evolución de LP de {_e(x["apodo"])}">'
            f'<g class="grid">{"".join(grid)}<text x="{L}" y="{H - 6}">{d0}</text>'
            f'<text x="{W - R}" y="{H - 6}" text-anchor="end">{d1}</text></g>'
            f'<polygon class="area" points="{area}"/><polyline class="line" points="{path}"/>'
            f'<circle class="dot" cx="{X(steps[-1][0]):.1f}" cy="{Y(steps[-1][1]):.1f}" r="4.5"/></svg>')


def _value_name(v):
    tier = TIERS[min(int(v // 400), TIERS.index("MASTER"))]
    if soloq.apex(tier):
        return f"{TIER_ES[tier]} {int(v - 2800)}"
    div = ["IV", "III", "II", "I"][int(v % 400 // 100)]
    return f"{TIER_ES[tier]} {div}"


def _signed(n, unit=" LP"):
    if n is None:
        return '<span class="zero">–</span>'
    if n == 0:
        return f'<span class="zero">0{unit}</span>'
    return f'<span class="{"up" if n > 0 else "down"}">{"+" if n > 0 else "−"}{abs(n)}{unit}</span>'


def _delta(x):
    c = x.get("cambio")
    if c is None:
        return '<div class="delta new" title="Nuevo en la tabla desde las 07:00">NUEVO</div>' if "cambio" in x else '<div class="delta eq">–</div>'
    if c == 0:
        return '<div class="delta eq" title="Mismo puesto que a las 07:00">=</div>'
    return (f'<div class="delta {"up" if c > 0 else "down"}" title="{"Sube" if c > 0 else "Baja"} {abs(c)} '
            f'{"puesto" if abs(c) == 1 else "puestos"} desde las 07:00">{"▲" if c > 0 else "▼"}{abs(c)}</div>')


def _opgg(cfg, riot_id):
    region = PLATFORM_OPGG.get(cfg.get("platform", "euw1"), "euw")
    name, tag = riot_id.rsplit("#", 1)
    return f"https://www.op.gg/summoners/{region}/{urllib.parse.quote(name)}-{urllib.parse.quote(tag)}"


def _fila(cfg, r, x, ver, rel_paper):
    wr = x["winrate"]
    top = f' top{x["puesto"]}' if x["puesto"] <= 3 and x["valor"] is not None else ""
    if x["valor"] is not None:
        lg = (f'<div class="lg">{crest(x["tier"])}<div><b style="color:{_tier_color(x["tier"])}">{_e(x["liga_corta"])}</b>'
              f'<span>{x["lp"]} LP</span>'
              + ('' if x["partidas"] >= r["min_partidas"] else
                 f'<div class="nq">Faltan {r["min_partidas"] - x["partidas"]} partidas para optar</div>') + '</div></div>')
    else:
        lg = (f'<div class="lg">{crest(None)}<div><b style="color:var(--grey1)">Sin clasificar</b>'
              f'<span>{"En partidas de clasificación" if x["partidas"] else "Sin jugar todavía"}</span></div></div>')
    hoy = x["hoy"]
    hoy_html = (f'<div class="hoy">{_signed(x.get("lp_hoy"))}'
                + (f'<small>{hoy[0]}V {hoy[1]}D hoy</small>' if sum(hoy) else '<small>sin jugar hoy</small>') + '</div>')
    wr_html = (f'<div class="wr"><div class="n"><span>{x["victorias"]}V {x["derrotas"]}D</span><b>{round(wr * 100)} %</b></div>'
               f'<div class="bar"><i style="width:{wr * 100:.1f}%"></i></div></div>' if wr is not None else
               '<div class="wr"><div class="n"><span>0 partidas</span><b>–</b></div><div class="bar"></div></div>')
    rk = x["racha"]
    racha = (f'<div class="racha {"w" if rk > 0 else "l"}" title="Racha actual">{abs(rk)}{"V" if rk > 0 else "D"}</div>'
             if rk else '<div class="racha" style="color:var(--grey3)">–</div>')
    ult = "".join(f'<i class="{"w" if g["win"] else "l"}" title="{_e(g["champ"])} {g["k"]}/{g["d"]}/{g["a"]}">'
                  f'{"V" if g["win"] else "D"}</i>' for g in reversed(x["ultimas"][:5]))
    ult = f'<div class="ult c-ult">{ult or "<span class=none>sin partidas</span>"}</div>'
    summary = (f'<summary><div class="pos">{x["puesto"]}</div>{_delta(x)}'
               f'<div class="inv">{_profile(x, ver)}<div class="t"><div class="nm">{_e(x["apodo"])}</div>'
               f'<div class="rid">{_e(x["riot_id"])}</div><div class="ver">{_e(x["veredicto"])}</div></div></div>'
               f'{lg}{hoy_html}{wr_html}{racha}{ult}</summary>')
    # detail
    kv = [("Empezó en", x["inicio"]), ("Pico", x["pico"] or "–"),
          ("LP desde que se apuntó", None), ("KDA", fmt_num(x["kda"], 2) if x["kda"] is not None else "–"),
          ("Horas jugadas", fmt_num(x["horas"], 1)), ("Temporada", f'{x["temporada"][0]}V {x["temporada"][1]}D')]
    kv_html = "".join(f'<div><span>{_e(k)}</span><b>{_signed(x["lp_reto"]) if v is None else _e(v)}</b></div>' for k, v in kv)
    obj = ""
    if x.get("objetivo"):
        gv = soloq.target_value(x["objetivo"])
        base = (x.get("serie") or [(0, x["valor"] or 0)])[0][1] or 0
        pct = 100 if x["cumplido"] else max(0, min(100, ((x["valor"] or 0) - base) / max(gv - base, 1) * 100)) if gv else 0
        txt = ("Objetivo cumplido. Ahora a no tirarlo." if x["cumplido"] else
               f'Le faltan {x["falta"]} LP. Lo dijo en voz alta, que conste.' if x.get("falta") is not None else
               "Primero tendrá que salir de las de clasificación.")
        obj = (f'<div class="panel obj" style="margin-top:14px"><h4>Objetivo declarado: {_e(x["objetivo_es"])}</h4>'
               f'<div class="track"><i style="width:{pct:.0f}%"></i></div><p>{_e(txt)}</p></div>')
    champs = "".join(f'<div class="champ">{_champ_img(c.get("cid"), c["champ"], ver)}<span>{_e(c["champ"])}</span>'
                     f'<span class="wrc">{c["partidas"]} partidas · {round(c["victorias"] / c["partidas"] * 100)} %</span></div>'
                     for c in x["campeones"]) or '<p style="margin:0;color:var(--grey2)">Aún sin partidas en el reto.</p>'
    games = "".join(f'<span class="game {"w" if g["win"] else "l"}" title="{_e(g["champ"])}">'
                    f'{_champ_img(g.get("cid"), g["champ"], ver)}{g["k"]}/{g["d"]}/{g["a"]}</span>' for g in x["ultimas"])
    lema = f'<p class="lema">«{_e(x["lema"])}»</p>' if x.get("lema") else ""
    links = [f'<a href="{_e(_opgg(cfg, x["riot_id"]))}" target="_blank" rel="noopener">OP.GG ↗</a>']
    if x.get("jugador"):
        links.append(f'<a href="{rel_paper}jugadores/{_e(x["jugador"])}.html">Su ficha en El Rincón del Feeder</a>')
    det = (f'<div class="det"><div><div class="panel"><h4>Evolución de LP</h4>{_chart(x, r)}</div>'
           f'<div class="kv">{kv_html}</div>{obj}</div>'
           f'<div><div class="panel"><h4>Campeones del reto</h4><div class="champs">{champs}</div></div>'
           f'<div class="panel" style="margin-top:14px"><h4>Últimas partidas</h4><div class="games">'
           f'{games or "<span style=color:var(--grey2)>Ni una todavía.</span>"}</div>{lema}'
           f'<div class="enl">{"".join(links)}</div></div></div></div>')
    return (f'<details class="fila{top}" id="j-{_e(soloq.slug_key(x["key"]))}" data-key="{_e(x["key"])}">'
            f'{summary}{det}</details>')


def _feed(moves):
    if not moves:
        return ('<ul class="feed"><li><div></div><div class="x">Ni un movimiento todavía. La tabla está más quieta '
                'que un tirador sin soporte.</div><div></div></li></ul>')
    icons = {"ascenso": "▲", "sube": "+", "descenso": "▼", "baja": "−", "liga": "★", "inscripcion": "✦"}
    lis = []
    for m in moves:
        lp = ""
        if m["tipo"] in ("sube", "baja", "ascenso", "descenso"):
            games = m.get("partidas") or 0
            lp = (f'<div class="lp">{_signed(m["delta"])}<small>'
                  + (f'{m["victorias"]}V {m["derrotas"]}D' if games else "") + '</small></div>')
        elif m["tipo"] in ("liga", "inscripcion"):
            lp = f'<div class="lp"><small>{_e(m["ahora"])}</small></div>'
        lis.append(f'<li class="{m["tipo"]}"><div class="ic"><span>{icons[m["tipo"]]}</span></div>'
                   f'<div><div class="q">{_e(m["apodo"])}<small data-ts="{m["ts"]}"></small></div>'
                   f'<div class="x">{_e(m["texto"])}</div></div>{lp}</li>')
    return '<ul class="feed">' + "".join(lis) + '</ul>'


def _muro(awards):
    if not awards:
        return ('<div class="premio"><div class="tt">Vitrina vacía</div><p>Los premios a la vergüenza se reparten en '
                'cuanto alguien juegue. Paciencia: material no va a faltar.</p></div>')
    return '<div class="muro">' + "".join(
        f'<div class="premio"><div class="tt">{_e(a["titulo"])}</div><div class="cr">{_e(a["criterio"])}</div>'
        f'<div class="who">{_e(a["apodo"])}</div><p>{_e(a["texto"])}</p></div>' for a in awards) + '</div>'


def _date_es(iso):
    return long_date(datetime.fromisoformat(iso).date())


def render(cfg, datos, now_ms, roster=(), ver=None, rel_paper="../"):
    """The whole page as HTML, plus the small JSON the open pages poll to notice changes."""
    r = soloq.reto(cfg)
    ph = soloq.fase(r, now_ms)
    at = min(now_ms, r["fin_ms"])
    ref = soloq.ultimo_corte(r, at) if ph == "en_juego" else None
    rows = soloq.tabla(datos, r, at, ref)
    day = datetime.fromtimestamp(at / 1000, r["tz"]).date().isoformat()
    for x in rows:
        x["veredicto"] = soloq.veredicto(x, rows, day)
    ranked = [x for x in rows if x["valor"] is not None]
    awards = soloq.premios(rows)
    moves = soloq.movimientos(datos, r, r["inicio_ms"] - 7 * 86400000, at, limit=14)
    _, rejected = soloq.activos(datos, r)
    title = r["nombre"]
    site_title = cfg.get("site_title", "El Rincón del Feeder")

    # hero
    label = {"previa": "Próximamente", "en_juego": "En juego", "finalizado": "Finalizado"}[ph]
    target = r["inicio_ms"] if ph == "previa" else r["fin_ms"]
    when = {"previa": "Empieza en", "en_juego": "Termina en", "finalizado": "Terminó el"}[ph]
    if ph == "finalizado":
        clock = f'<div class="countdown-label">{when} {_e(_date_es(r["fin"]))}</div>'
    else:
        units = "".join(f'<div class="u"><b data-u="{k}">--</b><span>{n}</span></div>'
                        for k, n in (("d", "Días"), ("h", "Horas"), ("m", "Min"), ("s", "Seg")))
        clock = (f'<div class="countdown-label">{when}</div>'
                 f'<div class="countdown" id="countdown" data-target="{target}">{units}</div>')
    lead = ranked[0] if ranked else None
    if lead:
        wr = f'{round(lead["winrate"] * 100)} %' if lead["winrate"] is not None else "–"
        rey = (f'<aside class="rey"><div class="titulo">{"Campeón del reto" if ph == "finalizado" else "Rey de la Grieta"}</div>'
               f'{crest(lead["tier"])}<div class="nombre">{_e(lead["apodo"])}</div><div class="rid">{_e(lead["riot_id"])}</div>'
               f'<div class="liga" style="color:{_tier_color(lead["tier"])}">{_e(lead["liga"])}</div>'
               f'<div class="mini"><span><b>{lead["partidas"]}</b> partidas</span><span><b>{wr}</b> victorias</span>'
               f'<span>{_signed(lead["lp_reto"])}</span></div>'
               f'<p class="frase">{_e(lead["veredicto"])}</p></aside>')
    else:
        rey = (f'<aside class="rey"><div class="titulo">El trono</div>{crest(None)}<div class="nombre">Vacante</div>'
               '<div class="rid">Se busca valiente</div><p class="frase">Nadie ha llegado todavía a la tabla. '
               'El primero que se apunte será líder sin jugar, que es como lideran los mejores.</p></aside>')
    hero = (f'<section class="hero"><div class="wrap"><div><div class="kicker">{_e(site_title)} presenta · '
            f'{_e(cfg.get("platform", "euw1").upper().rstrip("1"))} · Solo/Dúo</div>'
            f'<h1>{_e(title)}</h1><p class="lema">{_e(r["lema"])}</p>'
            f'<span class="estado {ph}"><i></i>{label} · del {_e(_date_es(r["inicio"]).split(", ")[1])} al '
            f'{_e(_date_es(r["fin"]).split(", ")[1])}</span>{clock}'
            '<div class="btns"><a class="btn primary" href="#inscripcion">Inscribirse</a>'
            '<a class="btn" href="#clasificacion">Ver clasificación</a></div></div>'
            f'{rey}</div></section>')

    # stats strip
    all_moves = soloq.movimientos(datos, r, r["inicio_ms"], at)
    lost = sum(-m["delta"] for m in all_moves if m.get("delta") and m["delta"] < 0)
    strip = (f'<div class="strip"><div><b>{len(rows)}</b><span>Valientes inscritos</span></div>'
             f'<div><b>{fmt_int(sum(x["partidas"] for x in rows))}</b><span>Partidas jugadas y sufridas</span></div>'
             f'<div><b>{fmt_num(sum(x["horas"] for x in rows), 0)}</b><span>Horas que no volverán</span></div>'
             f'<div class="neg"><b>{fmt_int(lost)}</b><span>LP tirados a la basura</span></div></div>')

    # podium
    podio = ""
    if len(ranked) >= 3:
        def card(x, n):
            wr = f'{round(x["winrate"] * 100)} %' if x["winrate"] is not None else "–"
            return (f'<div class="p n{n}"><div class="num"><span>{n}</span></div>{crest(x["tier"])}'
                    f'<div class="nm">{_e(x["apodo"])}</div><div class="lg" style="justify-content:center;color:{_tier_color(x["tier"])}">'
                    f'{_e(x["liga"])}</div><div class="wl">{x["victorias"]}V {x["derrotas"]}D · {wr}</div></div>')
        podio = '<div class="podio">' + card(ranked[1], 2) + card(ranked[0], 1) + card(ranked[2], 3) + '</div>'

    head = ('<div class="cab"><span>#</span><span title="Puestos ganados o perdidos desde las 07:00">±</span><span>Invocador</span>'
            '<span>Liga</span><span style="text-align:right">LP hoy</span><span>Reto</span><span style="text-align:center">Racha</span>'
            '<span class="c-ult" style="text-align:right">Últimas 5</span></div>')
    body = "".join(_fila(cfg, r, x, ver, rel_paper) for x in rows) or (
        '<div class="vacia"><b>Aún no hay valientes</b>La tabla está más vacía que el chat de tu equipo cuando pides ayuda. '
        '<a href="#inscripcion">Sé el primero en hacer el ridículo</a>.</div>')
    upd = datos.inscritos.get("actualizado")
    meta = (f'Última novedad <span data-ts="{upd}"></span><br>Se comprueba cada 30 minutos' if upd else
            'Se comprueba cada 30 minutos')
    tabla = (f'<section class="sec" id="clasificacion"><div class="sec-head"><div><h2>Clasificación</h2>'
             '<p>Manda la liga, luego la división y luego los LP. Pulsa en un jugador para ver su ficha.</p></div>'
             f'<div class="meta">{meta}</div></div>{podio}<div class="tabla">{head}{body}</div></section>')

    dos = (f'<div class="dos"><section class="sec" id="movimientos"><div class="sec-head"><div><h2>Últimos movimientos</h2>'
           '<p>Quién sube, quién baja y quién se hunde con estilo.</p></div></div>'
           f'{_feed(moves)}</section>'
           '<section class="sec" id="muro"><div class="sec-head"><div><h2>Muro de la vergüenza</h2>'
           '<p>Los premios que nadie quiere ganar.</p></div></div>'
           f'{_muro(awards)}</section></div>')

    # sign-up
    configured = bool(cfg.get("supabase_url") and cfg.get("supabase_anon_key"))
    tiers = "".join(f'<option value="{t}">{_e(TIER_ES[t])}</option>' for t in TIERS)
    who = "".join(f'<option value="{_e(p["slug"])}">{_e(p["alias"])}</option>' for p in roster)
    closed = ph == "finalizado"
    off = ("" if configured and not closed else
           '<div class="off">El reto ha terminado. Las inscripciones vuelven en la próxima temporada.</div>' if closed else
           '<div class="off">Las inscripciones se abren en cuanto la web tenga su base de datos (Supabase). '
           'Mientras, pide al administrador que te apunte a mano.</div>')
    form = (f'<form class="form" id="alta" novalidate>{off}'
            '<div class="row"><label>Riot ID<input type="text" name="riot_id" placeholder="Nombre#EUW" maxlength="23" '
            'autocomplete="off" required><span class="hint">El de tu cuenta de EUW, con el tag después de la #. '
            'Puede ser cualquier cuenta tuya, pero solo una.</span></label>'
            '<label>Apodo<input type="text" name="apodo" placeholder="Como quieres salir en la tabla" maxlength="24" required>'
            '<span class="hint">Elige bien: va a salir en el periódico.</span></label></div>'
            '<div class="row"><label>¿Sales en El Rincón del Feeder?<select name="jugador"><option value="">No, vengo de fuera</option>'
            f'{who}</select><span class="hint">Así la redacción sabe a quién está humillando.</span></label>'
            f'<label>¿Hasta dónde vas a llegar?<select name="objetivo"><option value="">Prefiero no comprometerme</option>{tiers}</select>'
            '<span class="hint">Lo que digas aquí se usará en tu contra.</span></label></div>'
            '<label>Grito de guerra<input type="text" name="lema" maxlength="120" placeholder="«Este mes salgo de Plata o desinstalo»">'
            '<span class="hint">Opcional. Saldrá en tu ficha y, cuando falles, en los titulares.</span></label>'
            '<label class="check"><input type="checkbox" name="acepto"> Acepto que el SoloQ Challenge y El Rincón del Feeder '
            'se rían de cómo juego, en público y cada mañana.</label>'
            '<button class="btn primary" type="submit" style="margin-top:6px">Entrar en la cola</button>'
            '<p class="msg" id="alta-msg" role="status"></p></form>')
    rej = [(k, c, why) for k, c, why in rejected if why in ("no_encontrado", "duplicado", "lleno")][:8]
    why_txt = {"no_encontrado": "No existe en Riot. Revisa el tag, genio.", "duplicado": "Ya está apuntado con otra cuenta.",
               "lleno": "Reto completo: está en la lista de espera."}
    rej_html = ("<ul>" + "".join(f'<li><b>{_e(c["riot_id"])}</b><span>{_e(why_txt[why])}</span></li>' for _, c, why in rej)
                + "</ul>") if rej else "<p>Nadie. De momento todo el mundo sabe escribir su Riot ID.</p>"
    alta = (f'<section class="sec" id="inscripcion"><div class="sec-head"><div><h2>Inscripción</h2>'
            '<p>Apúntate con tu Riot ID. Lo peor que puede pasar es que el periódico escriba sobre ti cada mañana.</p></div></div>'
            f'<div class="alta">{form}<div class="lado"><div class="panel"><h4>En el vestuario</h4><div id="vestuario">'
            f'<p>{"Comprobando quién espera…" if configured else "Sin base de datos todavía."}</p></div></div>'
            f'<div class="panel"><h4>Rechazados</h4>{rej_html}</div></div></div></section>')

    # rules
    rules = [
        ("La cola", "Solo cuenta Solo/Dúo en EUW. Flex, normales y ARAM no existen para el reto. Las remakes tampoco."),
        ("Las fechas", f'Del {_date_es(r["inicio"])} al {_date_es(r["fin"])}, a medianoche. Lo que pase después es vicio.'),
        ("Cómo se gana", "Gana quien esté más arriba al acabar: primero la liga, luego la división y luego los LP. "
                         "A igualdad, quien haya necesitado menos partidas."),
        ("Mínimo de partidas", f'Para optar al trono hay que jugar al menos {r["min_partidas"]} partidas del reto. '
                               "Apuntarse y esconderse no es una estrategia, es cobardía."),
        ("Una cuenta por cabeza", "Vale cualquier cuenta tuya, pero solo una. Si te apuntas tarde, tus LP del reto "
                                  "cuentan desde que te apuntas; la posición, la que tengas."),
        ("Juego limpio", "Nada de pagar a nadie para que te suba la cuenta. Además de prohibido, da una vergüenza ajena que flipas."),
    ]
    if r.get("premio"):
        rules.append(("Premio", r["premio"]))
    if r.get("castigo"):
        rules.append(("Castigo", r["castigo"]))
    rules_html = "".join(
        f'<div class="regla{" premio-r" if k == "Premio" else " castigo-r" if k == "Castigo" else ""}"><b>{_e(k)}</b>'
        f'<p>{_e(v)}</p></div>' for k, v in rules)
    reglas = (f'<section class="sec" id="reglas"><div class="sec-head"><div><h2>Reglas</h2>'
              '<p>Pocas y claras, como las ideas de vuestro jungla.</p></div>'
              f'<div class="meta">Datos de la API oficial de Riot</div></div><div class="reglas">{rules_html}</div></section>')

    feeder = json.dumps({"url": cfg.get("supabase_url", "") if not closed else "", "key": cfg.get("supabase_anon_key", ""),
                         "conocidos": sorted({x["key"] for x in rows} | {k for k, _, _ in rejected}),
                         "actualizado": upd}, ensure_ascii=False)
    paper = f"{rel_paper}index.html"
    desc = f'{r["lema"]}. Clasificación en directo, inscripción y muro de la vergüenza.'
    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)} · {_e(site_title)}</title>
<meta name="description" content="{_e(desc)}">
<meta property="og:title" content="{_e(title)}">
<meta property="og:description" content="{_e(desc)}">
<meta property="og:type" content="website">
<meta name="theme-color" content="#010a13">
{FONTS}
<link rel="stylesheet" href="soloq.css?v={ASSET_VERSION}">
</head>
<body>
{_gradients()}
<header class="top"><div class="wrap">
<a class="logo" href="#">{crest("CHALLENGER", "")}<span>{_e(title.upper())}<small>Temporada de la vergüenza</small></span></a>
<nav class="nav"><a href="#clasificacion">Clasificación</a><a href="#movimientos">Movimientos</a><a href="#muro">Vergüenza</a>
<a href="#reglas">Reglas</a><a class="ext" href="{paper}">El Rincón del Feeder ↗</a><a class="cta" href="#inscripcion">Inscribirse</a></nav>
</div></header>
<main>
{hero}
<div class="wrap">
{strip}
{tabla}
{dos}
{alta}
{reglas}
</div>
</main>
<footer><div class="wrap"><p>{_e(LEGAL.format(name=title, site=site_title))}</p>
<p><a href="{paper}">Leer El Rincón del Feeder</a>, el periódico que cuenta cada mañana lo que pasa aquí.</p></div></footer>
<div class="toast" id="toast" role="status"><span>Hay movimiento en la tabla</span><button class="btn primary" type="button">Recargar</button></div>
<script>window.SOLOQ={feeder};</script>
<script src="soloq.js?v={ASSET_VERSION}" defer></script>
</body>
</html>
"""
    public = {"nombre": title, "fase": ph, "actualizado": upd, "clasificacion": [
        {k: x[k] for k in ("puesto", "apodo", "riot_id", "liga", "lp_hoy", "partidas", "victorias", "derrotas", "racha")}
        for x in rows]}
    return html, public


def build(cfg, datos, out_dir, now_ms, roster=(), ver=None, rel_paper="../"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    html, public = render(cfg, datos, now_ms, roster, ver, rel_paper)
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "soloq.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (out / "soloq.js").write_text(JS, encoding="utf-8")
    (out / "datos.json").write_text(json.dumps(public, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out
