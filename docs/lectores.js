(function(){
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
  function layout(){
    restore();
    var mr = main.getBoundingClientRect(), ar = aside.getBoundingClientRect();
    if (ar.left < mr.right) return;                       // phone: sidebar already below
    var last = aside.lastElementChild, top = mr.top, best = null;
    var h = last ? last.getBoundingClientRect().bottom - ar.top : 0;
    Array.prototype.forEach.call(main.children, function(sec){
      var y = sec.getBoundingClientRect().top - top;
      if (y > h / 2) consider({y: y, sec: sec});
      var grid = sec.querySelector('.sec-grid'), seen = {};
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
      cont.className = best.sec.className + ' cont'; g.className = 'sec-grid'; cont.appendChild(g); full.appendChild(cont);
      Array.prototype.slice.call(best.grid.children).forEach(function(a){
        if (Math.round(a.getBoundingClientRect().top) >= best.row) move(a, g);
      });
      rest = best.sec.nextElementSibling;
    }
    while (rest) { var next = rest.nextElementSibling; move(rest, full); rest = next; }
  }
  var timer;
  function later(){ clearTimeout(timer); timer = setTimeout(layout, 120); }
  layout();
  window.addEventListener('load', later);
  window.addEventListener('resize', later);
  document.addEventListener('load', function(e){ if (e.target.tagName === 'IMG') later(); }, true);
  if (document.fonts) document.fonts.ready.then(later);
})();
