import {partyColor} from './district-map.js';
const $=s=>document.querySelector(s),f=(n,d=1)=>Number(n).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const tc=s=>String(s||'').toLowerCase().replace(/(^|[\s(\-])(\S)/g,(m,a,b)=>a+b.toUpperCase());
const VIEW=document.body.dataset.view,LIMA='140100';
const fmt=s=>{try{return new Intl.DateTimeFormat('es-PE',{timeZone:'America/Lima',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(s)).replace(',',' ·')}catch(e){return s}};
let R=[],ALL=[],P={},sel=null,filt=null,dep='',prov='',q='',sortK='margin',limit=30,showPend=false,rank=[];
const svg=$('#map'),maxM=10,tk=[0,2,4,6,8,10];
$('#sc').innerHTML=tk.map(v=>`<span style="left:${v/maxM*100}%">${v}</span>`).join('');
const scope=c=>VIEW==='lima'?c.province_code===LIMA&&c.level==='distrital':c.level==='distrital';
function view(){let a=R.filter(r=>(filt===null||r.org===filt)&&(!dep||r.dep===dep)&&(!prov||r.prov===prov)&&(!q||(r.name+' '+r.prov+' '+r.dep+' '+r.party).toLowerCase().includes(q)));
 a=a.slice().sort({margin:(x,y)=>x.m-y.m,big:(x,y)=>y.m-x.m,actas:(x,y)=>x.adv-y.adv,name:(x,y)=>x.name.localeCompare(y.name,'es')}[sortK]);return a}
function pend(){return showPend?ALL.filter(c=>!c.rec&&(!dep||c.dep===dep)&&(!prov||c.prov===prov)&&(!q||(c.name+' '+c.prov+' '+c.dep).toLowerCase().includes(q))&&filt===null):[]}
function rows(){
 const a=view(),pe=pend();const lim=sel&&a.findIndex(r=>r.id===sel)>=limit?Infinity:limit;const v=a.slice(0,lim);
 $('#cnt').textContent=`${a.length} de ${R.length} con resultados`;
 let h=v.map(r=>`<div class="row${r.m<3?' close':''}${sel===r.id?' sel':''}" data-id="${r.id}" style="--c:${r.color}" tabindex="0" role="button" aria-expanded="${sel===r.id}">
 <div class="nm">${esc(tc(r.name))}<small>${esc(tc(r.prov))}${VIEW==='lima'?'':' · '+esc(tc(r.dep))} · ${esc(tc(r.party))}</small></div>
 <div class="dumb"><div class="grid">${tk.slice(1).map(x=>`<i style="left:${x/maxM*100}%"></i>`).join('')}<i class="thr" style="left:${3/maxM*100}%"></i></div><div class="bar" style="width:${Math.min(Math.max(r.m/maxM*100,.8),100)}%${r.m>maxM?';border-radius:0':''}"></div>${r.m>maxM?'<div class="ov">▸ sigue</div>':''}<div class="bl"><b>${f(r.p1,2)}</b> % <span>vs</span> ${f(r.p2,2)} %</div></div>
 <div class="mg"><b>${f(r.m,2)}</b><small>pp · ${f(r.adv,1)} % actas</small><div class="act"><i style="width:${r.adv}%"></i></div></div>
 <div class="more">${r.top.map((c,i)=>`<div class="cand" style="--c:${i?'#8A98A3':r.color}"><img src="${esc(c.symbol_url||'')}" alt="" onerror="this.style.visibility='hidden'"><div><b>${esc(c.organization)}</b><span>${i+1}.º lugar</span><em>${f(c.pct_valid,2)} %</em><span>${c.votes.toLocaleString('en-US')} votos válidos</span></div></div>`).join('')}<div class="cand" style="--c:#C9C6BE;grid-column:1/-1"><div><span>Actas: ${r.ca.toLocaleString('en-US')} contabilizadas de ${r.ta.toLocaleString('en-US')} · ${r.jee} para JEE · ${r.pe} pendientes · ${r.org_n} organizaciones</span><span>Corte ONPE: ${esc(fmt(r.upd))}</span></div></div></div></div>`).join('');
 if(showPend)h+=pe.slice(0,60).map(c=>`<div class="row" style="--c:#C9C6BE"><div class="nm">${esc(tc(c.name))}<small>${esc(tc(c.prov))} · ${esc(tc(c.dep))}</small></div><div class="dumb"><div class="bl" style="bottom:6px;font-style:italic">${c.status==='not_applicable'?'Sin elección distrital propia':'Pendiente de incorporar'}</div></div><div class="mg"><small>—</small></div></div>`).join('');
 $('#rows').innerHTML=h||'<div class="empty2">No hay distritos con ese filtro.</div>';
 $('#more').hidden=!(lim!==Infinity&&a.length>limit);
 const ids=new Set(a.map(r=>r.id)),f_=!!(filt!==null||dep||prov||q);
 svg.classList.toggle('dim',f_);svg.querySelectorAll('path').forEach(p=>{p.classList.toggle('on',ids.has(p.dataset.id));p.classList.toggle('sel',p.dataset.id===sel)});
}
function chips(){const top=rank.slice(0,12);$('#chips').innerHTML=top.map(([o,n])=>{const r=R.find(x=>x.org===o);return `<button class="chip" aria-pressed="${filt===o}" data-o="${esc(o)}"><i style="background:${r.color}"></i>${esc(tc(o))}<b>${n}</b></button>`}).join('')+(rank.length>12?`<span class="pillnote" style="align-self:center">+${rank.length-12} organizaciones más</span>`:'')}
function zoom(){let S=ALL.filter(c=>c.b&&(!dep||c.dep===dep)&&(!prov||c.prov===prov));if(VIEW==='lima'&&!prov)S=ALL.filter(c=>c.b);
 if(!dep&&!prov&&VIEW!=='lima'){svg.setAttribute('viewBox','0 0 760 1124');return}
 const x0=Math.min(...S.map(c=>c.b[0])),y0=Math.min(...S.map(c=>c.b[1])),x1=Math.max(...S.map(c=>c.b[2])),y1=Math.max(...S.map(c=>c.b[3])),pw=(x1-x0)*.08,ph=(y1-y0)*.08;svg.setAttribute('viewBox',`${x0-pw} ${y0-ph} ${x1-x0+2*pw} ${y1-y0+2*ph}`)}
function pick(id,scroll){sel=sel===id?null:id;rows();if(sel&&scroll)document.querySelector(`.row[data-id="${sel}"]`)?.scrollIntoView({block:'center',behavior:'smooth'})}
function head(m){
 const close=R.filter(r=>r.m<3),by={};R.forEach(r=>by[r.org]=(by[r.org]||0)+1);rank=Object.entries(by).sort((a,b)=>b[1]-a[1]);
 const A=R.map(r=>r.adv),mn=Math.min(...A),mx=Math.max(...A),exp=VIEW==='lima'?42:m.expected_distrital;
 const done=VIEW==='lima'?R.length:m.distrital;
 if(VIEW==='lima'){const t=M.top;const mg=t[0].pct_valid-t[1].pct_valid;
  $('#h1').innerHTML=`Alcaldía de Lima Metropolitana.<br><em>${tc(t[0].organization)} va primero por ${f(mg,2)} puntos.</em>`;
  $('#sub').textContent=`Con ${f(M.counted_pct,3)} % de actas contabilizadas, ${tc(t[0].organization)} suma ${f(t[0].pct_valid,3)} % de los votos válidos y ${tc(t[1].organization)}, ${f(t[1].pct_valid,3)} %. Abajo, los ${R.length} distritos de la provincia.`}
 else{$('#h1').innerHTML=`${R.length} distritos con resultados.<br><em>${close.length} se deciden por menos de 3 puntos.</em>`;
  $('#sub').textContent=`La descarga distrital sigue en curso: ${f(done,0)} de ${f(exp,0)} elecciones incorporadas, más ${m.not_applicable} territorios sin elección distrital propia. ${rank.length?tc(rank[0][0])+' lidera en '+rank[0][1]+' distritos.':''}`}
 $('#kpis').innerHTML=`<div class="hot"><b>${close.length}</b><span>distritos con ventaja menor a 3 pp</span></div><div><b>${f(done,0)}<small style="font-size:.5em;font-weight:600"> / ${f(exp,0)}</small></b><span>distritos con resultados incorporados</span></div><div><b>${f(mn)}–${f(mx)} %</b><span>actas contabilizadas, según distrito</span></div>`;
 const us=R.map(r=>new Date(r.upd)).filter(d=>!isNaN(d)).sort((a,b)=>a-b);
 $('#cut').innerHTML=`<i></i><span>Cortes ONPE por distrito: <b>${fmt(us[0])}</b> a <b>${fmt(us[us.length-1])}</b> · hora de Perú (UTC−5). Cada distrito conserva su propia hora de corte.</span>`+(VIEW==='lima'?'':`<span class="pillnote">Descarga en curso</span>`);
}
let M=null;
Promise.all([fetch('/api/municipal-data',{cache:'no-store'}).then(r=>r.json()),fetch('/district-paths.json').then(r=>r.json()),VIEW==='lima'?fetch('/lima-metropolitana-onpe.json').then(r=>r.json()):null]).then(([d,paths,lima])=>{
 const recs=new Map(d.records.filter(r=>r.level==='distrital').map(r=>[r.ubigeo,r]));
 ALL=d.coverage.filter(scope).map(c=>({id:c.ubigeo,name:c.district,prov:c.province,dep:c.department,status:c.status,d:(paths[c.ubigeo]||{}).d,b:(paths[c.ubigeo]||{}).b,rec:recs.get(c.ubigeo)||null}));
 R=ALL.filter(c=>c.rec&&c.rec.valid_votes>0&&c.rec.organizations.length>0).map(c=>{const r=c.rec,o=[...r.organizations].sort((a,b)=>b.votes-a.votes),t=o.slice(0,2),col=partyColor(t[0].organization);return{id:c.id,name:c.name,prov:c.prov,dep:c.dep,org:t[0].organization,party:t[0].organization,color:col,p1:t[0].pct_valid,p2:t[1]?t[1].pct_valid:0,m:t[0].pct_valid-(t[1]?t[1].pct_valid:0),adv:r.counted_pct,upd:r.source_updated_at,top:t,ca:r.counted_actas,ta:r.total_actas,jee:r.jee_actas,pe:r.pending_actas,org_n:r.organization_count}});
 const byId=new Map(R.map(r=>[r.id,r]));
 svg.innerHTML=ALL.filter(c=>c.d).map(c=>{const r=byId.get(c.id);return `<path data-id="${c.id}" d="${c.d}" fill="${r?r.color:'#E4E2DC'}" class="${r?'':'nodata'}"><title>${esc(tc(c.name))}${r?'':' · sin resultados aún'}</title></path>`}).join('');
 if(lima){const m=lima.metropolitan.total_before;M={top:[...m.organizations].sort((a,b)=>b.votes-a.votes).slice(0,2),counted_pct:m.counted_pct};
  $('#duel').innerHTML=M.top.map((o,i)=>`<div class="cand" style="--c:${i?'#8A98A3':partyColor(o.organization)}"><img src="${esc(o.symbol_url)}" alt=""><div><b>${esc(o.organization)}</b><span>${i+1}.º lugar · alcaldía metropolitana</span><em>${f(o.pct_valid,3)} %</em><span>${o.votes.toLocaleString('en-US')} votos válidos</span></div></div>`).join('');
  $('#duelnote').textContent=`Actas contabilizadas: ${f(m.counted_pct,3)} % (${m.counted_actas.toLocaleString('en-US')} de ${m.total_actas.toLocaleString('en-US')}; ${m.jee_actas.toLocaleString('en-US')} para envío al JEE). Corte ONPE: ${fmt(lima.metropolitan.metadata.source_cut_until)}`}
 const deps=[...new Set(ALL.map(c=>c.dep))].sort((a,b)=>a.localeCompare(b,'es'));
 if($('#dep'))deps.forEach(x=>$('#dep').insertAdjacentHTML('beforeend',`<option value="${esc(x)}">${esc(tc(x))}</option>`));
 head(d.metadata);chips();zoom();rows();
}).catch(e=>{console.error(e);$('#h1').textContent='No se pudo cargar el corte distrital';$('#sub').textContent='Recarga la página en unos minutos.'});
$('#rows').addEventListener('click',e=>{const r=e.target.closest('.row[data-id]');if(r)pick(r.dataset.id,false)});
$('#rows').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){const r=e.target.closest('.row[data-id]');if(r){e.preventDefault();pick(r.dataset.id,false)}}});
svg.addEventListener('click',e=>{const p=e.target.closest('path');if(!p)return;if(p.classList.contains('nodata'))return;pick(p.dataset.id,true)});
const tip=$('#tip');svg.addEventListener('mousemove',e=>{const p=e.target.closest('path');if(!p){tip.style.display='none';return}const r=R.find(x=>x.id===p.dataset.id),c=ALL.find(x=>x.id===p.dataset.id);tip.innerHTML=r?`<b>${esc(tc(r.name))}</b>${esc(tc(r.prov))}<br>1.º ${esc(tc(r.party))} · ${f(r.p1,2)} %<br>Ventaja ${f(r.m,2)} pp`:`<b>${esc(tc(c.name))}</b>${c.status==='not_applicable'?'Sin elección distrital propia':'Resultado pendiente de incorporar'}`;tip.style.display='block';tip.style.left=Math.min(e.clientX+14,innerWidth-250)+'px';tip.style.top=(e.clientY+14)+'px'});
svg.addEventListener('mouseleave',()=>tip.style.display='none');
$('#sort').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;sortK=b.dataset.k;document.querySelectorAll('#sort button').forEach(x=>x.setAttribute('aria-pressed',x===b));limit=30;rows()});
$('#chips').addEventListener('click',e=>{const b=e.target.closest('.chip');if(!b)return;const o=b.dataset.o;filt=filt===o?null:o;chips();limit=30;rows()});
$('#dep')?.addEventListener('change',e=>{dep=e.target.value;prov='';sel=null;const ps=[...new Set(ALL.filter(c=>!dep||c.dep===dep).map(c=>c.prov))].sort((a,b)=>a.localeCompare(b,'es'));$('#prov').innerHTML='<option value="">Todas las provincias</option>'+ps.map(x=>`<option value="${esc(x)}">${esc(tc(x))}</option>`).join('');$('#prov').disabled=!dep;zoom();limit=30;rows()});
$('#prov')?.addEventListener('change',e=>{prov=e.target.value;sel=null;zoom();limit=30;rows()});
$('#q').addEventListener('input',e=>{q=e.target.value.trim().toLowerCase();limit=30;rows()});
$('#pend')?.addEventListener('change',e=>{showPend=e.target.checked;rows()});
$('#more').addEventListener('click',()=>{limit+=40;rows()});
