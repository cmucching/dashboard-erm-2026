"""Genera site/dept-paths.json: contornos de las 26 regiones (25 con gobernador + Lima Metropolitana) con la misma proyección que district-paths.json.
Clave: id de región (PE-XXX). Estático: solo depende de la cartografía INEI, no del conteo."""
import json, math
from pathlib import Path
from shapely.geometry import shape
S = Path(__file__).resolve().parent.parent / "site"
g = json.loads((S / "map-geography.json").read_text(encoding="utf-8"))["regional"]
K = math.cos(math.radians(9)); SC = 60; W, N = -81.4, 0.2
pt = lambda c: f"{(c[0]-W)*K*SC:.1f} {(N-c[1])*SC:.1f}"
ring = lambda r: "M" + "L".join(pt(c) for c in r) + "Z"
out = {}
for f in g["features"]:
    geom = shape(f["geometry"]).buffer(0).simplify(0.004, preserve_topology=True)
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    out[f["properties"]["id"]] = {"n": f["properties"]["name"], "d": "".join(ring(p.exterior.coords) + "".join(ring(i.coords) for i in p.interiors) for p in polys)}
(S / "dept-paths.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(len(out), f"{(S/'dept-paths.json').stat().st_size/1e3:.0f} KB")
