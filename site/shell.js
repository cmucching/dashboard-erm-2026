(function(){
 var P=(location.pathname.split('/').pop()||'index.html').replace(/\.html$/,'')||'index';
 var items=[['index','Gobernadores regionales'],['provincial','Alcaldes provinciales'],['distrital','Alcaldes distritales'],['evolucion','Evolución del conteo'],['proyeccion','Proyección de cierre'],['analisis','Análisis espacial'],['regiones','Regiones electorales'],['lima-metropolitana','Lima Metropolitana'],['base-municipal','Base municipal · descarga']];
 var d=document,h=d.createElement('div');
 h.innerHTML='<div class="sh-band"><img src="banner-marca-personal.jpg" width="1584" height="396" alt="Geomática y Dirección de Proyectos. Precisión técnica. Visión de proyecto."><div class="sh-id"><b>Ing. PMP Carlos Mucching Mendoza</b><a href="https://www.linkedin.com/in/carlosmucching" target="_blank" rel="noopener">linkedin.com/in/carlosmucching ↗</a></div></div>'+
 '<nav class="sh-nav" aria-label="Vistas electorales">'+items.map(function(i){return '<a href="'+i[0]+'.html"'+(i[0]===P?' aria-current="page"':'')+'>'+i[1]+'</a>'}).join('')+'</nav>'+
 '<div class="sh-cut" id="shCut"><i></i><span>Consultando el corte ONPE…</span></div>';
 while(h.lastChild)d.body.insertBefore(h.lastChild,d.body.firstChild);
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
 var open=function(){ov.hidden=false;var q=d.getElementById('shQ');q.value='';q.focus();draw();load().then(draw)},close=function(){ov.hidden=true;bt.focus()};
 bt.onclick=open;ov.addEventListener('mousedown',function(e){if(e.target===ov)close()});
 d.getElementById('shQ').addEventListener('input',draw);
 d.addEventListener('keydown',function(e){var t=e.target,typing=t&&/INPUT|TEXTAREA|SELECT/.test(t.tagName);
  if(ov.hidden){if((e.key==='/'&&!typing)||((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k')){e.preventDefault();open()}return}
  if(e.key==='Escape'){close()}else if(e.key==='ArrowDown'){e.preventDefault();cur=Math.min(list.length-1,cur+1);mark()}else if(e.key==='ArrowUp'){e.preventDefault();cur=Math.max(0,cur-1);mark()}else if(e.key==='Enter'&&list[cur]){location.href='unidad.html?u='+list[cur].u}});
 var fmt=function(s){try{return new Intl.DateTimeFormat('es-PE',{timeZone:'America/Lima',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(s)).replace(',',' ·')}catch(e){return s}};
 var n=function(x){return Number(x).toLocaleString('en-US')};
 fetch('api/municipal-status.json',{cache:'no-store'}).then(function(r){return r.json()}).then(function(s){
  var full=s.distrital>=s.expected_distrital&&s.provincial>=s.expected_provincial;
  d.getElementById('shCut').innerHTML='<i></i><span>Corte ONPE más reciente: <b>'+fmt(s.source_cut_until)+'</b> (hora de Perú, UTC−5). Datos desde '+fmt(s.source_cut_from)+'.</span><span class="'+(full?'':'warn')+'">'+(full?'Descarga completa':'Descarga en curso: '+n(s.provincial)+' de '+n(s.expected_provincial)+' provincias y '+n(s.distrital)+' de '+n(s.expected_distrital)+' distritos')+'</span>';
 }).catch(function(){d.getElementById('shCut').innerHTML='<i></i><span>Cada territorio muestra su propia hora de corte ONPE (UTC−5).</span>'});
})();
