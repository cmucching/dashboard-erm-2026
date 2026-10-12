"""Cartograma continuo por difusión (Gastner y Newman, 2004): cada distrito o provincia ocupa un área proporcional a sus votos válidos.
Genera site/cartogram-dist.json y site/cartogram-prov.json: {vb:[x,y,w,h], paths:{ubigeo:"M…"}, dep:{departamento:"M…"}, err:{mediana,p90}}.
Solo numpy + shapely (>=2). Las geometrías se deforman con el mismo campo de velocidad, de modo que las fronteras se mantienen."""
import json, math, sys, time
from pathlib import Path
import numpy as np
import shapely
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.ops import unary_union
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _geo
S = Path(__file__).resolve().parent.parent / "site"
K = math.cos(math.radians(9)); SC = 60; W, N = -81.4, 0.2  # misma proyección que los mapas planos
proj = lambda x, y: ((x - W) * K * SC, (N - y) * SC)

def polys(g):
    return [g] if g.geom_type == "Polygon" else list(g.geoms)

def preparar(feats, tol, seg=0.06):
    """feats: (clave, geometría lon/lat, departamento). Devuelve unidades con polígonos proyectados y simplificados."""
    out = []
    for u, geom, dep in feats:
        g = shape(geom).buffer(0).simplify(tol, preserve_topology=True)
        if g.is_empty: continue
        g = shapely.segmentize(g, seg)
        ps = []
        for p in polys(g):
            ext = np.array([proj(x, y) for x, y in p.exterior.coords]); ints = [np.array([proj(x, y) for x, y in r.coords]) for r in p.interiors]
            ps.append((ext, ints))
        out.append(dict(u=u, dep=dep, ps=ps))
    return out

def rasterizar(U, w, nx, ny, x0, y0, c):
    """Densidad (votos por celda) conservando la masa: unidades grandes reparten su masa en sus celdas; las pequeñas, en la celda del centroide."""
    rho = np.zeros((ny, nx)); xs = x0 + (np.arange(nx) + .5) * c; ys = y0 + (np.arange(ny) + .5) * c
    for un, v in zip(U, w):
        geom = MultiPolygon([Polygon(e, i) for e, i in un["ps"]]).buffer(0)
        minx, miny, maxx, maxy = geom.bounds
        ix = np.where((xs >= minx) & (xs <= maxx))[0]; iy = np.where((ys >= miny) & (ys <= maxy))[0]; n = 0
        if len(ix) and len(iy):
            gx, gy = np.meshgrid(xs[ix], ys[iy]); m = shapely.contains_xy(geom, gx, gy); n = int(m.sum())
            if n:
                sub = rho[np.ix_(iy, ix)]; sub[m] += v / n; rho[np.ix_(iy, ix)] = sub
        if not n:
            cx, cy = geom.representative_point().x, geom.representative_point().y
            rho[min(ny - 1, max(0, int((cy - y0) / c))), min(nx - 1, max(0, int((cx - x0) / c)))] += v
    return rho

def bilinear(F, px, py):
    """F[ny,nx] con centros de celda en i+.5; px, py en coordenadas de celda."""
    ny, nx = F.shape; x = np.clip(px - .5, 0, nx - 1.001); y = np.clip(py - .5, 0, ny - 1.001)
    i = x.astype(int); j = y.astype(int); fx = x - i; fy = y - j
    return (F[j, i] * (1 - fx) * (1 - fy) + F[j, i + 1] * fx * (1 - fy) + F[j + 1, i] * (1 - fx) * fy + F[j + 1, i + 1] * fx * fy)

def difundir(rho, P, q=1.07, t0=0.2):
    """Integra las posiciones P (en celdas) por el campo v = -∇ρ/ρ de la ecuación de difusión (extensión par = frontera reflectora)."""
    ny, nx = rho.shape; ext = np.block([[rho, rho[:, ::-1]], [rho[::-1, :], rho[::-1, ::-1]]])
    F0 = np.fft.rfft2(ext); ky = 2 * np.pi * np.fft.fftfreq(2 * ny)[:, None]; kx = 2 * np.pi * np.fft.rfftfreq(2 * nx)[None, :]; k2 = kx ** 2 + ky ** 2
    tmax = 6 / (np.pi / max(nx, ny)) ** 2
    def campo(t):
        A = F0 * np.exp(-k2 * t); r = np.fft.irfft2(A, s=ext.shape)[:ny, :nx]; gx = np.fft.irfft2(1j * kx * A, s=ext.shape)[:ny, :nx]; gy = np.fft.irfft2(1j * ky * A, s=ext.shape)[:ny, :nx]
        r = np.maximum(r, rho.mean() * 1e-3); return -gx / r, -gy / r
    t = t0; vx, vy = campo(t); pasos = 0
    while t < tmax:
        dt = t * (q - 1); vx1, vy1 = campo(t + dt)
        ax, ay = bilinear(vx, P[:, 0], P[:, 1]), bilinear(vy, P[:, 0], P[:, 1]); pp = P + dt * np.stack([ax, ay], 1)
        bx, by = bilinear(vx1, pp[:, 0], pp[:, 1]), bilinear(vy1, pp[:, 0], pp[:, 1])
        P = P + dt / 2 * np.stack([ax + bx, ay + by], 1); vx, vy = vx1, vy1; t += dt; pasos += 1
    return P, pasos

