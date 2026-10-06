import {normalize,leadingOrganizations} from './district-data.js';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=n=>new Intl.NumberFormat('es-PE').format(n);
const percent=n=>new Intl.NumberFormat('en-US',{minimumFractionDigits:3,maximumFractionDigits:3}).format(n)+' %';
const date=v=>new Intl.DateTimeFormat('es-PE',{timeZone:'America/Lima',dateStyle:'short',timeStyle:'medium'}).format(new Date(v));
const hash=text=>{let h=2166136261;for(const c of normalize(text))h=Math.imul(h^c.codePointAt(0),16777619);return h>>>0;};
export const districtFeatureKey=f=>typeof f?.properties?.key==='string'&&/^distrital:\d{6}$/.test(f.properties.key)?f.properties.key:null;
export function districtFeatures(geo,scope=''){
 if(geo?.crs!=='EPSG:4326'||!Array.isArray(geo.features)||!geo.features.length)throw Error('Cartografía distrital incompleta.');
 return geo.features.filter(f=>f.geometry&&['Polygon','MultiPolygon'].includes(f.geometry.type)&&(!scope||f.properties?.province_code===scope));
}
export function partyColor(name){const h=hash(name)%36000/100,s=.66,l=.43,a=s*Math.min(l,1-l);const channel=n=>{const k=(n+h/30)%12;return Math.round(255*(l-a*Math.max(-1,Math.min(k-3,9-k,1)))).toString(16).padStart(2,'0');};return '#'+channel(0)+channel(8)+channel(4);}
export async function createDistrictMap({element,scope='',lookup,onSelect,feedback,legend,textureInput}){
 let map;
 try{
  if(!window.L)throw Error('El navegador no pudo cargar el mapa.');
  const [geometryResponse,registryResponse]=await Promise.all([fetch('/district-geography.json',{cache:'force-cache'}),fetch('/provincias.json',{cache:'no-cache'})]);
  if(!geometryResponse.ok)throw Error('La cartografía distrital no está disponible.');
  const geometry=await geometryResponse.json(),features=districtFeatures(geometry,scope);if(!features.length)throw Error('No hay geometría distrital para este ámbito.');
  const colors=new Map();if(registryResponse.ok){const registry=await registryResponse.json();for(const o of registry.organizations||[])if(/^#[0-9A-F]{6}$/i.test(o.color))colors.set(normalize(o.party),o.color);}
  const color=name=>{const key=normalize(name);if(!colors.has(key))colors.set(key,partyColor(key));return colors.get(key);};
  // Initialize the view before adding paths so the shared SVG renderer has bounds.
  element.replaceChildren();map=L.map(element,{zoomControl:false,minZoom:4,maxZoom:15,zoomSnap:.25,scrollWheelZoom:true,touchZoom:true,keyboard:true,zoomAnimation:!matchMedia('(prefers-reduced-motion: reduce)').matches,maxBounds:[[-50,-100],[15,-45]],maxBoundsViscosity:.6}).setView([-9.19,-75.015],5);
  L.control.zoom({position:'topleft',zoomInTitle:'Acercar (+)',zoomOutTitle:'Alejar (−)'}).addTo(map);L.control.scale({position:'bottomleft',imperial:false,maxWidth:100}).addTo(map);
  let baseLoaded=0,baseErrors=0,selectedKey=null,visibleKeys=null;
  const base=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',{maxZoom:16,maxNativeZoom:16,noWrap:true,keepBuffer:1,updateWhenIdle:true,updateWhenZooming:false,bounds:[[-50,-100],[15,-45]],attribution:'Fondo: Esri, HERE, Garmin, © colaboradores de OpenStreetMap'});
  base.on('tileload',()=>{baseLoaded++;feedback.textContent='';});base.on('tileerror',()=>{baseErrors++;if(!baseLoaded&&baseErrors>=3)feedback.textContent='El fondo cartográfico no está disponible; los resultados distritales siguen visibles.';});
  const layers=new Map(),renderer=L.svg({padding:.4});
  function tooltip(feature){
   const key=districtFeatureKey(feature),t=key?lookup(key):null,r=t?.record,top=leadingOrganizations(r),name=t?.district||feature.properties.district||'Distrito';
   let body=`<strong class="district-tip-title">${esc(name)}</strong><span class="district-tip-meta">${esc((t?.province||feature.properties.province||'')+' · '+(t?.department||feature.properties.department||''))}</span>`;
   if(r){body+=top.length?top.slice(0,2).map((p,i)=>`<div class="district-tip-rank"><img src="${esc(p.symbol_url)}" alt=""><span><small>${i+1}.º puesto</small><strong>${esc(p.organization)}</strong><b>${percent(p.pct_valid)}</b></span></div>`).join(''):'<p>Sin votos válidos en este corte. No se identifica una organización líder.</p>';body+=`<p class="district-tip-meta">Actas contabilizadas: ${percent(r.counted_pct)}<br>Corte ONPE: ${esc(date(r.source_updated_at))}<br>Candidaturas distritales pendientes de contrastar con JNE.</p>`;}
   else body+=`<p>${!key?'Sin cruce electoral verificado para esta geometría.':t?.status==='not_applicable'?'Sin elección distrital propia, según las opciones oficiales de ONPE.':'Pendiente de incorporar al tablero; ONPE puede tener resultados disponibles.'}</p>`;
   return body;
  }
  const group=L.geoJSON({type:'FeatureCollection',features},{renderer,style:{color:'#FFFFFF',weight:.8,fillColor:'#CAD3D9',fillOpacity:.84},onEachFeature(feature,layer){
   const key=districtFeatureKey(feature),id=key||'unmapped:'+feature.properties.inei_id;layers.set(id,layer);layer.bindTooltip(()=>tooltip(feature),{sticky:true,direction:'auto',className:'district-map-tooltip',opacity:1});
   if(key)layer.on('click',()=>onSelect(key));
   layer.on('add',()=>{const p=layer.getElement();if(!p)return;p.classList.add('geo-feature');p.dataset.districtKey=key||'';p.setAttribute('aria-label',(feature.properties.district||'Distrito')+(key?' · consulta electoral':' · sin cruce verificado'));if(key){p.setAttribute('role','button');p.setAttribute('tabindex','0');p.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(key);}if(e.key==='Escape')layer.closeTooltip();});p.addEventListener('focus',()=>layer.openTooltip());p.addEventListener('blur',()=>layer.closeTooltip());}});
  }}).addTo(map);
  function fit(){const active=[...layers.values()].filter(l=>map.hasLayer(l));if(active.length)map.fitBounds(L.featureGroup(active).getBounds(),{padding:[20,20],maxZoom:12,animate:false});}
  const home=L.control({position:'topleft'});home.onAdd=()=>{const bar=L.DomUtil.create('div','leaflet-bar'),button=L.DomUtil.create('button','geo-home',bar);button.type='button';button.textContent='⌂';button.title='Encuadrar distritos del filtro';button.setAttribute('aria-label',button.title);L.DomEvent.disableClickPropagation(bar);button.addEventListener('click',fit);return bar;};home.addTo(map);
  const background=L.control({position:'topright'});background.onAdd=()=>{const control=L.DomUtil.create('div','geo-layer-control');control.innerHTML='<label><input type="checkbox" checked> Fondo gris</label>';L.DomEvent.disableClickPropagation(control);L.DomEvent.disableScrollPropagation(control);control.querySelector('input').addEventListener('change',e=>{if(e.target.checked)base.addTo(map);else{map.removeLayer(base);feedback.textContent='';}});return control;};background.addTo(map);
  base.addTo(map);fit();
  function update({rows,selected,fitBounds=false,filters={}}){
   selectedKey=selected;visibleKeys=new Set(rows.map(t=>t.key));
   const svg=element.querySelector('.leaflet-overlay-pane svg');let defs=svg?.querySelector('defs[data-district-patterns]');if(svg&&!defs){defs=document.createElementNS('http://www.w3.org/2000/svg','defs');defs.dataset.districtPatterns='true';svg.prepend(defs);}
   if(defs)defs.innerHTML='';const used=new Set(),winners=new Map();
   for(const [id,layer] of layers){const key=districtFeatureKey(layer.feature),t=key?lookup(key):null,show=key?visibleKeys.has(key):!scope&&(!filters.department||normalize(layer.feature.properties.department)===normalize(filters.department))&&(!filters.province||layer.feature.properties.province_code===filters.province)&&(!filters.search||normalize(layer.feature.properties.district).includes(normalize(filters.search)));if(show){if(!map.hasLayer(layer))layer.addTo(map);}else{if(map.hasLayer(layer))map.removeLayer(layer);continue;}
    const winner=leadingOrganizations(t?.record)[0],fill=winner?color(winner.organization):t?.record?'#DCE9F0':t?.status==='not_applicable'?'#EDF0F2':'#CAD3D9';
    if(winner){const entry=winners.get(winner.organization)||{count:0,color:fill};entry.count++;winners.set(winner.organization,entry);}
    layer.setStyle({fillColor:fill,color:key===selectedKey?'#082F49':'#FFFFFF',weight:key===selectedKey?2.6:.8,fillOpacity:.86});
    const p=layer.getElement();if(!p)continue;
    if(winner&&textureInput.checked&&defs){const pattern='district-org-'+hash(winner.organization).toString(16),type=hash(winner.organization)%4;if(!used.has(pattern)){used.add(pattern);defs.insertAdjacentHTML('beforeend',`<pattern id="${pattern}" patternUnits="userSpaceOnUse" width="8" height="8"><rect width="8" height="8" fill="${fill}"/>${type===0?'<path d="M-2 2L2-2M0 8L8 0M6 10L10 6" stroke="#FFFFFF" stroke-opacity=".3" stroke-width="1"/>':type===1?'<path d="M0 4H8" stroke="#FFFFFF" stroke-opacity=".3" stroke-width="1"/>':type===2?'<circle cx="2" cy="2" r=".8" fill="#FFFFFF" fill-opacity=".4"/>':'<path d="M0 4H8M4 0V8" stroke="#FFFFFF" stroke-opacity=".25" stroke-width=".8"/>'}</pattern>`);}p.style.fill='url(#'+pattern+')';}else p.style.fill=fill;
    p.classList.toggle('district-map-selected',key===selectedKey);
   }
   const chosen=layers.get(selectedKey);if(chosen&&map.hasLayer(chosen))chosen.bringToFront();
   legend.innerHTML='<span><i style="background:#CAD3D9"></i>Pendiente de incorporar</span><span><i style="background:#EDF0F2;border:1px solid #AABBC4"></i>Sin elección distrital propia</span><span><i style="background:#DCE9F0;border:1px solid #AABBC4"></i>Corte incorporado · sin votos válidos</span>'+[...winners].sort((a,b)=>b[1].count-a[1].count||a[0].localeCompare(b[0],'es')).map(([name,v])=>`<span><i style="background:${v.color}"></i>${esc(name)} <b>${number(v.count)}</b></span>`).join('');
   if(fitBounds)fit();
  }
  return {update,fit,focus(key){const layer=layers.get(key);if(layer&&map.hasLayer(layer)){layer.bringToFront();map.fitBounds(layer.getBounds(),{padding:[35,35],maxZoom:13,animate:false});}else feedback.textContent='Este distrito no dispone de un polígono con cruce cartográfico verificado; sus datos siguen disponibles en la consulta.';},dispose(){map.remove();}};
 }catch(error){if(map)map.remove();element.innerHTML='<p class="district-map-unavailable">El mapa distrital no está disponible. Puedes consultar los mismos resultados en la tabla.</p>';feedback.textContent=error.message;textureInput.disabled=true;return null;}
}
