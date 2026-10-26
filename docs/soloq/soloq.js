(function(){
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
