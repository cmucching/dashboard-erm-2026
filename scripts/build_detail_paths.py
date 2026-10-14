"""Genera site/detail/<departamento>.json: trazos de distritos, provincias y contorno del departamento con mucho más detalle
(vértices casi originales de INEI 2023) para cuando el visitante acerca el mapa. El mapa los carga por departamento al entrar.
Estático: se regenera solo si cambia district-geography.json."""
import json, math
from pathlib import Path
from collections import defaultdict
from shapely.geometry import shape
from shapely.ops import unary_union
S = Path(__file__).resolve().parent.parent / "site"
g = json.loads((S / "district-geography.json").read_text(encoding="utf-8"))
K = math.cos(math.radians(9)); SC = 60; W, N = -81.4, 0.2
pt = lambda c: f"{(c[0]-W)*K*SC:.2f} {(N-c[1])*SC:.2f}"
ring = lambda r: "M" + "L".join(pt(c) for c in r.coords) + "Z"
def path(geom):
    polys = [geom] if geom.geom_type == "Polygon" else [p for p in geom.geoms if p.geom_type == "Polygon"]
    return "".join(ring(p.exterior) + "".join(ring(i) for i in p.interiors) for p in polys)
dep = defaultdict(lambda: {"d": {}, "p": defaultdict(list)})
for f in g["features"]:
    p = f["properties"]; geom = shape(f["geometry"]).buffer(0)
    if geom.is_empty: continue
    dep[p["department_code"]]["d"][p["ubigeo"]] = geom
    dep[p["department_code"]]["p"][p["province_code"]].append(geom)
(S / "detail").mkdir(exist_ok=True); tot = 0
for dc, v in dep.items():
    provs = {pc: unary_union(gs).buffer(0) for pc, gs in v["p"].items()}
    out = {"d": {u: path(gm.simplify(0.00012, preserve_topology=True)) for u, gm in v["d"].items()},
           "p": {pc: path(gm.simplify(0.0002, preserve_topology=True)) for pc, gm in provs.items()},
           "o": path(unary_union(list(provs.values())).buffer(0).simplify(0.0003, preserve_topology=True))}
    f = S / "detail" / f"{dc}.json"; f.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8"); tot += f.stat().st_size
print(len(dep), "departamentos", f"{tot/1e6:.2f} MB")
