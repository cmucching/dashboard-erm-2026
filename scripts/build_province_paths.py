"""Genera site/province-paths.json con la misma proyección que district-paths.json (clave: ubigeo provincial de 6 dígitos)."""
import json, math, sys
from pathlib import Path
from shapely.geometry import shape
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _geo
S = Path(__file__).resolve().parent.parent / "site"
g = json.loads((S / "map-geography.json").read_text(encoding="utf-8"))["provincial"]
K = math.cos(math.radians(9)); SC = 60; W, N = -81.4, 0.2
pt = lambda c: f"{(c[0]-W)*K*SC:.1f} {(N-c[1])*SC:.1f}"
ring = lambda r: "M" + "L".join(pt(c) for c in r) + "Z"
MAPA, FALTA, _ = _geo.mapa_provincias()
if FALTA: print("AVISO provincias sin código ONPE:", FALTA)
out = {}
for f in g["features"]:
    geom = shape(f["geometry"]).simplify(0.004, preserve_topology=True)
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    d = "".join(ring(p.exterior.coords) + "".join(ring(i.coords) for i in p.interiors) for p in polys)
    if f["properties"]["id"] in MAPA: out[MAPA[f["properties"]["id"]]] = {"d": d}
(S / "province-paths.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
print(len(out), f"{(S/'province-paths.json').stat().st_size/1e6:.2f} MB")
