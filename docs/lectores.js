(function(){
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
