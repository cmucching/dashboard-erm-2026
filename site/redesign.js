/* Capa de rediseño (R1): formato numérico, indicadores, tabla con búsqueda/orden/ventaja. */
(function(){
  'use strict';
  var num=function(t){var m=String(t).replace(/\s/g,'').match(/-?\d+(?:[.,]\d+)?/);return m?parseFloat(m[0].replace(',','.')):NaN;};

  // 1 · «66,654 %–98,832 %» → «66.7 %–98.8 %» (punto decimal, sin ambigüedad con miles)
  function fixRange(){
    document.querySelectorAll('.stat strong').forEach(function(el){
      var m=el.textContent.match(/^\s*(\d+)[.,](\d+)\s*%\s*[–-]\s*(\d+)[.,](\d+)\s*%\s*$/);
      if(!m)return;
      var a=parseFloat(m[1]+'.'+m[2]),b=parseFloat(m[3]+'.'+m[4]);
      el.textContent=a.toFixed(1)+' %–'+b.toFixed(1)+' %';
      var card=el.closest('.stat');
      if(card&&!card.querySelector('.rangebar')){
        var bar=document.createElement('div');bar.className='rangebar';bar.setAttribute('aria-hidden','true');
        bar.innerHTML='<i style="left:'+a+'%;width:'+Math.max(b-a,1)+'%"></i>';
        var sc=document.createElement('div');sc.className='rangescale';sc.setAttribute('aria-hidden','true');
        sc.innerHTML='<span>0 %</span><span>100 %</span>';
        el.insertAdjacentElement('afterend',bar);bar.insertAdjacentElement('afterend',sc);
      }
    });
  }

  // 2 · Tabla: columna de ventaja, búsqueda y orden
  var table,tbody,busy=false,sortState={col:null,dir:1},query='';
  function enhanceRows(){
    if(busy)return;busy=true;
    try{
      var head=table.querySelector('thead tr');
      if(head&&!head.querySelector('[data-lead]')){
        var th=document.createElement('th');th.scope='col';th.textContent='Ventaja (pp)';th.setAttribute('data-lead','1');
        head.insertBefore(th,head.children[7]);
        head.querySelectorAll('th').forEach(function(h,i){h.setAttribute('data-sort',i);h.setAttribute('tabindex','0');});
      }
      tbody.querySelectorAll('tr').forEach(function(tr){
        if(tr.querySelector('td.lead'))return;
        var c=tr.children,a=num(c[2]&&c[2].textContent),b=num(c[5]&&c[5].textContent);
        var td=document.createElement('td');td.className='lead';
        if(!isNaN(a)&&!isNaN(b)){
          var d=a-b,tight=d<3;
          td.innerHTML='<span class="leadnum">'+d.toFixed(2)+' pp</span>'+(tight?' <span class="leadtag">· reñida</span>':'')+
            '<div class="leadbar'+(tight?' tight':'')+'" aria-hidden="true"><i style="width:'+Math.min(100,d*2.5)+'%"></i></div>';
          td.setAttribute('data-v',d);
        }
        tr.insertBefore(td,c[7]);
      });
      apply();
    }finally{busy=false;}
  }
  function apply(){
    var rows=Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    var q=query.trim().toLowerCase(),shown=0;
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
    var cnt=document.getElementById('tableCount');if(cnt)cnt.textContent=shown+' de '+rows.length+' regiones';
  }
  function setupTable(){
    table=document.querySelector('.tablepanel table');tbody=document.getElementById('rows');
    if(!table||!tbody)return;
    var tools=document.createElement('div');tools.className='tabletools';
    tools.innerHTML='<label class="sr" for="tableSearch" style="position:absolute;left:-9999px">Buscar región u organización</label>'+
      '<input id="tableSearch" type="search" placeholder="Buscar región, partido o candidato" autocomplete="off">'+
      '<small id="tableCount" aria-live="polite"></small><small>Clic en un encabezado para ordenar. «Ventaja»: diferencia entre 1.º y 2.º en puntos porcentuales.</small>';
    table.closest('.tablewrap').insertAdjacentElement('beforebegin',tools);
    tools.querySelector('input').addEventListener('input',function(e){query=e.target.value;apply();});
    table.querySelector('thead').addEventListener('click',function(e){
      var th=e.target.closest('th[data-sort]');if(!th)return;
      var i=+th.getAttribute('data-sort');
      sortState.dir=(sortState.col===i)?-sortState.dir:(i<=1?1:-1);sortState.col=i;
      table.querySelectorAll('th').forEach(function(h){h.removeAttribute('aria-sort');});
      th.setAttribute('aria-sort',sortState.dir===1?'ascending':'descending');apply();
    });
    table.querySelector('thead').addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){var th=e.target.closest('th[data-sort]');if(th){e.preventDefault();th.click();}}});
    new MutationObserver(enhanceRows).observe(tbody,{childList:true});
    enhanceRows();
  }

  function init(){fixRange();setupTable();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
