#!/usr/bin/env python3
"""Descarga las actas por mesa de varios distritos, agrega por local de votación, valida contra ONPE y deja listo para publicar.
Uso: python3 scripts/lote_locales.py <carpeta_trabajo> 140124 140111 ...
Por distrito: bajar_mesas.py -> agregar_locales.py -> ubicar_locales.py (sin coordenadas si no hay fuente) -> validación
(votos válidos y actas contabilizadas de la elección provincial vs data/municipal_lima.json) -> site/api/locales/<u>.json + data/mesas/*.gz
Es reanudable: bajar_mesas.py retoma desde lo ya guardado."""
import os, json, sys, subprocess, gzip, shutil, pathlib, datetime
R = pathlib.Path(__file__).resolve().parent.parent
W = pathlib.Path(sys.argv[1]); W.mkdir(parents=True, exist_ok=True); ids = sys.argv[2:]
lima = {r["ubigeo"]: r for r in json.load(open(R / "data/municipal_lima.json", encoding="utf-8"))}
def nombre(u):
    n = lima[u]["nombre"].title().replace(" De ", " de ").replace(" Del ", " del ")
    return n
res = []
for u in ids:
    jl = W / f"mesas-{u}.jsonl"
    r = subprocess.run([sys.executable, str(R / "scripts/bajar_mesas.py"), u, str(jl), "--pausa", os.environ.get("PAUSA", "0.4")], capture_output=True, text=True)
    (W / f"log-{u}.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
    if r.returncode != 0:
        print(u, "INCOMPLETO (reanudable):", (r.stdout + r.stderr).strip().splitlines()[-1:], flush=True); res.append((u, "INCOMPLETO")); continue
    t = lima[u]["totales"]; corte = t["fechaActualizacion"].replace(".241Z", "Z")
    out = R / f"site/api/locales/{u}.json"
    subprocess.run([sys.executable, str(R / "scripts/agregar_locales.py"), str(jl), str(out), nombre(u), t["fechaActualizacion"]], check=True, capture_output=True)
    subprocess.run([sys.executable, str(R / "scripts/ubicar_locales.py"), str(out), nombre(u)], check=True, capture_output=True)
    rows = [json.loads(l) for l in open(jl, encoding="utf-8")]
    va = sum(x["va"] or 0 for x in rows if x["e"] == 3 and x["st"] == "C"); nc = sum(1 for x in rows if x["e"] == 3 and x["st"] == "C")
    ok = va == t["totalVotosValidos"] and nc == t["contabilizadas"]
    with open(jl, "rb") as f, gzip.open(R / f"data/mesas/mesas-{u}.jsonl.gz", "wb") as g: shutil.copyfileobj(f, g)
    d = json.load(open(out, encoding="utf-8")); d["corte_onpe"] = t["fechaActualizacion"]
    json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(u, nombre(u), len({x["m"] for x in rows}), "mesas", len(d["locales"]), "locales | prov votos", va, "vs", t["totalVotosValidos"], "| actas", nc, "vs", t["contabilizadas"], "OK" if ok else "DIFERENCIA", flush=True)
    res.append((u, "OK" if ok else "DIFERENCIA"))
(W / "fin.json").write_text(json.dumps(res), encoding="utf-8"); print("FIN", res, flush=True)
