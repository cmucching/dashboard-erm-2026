// Leaflet 1.9.4. Only the visible viewport requests OSM tiles; no prefetch or offline download.
// Electoral data stays independent of the optional background. Existing SVG is the fallback.
(()=>{
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 window.ElectionMapNavigation={async create(options){
  const source=document.getElementById(options.sourceId||'map');if(!source||!window.L)return null;
  let wrapper,map,feedback;
  try{
   const response=await fetch('/map-geography.json');if(!response.ok)throw Error('Cartografía no disponible');
   const geography=await response.json(),features=geography[options.kind]?.features;
   if(!Array.isArray(features)||features.length!==(options.kind==='regional'?26:196))throw Error('Cartografía incompleta');
   wrapper=document.createElement('div');wrapper.className='geo-map';wrapper.id='geo-map';wrapper.setAttribute('aria-label',options.kind==='regional'?'Mapa navegable de regiones del Perú':'Mapa navegable de provincias del Perú');
   source.parentElement.classList.add('geo-map-host');source.before(wrapper);
   const guidance=document.createElement('div');guidance.className='geo-guidance';guidance.innerHTML='<span>Acerca con +/− o la rueda · Arrastra para mover · Pellizca en pantalla táctil</span><span>Cartografía electoral: INEI 2023</span>';source.before(guidance);
   feedback=document.createElement('p');feedback.className='geo-feedback';feedback.setAttribute('role','status');source.before(feedback);
   map=L.map(wrapper,{zoomControl:false,minZoom:4,maxZoom:13,zoomSnap:.25,zoomDelta:1,scrollWheelZoom:true,touchZoom:true,keyboard:true,zoomAnimation:!matchMedia('(prefers-reduced-motion: reduce)').matches,maxBounds:[[-50,-100],[15,-45]],maxBoundsViscosity:.6});
   L.control.zoom({position:'topleft',zoomInTitle:'Acercar (+)',zoomOutTitle:'Alejar (−)'}).addTo(map);
   L.control.scale({position:'bottomleft',imperial:false,maxWidth:100}).addTo(map);
   let visible=null,tilesLoaded=0,tileErrors=0,baseEnabled=true;
   const basemap=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',{maxZoom:16,maxNativeZoom:16,noWrap:true,keepBuffer:1,updateWhenIdle:true,updateWhenZooming:false,bounds:[[-50,-100],[15,-45]],attribution:'Fondo: Esri, HERE, Garmin, © colaboradores de OpenStreetMap'});
   basemap.on('tileload',()=>{tilesLoaded++;feedback.textContent='';});
   basemap.on('tileerror',()=>{tileErrors++;if(!tilesLoaded&&tileErrors>=3)feedback.textContent='El fondo cartográfico no está disponible. Los resultados electorales y la navegación siguen visibles.';});
   const renderer=L.svg({padding:.4}),layers=new Map();
   const isVisible=id=>!visible||visible.has(id);
   const group=L.geoJSON({type:'FeatureCollection',features},{renderer,style:{color:'#FFFFFF',weight:1,fillColor:'#CBD3D9',fillOpacity:.86},onEachFeature(feature,layer){
    const id=feature.properties.id;layers.set(id,layer);
    layer.on('add',()=>{
     const p=layer.getElement();if(!p)return;p.classList.add('geo-feature');p.dataset.territory=id;
     if(!feature.properties.excluded){p.setAttribute('role','button');p.setAttribute('tabindex','0');p.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();options.select(id);}if(e.key==='Escape')options.hideTip?.();});
      p.addEventListener('focus',()=>{const b=p.getBoundingClientRect();options.showTip?.(id,p,b.right,b.top+b.height/2);});p.addEventListener('blur',()=>options.hideTip?.());}
    });
    layer.on('click',()=>{if(!feature.properties.excluded)options.select(id);});
    layer.on('mouseover',e=>{if(!feature.properties.excluded&&e.originalEvent?.pointerType!=='touch')options.showTip?.(id,layer.getElement(),e.originalEvent?.clientX,e.originalEvent?.clientY);});
    layer.on('mousemove',e=>{if(!feature.properties.excluded&&e.originalEvent?.pointerType!=='touch')options.showTip?.(id,layer.getElement(),e.originalEvent?.clientX,e.originalEvent?.clientY);});
    layer.on('mouseout',()=>options.hideTip?.());
    if(feature.properties.excluded)layer.bindTooltip('Lima Metropolitana · sin elección de gobernador regional',{sticky:true});
   }}).addTo(map);
   const prefix='geo-'+options.kind+'-';
   function patterns(){
    const svg=wrapper.querySelector('.leaflet-overlay-pane svg'),original=source.querySelector('defs');if(!svg||!original)return;
    svg.querySelector('defs[data-electoral-patterns]')?.remove();const defs=original.cloneNode(true);defs.dataset.electoralPatterns='true';
    defs.querySelectorAll('[id]').forEach(p=>p.id=prefix+p.id);svg.prepend(defs);
   }
   function refresh(){
    patterns();for(const [id,layer] of layers){
     if(isVisible(id)){if(!map.hasLayer(layer))layer.addTo(map);}else {if(map.hasLayer(layer))map.removeLayer(layer);continue;}
     const feature=layer.feature,row=options.row(id),style=options.style(id,row)||{},excluded=feature.properties.excluded;
     layer.setStyle({color:style.selected?'#082F49':'#FFFFFF',weight:style.selected?2.5:.8,opacity:1,fillColor:style.color||'#CBD3D9',fillOpacity:style.dim ? .17 : excluded ? .76 : .87});
     const p=layer.getElement();if(p){p.style.fill=style.pattern?'url(#'+prefix+style.pattern+')':style.color||'#CBD3D9';p.style.stroke=style.selected?'#082F49':'#FFFFFF';p.style.strokeWidth=style.selected?'2.5px':'.8px';p.classList.toggle('geo-selected',!!style.selected);p.setAttribute('aria-label',options.label?.(id,row)||feature.properties.name||feature.properties.province||id);}
    }
    const chosen=layers.get(options.selected?.());if(chosen?.getElement())chosen.bringToFront();
   }
   function fit(){const shown=[...layers].filter(([id])=>isVisible(id)).map(([,layer])=>layer);if(shown.length)map.fitBounds(L.featureGroup(shown).getBounds(),{padding:[22,22],animate:false,maxZoom:11});}
   const home=L.control({position:'topleft'});home.onAdd=()=>{const bar=L.DomUtil.create('div','leaflet-bar'),button=L.DomUtil.create('button','geo-home',bar);button.type='button';button.textContent='⌂';button.title='Encuadrar la vista';button.setAttribute('aria-label','Encuadrar la vista');L.DomEvent.disableClickPropagation(bar);button.addEventListener('click',fit);return bar;};home.addTo(map);
   const baseControl=L.control({position:'topright'});baseControl.onAdd=()=>{const control=L.DomUtil.create('div','geo-layer-control');control.innerHTML='<label><input type="checkbox" checked> Fondo gris</label>';L.DomEvent.disableClickPropagation(control);L.DomEvent.disableScrollPropagation(control);control.querySelector('input').addEventListener('change',e=>{baseEnabled=e.target.checked;if(baseEnabled)basemap.addTo(map);else {map.removeLayer(basemap);feedback.textContent='';}});return control;};baseControl.addTo(map);
   map.on('movestart zoomstart',()=>options.hideTip?.());
   const resize=new ResizeObserver(()=>map.invalidateSize({pan:false}));resize.observe(wrapper);
   const api={map,refresh,fit,scope(ids,fitView=true){visible=ids?new Set(ids):null;refresh();if(fitView)fit();}};
   source.classList.add('map-source-ready');source.setAttribute('aria-hidden','true');source.querySelectorAll('[tabindex]').forEach(p=>p.setAttribute('tabindex','-1'));
   refresh();fit();basemap.addTo(map);
   return api;
  }catch(error){map?.remove();wrapper?.remove();source.parentElement.classList.remove('geo-map-host');source.classList.remove('map-source-ready');source.removeAttribute('aria-hidden');console.warn('Se conserva el mapa electoral de respaldo:',error.message);return null;}
 }};
})();
