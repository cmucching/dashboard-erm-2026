(()=>{
 const box=document.getElementById('freshness');if(!box)return;
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const date=s=>new Date(s).toLocaleString('es-PE',{timeZone:'America/Lima',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'});
 const interval=30*60*1000;
 let revision,busy=false,lastAttempt=0,lastStatus;
 function render(s){
   const waiting=s.complete&&window.displayedElectionRevision!==s.revision;box.dataset.state=waiting?'loading':s.state;
   const title=waiting?'Nueva publicación disponible · cargando':s.mode==='downloaded'?(s.state==='stale'?'Cobertura completa verificada · algunos cortes requieren renovación':'Cobertura completa · cortes verificados'):s.state==='recent'?'Lectura completa reciente':s.state==='stale'?'Datos pendientes de renovar':'Actualización completa pendiente';
   const reading=s.mode==='downloaded'?`${Number(s.regional_count)} regiones y ${Number(s.provincial_count)} provincias. Lecturas ONPE realizadas entre ${esc(date(s.collected_from))} y ${esc(date(s.collected_until))} · hora del Perú. Consulta la hora de corte de cada territorio.`:`Última lectura completa de ONPE · ${esc(date(s.collected_until))} · hora del Perú. ${s.age_minutes===0?'Hace menos de un minuto.':`Hace ${Number(s.age_minutes)} minutos.`}`;
   box.innerHTML=`<strong>${title}</strong><p>${s.complete?reading:`Se conservan los cortes publicados: ${Number(s.regional_count)} regiones y ${Number(s.provincial_count)}/${Number(s.provincial_total)} provincias con datos. Aún no hay una lectura completa reciente de ambos mapas.`}</p><small>${s.source_cut_from?`Cortes ONPE incluidos · ${esc(s.source_cut_from)} a ${esc(s.source_cut_until)}. `:''}La hora de lectura y la hora del corte ONPE son distintas. ${s.automatic?'':'La extracción automática de ONPE está pendiente. Comprobamos nuevas publicaciones del tablero cada 30 minutos.'}</small><p><a href="https://resultadoelectoral.onpe.gob.pe/" target="_blank" rel="noopener">Consultar el cómputo oficial más reciente · ONPE</a></p><button type="button">Comprobar nueva publicación</button><small id="freshnessCheck">Tablero comprobado · ${esc(date(new Date().toISOString()))} · hora del Perú</small>`;
   box.querySelector('button').onclick=()=>check(true);
 }
 async function check(force=false){
  if(busy||(!force&&Date.now()-lastAttempt<interval)||(!force&&document.hidden))return;busy=true;lastAttempt=Date.now();
  const button=box.querySelector('button');if(button)button.disabled=true;
  try{
   const r=await fetch('api/update-status.json',{cache:'no-store'});if(!r.ok)throw Error('Estado no disponible');const s=await r.json();
   lastStatus=s;render(s);
   if((revision!==undefined&&revision!==s.revision)||(s.complete&&window.displayedElectionRevision!==s.revision))window.dispatchEvent(new CustomEvent('complete-cut-published',{detail:s}));revision=s.revision;
  }catch{
   box.dataset.state='unavailable';box.innerHTML='<strong>No se pudo comprobar una nueva publicación</strong><p>Se conserva el corte mostrado. Consulta ONPE para verificar la información más reciente.</p><button type="button">Volver a comprobar</button>';box.querySelector('button').onclick=()=>check(true);
  }finally{busy=false;const button=box.querySelector('button');if(button)button.disabled=false;}
 }
 window.addEventListener('cut-displayed',()=>{if(lastStatus)render(lastStatus);});
 window.addEventListener('cut-display-error',()=>{box.dataset.state='unavailable';box.innerHTML='<strong>No se pudo cargar la publicación más reciente</strong><p>Se conserva el corte anterior mostrado en el mapa. Vuelve a comprobar o consulta ONPE.</p><button type="button">Volver a comprobar</button>';box.querySelector('button').onclick=()=>check(true);});
 check();setInterval(check,interval);document.addEventListener('visibilitychange',()=>{if(!document.hidden)check();});window.addEventListener('focus',()=>check());
})();
