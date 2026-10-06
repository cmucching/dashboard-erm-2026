(function(){
 var P=(location.pathname.split('/').pop()||'index.html').replace(/\.html$/,'')||'index';
 var items=[['index','Gobernadores regionales'],['provincial','Alcaldes provinciales'],['distrital','Alcaldes distritales'],['lima-metropolitana','Lima Metropolitana'],['base-municipal','Base municipal · descarga']];
 var d=document,h=d.createElement('div');
 h.innerHTML='<div class="sh-band"><img src="banner-marca-personal.jpg" width="1584" height="396" alt="Geomática y Dirección de Proyectos. Precisión técnica. Visión de proyecto."><div class="sh-id"><b>Ing. PMP Carlos Mucching Mendoza</b><a href="https://www.linkedin.com/in/carlosmucching" target="_blank" rel="noopener">linkedin.com/in/carlosmucching ↗</a></div></div>'+
 '<nav class="sh-nav" aria-label="Vistas electorales">'+items.map(function(i){return '<a href="'+i[0]+'.html"'+(i[0]===P?' aria-current="page"':'')+'>'+i[1]+'</a>'}).join('')+'</nav>'+
 '<div class="sh-cut" id="shCut"><i></i><span>Consultando el corte ONPE…</span></div>';
 while(h.lastChild)d.body.insertBefore(h.lastChild,d.body.firstChild);
 var fmt=function(s){try{return new Intl.DateTimeFormat('es-PE',{timeZone:'America/Lima',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(s)).replace(',',' ·')}catch(e){return s}};
 var n=function(x){return Number(x).toLocaleString('en-US')};
 fetch('api/municipal-status.json',{cache:'no-store'}).then(function(r){return r.json()}).then(function(s){
  var full=s.distrital>=s.expected_distrital&&s.provincial>=s.expected_provincial;
  d.getElementById('shCut').innerHTML='<i></i><span>Corte ONPE más reciente: <b>'+fmt(s.source_cut_until)+'</b> (hora de Perú, UTC−5). Datos desde '+fmt(s.source_cut_from)+'.</span><span class="'+(full?'':'warn')+'">'+(full?'Descarga completa':'Descarga en curso: '+n(s.provincial)+' de '+n(s.expected_provincial)+' provincias y '+n(s.distrital)+' de '+n(s.expected_distrital)+' distritos')+'</span>';
 }).catch(function(){d.getElementById('shCut').innerHTML='<i></i><span>Cada territorio muestra su propia hora de corte ONPE (UTC−5).</span>'});
})();