def ruta(g):
    d = []
    for p in polys(g):
        for r in [p.exterior, *p.interiors]: d.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in r.coords) + "Z")
    return "".join(d)

def cartograma(nombre, feats, votos, tol, ny=560, seg=0.06):
    t0 = time.time(); U = preparar(feats, tol, seg); w = np.array([max(1.0, votos.get(u["u"], 0)) for u in U], float)
    allp = np.vstack([e for u in U for e, _ in u["ps"]]); minx, miny = allp.min(0); maxx, maxy = allp.max(0)
    padx, pady = (maxx - minx) * .25, (maxy - miny) * .25; H = (maxy - miny) + 2 * pady; c = H / ny; nx = int(math.ceil(((maxx - minx) + 2 * padx) / c)); x0, y0 = minx - padx, miny - pady
    rho = rasterizar(U, w, nx, ny, x0, y0, c)
    # fuera del país: densidad media, para que el contorno también se deforme
    area_pais = sum(Polygon(e).area for u in U for e, _ in u["ps"]); medio = w.sum() / area_pais
    dentro = rho > 0
    rho[~dentro] = medio * c * c
    Pall = np.vstack([np.vstack([e] + i) for u in U for e, i in u["ps"]]); Pg = np.column_stack([(Pall[:, 0] - x0) / c, (Pall[:, 1] - y0) / c])
    Pn, pasos = difundir(rho, Pg); Pn = np.column_stack([Pn[:, 0] * c + x0, Pn[:, 1] * c + y0])
    paths, geoms, deps, k = {}, {}, {}, 0
    for u in U:
        ps = []
        for e, ints in u["ps"]:
            n = len(e); ring = Pn[k:k + n]; k += n; hs = []
            for i in ints: hs.append(Pn[k:k + len(i)]); k += len(i)
            ps.append(Polygon(ring, hs).buffer(0))
        g = unary_union(ps); geoms[u["u"]] = g; paths[u["u"]] = ruta(g); deps.setdefault(u["dep"], []).append(g)
    # error del cartograma: área obtenida frente a la deseada (votos / densidad media por celda)
    err = []
    for u, v in zip(U, w):
        a = geoms[u["u"]].area; d = v / (medio * c * c) * c * c  # área deseada en unidades del mapa
        err.append(abs(a - d) / d if d > 0 else 0)
    # área deseada se calcula sobre la densidad media de todo el mapa (masa / área del lienzo)
    dep_paths = {d: ruta(unary_union(gs)) for d, gs in deps.items()}
    b = unary_union(list(geoms.values())).bounds; m = 12
    out = {"vb": [round(b[0] - m, 1), round(b[1] - m, 1), round(b[2] - b[0] + 2 * m, 1), round(b[3] - b[1] + 2 * m, 1)], "paths": paths, "dep": dep_paths}
    rel = np.array(err); out["err"] = {"mediana": round(float(np.median(rel)), 3), "p90": round(float(np.percentile(rel, 90)), 3)}
    dest = S / nombre; dest.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(nombre, len(U), f"{dest.stat().st_size/1e6:.2f} MB", f"{pasos} pasos", f"{time.time()-t0:.0f}s", "error relativo de área: mediana", out["err"]["mediana"], "p90", out["err"]["p90"], file=sys.stderr)

def main():
    md = json.loads((S / "api" / "municipal-data.json").read_text(encoding="utf-8"))["records"]
    vd = {r["ubigeo"]: r["valid_votes"] for r in md if r["level"] == "distrital"}; vp = {r["ubigeo"]: r["valid_votes"] for r in md if r["level"] == "provincial"}
    fd = json.loads((S / "district-geography.json").read_text(encoding="utf-8"))["features"]
    MAPA, _, fp = _geo.mapa_provincias()
    cartograma("cartogram-prov.json", [(MAPA[f["properties"]["id"]], f["geometry"], f["properties"]["department"].upper()) for f in fp if f["properties"]["id"] in MAPA], vp, 0.006)
    cartograma("cartogram-dist.json", [(f["properties"]["ubigeo"], f["geometry"], f["properties"]["department"]) for f in fd], vd, 0.004, ny=800, seg=0.02)
if __name__ == "__main__": main()
