/* Rediseño R2 · capa de comportamiento. Lee DATA/select() de la página; no modifica datos. */
(function(){
  'use strict';
  var doc=document,root=doc.documentElement;
  var $=function(s,c){return(c||doc).querySelector(s);},$$=function(s,c){return Array.prototype.slice.call((c||doc).querySelectorAll(s));};
  var num=function(t){var m=String(t).replace(/\s/g,'').match(/-?\d+(?:[.,]\d+)?/);return m?parseFloat(m[0].replace(',','.')):NaN;};
  var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
  var tc=function(s){return String(s||'').toLowerCase().replace(/(^|\s|-)([a-záéíóúñ])/g,function(m,a,b){return a+b.toUpperCase();}).replace(/\b(De|Del|La|Las|Los|Y|El|Pp)\b/g,function(w){return w.toLowerCase();}).replace(/^./,function(c){return c.toUpperCase();});};
  var D=function(){try{return typeof DATA!=='undefined'&&Array.isArray(DATA)?DATA:[];}catch(e){return[];}};
  var margin=function(r){return r.top&&r.top[1]?r.top[0].percent-r.top[1].percent:NaN;};
  var fx=function(n,d){return Number(n).toFixed(d==null?1:d);};
  function textOn(hex){var m=/^#?([0-9a-f]{6})$/i.exec(hex||'');if(!m)return'#fff';var v=parseInt(m[1],16),r=v>>16&255,g=v>>8&255,b=v&255;
    var l=[r,g,b].map(function(c){c/=255;return c<=.03928?c/12.92:Math.pow((c+.055)/1.055,2.4);});var L=.2126*l[0]+.7152*l[1]+.0722*l[2];return L>.36?'#06263D':'#fff';}

  /* 1 · Tema */
  function setTheme(t){root.dataset.theme=t;try{localStorage.setItem('erm-theme',t);}catch(e){}var b=$('#themeBtn');if(b){b.querySelector('.ico').textContent=t==='dark'?'☀':'☾';b.setAttribute('aria-label',t==='dark'?'Cambiar a tema claro':'Cambiar a tema oscuro');}}

  /* 2 · Estructura común: cabecera, pestañas y herramientas (todas las páginas) */
  var ORDER=['/','/provincial','/distrital','/lima-metropolitana','/base-municipal'];
  function shell(){
    var h=$('header');if(h&&!h.classList.contains('hero'))h.classList.add('hero');
    var nav=$('nav[aria-label="Vistas electorales"]');
    if(!nav)return;
    nav.classList.add('election-nav');nav.removeAttribute('style');
    var links=$$(':scope > a',nav);
    links.sort(function(a,b){
      var ia=ORDER.indexOf(a.getAttribute('href')),ib=ORDER.indexOf(b.getAttribute('href'));
      return (ia<0?99:ia)-(ib<0?99:ib);
    }).forEach(function(a){nav.appendChild(a);});
    if(!$('.navtools',nav)){
      var t=doc.createElement('div');t.className='navtools';
      t.innerHTML='<button type="button" id="searchBtn" aria-haspopup="dialog"><span aria-hidden="true">⌕</span><span class="lbl">Buscar</span><kbd>Ctrl K</kbd></button>'+
        '<button type="button" id="themeBtn"><span class="ico" aria-hidden="true">☾</span></button>';
      nav.appendChild(t);
    }
    setTheme(root.dataset.theme==='dark'?'dark':'light');
    $('#themeBtn').addEventListener('click',function(){setTheme(root.dataset.theme==='dark'?'light':'dark');});
    $('#searchBtn').addEventListener('click',openPalette);
  }

  /* 3 · Indicador de rango: «66,654 %–98,832 %» → «66.7 %–98.8 %» */
  function fixRange(){
    $$('.stat strong').forEach(function(el){
      var m=el.textContent.match(/^\s*(\d+)[.,](\d+)\s*%\s*[–-]\s*(\d+)[.,](\d+)\s*%\s*$/);
      if(!m)return;
      var a=parseFloat(m[1]+'.'+m[2]),b=parseFloat(m[3]+'.'+m[4]);
      el.textContent=fx(a)+' %–'+fx(b)+' %';
      var card=el.closest('.stat');
      if(card&&!card.querySelector('.rangebar')){
        var bar=doc.createElement('div');bar.className='rangebar';bar.setAttribute('aria-hidden','true');
        bar.innerHTML='<i style="left:'+a+'%;width:'+Math.max(b-a,1)+'%"></i>';
        var sc=doc.createElement('div');sc.className='rangescale';sc.setAttribute('aria-hidden','true');sc.innerHTML='<span>0 %</span><span>100 %</span>';
        el.insertAdjacentElement('afterend',bar);bar.insertAdjacentElement('afterend',sc);
      }
    });
  }

  /* 4 · Panorama: cuadrícula de regiones, posiciones y lectura rápida (solo página de gobernadores) */
  var POS={'Tumbes':[1,1],'Loreto':[4,1],'Piura':[1,2],'Cajamarca':[2,2],'Amazonas':[3,2],'San Martín':[4,2],'Lambayeque':[1,3],'La Libertad':[2,3],'Huánuco':[3,3],'Ucayali':[4,3],'Áncash':[2,4],'Pasco':[3,4],'Junín':[4,4],'Callao':[1,5],'Lima región':[2,5],'Huancavelica':[3,5],'Cusco':[4,5],'Madre de Dios':[5,5],'Ica':[2,6],'Ayacucho':[3,6],'Apurímac':[4,6],'Puno':[5,6],'Arequipa':[3,7],'Moquegua':[4,7],'Tacna':[5,7]};
  var panSig='';
  function selectedId(){try{return typeof selected!=='undefined'?selected:null;}catch(e){return null;}}
  function filterOrg(){try{return typeof partyFilter!=='undefined'?partyFilter:null;}catch(e){return null;}}
  function goSelect(id){try{select(id);}catch(e){}var d=$('.detail');if(d)d.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth',block:'start'});}
  function buildPanorama(){
    var data=D(),ws=$('.workspace');
    if(!ws||data.length<20)return;
    var sig=data.map(function(r){return r.id+':'+r.votos+':'+(r.top[1]&&r.top[1].votes);}).join('|');
    if(sig===panSig){syncTiles();return;}
    panSig=sig;
    var old=$('.panorama');if(old)old.remove();
    var tight=data.filter(function(r){return margin(r)<3;});
    var byOrg={};data.forEach(function(r){var o=byOrg[r.organizacion]||(byOrg[r.organizacion]={n:0,color:r.color,img:r.simbolo});o.n++;});
    var orgs=Object.keys(byOrg).map(function(k){return{name:k,n:byOrg[k].n,color:byOrg[k].color,img:byOrg[k].img};}).sort(function(a,b){return b.n-a.n||a.name.localeCompare(b.name,'es');});
    var maxN=orgs[0]?orgs[0].n:1;
    var close=data.slice().sort(function(a,b){return margin(a)-margin(b);})[0];
    var wide=data.slice().sort(function(a,b){return margin(b)-margin(a);})[0];
    var low=data.slice().sort(function(a,b){return a.actas_contabilizadas-b.actas_contabilizadas;})[0];
    var order=data.slice().sort(function(a,b){var pa=POS[a.region]||[9,9],pb=POS[b.region]||[9,9];return pa[1]-pb[1]||pa[0]-pb[0];});
    var extra=0;
    var tiles=order.map(function(r,i){
      var p=POS[r.region];if(!p){p=[1+extra%5,8+Math.floor(extra/5)];extra++;}
      var m=margin(r),ab=(r.id||'').replace(/^PE-/,'')||r.region.slice(0,3).toUpperCase();
      return '<button type="button" class="tile'+(m<3?' tight':'')+'" data-id="'+esc(r.id)+'" data-org="'+esc(r.organizacion)+'" style="--x:'+p[0]+';--y:'+p[1]+';--c:'+esc(r.color)+';--t:'+textOn(r.color)+';--d:'+(p[1]*2+p[0])+'" '+
        'aria-pressed="false" aria-label="'+esc(r.region+': lidera '+r.organizacion+', ventaja de '+fx(m,2)+' puntos porcentuales')+'"><b>'+esc(ab)+'</b><small>+'+fx(m,1)+'</small></button>';
    }).join('');
    var stand=orgs.map(function(o){
      return '<li><button type="button" data-org="'+esc(o.name)+'" style="--c:'+esc(o.color)+';--w:'+(o.n/maxN*100)+'%"><img src="'+esc(o.img)+'" alt="" loading="lazy"><span><span class="nm">'+esc(o.name)+'</span><span class="bar"><i></i></span></span><span class="n">'+o.n+'</span></button></li>';
    }).join('');
    var sec=doc.createElement('section');sec.className='panorama';sec.setAttribute('aria-label','Panorama nacional');
    sec.innerHTML=
      '<div class="pan-card"><h2>Las 25 regiones de un vistazo</h2><p class="sub">Cada cuadro es una región, ubicada de norte a sur. El color es la organización que lidera; el número, su ventaja sobre la segunda en puntos porcentuales.</p>'+
      '<div class="tilegrid" role="group" aria-label="Cuadrícula de regiones">'+tiles+'</div>'+
      '<div class="tilekey"><span><i></i>Ventaja menor a 3 pp: puede cambiar</span><span>Toca una región para ver su detalle</span></div></div>'+
      '<div class="pan-card"><div class="standings-head"><h2>Quién lidera más regiones</h2><button type="button" class="chipclear" id="chipClear">Quitar filtro</button></div><p class="sub">'+data.length+' regiones, '+orgs.length+' organizaciones. Toca una organización para filtrar el mapa y la tabla.</p>'+
      '<ul class="standings">'+stand+'</ul>'+
      '<h2 style="margin-top:22px;font-size:17px">Lectura rápida</h2>'+
      '<div class="insights">'+
        '<button type="button" class="insight" data-go="'+esc(close.id)+'"><small>Más reñida</small><b>'+esc(close.region)+' · '+fx(margin(close),2)+' pp</b><span>'+esc(close.organizacion)+' frente a '+esc(tc(close.top[1].party))+'</span></button>'+
        '<button type="button" class="insight" data-go="'+esc(wide.id)+'"><small>Mayor ventaja</small><b>'+esc(wide.region)+' · '+fx(margin(wide),2)+' pp</b><span>'+esc(wide.organizacion)+'</span></button>'+
        '<button type="button" class="insight" data-go="'+esc(low.id)+'"><small>Menos actas contabilizadas</small><b>'+esc(low.region)+' · '+fx(low.actas_contabilizadas,1)+' %</b><span>Su resultado puede moverse más</span></button>'+
        '<button type="button" class="insight" data-tight="1"><small>Ventaja menor a 3 pp</small><b>'+tight.length+' de '+data.length+' regiones</b><span>Ordenar la tabla por ventaja</span></button>'+
      '</div></div>';
    ws.parentNode.insertBefore(sec,ws.nextSibling);
    buildMapExtras(orgs,data.length);
    sec.addEventListener('click',function(e){
      var t=e.target.closest('.tile');if(t){goSelect(t.getAttribute('data-id'));return;}
      var g=e.target.closest('[data-go]');if(g){goSelect(g.getAttribute('data-go'));return;}
      if(e.target.closest('#chipClear')){var cl=$('.legendpanel .clear');if(cl)cl.click();return;}
      var o=e.target.closest('.standings button');
      if(o){var name=o.getAttribute('data-org');var pb=$$('.party').filter(function(b){var n=b.querySelector('.name');return n&&n.textContent.trim()===name;})[0];
        if(pb){pb.click();ws.scrollIntoView({behavior:'smooth',block:'start'});}return;}
      if(e.target.closest('[data-tight]')){
        var th=$('th[data-lead]');if(th){th.click();if(th.getAttribute('aria-sort')==='descending')th.click();$('.tablepanel').scrollIntoView({behavior:'smooth',block:'start'});}
      }
    });
    syncTiles();
  }
  function filterByOrg(name){
    var pb=$$('.party').filter(function(b){var n=b.querySelector('.name');return n&&n.textContent.trim()===name;})[0];
    if(pb)pb.click();
  }
  function buildMapExtras(orgs,total){
    var wrap=$('.mapwrap'),panel=wrap&&wrap.closest('.panel');
    if(!wrap)return;
    var old=$('.maplegend',wrap);if(old)old.remove();
    var top=orgs.slice(0,6),rest=orgs.length-top.length;
    var lg=doc.createElement('div');lg.className='maplegend';
    lg.innerHTML='<h3>Quién lidera más regiones</h3>'+top.map(function(o){return '<button type="button" data-org="'+esc(o.name)+'" style="--c:'+esc(o.color)+'"><i></i><span>'+esc(o.name)+'</span><b>'+o.n+'</b></button>';}).join('')+(rest>0?'<div class="more">y '+rest+' organizaciones más, en el panorama</div>':'');
    wrap.appendChild(lg);
    lg.addEventListener('click',function(e){var b=e.target.closest('button');if(b)filterByOrg(b.getAttribute('data-org'));});
    var head=panel&&$('.panelhead',panel);
    if(head&&!$('.fsbtn',head)&&doc.fullscreenEnabled){
      var fb=doc.createElement('button');fb.type='button';fb.className='fsbtn';fb.innerHTML='<span aria-hidden="true">⛶</span> Pantalla completa';
      head.insertBefore(fb,head.querySelector('.texture-switch'));
      fb.addEventListener('click',function(){if(doc.fullscreenElement)doc.exitFullscreen();else panel.requestFullscreen().catch(function(){});});
      doc.addEventListener('fullscreenchange',function(){fb.innerHTML=doc.fullscreenElement?'<span aria-hidden="true">⤢</span> Salir de pantalla completa':'<span aria-hidden="true">⛶</span> Pantalla completa';setTimeout(function(){window.dispatchEvent(new Event('resize'));},120);});
    }
  }
  function syncTiles(){
    var sel=selectedId(),f=filterOrg();
    var cc=$('#chipClear');if(cc)cc.setAttribute('data-on',f?'1':'0');
    $$('.standings button').forEach(function(b){b.style.opacity=(f&&b.getAttribute('data-org')!==f)?'.45':'';});
    $$('.tile').forEach(function(t){t.setAttribute('aria-pressed',t.getAttribute('data-id')===sel?'true':'false');t.classList.toggle('dim',!!f&&t.getAttribute('data-org')!==f);});
  }

  /* 5 · Tabla: ventaja, búsqueda y orden */
  var table,tbody,busy=false,sortState={col:null,dir:1},query='';
  function enhanceRows(){
    if(busy)return;busy=true;
    try{
      var head=table.querySelector('thead tr');
      if(head&&!head.querySelector('[data-lead]')){
        var th=doc.createElement('th');th.scope='col';th.textContent='Ventaja (pp)';th.setAttribute('data-lead','1');
        head.insertBefore(th,head.children[7]);
        $$('th',head).forEach(function(h,i){h.setAttribute('data-sort',i);h.setAttribute('tabindex','0');});
      }
      $$('tr',tbody).forEach(function(tr){
        if(tr.querySelector('td.lead'))return;
        var c=tr.children,a=num(c[2]&&c[2].textContent),b=num(c[5]&&c[5].textContent);
        var td=doc.createElement('td');td.className='lead';
        if(!isNaN(a)&&!isNaN(b)){
          var d=a-b,tight=d<3;
          td.innerHTML='<span class="leadnum">'+fx(d,2)+' pp</span>'+(tight?' <span class="leadtag">reñida</span>':'')+
            '<div class="leadbar'+(tight?' tight':'')+'" aria-hidden="true"><i style="width:'+Math.min(100,d*2.5)+'%"></i></div>';
          td.setAttribute('data-v',d);
        }
        tr.insertBefore(td,c[7]);
      });
      applyTable();
    }finally{busy=false;}
  }
  function applyTable(){
    var rows=$$('tr',tbody),q=query.trim().toLowerCase(),shown=0;
    rows.forEach(function(tr){var ok=!q||tr.textContent.toLowerCase().indexOf(q)>-1;tr.hidden=!ok;if(ok)shown++;});
    if(sortState.col!==null){
      var i=sortState.col,dir=sortState.dir;
      rows.sort(function(r1,r2){
        var a=r1.children[i],b=r2.children[i],va=a.getAttribute('data-v'),vb=b.getAttribute('data-v');
        va=va!==null?parseFloat(va):num(a.textContent);vb=vb!==null?parseFloat(vb):num(b.textContent);
        if(isNaN(va)||isNaN(vb))return dir*a.textContent.localeCompare(b.textContent,'es');
        return dir*(va-vb);
      }).forEach(function(r){tbody.appendChild(r);});
    }
    var cnt=$('#tableCount');if(cnt)cnt.textContent=shown+' de '+rows.length+' regiones';
  }
  function setupTable(){
    table=$('.tablepanel table');tbody=$('#rows');
    if(!table||!tbody)return;
    var tools=doc.createElement('div');tools.className='tabletools';
    tools.innerHTML='<input id="tableSearch" type="search" aria-label="Buscar región, partido o candidato" placeholder="Buscar región, partido o candidato" autocomplete="off">'+
      '<small id="tableCount" aria-live="polite"></small><small>Toca un encabezado para ordenar. Ventaja: diferencia entre el 1.º y el 2.º, en puntos porcentuales (pp).</small>';
    table.closest('.tablewrap').insertAdjacentElement('beforebegin',tools);
    $('input',tools).addEventListener('input',function(e){query=e.target.value;applyTable();});
    var thead=table.querySelector('thead');
    thead.addEventListener('click',function(e){
      var th=e.target.closest('th[data-sort]');if(!th)return;
      var i=+th.getAttribute('data-sort');
      sortState.dir=(sortState.col===i)?-sortState.dir:(i<=1?1:-1);sortState.col=i;
      $$('th',table).forEach(function(h){h.removeAttribute('aria-sort');});
      th.setAttribute('aria-sort',sortState.dir===1?'ascending':'descending');applyTable();
    });
    thead.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){var th=e.target.closest('th[data-sort]');if(th){e.preventDefault();th.click();}}});
    new MutationObserver(function(){enhanceRows();buildPanorama();}).observe(tbody,{childList:true});
    enhanceRows();
  }

  /* 6 · Buscador rápido (Ctrl/⌘ K o «/») */
  var pal,palList,palInput,palIdx=0,palItems=[];
  function ensurePalette(){
    if(pal)return;
    pal=doc.createElement('div');pal.className='cmdk';pal.setAttribute('role','dialog');pal.setAttribute('aria-modal','true');pal.setAttribute('aria-label','Buscar región, organización o candidato');
    pal.innerHTML='<div class="cmdk-box"><input type="text" id="cmdkInput" placeholder="Buscar región, organización o candidato" autocomplete="off" aria-label="Buscar"><ul class="cmdk-list" id="cmdkList" role="listbox"></ul><div class="cmdk-foot"><span>↑↓ para moverte</span><span>Enter para abrir</span><span>Esc para cerrar</span></div></div>';
    doc.body.appendChild(pal);
    palList=$('#cmdkList',pal);palInput=$('#cmdkInput',pal);
    pal.addEventListener('mousedown',function(e){if(e.target===pal)closePalette();});
    palInput.addEventListener('input',function(){palIdx=0;renderPalette();});
    palInput.addEventListener('keydown',function(e){
      if(e.key==='ArrowDown'){e.preventDefault();palIdx=Math.min(palItems.length-1,palIdx+1);markPalette();}
      else if(e.key==='ArrowUp'){e.preventDefault();palIdx=Math.max(0,palIdx-1);markPalette();}
      else if(e.key==='Enter'){e.preventDefault();pick(palItems[palIdx]);}
    });
    palList.addEventListener('click',function(e){var b=e.target.closest('button');if(b)pick(palItems[+b.getAttribute('data-i')]);});
  }
  function renderPalette(){
    var q=palInput.value.trim().toLowerCase(),data=D();
    palItems=data.map(function(r){
      var hay=[r.region,r.organizacion,r.top[0].candidate,r.top[1]&&r.top[1].party,r.top[1]&&r.top[1].candidate].join(' ').toLowerCase();
      var s=!q?1:(r.region.toLowerCase().indexOf(q)===0?3:r.region.toLowerCase().indexOf(q)>-1?2:hay.indexOf(q)>-1?1:0);
      return{r:r,s:s};
    }).filter(function(x){return x.s>0;}).sort(function(a,b){return b.s-a.s||a.r.region.localeCompare(b.r.region,'es');}).slice(0,8);
    palList.innerHTML=palItems.length?palItems.map(function(x,i){
      var r=x.r;return '<li><button type="button" role="option" data-i="'+i+'" aria-selected="'+(i===palIdx)+'" style="--c:'+esc(r.color)+'"><i></i><span><b>'+esc(r.region)+'</b><small>'+esc(r.organizacion)+' · '+esc(r.top[0].candidate)+'</small></span><em>'+fx(r.top[0].percent,1)+' %</em></button></li>';
    }).join(''):'<li class="cmdk-empty">No hay coincidencias. Prueba con el nombre de una región o de un candidato.</li>';
  }
  function markPalette(){$$('button',palList).forEach(function(b,i){b.setAttribute('aria-selected',i===palIdx);if(i===palIdx)b.scrollIntoView({block:'nearest'});});}
  function pick(x){if(!x)return;closePalette();goSelect(x.r.id);}
  function openPalette(){ensurePalette();pal.setAttribute('data-open','1');palInput.value='';palIdx=0;renderPalette();setTimeout(function(){palInput.focus();},0);}
  function closePalette(){if(pal)pal.removeAttribute('data-open');var b=$('#searchBtn');if(b)b.focus();}
  doc.addEventListener('keydown',function(e){
    var typing=/^(INPUT|TEXTAREA|SELECT)$/.test((doc.activeElement||{}).tagName||'');
    if((e.key==='k'||e.key==='K')&&(e.ctrlKey||e.metaKey)){e.preventDefault();pal&&pal.getAttribute('data-open')?closePalette():openPalette();}
    else if(e.key==='/'&&!typing&&!(pal&&pal.getAttribute('data-open'))){e.preventDefault();openPalette();}
    else if(e.key==='Escape'&&pal&&pal.getAttribute('data-open'))closePalette();
  });

  doc.addEventListener('click',function(){setTimeout(syncTiles,60);});
  function init(){
    shell();fixRange();setupTable();buildPanorama();
    window.addEventListener('cut-displayed',function(){fixRange();buildPanorama();});
  }
  if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',init);else init();
})();
