#!/usr/bin/env python3
"""Agrega las actas por mesa (jsonl de bajar_mesas.py) por local de votación.

Uso: python3 scripts/agregar_locales.py mesas-140130.jsonl site/api/locales/140130.json "Santiago de Surco" 2026-10-14T13:45:34Z
Salida: un JSON por distrito con, por local: mesas, electores, asistentes, emitidos, válidos, blancos, nulos,
y votos por organización en la elección distrital (d) y provincial (p). Las coordenadas se añaden en otro paso.
"""
import json, sys, pathlib, collections

ESPECIALES = {"80": "bl", "81": "nu", "82": "im"}

def main(src, dst, distrito="", corte=""):
    muni = json.load(open(pathlib.Path(__file__).resolve().parent.parent / "site/api/municipal-data.json", encoding="utf-8"))
    nombres = {}
    for r in muni["records"]:
        for o in r.get("organizations", []): nombres[o["organization_id"]] = o["organization"]
    L = {}; ubigeo = None
    for linea in open(src, encoding="utf-8"):
        if not linea.strip(): continue
        a = json.loads(linea); ubigeo = a["u"]
        k = (a["lc"], a["ln"])
        g = L.setdefault(k, {"c": a["lc"], "n": a["ln"], "mesas": set(), "mc": {"3": 0, "4": 0},
                             "el": 0, "as": 0, "em": 0, "va": 0, "bl": 0, "nu": 0, "im": 0, "d": collections.Counter(), "p": collections.Counter()})
        g["mesas"].add(a["m"])
        cont = a["st"] == "C"
        t = "d" if a["e"] == 4 else "p"
        if cont: g["mc"][str(a["e"])] += 1
        if a["e"] == 4:  # electores y asistencia se cuentan una vez por mesa (elección distrital)
            g["el"] += a["el"] or 0
            if cont:
                g["as"] += a["as"] or 0; g["em"] += a["em"] or 0; g["va"] += a["va"] or 0
        if cont:
            for cod, v in a["v"].items():
                if cod in ESPECIALES:
                    if a["e"] == 4: g[ESPECIALES[cod]] += v
                else: g[t][cod] += v
    orgs = {}
    locales = []
    for g in L.values():
        for t in ("d", "p"):
            for cod in g[t]: orgs[cod] = nombres.get(cod, cod)
        locales.append({"c": g["c"], "n": g["n"], "mesas": len(g["mesas"]), "mc_d": g["mc"]["4"], "mc_p": g["mc"]["3"],
                        "el": g["el"], "as": g["as"], "em": g["em"], "va": g["va"], "bl": g["bl"], "nu": g["nu"], "im": g["im"],
                        "d": {k: v for k, v in sorted(g["d"].items(), key=lambda x: -x[1]) if v},
                        "p": {k: v for k, v in sorted(g["p"].items(), key=lambda x: -x[1]) if v}})
    locales.sort(key=lambda x: -x["el"])
    out = {"ubigeo": str(ubigeo), "distrito": distrito, "corte_onpe": corte, "actas_total": len({m for l in L.values() for m in l["mesas"]}),
           "actas_contadas": sum(l["mc_d"] for l in locales), "locales": locales, "organizaciones": orgs}
    pathlib.Path(dst).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(locales)} locales, {sum(l['mesas'] for l in locales)} mesas -> {dst}")

main(*sys.argv[1:5])
