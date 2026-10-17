#!/usr/bin/env python3
"""Ubica los locales de votación de ONPE con el padrón de IIEE de Minedu (SIGMED, restsig.svc/padron).

Entrada: padron_minedu_<fecha>.json.gz  {fuente, fecha, campos, regiones, provincias, distritos, data}
         data[ubigeo INEI] = [[CODIGO_MODULAR, ANEXO, CODIGO_LOCAL, NIVEL, NOMBRE, DIRECCION, LAT, LON, ESTADO, GESTION, CCPP], ...]

1) Cruce de distritos ONPE -> INEI (los códigos difieren: ONPE Lima = 14, INEI Lima = 15). Se hace por nombre:
   primero los nombres únicos fijan departamento y provincia por votación (sin ambigüedad), luego se
   empareja cada distrito por nombre dentro de su provincia INEI. Los pocos restantes se emparejan solo si
   queda un único distrito sin usar en esa provincia (diferencias de ortografía).
2) Cruce de locales dentro del distrito, con filtro estricto:
   - los números de IE (≥ 3 cifras) del nombre ONPE deben aparecer en el nombre Minedu;
   - cobertura de palabras distintivas ONPE ≥ 0.80 y Minedu ≥ 0.50;
   - se agrupa por CODIGO_LOCAL de Minedu (un local = varios niveles/servicios);
   - si dos locales distintos empatan y están a más de 150 m, se descarta (ambiguo);
   - se descartan coordenadas fuera de Perú y las que se alejan del grueso de IIEE del distrito.
Cada punto lleva fuente='Minedu', calidad y ref (CODIGO_LOCAL). Lo que no pasa queda sin ubicar.

Uso: python3 scripts/ubicar_padron_minedu.py padron.json.gz [--aplicar] [--distritos 140101 ...] [--muestra N]
Sin --aplicar solo informa (simulación).
"""
import json, re, sys, gzip, math, difflib, argparse, pathlib, unicodedata, collections, statistics

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PARADA = set("ie iep iei ei cebe ceba cetpro colegio institucion educativa educacion de del la las los el y e en nuestra "
             "senora sra san santa santo nro n inicial primaria secundaria pnp fap se pri ini pnpa gue cn pj emblematica emblematico sede".split())


def nrm(t):
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", " ", t).strip()


def toks(nombre):
    t = [x.lstrip("0") or "0" if x.isdigit() else x for x in nrm(nombre).lower().split()]
    nums = {x for x in t if x.isdigit() and len(x) >= 3}
    pal = {x for x in t if x not in PARADA and len(x) > 1 and x not in nums}
    return nums, pal, set(t)


def km(a, b):
    r = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1]); dp = p2 - p1
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def cruce_distritos(M, O):
    """ONPE ubigeo -> INEI ubigeo por nombre. Devuelve (dict, lista de aproximados)."""
    mi = collections.defaultdict(list)
    for c, n, p in M["distritos"]: mi[nrm(n)].append(c)
    oi = collections.defaultdict(list)
    for o in O: oi[nrm(o["nombre"])].append(o)
    vd = collections.defaultdict(collections.Counter); vp = collections.defaultdict(collections.Counter)
    for k, os_ in oi.items():
        if len(os_) == 1 and len(mi.get(k, [])) == 1:
            o, i = os_[0], mi[k][0]; vd[o["dep"]][i[:2]] += 1; vp[o["prov"]][i[:4]] += 1
    pm = {p: c.most_common(1)[0][0] for p, c in vp.items()}
    porprov = collections.defaultdict(lambda: collections.defaultdict(list))
    for c, n, p in M["distritos"]: porprov[p][nrm(n)].append(c)
    cw, resto = {}, []
    for o in O:
        ip = pm.get(o["prov"]); c = porprov.get(ip, {}).get(nrm(o["nombre"]), []) if ip else []
        if len(c) == 1: cw[o["ubigeo"]] = c[0]
        else: resto.append(o)
    usados = set(cw.values()); aprox = []
    for o in resto:
        ip = pm.get(o["prov"])
        libres = [(c, n) for c, n, p in M["distritos"] if p == ip and c not in usados]
        if ip and len(libres) == 1:
            cw[o["ubigeo"]] = libres[0][0]; usados.add(libres[0][0]); aprox.append((o["ubigeo"], o["nombre"], libres[0][1]))
    return cw, aprox


