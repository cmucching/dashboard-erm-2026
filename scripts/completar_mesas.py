#!/usr/bin/env python3
"""Completa mesas-<ubigeo>.jsonl con mesas fuera del bloque contiguo (p. ej. 9033xx).

Lista las actas del distrito con /presentacion-backend/actas (paginado, 50 por página; ambas elecciones),
compara con el .jsonl y baja con actas/buscar/mesa solo las que faltan. Un solo flujo, pausa >= 0.5 s.
Uso: completar_mesas.py <ubigeo> <mesas-ubigeo.jsonl>"""
import json, sys, time, pathlib
from playwright.sync_api import sync_playwright
BASE = "https://resultadoelectoral.onpe.gob.pe"
JS = """async u=>{const ac=new AbortController();setTimeout(()=>ac.abort(),20000);try{const r=await fetch(u,{headers:{Accept:'application/json'},signal:ac.signal});return [r.status,await r.text()]}catch(e){return [0,'']}}"""
def compacta(a):
    return {"m": a["codigoMesa"], "e": a["idEleccion"], "u": a["idUbigeo"], "lc": a["codigoLocalVotacion"],
            "ln": a["nombreLocalVotacion"], "cp": a.get("centroPoblado"),
            "el": a["totalElectoresHabiles"], "as": a["totalAsistentes"], "em": a["totalVotosEmitidos"],
            "va": a["totalVotosValidos"], "st": a["codigoEstadoActa"],
            "v": {d["adCodigo"]: d["adVotos"] for d in a["detalle"] if d["adVotos"] is not None}}
ub = int(sys.argv[1]); out = pathlib.Path(sys.argv[2])
hechas = {json.loads(l)["m"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()} if out.exists() else set()
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto(BASE + "/main/alcance-electoral", wait_until="networkidle", timeout=60000)
    def get(url):
        for i in range(6):
            st, t = pg.evaluate(JS, url)
            if st == 200 and t: return json.loads(t)["data"]
            if st == 204: return []
            if st in (401, 403): raise SystemExit(f"ONPE bloqueó la consulta ({st}); se detiene")
            print(f"  estado {st}, reintento {i+1}/6", flush=True); time.sleep(5 * (i + 1))
            try: pg.goto(BASE + "/main/alcance-electoral", wait_until="networkidle", timeout=60000)
            except Exception: pass
        raise SystemExit("sin respuesta; se detiene")
    todas = set(); pag = 0
    while True:
        d = get(f"/presentacion-backend/actas?pagina={pag}&tamanio=50&idEleccion=4&idAmbitoGeografico=1&idUbigeo={ub}")
        todas |= {c["codigoMesa"] for c in d["content"]}; pag += 1
        if pag >= d["totalPaginas"]: break
        time.sleep(0.5)
    falt = sorted(todas - hechas)
    print(f"{ub}: {len(todas)} mesas en ONPE, {len(hechas)} en archivo, faltan {len(falt)}: {falt[:15]}", flush=True)
    with out.open("a", encoding="utf-8") as f:
        for c in falt:
            for a in get(f"/presentacion-backend/actas/buscar/mesa?codigoMesa={c}&idEleccion=4"):
                if a["idEleccion"] in (3, 4) and a["idUbigeo"] == ub:
                    f.write(json.dumps(compacta(a), ensure_ascii=False, separators=(",", ":")) + "\n")
            time.sleep(0.6)
    b.close()
print("listo")
