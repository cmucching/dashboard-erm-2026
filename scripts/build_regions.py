"""Genera site/api/regions.json: regionalización electoral por aglomeración jerárquica de Ward con restricción de
contigüidad (solo se fusionan regiones vecinas). Variables: % de votos válidos de los 8 partidos con más votos.
Corre para distritos y provincias, con k = 3..12. Solo numpy + shapely."""
import json, sys, heapq
from pathlib import Path
from collections import Counter
import math
import numpy as np
from shapely.geometry import shape
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _geo
from build_analysis import contiguidad
R = Path(__file__).resolve().parent.parent; S = R / "site"
KS = list(range(3, 13)); NTOP = 8
K = math.cos(math.radians(9)); SC = 60; W, N = -81.4, 0.2   # misma proyección que district-paths.json / province-paths.json

def geom_info(feat):
    """Centroide en coordenadas SVG del mapa y superficie aproximada en km² (grado ajustado por la latitud)."""
    g = shape(feat["geometry"]).buffer(0); c = g.centroid
    km2 = g.area * (111.32 * math.cos(math.radians(c.y))) * 110.57
    return [(c.x - W) * K * SC, (N - c.y) * SC], km2

def dorling(P, w, rmax, iters=500):
    """Cartograma de círculos: radio ∝ √peso; parten del centroide y se separan hasta no solaparse.
    Los pares candidatos se recalculan cada 25 iteraciones; entre medias solo se resuelven esos pares."""
    P = np.array(P, float); r = np.sqrt(w); r = r / r.max() * rmax; P0 = P.copy(); n = len(P)
    for it in range(iters):
        if it % 25 == 0:
            d = P[:, None, :] - P[None, :, :]; dist = np.sqrt((d ** 2).sum(-1)); np.fill_diagonal(dist, np.inf)
            I, J = np.where(np.triu(dist < (r[:, None] + r[None, :] + 6)))
        dv = P[I] - P[J]; dd = np.sqrt((dv ** 2).sum(1)) + 1e-9; ov = r[I] + r[J] + 0.3 - dd
        m = ov > 0
        if it % 25 and not m.any(): break
        mv = dv[m] / dd[m, None] * (ov[m, None] * 0.5)
        np.add.at(P, I[m], mv * 0.6); np.add.at(P, J[m], -mv * 0.6)
        P += (P0 - P) * 0.01
    return P, r

def ward_contiguo(X, nb, w=None):
    """Devuelve la lista de fusiones [(a,b,nuevo)] hasta que no queden pares vecinos. Ward: coste = na*nb/(na+nb)*|ca-cb|²."""
    n = len(X); w = np.ones(n) if w is None else np.asarray(w, float); size = {i: float(w[i]) for i in range(n)}; cen = {i: X[i].astype(float) for i in range(n)}
    adj = {i: set(j for j in nb[i] if j != i) for i in range(n)}; ver = {i: 0 for i in range(n)}
    def cost(a, b):
        d = cen[a] - cen[b]; return size[a] * size[b] / (size[a] + size[b]) * float(d @ d)
    h = [(cost(i, j), i, j, 0, 0) for i in range(n) for j in adj[i] if i < j]; heapq.heapify(h)
    merges = []; nxt = n
    while h:
        c, a, b, va, vb = heapq.heappop(h)
        if a not in size or b not in size or ver[a] != va or ver[b] != vb: continue
        m = nxt; nxt += 1
        size[m] = size[a] + size[b]; cen[m] = (cen[a] * size[a] + cen[b] * size[b]) / size[m]; ver[m] = 0
        adj[m] = (adj[a] | adj[b]) - {a, b}
        for x in adj[m]:
            adj[x] -= {a, b}; adj[x].add(m)
            heapq.heappush(h, (cost(m, x), min(m, x), max(m, x), ver[min(m, x)], ver[max(m, x)]))
        for z in (a, b): del size[z], cen[z], adj[z]
        merges.append((a, b, m))
    return merges

