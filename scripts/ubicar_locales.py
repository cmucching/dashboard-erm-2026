#!/usr/bin/env python3
"""Asigna coordenadas a los locales de votación de un distrito.

Fuentes, en orden de prioridad:
  1) Padrón de IIEE de Minedu (ESCALE), si se entrega con --minedu <archivo .csv/.xlsx/.dbf>. Fuente oficial.
  2) Geocodificación provisional con OpenStreetMap (Nominatim), solo si el resultado pasa un filtro estricto
     (coinciden el número de la IE y las palabras distintivas y la dirección cae en el distrito).
Cada punto lleva su 'fuente' y su 'calidad' para que el mapa lo indique; lo que no pasa el filtro queda sin ubicar.

Uso: python3 scripts/ubicar_locales.py site/api/locales/140130.json "Santiago de Surco" [--minedu padron.xlsx] [--osm cache.json]
"""
import json, re, sys, argparse, unicodedata, pathlib

PARADA = set("ie iep iei ei cebe ceba cetpro colegio institucion educativa educacion de del la las los el y e en nuestra senora sra san santa santo nro n inicial primaria secundaria pnp fap se pri ini".split())

def norm(t):
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", t)

def claves(nombre):
    toks = norm(nombre).split()
    nums = [t for t in toks if t.isdigit() and len(t) >= 3]
    pal = [t for t in toks if t not in PARADA and not t.isdigit() and len(t) > 2]
    return nums, pal

def coincide(nombre, otro):
    """Reglas estrictas: si hay número de IE debe aparecer; y deben aparecer ≥ 70 % de las palabras distintivas."""
    nums, pal = claves(nombre); o = set(norm(otro).split())
    if nums and not all(n in o for n in nums): return 0.0
    if not pal: return 0.0
    return sum(p in o for p in pal) / len(pal)

def desde_osm(locales, cache, distrito):
    out = {}
    dn = norm(distrito)
    for l in locales:
        h = cache.get(l["c"])
        if not h or h.get("lat") is None: continue
        nombre = h["found"].split(",")[0]
        if dn not in norm(h["found"]): continue
        sc = coincide(l["n"], nombre)
        if sc >= 0.7:
            out[l["c"]] = {"lat": round(h["lat"], 6), "lon": round(h["lon"], 6), "fuente": "OpenStreetMap", "calidad": "provisional", "ref": h.get("osm")}
    return out

def leer_minedu(ruta):
    import csv
    p = pathlib.Path(ruta); filas = []
    if p.suffix.lower() in (".xlsx", ".xls"):
        import openpyxl
        ws = openpyxl.load_workbook(p, read_only=True, data_only=True).worksheets[0]
        it = ws.iter_rows(values_only=True); cab = [str(c or "").strip() for c in next(it)]
        filas = [dict(zip(cab, r)) for r in it]
    elif p.suffix.lower() == ".dbf":
        from dbfread import DBF
        filas = [dict(r) for r in DBF(str(p), encoding="latin-1")]
    else:
        with open(p, encoding="utf-8-sig", errors="replace", newline="") as f:
            filas = list(csv.DictReader(f, delimiter=";" if f.readline().count(";") > 3 else ","))
    return filas

def desde_minedu(locales, filas, ubigeo_inei, distrito):
    """Cruza por distrito (CODGEO/UBIGEO INEI) y nombre. Campos habituales del Padrón Web: CEN_EDU, NLAT_IE, NLONG_IE, CODGEO, D_DIST."""
    def g(f, *ks):
        for k in ks:
            for kk in f:
                if str(kk).strip().lower() == k: return f[kk]
        return None
    cand = []
    for f in filas:
        d = str(g(f, "d_dist", "distrito") or ""); cg = str(g(f, "codgeo", "ubigeo") or "")
        if norm(distrito) not in norm(d) and not cg.endswith(str(ubigeo_inei)[-6:]): continue
        try: lat = float(str(g(f, "nlat_ie", "latitud", "lat")).replace(",", ".")); lon = float(str(g(f, "nlong_ie", "longitud", "lon")).replace(",", "."))
        except Exception: continue
        if not (-90 < lat < 0 and -85 < lon < -60): continue
        cand.append((str(g(f, "cen_edu", "nombre") or ""), str(g(f, "cod_mod", "codigo_modular") or ""), lat, lon))
    out = {}
    for l in locales:
        mejor = max(((coincide(l["n"], c[0]), c) for c in cand), key=lambda x: x[0], default=(0, None))
        if mejor[0] >= 0.7:
            c = mejor[1]; out[l["c"]] = {"lat": round(c[2], 6), "lon": round(c[3], 6), "fuente": "Minedu", "calidad": "oficial", "ref": c[1]}
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("json"); ap.add_argument("distrito")
    ap.add_argument("--minedu"); ap.add_argument("--osm"); ap.add_argument("--ubigeo-inei", default="")
    a = ap.parse_args(); d = json.load(open(a.json, encoding="utf-8")); L = d["locales"]
    pts = {}
    if a.osm: pts.update(desde_osm(L, json.load(open(a.osm, encoding="utf-8")), a.distrito))
    if a.minedu: pts.update(desde_minedu(L, leer_minedu(a.minedu), a.ubigeo_inei or d["ubigeo"], a.distrito))  # Minedu pisa a OSM
    for l in L:
        for k in ("lat", "lon", "fuente", "calidad", "ref"): l.pop(k, None)
        if l["c"] in pts: l.update(pts[l["c"]])
    d["ubicados"] = {"total": len(L), "con_coordenadas": sum("lat" in l for l in L), "electores_ubicados": sum(l["el"] for l in L if "lat" in l), "electores": sum(l["el"] for l in L)}
    json.dump(d, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(d["ubicados"], {k: sum(1 for l in L if l.get("fuente") == k) for k in ("Minedu", "OpenStreetMap")})

main()
