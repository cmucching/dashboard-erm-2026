#!/usr/bin/env python3
"""Contrasta lo descargado por mesa con el resumen de ONPE en vivo (votos válidos y actas contabilizadas, elecciones 3 y 4).
Uso: python3 scripts/validar_onpe.py [--sellar] <carpeta_con_mesas-UBIGEO.jsonl> 140109 140138 ...
--sellar: si ambas elecciones cuadran exacto con ONPE, fija corte_onpe = fecha de ONPE en site/api/locales/<u>.json."""
import json, sys, pathlib
from playwright.sync_api import sync_playwright
args = [a for a in sys.argv[1:] if a != '--sellar']; sellar = '--sellar' in sys.argv; W = pathlib.Path(args[0]); ids = args[1:]
R = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://resultadoelectoral.onpe.gob.pe"
Q = "/presentacion-backend/resumen-general/totales?idEleccion={e}&tipoFiltro=ubigeo_nivel_03&idAmbitoGeografico=1&idUbigeoDepartamento=140000&idUbigeoProvincia=140100&idUbigeoDistrito={u}"
JS = "async u=>{const r=await fetch(u,{headers:{Accept:'application/json'}});return [r.status,await r.text()]}"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); pg.goto(BASE + "/main/alcance-electoral", wait_until="networkidle", timeout=60000)
    for u in ids:
        rows = [json.loads(l) for l in open(W / f"mesas-{u}.jsonl", encoding="utf-8")]
        okk = True; fecha = None
        for e in (3, 4):
            st, t = pg.evaluate(JS, Q.format(e=e, u=u)); d = json.loads(t)["data"] if st == 200 else {}
            va = sum(x["va"] or 0 for x in rows if x["e"] == e and x["st"] == "C"); nc = sum(1 for x in rows if x["e"] == e and x["st"] == "C")
            ov, oc = d.get("totalVotosValidos"), d.get("contabilizadas")
            okk &= (va, nc) == (ov, oc); fecha = d.get("fechaActualizacion")
            print(u, "prov" if e == 3 else "dist", "votos", va, "ONPE", ov, "| actas", nc, "ONPE", oc, "|", d.get("fechaActualizacion"), "OK" if (va, nc) == (ov, oc) else "DIFIERE", flush=True)
        if sellar and okk and fecha:
            f = R / f"site/api/locales/{u}.json"; j = json.load(open(f, encoding="utf-8")); j["corte_onpe"] = fecha
            json.dump(j, open(f, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":")); print("  sellado", u, fecha, flush=True)
    b.close()