def cortar(n, merges, k):
    """Etiquetas 0..k-1 con k regiones (o más si el grafo tiene islas desconectadas)."""
    par = list(range(n + len(merges)))
    def raiz(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    comp = n
    for a, b, m in merges:
        if comp <= k: break
        par[a] = m; par[b] = m; comp -= 1
    lab = {}; out = np.zeros(n, int)
    for i in range(n): out[i] = lab.setdefault(raiz(i), len(lab))
    return out

def r2(X, lab, w):
    mu = (X * w[:, None]).sum(0) / w.sum(); tss = (w[:, None] * (X - mu) ** 2).sum(); wss = 0.0
    for g in np.unique(lab):
        m = lab == g; mg = (X[m] * w[m, None]).sum(0) / w[m].sum(); wss += (w[m, None] * (X[m] - mg) ** 2).sum()
    return 1 - wss / tss

def silueta(D, lab, w):
    n = len(lab); s = np.zeros(n); gs = np.unique(lab)
    if len(gs) < 2: return 0.0
    for i in range(n):
        own = lab == lab[i]; ni = own.sum()
        if ni < 2: continue
        a = D[i, own].sum() / (ni - 1)
        b = min(D[i, lab == g].mean() for g in gs if g != lab[i])
        s[i] = (b - a) / max(a, b)
    return float((s * w).sum() / w.sum())

def ari(a, b):
    a = np.asarray(a); b = np.asarray(b)
    ua, ia = np.unique(a, return_inverse=True); ub, ib = np.unique(b, return_inverse=True)
    M = np.zeros((len(ua), len(ub))); np.add.at(M, (ia, ib), 1)
    c2 = lambda x: x * (x - 1) / 2
    s = c2(M).sum(); sa = c2(M.sum(1)).sum(); sb = c2(M.sum(0)).sum(); t = c2(len(a))
    e = sa * sb / t; mx = (sa + sb) / 2
    return float((s - e) / (mx - e)) if mx != e else 1.0

def regionalizar(level, feats, ids, rec, nombres):
    n = len(ids); pos = {u: i for i, u in enumerate(ids)}
    tot = Counter()
    for u, r in rec.items():
        if u in pos and r["valid_votes"]:
            for q in r["organizations"]: tot[q["organization"]] += q["votes"]
    top = [o for o, _ in tot.most_common(NTOP)]
    ok = [i for i, u in enumerate(ids) if u in rec and rec[u]["valid_votes"] and rec[u]["organizations"]]
    top_c = top + ["OTROS (movimientos regionales y locales)"]
    X = np.zeros((len(ok), len(top_c))); pct = np.zeros(len(ok))
    for j, i in enumerate(ok):
        r = rec[ids[i]]; d = {q["organization"]: q["pct_valid"] for q in r["organizations"]}
        v = [d.get(o, 0.0) for o in top]; X[j] = v + [max(0.0, 100 - sum(v))]; pct[j] = r.get("counted_pct") or 0
    nb_all = contiguidad(feats); loc = {i: j for j, i in enumerate(ok)}
    nb = [set(loc[k] for k in nb_all[i] if k in loc) for i in ok]
    def correr(sel, wt=None):
        idx = np.array(sel); mp = {int(g): k for k, g in enumerate(idx)}
        nbs = []
        for g in idx:  # vecinos directos + vecinos de las unidades excluidas contiguas (puente de un salto)
            v = set(k for k in nb[g] if k in mp)
            for h in nb[g]:
                if h not in mp: v |= set(k for k in nb[h] if k in mp)
            v.discard(g); nbs.append(set(mp[k] for k in v))
        return idx, ward_contiguo(X[idx], nbs, None if wt is None else wt[idx])
    D = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(-1))
    dep = [nombres.get(ids[i], {}).get("d", "") for i in ok]
    info = [geom_info(feats[i]) for i in ok]; AREA = [a for _, a in info]
    VOT = [int(rec[ids[i]]["valid_votes"]) for i in ok]
    P, rr = dorling([c for c, _ in info], VOT, 16 if level == "dist" else 34)
    DOR = [[round(float(x), 1), round(float(y), 1), round(float(q), 1)] for (x, y), q in zip(P, rr)]
    V = np.array(VOT, float)
    def construir(ponderar):
        wt = V if ponderar else None; w = V if ponderar else np.ones(len(ok))
        idx, mg = correr(range(len(ok)), wt); res = {}
        for k in KS:
            lab = cortar(len(ok), mg, k); kk = int(lab.max()) + 1
            clave = {g: (V[lab == g].sum() if ponderar else (lab == g).sum()) for g in range(kk)}  # regiones por tamaño (votos si ponderada)
            rem = {g: r for r, g in enumerate(sorted(clave, key=lambda g: -clave[g]))}; lab = np.array([rem[g] for g in lab])
            regs = []
            for g in range(kk):
                m = lab == g; prom = (X[m] * w[m, None]).sum(0) / w[m].sum(); o = np.argsort(-prom)[:3]
                dc = Counter(d for d, f in zip(dep, m) if f)
                vt = sum(v for v, f in zip(VOT, m) if f); ar = sum(a for a, f in zip(AREA, m) if f)
                regs.append(dict(n=int(m.sum()), vot=vt, area=round(ar, 0), lider=top_c[int(o[0])], perfil=[[top_c[int(t)], round(float(prom[t]), 1)] for t in o],
                                 deps=[[d, c] for d, c in dc.most_common(4)], ndeps=len(dc), prom=[round(float(v), 1) for v in prom]))
            # robustez: misma regionalización con solo las unidades de ≥95 % de actas (ARI sobre las comunes)
            rob = None; sel = [j for j in range(len(ok)) if pct[j] >= 95]
            if len(sel) > 30 and len(sel) < len(ok) and level == "dist":
                ix2, mg2 = correr(sel, wt); l2 = cortar(len(sel), mg2, k); rob = round(ari(lab[ix2], l2), 3)
            res[str(k)] = dict(lab=[int(v) for v in lab], R2=round(float(r2(X, lab, w)), 4), sil=round(silueta(D, lab, w), 3),
                               ari_dep=round(ari(lab, [{d: i for i, d in enumerate(sorted(set(dep)))}[d] for d in dep]), 3), rob=rob, regs=regs)
            print(f"{level} {'POND' if ponderar else 'simple'} k={k} R²={res[str(k)]['R2']} sil={res[str(k)]['sil']} ARI(dep)={res[str(k)]['ari_dep']} rob={rob}", file=sys.stderr)
        return res
    res = construir(False); resw = construir(True)
    return dict(ids=[ids[i] for i in ok], top=top_c, ks=KS, res=res, resw=resw, n=len(ok), pct95=int(sum(pct >= 95)), vot=VOT, area=[round(a, 1) for a in AREA], dor=DOR)

def main():
    md = json.loads((S / "api" / "municipal-data.json").read_text(encoding="utf-8"))["records"]
    hist = json.loads((S / "api" / "history.json").read_text(encoding="utf-8"))
    fd = json.loads((S / "district-geography.json").read_text(encoding="utf-8"))["features"]
    ids_d = [f["properties"]["ubigeo"] for f in fd]
    MAPA, _, fp = _geo.mapa_provincias()
    fp = [f for f in fp if f["properties"]["id"] in MAPA]; ids_p = [MAPA[f["properties"]["id"]] for f in fp]
    nom = {r["ubigeo"]: {"d": r["department"]} for r in md}
    out = {"corte": hist["cortes"][-1], "dist": regionalizar("dist", fd, ids_d, {r["ubigeo"]: r for r in md if r["level"] == "distrital"}, nom),
           "prov": regionalizar("prov", fp, ids_p, {r["ubigeo"]: r for r in md if r["level"] == "provincial"}, nom)}
    dest = S / "api" / "regions.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{dest.stat().st_size/1e6:.2f} MB")
if __name__ == "__main__": main()
