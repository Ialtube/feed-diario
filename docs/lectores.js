(function(){
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
  var tu = document.getElementById('tu-edicion');
  function pintaTu(){
    if (!tu) return;
    var y = Yo.get(), J = DATOS.jugadores || {}, li = [];
    if (!y) {
      tu.innerHTML = '<h4>Tu edición</h4><p class="small">Dinos quién eres y te enseñamos, antes que nada, lo que el periódico dice hoy de ti.</p>' +
        '<p style="margin-top:6px"><button type="button">¿Quién eres?</button></p>';
      tu.querySelector('button').onclick = function(){ Yo.open(); };
      tu.hidden = false; return;
    }
    var slug = (y.cuentas || [])[0], me = slug ? J[slug] : null;
    if (me && me.piezas.length) li.push('Hoy sales en <b>' + me.piezas.length + '</b> pieza' + (me.piezas.length > 1 ? 's' : '') + ': ' +
      me.piezas.slice(0, 3).map(function(p){ return '<a href="#p-' + esc(p[0]) + '">' + esc(p[1]) + '</a>'; }).join(' · ') +
      (me.piezas.length > 3 ? ' y ' + (me.piezas.length - 3) + ' más.' : ''));
    else if (slug) li.push('Hoy no sales en el periódico. Disfrútalo: no durará.');
    if (me && me.puesto) li.push('Tu día: <b>' + esc(me.dia) + '</b>, puesto ' + me.puesto + ' de ' + me.de + ' en la tabla de la vergüenza' +
      (me.puesto === 1 ? ' (sí, el peor)' : '') + '.');
    if (me && me.tiempo) li.push('<span data-extra></span>Tu tiempo, según Madame Niebla: <i>' + esc(me.tiempo.split(/(?<=\.)\s/)[0]) + '</i>');
    var saldo = (DATOS.saldos || {})[Yo.key()];
    li.push('Lonja de Coronas: ' + (saldo != null ? '<b>' + saldo + '</b> coronas.' : 'aún no tienes cuenta; empiezas con 100 coronas.') + ' <a href="#lonja">Apostar</a>');
    if (document.getElementById('jurado')) li.push(remember('feeder-jurado-' + EDICION) ? 'Ya has votado en el jurado popular.' : 'El jurado popular espera <a href="#jurado">tu voto</a>.');
    if (document.getElementById('quienfue')) {
      var q = {}; try { q = JSON.parse(remember('feeder-qf-' + EDICION) || '{}'); } catch(e){}
      li.push(q.fin ? '¿Quién fue?: ' + (q.acierto ? 'resuelto en ' + q.intentos + ' intento' + (q.intentos > 1 ? 's' : '') + '.' : 'hoy no lo sacaste.')
                    : '<a href="#quienfue">¿Quién fue?</a> sigue sin resolver.');
    }
    tu.innerHTML = '<h4>Tu edición, ' + esc(y.nombre) + '</h4><ul>' + li.map(function(t){
      return '<li' + (t.indexOf('data-extra') >= 0 ? ' class="extra"' : '') + '>' + t + '</li>'; }).join('') + '</ul>';
    tu.hidden = false;
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
