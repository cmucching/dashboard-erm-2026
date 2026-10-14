#!/usr/bin/env python3
"""Baja de ONPE las actas por mesa de un distrito (ERM 2026) y las guarda en formato compacto.

Uso:  python3 scripts/bajar_mesas.py 140130 out/mesas-140130.jsonl [--pausa 0.5]
- Localiza el rango de mesas del ubigeo por bisección (las mesas están ordenadas por ubigeo).
- Consulta /presentacion-backend/actas/buscar/mesa desde la propia página de ONPE (mismo origen).
- Reanuda: si el .jsonl ya existe, omite las mesas ya guardadas.
- Guarda por acta: mesa, elección (3 provincial, 4 distrital), local de votación, electores, votos por organización.
"""
import json, sys, time, argparse, pathlib
from playwright.sync_api import sync_playwright

BASE = "https://resultadoelectoral.onpe.gob.pe"
URL = "/presentacion-backend/actas/buscar/mesa?codigoMesa={c:06d}&idEleccion=4"
JS = """async u=>{const ac=new AbortController();setTimeout(()=>ac.abort(),20000);for(let i=0;i<2;i++){try{const r=await fetch(u,{headers:{Accept:'application/json'},signal:ac.signal});
 if(r.status==200)return [200,await r.text()]; if(r.status==204)return [204,''];
 if(r.status==403||r.status==401)return [r.status,''];
 await new Promise(s=>setTimeout(s,1500*(i+1)))}catch(e){await new Promise(s=>setTimeout(s,1000*(i+1)))}}return [0,'']}"""

def compacta(a):
    return {"m": a["codigoMesa"], "e": a["idEleccion"], "u": a["idUbigeo"], "lc": a["codigoLocalVotacion"],
            "ln": a["nombreLocalVotacion"], "cp": a.get("centroPoblado"),
            "el": a["totalElectoresHabiles"], "as": a["totalAsistentes"], "em": a["totalVotosEmitidos"],
            "va": a["totalVotosValidos"], "st": a["codigoEstadoActa"],
            "v": {d["adCodigo"]: d["adVotos"] for d in a["detalle"] if d["adVotos"] is not None}}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ubigeo", type=int); ap.add_argument("out")
    ap.add_argument("--pausa", type=float, default=0.5); ap.add_argument("--lo", type=int, default=30000); ap.add_argument("--hi", type=int, default=65000)
    a = ap.parse_args(); out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    hechas = set()
    if out.exists():
        for l in out.read_text(encoding="utf-8").splitlines():
            if l.strip(): hechas.add(json.loads(l)["m"])
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        pg.goto(BASE + "/main/alcance-electoral", wait_until="networkidle", timeout=60000)
        def get(c):
            for intento in range(6):
                try:
                    st, t = pg.evaluate(JS, URL.format(c=c))
                except Exception:
                    st, t = 0, ""
                if st == 200 and t: return json.loads(t)["data"]
                if st == 204: return []
                if st in (401, 403) and intento >= 2: raise SystemExit(f"ONPE bloqueó la consulta (estado {st}); se detiene")
                print(f"  mesa {c:06d}: estado {st}, recargo la página y reintento ({intento+1}/6)", flush=True)
                time.sleep(5 * (intento + 1))
                try: pg.goto(BASE + "/main/alcance-electoral", wait_until="networkidle", timeout=60000)
                except Exception: pass
            raise SystemExit(f"mesa {c:06d}: sin respuesta tras 6 intentos; se detiene (se puede reanudar)")
        def ub(c):
            d = get(c); time.sleep(0.3); return d[0]["idUbigeo"] if d else None
        # primera mesa con ubigeo >= objetivo; última con ubigeo <= objetivo
        lo, hi = a.lo, a.hi
        while hi - lo > 1:
            mid = (lo + hi) // 2; u = ub(mid)
            if u is not None and u >= a.ubigeo: hi = mid
            else: lo = mid
        primera = hi; lo, hi = primera, a.hi
        while hi - lo > 1:
            mid = (lo + hi) // 2; u = ub(mid)
            if u is not None and u <= a.ubigeo: lo = mid
            else: hi = mid
        ultima = lo
        print(f"ubigeo {a.ubigeo}: mesas {primera:06d}–{ultima:06d} ({ultima-primera+1})", flush=True)
        n = 0; t0 = time.time()
        with out.open("a", encoding="utf-8") as f:
            for c in range(primera, ultima + 1):
                cm = f"{c:06d}"
                if cm in hechas: continue
                for acta in get(c):
                    if acta["idEleccion"] in (3, 4) and acta["idUbigeo"] == a.ubigeo:
                        f.write(json.dumps(compacta(acta), ensure_ascii=False, separators=(",", ":")) + "\n")
                n += 1
                if n % 50 == 0: f.flush(); print(f"  {c:06d}  ({n} nuevas, {time.time()-t0:.0f} s)", flush=True)
                time.sleep(a.pausa)
        b.close()
    print("listo", flush=True)
main()
