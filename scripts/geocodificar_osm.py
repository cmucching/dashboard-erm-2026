#!/usr/bin/env python3
"""Geocodificación PROVISIONAL de locales de votación con OpenStreetMap (Nominatim, 1 consulta/s).
Uso: python3 scripts/geocodificar_osm.py site/api/locales/140140.json "San Borja" cache.json
Acota la búsqueda al rectángulo del distrito (site/district-geography.json). El resultado es un caché
que luego filtra scripts/ubicar_locales.py (--osm). Se reemplaza por el padrón oficial de Minedu cuando exista."""
import json, re, sys, time, urllib.parse, urllib.request, pathlib
from shapely.geometry import shape
R = pathlib.Path(__file__).resolve().parent.parent
ruta, distrito, salida = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(ruta, encoding="utf-8")); ub = d["ubigeo"]
g = json.load(open(R / "site" / "district-geography.json", encoding="utf-8"))
geom = next(shape(f["geometry"]) for f in g["features"] if f["properties"]["ubigeo"] == ub)
x0, y0, x1, y1 = geom.bounds; m = 0.004
vb = f"{x0-m},{y1+m},{x1+m},{y0-m}"
def q(txt):
    u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": txt, "format": "jsonv2", "limit": 3, "viewbox": vb, "bounded": 1, "countrycodes": "pe"})
    r = urllib.request.Request(u, headers={"User-Agent": "dashboard-erm-2026/1.0 (cmucching@gmail.com)"})
    try: return json.load(urllib.request.urlopen(r, timeout=25))
    except Exception: return None
def variantes(n):
    n = n.strip(); t = re.sub(r"^IEP\s+", "Colegio ", n); t = re.sub(r"^IE\s+", "Institución Educativa ", t)
    return list(dict.fromkeys([n, t + ", " + distrito, re.sub(r"^(IE|IEP)\s+\d+\s+", "", n) + ", " + distrito, n + " Lima"]))
try: res = json.load(open(salida, encoding="utf-8"))
except Exception: res = {}
for l in d["locales"]:
    if l["c"] in res: continue
    hit = None
    for v in variantes(l["n"]):
        r = q(v); time.sleep(1.1)
        if r: hit = (v, r[0]); break
    res[l["c"]] = {"n": l["n"], "q": hit[0] if hit else None, "lat": float(hit[1]["lat"]) if hit else None, "lon": float(hit[1]["lon"]) if hit else None,
                   "found": hit[1]["display_name"] if hit else None, "osm": f"{hit[1].get('osm_type')}/{hit[1].get('osm_id')}" if hit else None}
    json.dump(res, open(salida, "w", encoding="utf-8"), ensure_ascii=False)
print(sum(1 for v in res.values() if v["lat"]), "/", len(res), "con resultado OSM")
