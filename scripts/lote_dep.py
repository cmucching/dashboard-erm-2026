#!/usr/bin/env python3
"""Locales de votación de cualquier distrito del país: lista → baja → agrega → valida contra ONPE en vivo → sella → publica.

Uso:  [PAUSA=0.5] python3 scripts/lote_dep.py <carpeta_trabajo> (--dep 240000 | --prov 140200 | <ubigeo> ...)
Por distrito (un solo flujo, sin paralelismo):
  1. Lista las mesas con /presentacion-backend/actas (50 por página; incluye las numeradas fuera del bloque, p. ej. 9033xx).
  2. Baja con actas/buscar/mesa las que no estén en mesas-<u>.jsonl (reanuda).
  3. Agrega por local (agregar_locales.py) y valida votos válidos y actas contabilizadas, elecciones 3 y 4, contra ONPE en vivo.
  4. Si ONPE avanzó mientras se bajaba, vuelve a consultar solo las mesas no contabilizadas (hasta 4 veces).
  5. Si cuadra exacto: sella corte_onpe, guarda data/mesas/mesas-<u>.jsonl.gz y agrega el distrito a site/api/locales/index.json.
Si ONPE responde 401/403 se detiene (no se elude la verificación). Fin: <carpeta>/fin.json."""
import os, sys, json, time, gzip, shutil, pathlib, subprocess
from playwright.sync_api import sync_playwright
R = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://resultadoelectoral.onpe.gob.pe"
PAUSA = float(os.environ.get("PAUSA", "0.5"))
W = pathlib.Path(sys.argv[1]); W.mkdir(parents=True, exist_ok=True)
DIS = {d["ubigeo"]: d for d in json.load(open(R / "data/municipal_distritos.json", encoding="utf-8"))}
a = sys.argv[2:]
if a and a[0] == "--dep": ids = [u for u, d in DIS.items() if d["dep"] == a[1]]
elif a and a[0] == "--prov": ids = [u for u, d in DIS.items() if d["prov"] == a[1]]
else: ids = a
ids = sorted(ids)
PART = {"De", "Del", "La", "Las", "Los", "Y", "El"}
def nombre(u):
    ws = DIS[u]["nombre"].title().split()
    return " ".join(w.lower() if (i and w in PART) else w for i, w in enumerate(ws))
JS = """async u=>{const ac=new AbortController();setTimeout(()=>ac.abort(),20000);try{const r=await fetch(u,{headers:{Accept:'application/json'},signal:ac.signal});return [r.status,await r.text()]}catch(e){return [0,'']}}"""
def compacta(x):
    return {"m": x["codigoMesa"], "e": x["idEleccion"], "u": x["idUbigeo"], "lc": x["codigoLocalVotacion"],
            "ln": x["nombreLocalVotacion"], "cp": x.get("centroPoblado"),
            "el": x["totalElectoresHabiles"], "as": x["totalAsistentes"], "em": x["totalVotosEmitidos"],
            "va": x["totalVotosValidos"], "st": x["codigoEstadoActa"],
            "v": {d["adCodigo"]: d["adVotos"] for d in x["detalle"] if d["adVotos"] is not None}}
res = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    def entrar(): pg.goto(BASE + "/main/alcance-electoral", wait_until="networkidle", timeout=60000)
    entrar()
    def get(url):
        for i in range(6):
            st, t = pg.evaluate(JS, url)
            if st == 200 and t: return json.loads(t)["data"]
            if st == 204: return []
            if st in (401, 403): raise SystemExit(f"ONPE bloqueó la consulta ({st}); se detiene")
            print(f"  estado {st}, recargo y reintento {i+1}/6", flush=True); time.sleep(5 * (i + 1))
            try: entrar()
            except Exception: pass
        raise SystemExit("sin respuesta tras 6 intentos; se detiene (reanudable)")
    def listar(u):
        s = set(); pag = 0
        while True:
            d = get(f"/presentacion-backend/actas?pagina={pag}&tamanio=50&idEleccion=4&idAmbitoGeografico=1&idUbigeo={u}")
            s |= {c["codigoMesa"] for c in d["content"] if c["idUbigeo"] == int(u)}; pag += 1
            if pag >= d["totalPaginas"]: break
            time.sleep(PAUSA)
        return s
    def bajar(u, jl):
        hechas = {json.loads(l)["m"] for l in jl.read_text(encoding="utf-8").splitlines() if l.strip()} if jl.exists() else set()
        falt = sorted(listar(u) - hechas)
        with jl.open("a", encoding="utf-8") as f:
            for c in falt:
                for x in get(f"/presentacion-backend/actas/buscar/mesa?codigoMesa={c}&idEleccion=4"):
                    if x["idEleccion"] in (3, 4) and x["idUbigeo"] == int(u): f.write(json.dumps(compacta(x), ensure_ascii=False, separators=(",", ":")) + "\n")
                time.sleep(PAUSA)
        return len(falt)
    def quitar_pendientes(jl):
        L = [json.loads(l) for l in jl.read_text(encoding="utf-8").splitlines() if l.strip()]
        pend = {r["m"] for r in L if r["st"] != "C"}
        jl.write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in L if r["m"] not in pend), encoding="utf-8")
        return len(pend)
    def validar(u, rows):
        d0 = DIS[u]; ok = True; fecha = None; txt = []
        for e in (3, 4):
            if not any(r["e"] == e for r in rows): continue
            q = f"/presentacion-backend/resumen-general/totales?idEleccion={e}&tipoFiltro=ubigeo_nivel_03&idAmbitoGeografico=1&idUbigeoDepartamento={int(d0['dep'])}&idUbigeoProvincia={int(d0['prov'])}&idUbigeoDistrito={int(u)}"
            st, t = pg.evaluate(JS, q); d = json.loads(t)["data"] if st == 200 else {}
            va = sum(r["va"] or 0 for r in rows if r["e"] == e and r["st"] == "C"); nc = sum(1 for r in rows if r["e"] == e and r["st"] == "C")
            good = (va, nc) == (d.get("totalVotosValidos"), d.get("contabilizadas")); ok &= good; fecha = d.get("fechaActualizacion") or fecha
            txt.append(f"{'prov' if e == 3 else 'dist'} {va}/{nc} vs {d.get('totalVotosValidos')}/{d.get('contabilizadas')} {'OK' if good else 'DIFIERE'}")
            time.sleep(PAUSA)
        return ok, fecha, " | ".join(txt)
    for u in ids:
        jl = W / f"mesas-{u}.jsonl"; out = R / f"site/api/locales/{u}.json"; est = "?"
        for intento in range(5):
            n = bajar(u, jl)
            rows = [json.loads(l) for l in jl.read_text(encoding="utf-8").splitlines() if l.strip()]
            if not rows: est = "SIN_ACTAS"; break
            ok, fecha, txt = validar(u, rows)
            print(f"{u} {nombre(u)} intento {intento+1}: {len({r['m'] for r in rows})} mesas (+{n}) | {txt}", flush=True)
            if ok: est = "OK"; break
            est = "DIFIERE"; quitar_pendientes(jl)
        if est == "OK":
            subprocess.run([sys.executable, str(R / "scripts/agregar_locales.py"), str(jl), str(out), nombre(u), fecha], check=True, capture_output=True)
            subprocess.run([sys.executable, str(R / "scripts/ubicar_locales.py"), str(out), nombre(u)], check=True, capture_output=True)
            j = json.load(open(out, encoding="utf-8")); j["corte_onpe"] = fecha
            json.dump(j, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
            with open(jl, "rb") as f, gzip.open(R / f"data/mesas/mesas-{u}.jsonl.gz", "wb") as g: shutil.copyfileobj(f, g)
            ix = R / "site/api/locales/index.json"; idx = sorted(set(json.load(open(ix))) | {u}); json.dump(idx, open(ix, "w"))
        res.append((u, est)); (W / "fin.json").write_text(json.dumps(res), encoding="utf-8")
    b.close()
print("FIN", res, flush=True)
