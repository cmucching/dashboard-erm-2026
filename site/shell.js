(function(){
 var P=(location.pathname.split('/').pop()||'index.html').replace(/\.html$/,'')||'index';
 var solo=document.currentScript&&document.currentScript.hasAttribute('data-solo');
 var G=[['Datos',[['index','Mapa interactivo','De la región al distrito, con zoom'],['gobernadores','Gobernadores regionales','Las 25 carreras regionales'],['provincial','Alcaldes provinciales','196 provincias'],['distrital','Alcaldes distritales','Todos los distritos'],['lima-metropolitana','Lima Metropolitana','Alcalde metropolitano y sus 43 distritos'],['base-municipal','Base municipal · descarga','Tablas en CSV y JSON']]],
  ['Análisis',[['evolucion','Evolución del conteo','Cómo cambió cada corte'],['proyeccion','Proyección de cierre','Escenario con el avance actual'],['analisis','Análisis espacial','Moran, LISA y Gi*'],['regiones','Regiones electorales','Agrupa territorios por perfil de voto'],['mapa3d','Mapa 3D','Relieve electoral']]]];
 var here='';G.forEach(function(g){g[1].forEach(function(i){if(i[0]===P)here=i[1]})});if(P==='unidad')here='Ficha de un territorio';
 var caret='<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
 var navHTML='<nav class="sh-nav" aria-label="Secciones">'+G.map(function(g,gi){var on=g[1].some(function(i){return i[0]===P});
  return '<div class="sh-grp"><button type="button" class="sh-gb'+(on?' on':'')+'" aria-expanded="false" aria-haspopup="true" aria-controls="shm'+gi+'">'+g[0]+caret+'</button><div class="sh-menu" id="shm'+gi+'" hidden>'+g[1].map(function(i){return '<a href="'+i[0]+'.html"'+(i[0]===P?' aria-current="page"':'')+'>'+i[1]+'<small>'+i[2]+'</small></a>'}).join('')+'</div></div>'}).join('')+(here?'<span class="sh-here">Estás en <b>'+here+'</b></span>':'')+'</nav>';
 var d=document,h=d.createElement('div');
 if(solo){var old=d.querySelector('nav.top');h.innerHTML=navHTML;if(old)old.replaceWith(h.firstChild);else d.body.insertBefore(h.firstChild,d.body.firstChild)}
 else{h.innerHTML='<div class="sh-band"><img src="banner-marca-personal.jpg" width="1584" height="396" alt="Geomática y Dirección de Proyectos. Precisión técnica. Visión de proyecto."><div class="sh-id"><b>Ing. PMP Carlos Mucching Mendoza</b><a href="https://www.linkedin.com/in/carlosmucching" target="_blank" rel="noopener">linkedin.com/in/carlosmucching ↗</a></div></div>'+navHTML+
 '<div class="sh-cut" id="shCut"><i></i><span>Consultando el corte ONPE…</span></div>';
 while(h.lastChild)d.body.insertBefore(h.lastChild,d.body.firstChild)}
 // menús desplegables: clic abre, clic fuera o Esc cierra; solo uno abierto
 var bts=[].slice.call(d.querySelectorAll('.sh-gb')),closeM=function(f){bts.forEach(function(b){b.setAttribute('aria-expanded','false');d.getElementById(b.getAttribute('aria-controls')).hidden=true;if(f===b)b.focus()})};
 bts.forEach(function(b){b.addEventListener('click',function(e){e.stopPropagation();var o=b.getAttribute('aria-expanded')==='true';closeM();if(!o){b.setAttribute('aria-expanded','true');d.getElementById(b.getAttribute('aria-controls')).hidden=false}})});
 d.addEventListener('click',function(e){if(!e.target.closest('.sh-grp'))closeM()});
 d.addEventListener('keydown',function(e){if(e.key==='Escape'){var o=bts.filter(function(b){return b.getAttribute('aria-expanded')==='true'})[0];if(o){e.stopImmediatePropagation();closeM(o)}}},true);
 // Buscador global (tecla / o Ctrl+K): abre la ficha compartible de cualquier distrito o provincia
 var nav=d.querySelector('.sh-nav'),bt=d.createElement('button');bt.className='sh-find';bt.type='button';bt.setAttribute('aria-label','Buscar distrito o provincia');bt.innerHTML='Buscar <kbd>/</kbd>';d.body.appendChild(bt);
 var ov=d.createElement('div');ov.className='sh-ov';ov.hidden=true;ov.innerHTML='<div class="sh-box" role="dialog" aria-modal="true" aria-label="Buscar"><input id="shQ" type="search" placeholder="Distrito o provincia, por ejemplo Andoas" autocomplete="off" aria-label="Buscar distrito o provincia"><ul id="shR" role="listbox"></ul><p class="sh-hint">↑ ↓ para moverte · Enter abre la ficha · Esc cierra</p></div>';d.body.appendChild(ov);
 var IDX=null,cur=0,list=[],norm=function(t){return String(t||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase()};
 var tc=function(t){return String(t).toLowerCase().replace(/(^|[\s(\-])(\S)/g,function(m,x,y){return x+y.toUpperCase()}).replace(/ (De|Del|La|Las|Los|El|Y|Para)(?= )/g,function(m){return m.toLowerCase()})};
 var load=function(){return IDX?Promise.resolve(IDX):fetch('api/search-index.json').then(function(r){return r.json()}).then(function(x){x.forEach(function(e){e.k=norm(e.n);e.t=norm(e.n+' '+e.p+' '+e.d)});IDX=x;return x})};
 var esc=function(t){return String(t).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})};
 var draw=function(){var q=norm(d.getElementById('shQ').value).trim(),ul=d.getElementById('shR');
  if(!IDX){ul.innerHTML='<li class="sh-empty">Cargando…</li>';return}
  if(!q){ul.innerHTML='<li class="sh-empty">Escribe el nombre de un distrito o de una provincia.</li>';list=[];return}
  var tk=q.split(/\s+/);list=IDX.filter(function(e){return tk.every(function(t){return e.t.indexOf(t)>=0})}).sort(function(a,b){var sa=a.k.indexOf(q)===0?0:1,sb=b.k.indexOf(q)===0?0:1;return sa-sb||(a.l===b.l?b.v-a.v:(a.l==='p'?-1:1))}).slice(0,10);cur=0;
  ul.innerHTML=list.length?list.map(function(e,i){return '<li role="option" data-i="'+i+'"'+(i===0?' aria-selected="true"':'')+'><a href="unidad.html?u='+e.u+'"><b>'+esc(tc(e.n))+'</b><span>'+(e.l==='p'?'Provincia · ':'Distrito de ')+esc(tc(e.p))+' · '+esc(tc(e.d))+'</span>'+(e.w?'<em>'+esc(tc(e.w.replace(/ - .*$/,'')))+' '+e.lp.toLocaleString('en-US',{maximumFractionDigits:1})+' %</em>':'')+'</a></li>'}).join(''):'<li class="sh-empty">Sin resultados para «'+esc(d.getElementById('shQ').value)+'».</li>'};
 var mark=function(){d.querySelectorAll('#shR li[role=option]').forEach(function(l,i){l.setAttribute('aria-selected',i===cur?'true':'false');if(i===cur)l.scrollIntoView({block:'nearest'})})};
 var pickU=function(e){if(typeof window.ERM_goto==='function'){ov.hidden=true;window.ERM_goto(e.u);return true}return false};
 var open=function(){ov.hidden=false;var q=d.getElementById('shQ');q.value='';q.focus();draw();load().then(draw)},close=function(){ov.hidden=true;bt.focus()};
 bt.onclick=open;ov.addEventListener('mousedown',function(e){if(e.target===ov)close()});
 d.getElementById('shQ').addEventListener('input',draw);
 d.getElementById('shR').addEventListener('click',function(e){var li=e.target.closest('li[role=option]');if(!li||!list[+li.dataset.i])return;if(typeof window.ERM_goto==='function'){e.preventDefault();pickU(list[+li.dataset.i])}});
 d.addEventListener('keydown',function(e){var t=e.target,typing=t&&/INPUT|TEXTAREA|SELECT/.test(t.tagName);
  if(ov.hidden){if((e.key==='/'&&!typing)||((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k')){e.preventDefault();open()}return}
  if(e.key==='Escape'){close()}else if(e.key==='ArrowDown'){e.preventDefault();cur=Math.min(list.length-1,cur+1);mark()}else if(e.key==='ArrowUp'){e.preventDefault();cur=Math.max(0,cur-1);mark()}else if(e.key==='Enter'&&list[cur]){if(!pickU(list[cur]))location.href='unidad.html?u='+list[cur].u}});
 var fmt=function(s){try{return new Intl.DateTimeFormat('es-PE',{timeZone:'America/Lima',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(s)).replace(',',' ·')}catch(e){return s}};
 var n=function(x){return Number(x).toLocaleString('en-US')};
 if(d.getElementById('shCut'))fetch('api/municipal-status.json',{cache:'no-store'}).then(function(r){return r.json()}).then(function(s){
  var full=s.distrital>=s.expected_distrital&&s.provincial>=s.expected_provincial;
  d.getElementById('shCut').innerHTML='<i></i><span>Corte ONPE más reciente: <b>'+fmt(s.source_cut_until)+'</b> (hora de Perú, UTC−5). Datos desde '+fmt(s.source_cut_from)+'.</span><span class="'+(full?'':'warn')+'">'+(full?'Descarga completa':'Descarga en curso: '+n(s.provincial)+' de '+n(s.expected_provincial)+' provincias y '+n(s.distrital)+' de '+n(s.expected_distrital)+' distritos')+'</span>';
 }).catch(function(){d.getElementById('shCut').innerHTML='<i></i><span>Cada territorio muestra su propia hora de corte ONPE (UTC−5).</span>'});
})();
