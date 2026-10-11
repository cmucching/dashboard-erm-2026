"""Genera site/api/analysis.json: autocorrelación espacial (I de Moran global, LISA y Getis-Ord Gi*) del voto municipal.
Solo numpy + shapely. Contigüidad tipo reina (queen); unidades sin vecinos usan los 4 centroides más próximos."""
import json, sys
from pathlib import Path
import numpy as np
from shapely.geometry import shape
from shapely.strtree import STRtree
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _geo
R = Path(__file__).resolve().parent.parent; S = R / "site"
PERM = 999; SEED = 2026

def contiguidad(feats):
    geoms = [shape(f["geometry"]).buffer(0) for f in feats]; n = len(geoms)
    tree = STRtree(geoms); nb = [set() for _ in range(n)]
    for i, g in enumerate(geoms):
        for j in tree.query(g, predicate="intersects"):
            if j != i: nb[i].add(int(j))
    cen = np.array([[g.centroid.x, g.centroid.y] for g in geoms])
    for i in range(n):
        if not nb[i]:
            d = np.hypot(*(cen - cen[i]).T); d[i] = np.inf
            nb[i] = set(int(k) for k in np.argsort(d)[:4])
    for i in range(n):  # simetría
        for j in list(nb[i]): nb[j].add(i)
    return nb

def stats(x, nb, rng):
    """x: array con NaN donde no hay dato. Devuelve global (I,z,p), local (cl, p, lag) y Gi* z."""
    ok = np.where(~np.isnan(x))[0]; idx = {int(i): k for k, i in enumerate(ok)}
    vals = x[ok]; n = len(ok)
    vec = [[idx[j] for j in nb[i] if j in idx] for i in ok]
    sin = np.array([len(v) == 0 for v in vec])
    z = vals - vals.mean(); m2 = (z ** 2).sum() / n
    lag = np.array([z[v].mean() if v else 0.0 for v in vec])
    loc = z / m2 * lag
    # global
    keep = ~sin; Ig = float((z[keep] * lag[keep]).sum() / (z[keep] ** 2).sum())
    perm = []
    for _ in range(PERM):
        zp = rng.permutation(z); lp = np.array([zp[v].mean() if v else 0.0 for v in vec])
        perm.append((zp[keep] * lp[keep]).sum() / (zp[keep] ** 2).sum())
    perm = np.array(perm); zI = (Ig - perm.mean()) / perm.std(); pI = (np.sum(np.abs(perm - perm.mean()) >= abs(Ig - perm.mean())) + 1) / (PERM + 1)
    # local (permutación condicional)
    pl = np.ones(n)
    for i in range(n):
        k = len(vec[i])
        if not k: continue
        others = np.delete(np.arange(n), i)
        smp = z[others[rng.integers(0, n - 1, size=(PERM, k))]].mean(axis=1)
        Is = z[i] / m2 * smp
        pl[i] = (np.sum(np.abs(Is) >= abs(loc[i])) + 1) / (PERM + 1)
    cl = np.zeros(n, int)
    sig = (pl < 0.05) & ~sin
    cl[sig & (z > 0) & (lag > 0)] = 1; cl[sig & (z < 0) & (lag < 0)] = 2
    cl[sig & (z < 0) & (lag > 0)] = 3; cl[sig & (z > 0) & (lag < 0)] = 4
    # Gi* (binario, incluye la propia unidad)
    xb, s = vals.mean(), vals.std()
    gi = np.zeros(n)
    for i in range(n):
        v = vec[i] + [i]; w = len(v)
        gi[i] = (vals[v].sum() - xb * w) / (s * np.sqrt((n * w - w ** 2) / (n - 1)))
    full = lambda a, fill: [None if np.isnan(x[k]) else None for k in range(0)]
    return dict(I=Ig, z=float(zI), p=float(pI), E=-1 / (n - 1), n=n, ok=ok, cl=cl, gi=gi, sin=sin)

