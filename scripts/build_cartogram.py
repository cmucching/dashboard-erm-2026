"""Cartograma continuo por difusión (Gastner y Newman, 2004): cada distrito o provincia ocupa un área proporcional a sus votos válidos.
Genera site/cartogram-dist.json y site/cartogram-prov.json: {vb0, vb1 (cuadro original y deformado), u:{ubigeo:{o,m,n}}, dep:{departamento:{o,m,n}}, err}; o = vértices originales, m = deformados (décimas), n = vértices por anillo; la página interpola entre ambos.
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
    # contornos de departamento en coordenadas originales: se mueven con el mismo campo para poder interpolar
    orig = {}
    for u in U: orig.setdefault(u["dep"], []).append(MultiPolygon([Polygon(e, i) for e, i in u["ps"]]).buffer(0))
    depr = {d: [r.coords for g in [unary_union(gs)] for pp in polys(g) for r in [pp.exterior, *pp.interiors]] for d, gs in orig.items()}
    filas = [e for u in U for e, i in u["ps"] for e in [e, *i]]; filas_dep = [np.array(r) for rs in depr.values() for r in rs]
    Pall = np.vstack(filas + filas_dep); Pg = np.column_stack([(Pall[:, 0] - x0) / c, (Pall[:, 1] - y0) / c])
    Pn, pasos = difundir(rho, Pg); Pn = np.column_stack([Pn[:, 0] * c + x0, Pn[:, 1] * c + y0])
    ent = lambda A: [int(round(v * 10)) for v in A.ravel()]
    unid, geoms, k = {}, {}, 0
    for u in U:
        o, m, nn, ps = [], [], [], []
        for e, ints in u["ps"]:
            ring0 = [e, *ints]; hs = []
            for j, r in enumerate(ring0):
                n = len(r); seg_m = Pn[k:k + n]; o.append(ent(r)); m.append(ent(seg_m)); nn.append(n); k += n
                hs.append(seg_m)
            ps.append(Polygon(hs[0], hs[1:]).buffer(0))
        geoms[u["u"]] = unary_union(ps)
        unid[u["u"]] = {"o": [v for r in o for v in r], "m": [v for r in m for v in r], "n": nn}
    dep_out = {}
    for d, rs in depr.items():
        o, m, nn = [], [], []
        for r in rs:
            n = len(r); o += ent(np.array(r)); m += ent(Pn[k:k + n]); nn.append(n); k += n
        dep_out[d] = {"o": o, "m": m, "n": nn}
    # error del cartograma: área obtenida frente a la deseada (votos / densidad media por celda)
    err = []
    for u, v in zip(U, w):
        a = geoms[u["u"]].area; d = v / (medio * c * c) * c * c
        err.append(abs(a - d) / d if d > 0 else 0)
    b1 = unary_union(list(geoms.values())).bounds; b0 = (minx, miny, maxx, maxy); mg = 12
    vb = lambda b: [round(b[0] - mg, 1), round(b[1] - mg, 1), round(b[2] - b[0] + 2 * mg, 1), round(b[3] - b[1] + 2 * mg, 1)]
    out = {"vb0": vb(b0), "vb1": vb(b1), "u": unid, "dep": dep_out}
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