def candidatos(filas):
    """Agrupa filas válidas por CODIGO_LOCAL -> {nombre(s), lat, lon}. Descarta coordenadas inválidas y atípicas."""
    pts = []
    for f in filas:
        try: lat, lon = float(f[6]), float(f[7])
        except Exception: continue
        if not (-18.5 < lat < 0.2 and -81.5 < lon < -68.5): continue
        pts.append((f, lat, lon))
    if not pts: return []
    # coordenada genérica: ≥ 6 locales distintos exactamente en el mismo punto (centroide por defecto de Minedu)
    por_xy = collections.defaultdict(set)
    for f, lat, lon in pts: por_xy[(round(lat, 5), round(lon, 5))].add(f[2] or f[0])
    pts = [p for p in pts if len(por_xy[(round(p[1], 5), round(p[2], 5))]) < 6]
    if not pts: return []
    mlat = statistics.median(p[1] for p in pts); mlon = statistics.median(p[2] for p in pts)
    d = sorted(km((p[1], p[2]), (mlat, mlon)) for p in pts)
    corte = max(40.0, 6 * d[len(d) // 2] + 10)  # atípicos groseros (coordenadas mal digitadas)
    loc = collections.OrderedDict()
    for f, lat, lon in pts:
        if km((lat, lon), (mlat, mlon)) > corte: continue
        k = f[2] or f"mod{f[0]}"
        g = loc.setdefault(k, {"cod": f[2], "nombres": [], "pts": [], "estado": []})
        g["nombres"].append(f[4]); g["pts"].append((lat, lon)); g["estado"].append(str(f[8]))
    out = []
    for g in loc.values():
        la = statistics.median(p[0] for p in g["pts"]); lo = statistics.median(p[1] for p in g["pts"])
        disp = max(km(p, (la, lo)) for p in g["pts"]) * 1000
        out.append({"cod": g["cod"], "tk": [toks(n) for n in g["nombres"]], "nombres": g["nombres"], "lat": la, "lon": lo, "disp_m": disp})
    return out


def _en(p, conj):
    """¿La palabra p está en el conjunto, exacta o con ortografía muy cercana (≥ 0.86, misma inicial, largo ≥ 5)?"""
    if p in conj: return True
    if len(p) < 5 or p.isdigit(): return False
    return any(len(t) >= 5 and t[0] == p[0] and not t.isdigit() and difflib.SequenceMatcher(None, p, t).ratio() >= 0.86 for t in conj)


def puntaje(onpe, c):
    """Mejor puntaje entre los nombres del local Minedu. 0 si no pasa el filtro."""
    nn, pn, tn = toks(onpe); mejor = 0.0
    for (nm, pm_, tm) in c["tk"]:
        if nn and not nn <= tm: continue
        if not pn:
            # solo número de IE: debe coincidir exactamente
            if nn and nn <= tm: mejor = max(mejor, 0.85)
            continue
        cov_o = sum(_en(x, tm) for x in pn) / len(pn)
        cov_m = (sum(_en(x, tn) for x in pm_) / len(pm_)) if pm_ else (1.0 if nn else 0.0)
        if cov_o >= 0.80 and cov_m >= 0.50: mejor = max(mejor, 0.5 * cov_o + 0.5 * cov_m + (0.05 if nn else 0))
    return mejor


def ubicar(locales, cands):
    res = {}
    idx = collections.defaultdict(set)
    for i, c in enumerate(cands):
        for (nm, pm_, tm) in c["tk"]:
            for t in tm: idx[t].add(i)
    for l in locales:
        nn, pn, tn = toks(l["n"])
        ids = set().union(*(idx.get(t, set()) for t in (nn | pn))) if (nn | pn) else set()
        pun = sorted(((puntaje(l["n"], cands[i]), cands[i]) for i in ids), key=lambda x: -x[0])
        pun = [x for x in pun if x[0] >= 0.80]
        if not pun: continue
        top = pun[0]
        rivales = [x for x in pun[1:] if top[0] - x[0] < 0.05 and km((x[1]["lat"], x[1]["lon"]), (top[1]["lat"], top[1]["lon"])) > 0.15]
        if rivales: res[l["c"]] = ("ambiguo", top); continue
        c = top[1]
        if c["disp_m"] > 300: res[l["c"]] = ("disperso", top); continue
        cal = "oficial" if top[0] >= 0.9 else "oficial-aprox"
        res[l["c"]] = (cal, top)
    return res


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("padron"); ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--distritos", nargs="*"); ap.add_argument("--muestra", type=int, default=0)
    a = ap.parse_args()
    M = json.load(gzip.open(a.padron, "rt", encoding="utf-8"))
    O = json.load(open(RAIZ / "data/municipal_distritos.json", encoding="utf-8"))
    cw, aprox = cruce_distritos(M, O)
    print(f"distritos cruzados ONPE→INEI: {len(cw)} de {len(O)}; por ortografía: {aprox}")
    fecha = M["fecha"][:10]
    lista = a.distritos or [o["ubigeo"] for o in O]
    tot = collections.Counter(); ejemplos = []
    for u in lista:
        p = RAIZ / f"site/api/locales/{u}.json"
        if not p.exists() or u not in cw: tot["sin_archivo_o_cruce"] += 1; continue
        d = json.load(open(p, encoding="utf-8")); L = d["locales"]
        res = ubicar(L, candidatos(M["data"].get(cw[u], [])))
        for l in L:
            r = res.get(l["c"])
            ok = r and r[0].startswith("oficial")
            tot["locales"] += 1; tot["electores"] += l["el"]
            if r: tot[r[0]] += 1
            else: tot["sin_match"] += 1
            if ok:
                tot["ubicados"] += 1; tot["electores_ubicados"] += l["el"]
                if a.muestra and len(ejemplos) < a.muestra and (int(l["c"]) if str(l["c"]).isdigit() else 0) % 5 == 0:
                    ejemplos.append((u, l["n"], r[1][1]["nombres"][0], round(r[1][0], 2), r[0]))
            if a.aplicar:
                if ok:
                    c = r[1][1]
                    l.update({"lat": round(c["lat"], 6), "lon": round(c["lon"], 6), "fuente": "Minedu", "calidad": r[0], "ref": c["cod"]})
                elif l.get("fuente") == "Minedu":
                    for k in ("lat", "lon", "fuente", "calidad", "ref"): l.pop(k, None)
        if a.aplicar:
            d["ubicados"] = {"total": len(L), "con_coordenadas": sum("lat" in l for l in L),
                             "electores_ubicados": sum(l["el"] for l in L if "lat" in l), "electores": sum(l["el"] for l in L),
                             "fuente_padron": f"Minedu SIGMED {fecha}"}
            json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(dict(tot))
    if tot["locales"]: print(f"locales ubicados: {tot['ubicados']/tot['locales']*100:.1f} %  ·  electores ubicados: {tot['electores_ubicados']/max(1,tot['electores'])*100:.1f} %")
    for e in ejemplos: print(e)


if __name__ == "__main__":
    main()
