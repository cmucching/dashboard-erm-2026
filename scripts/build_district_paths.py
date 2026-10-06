"""Genera site/district-paths.json: trazos SVG simplificados por distrito (desde district-geography.json, INEI 2023)."""
import json, math
from pathlib import Path
from shapely.geometry import shape
S = Path(__file__).resolve().parent.parent / "site"
g = json.loads((S / "district-geography.json").read_text(encoding="utf-8"))
K = math.cos(math.radians(9)); SC = 60  # unidades por grado
W, N = -81.4, 0.2
def pt(c): return f"{(c[0]-W)*K*SC:.1f} {(N-c[1])*SC:.1f}"
def ring(r): return "M" + "L".join(pt(c) for c in r) + "Z"
out = {}
for f in g["features"]:
    p = f["properties"]; geom = shape(f["geometry"]).simplify(0.0025, preserve_topology=True)
    if geom.is_empty: continue
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    d = ""
    for po in polys:
        d += ring(po.exterior.coords) + "".join(ring(i.coords) for i in po.interiors)
    x0, y0, x1, y1 = geom.bounds
    out[p["ubigeo"]] = {"d": d, "b": [round((x0-W)*K*SC,1), round((N-y1)*SC,1), round((x1-W)*K*SC,1), round((N-y0)*SC,1)]}
(S / "district-paths.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
print(len(out), f"{(S/'district-paths.json').stat().st_size/1e6:.2f} MB")
