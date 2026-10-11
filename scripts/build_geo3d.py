"""Genera site/geo3d-dist.json y site/geo3d-prov.json: GeoJSON simplificado para el mapa 3D (clave u = ubigeo ONPE).
La cartografía no cambia entre cortes: se genera una vez y se versiona."""
import json, sys
from pathlib import Path
from shapely.geometry import shape, mapping
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _geo
S = Path(__file__).resolve().parent.parent / "site"

def redondear(c, n=3):
    return [redondear(x, n) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], n), round(c[1], n)]

def salida(nombre, feats, tol):
    out = []
    for u, geom, props in feats:
        g = shape(geom).buffer(0).simplify(tol, preserve_topology=True)
        if g.is_empty: continue
        m = mapping(g); out.append({"type": "Feature", "id": u, "properties": {"u": u, **props}, "geometry": {"type": m["type"], "coordinates": redondear(m["coordinates"])}})
    dest = S / nombre; dest.write_text(json.dumps({"type": "FeatureCollection", "features": out}, separators=(",", ":")), encoding="utf-8")
    print(nombre, len(out), f"{dest.stat().st_size/1e6:.2f} MB")

def main():
    fd = json.loads((S / "district-geography.json").read_text(encoding="utf-8"))["features"]
    salida("geo3d-dist.json", [(f["properties"]["ubigeo"], f["geometry"], {}) for f in fd], 0.004)
    MAPA, _, fp = _geo.mapa_provincias()
    salida("geo3d-prov.json", [(MAPA[f["properties"]["id"]], f["geometry"], {}) for f in fp if f["properties"]["id"] in MAPA], 0.006)
if __name__ == "__main__": main()
