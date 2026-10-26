(function(){
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