def variables(level, ids, rec, hist, n):
    """Variables por unidad (distrito o provincia). rec: ubigeo -> registro municipal."""
    from collections import Counter
    pos = {u: i for i, u in enumerate(ids)}; V = {}
    marg = np.full(n, np.nan); pend = np.full(n, np.nan); lid = Counter()
    for u, r in rec.items():
        if u not in pos or not r["valid_votes"] or not r["organizations"]: continue
        o = sorted(r["organizations"], key=lambda q: -q["votes"]); i = pos[u]
        marg[i] = o[0]["pct_valid"] - (o[1]["pct_valid"] if len(o) > 1 else 0)
        pend[i] = 100 - (r["counted_pct"] or 0); lid[o[0]["organization"]] += 1
    V["margen"] = dict(label="Ventaja del 1.º sobre el 2.º", unit="pp", x=marg, nota="Valores bajos = carrera reñida")
    V["pendiente"] = dict(label="Actas por contabilizar", unit="%", x=pend, nota="Mide dónde se concentra lo que falta contar")
    for org, c in lid.most_common(6):
        a = np.full(n, np.nan)
        for u, r in rec.items():
            if u in pos and r["valid_votes"]:
                a[pos[u]] = next((q["pct_valid"] for q in r["organizations"] if q["organization"] == org), 0.0)
        V["p_" + org] = dict(label=f"Voto de {org.title()}", unit="% válidos", x=a, nota=f"Lidera en {c} unidades")
    dm = np.full(n, np.nan)
    for u, sr in hist.get(level, {}).items():
        if u in pos:
            f = [x for x in sr if x]
            if len(f) > 1 and f[0][1] and f[-1][1]:
                dm[pos[u]] = (f[-1][3] - f[-1][4]) / f[-1][1] * 100 - (f[0][3] - f[0][4]) / f[0][1] * 100
    V["delta"] = dict(label="Cambio de la ventaja desde el primer corte", unit="pp", x=dm, nota="Dónde se movió la carrera mientras entraban actas")
    return V

def analizar(level, feats, ids, rec, hist, rng):
    from collections import Counter
    n = len(ids); nb = contiguidad(feats); out = {}
    for k, v in variables(level, ids, rec, hist, n).items():
        x = v["x"]
        if np.sum(~np.isnan(x)) < (30 if level == "dist" else 20): continue
        st = stats(x, nb, rng); cl = [None] * n; gi = [None] * n; val = [None] * n
        for j, i in enumerate(st["ok"]):
            cl[i] = int(st["cl"][j]) if not st["sin"][j] else None; gi[i] = round(float(st["gi"][j]), 2); val[i] = round(float(x[i]), 2)
        c = Counter(c for c in cl if c is not None)
        out[k] = dict(label=v["label"], unit=v["unit"], nota=v["nota"], I=round(st["I"], 3), z=round(st["z"], 1), p=round(st["p"], 4),
                      n=st["n"], E=round(st["E"], 4), v=val, cl=cl, gi=gi, conteo={str(a): c.get(a, 0) for a in range(5)})
        print(f"{level:4s} {k[:36]:36s} n={st['n']} I={st['I']:.3f} z={st['z']:.1f} p={st['p']:.3f} HH={c.get(1,0)} LL={c.get(2,0)}", file=sys.stderr)
    return out

def main():
    md = json.loads((S / "api" / "municipal-data.json").read_text(encoding="utf-8"))["records"]
    hist = json.loads((S / "api" / "history.json").read_text(encoding="utf-8"))
    rng = np.random.default_rng(SEED)
    fd = json.loads((S / "district-geography.json").read_text(encoding="utf-8"))["features"]
    ids_d = [f["properties"]["ubigeo"] for f in fd]
    MAPA, _, fp = _geo.mapa_provincias()
    fp = [f for f in fp if f["properties"]["id"] in MAPA]
    ids_p = [MAPA[f["properties"]["id"]] for f in fp]
    out = {"corte": hist["cortes"][-1], "desde": hist["cortes"][0], "perm": PERM,
           "dist": {"ids": ids_d, "vars": analizar("dist", fd, ids_d, {r["ubigeo"]: r for r in md if r["level"] == "distrital"}, hist, rng)},
           "prov": {"ids": ids_p, "vars": analizar("prov", fp, ids_p, {r["ubigeo"]: r for r in md if r["level"] == "provincial"}, hist, rng)}}
    dest = S / "api" / "analysis.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{dest.stat().st_size/1e6:.2f} MB")
if __name__ == "__main__": main()
