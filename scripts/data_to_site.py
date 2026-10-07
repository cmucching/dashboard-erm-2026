#!/usr/bin/env python3
"""Convierte data/*.json (descarga ONPE) en los snapshots que consume el sitio (site/api/*)."""
from __future__ import annotations

import csv
import io
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scraper.transform import nombre_region, slug_cartilla, titulo_es, formato_hora_onpe  # noqa: E402

LIMA = timezone(timedelta(hours=-5))
API = ROOT / "site" / "api"
SYM_URL = "https://resultadoelectoral.onpe.gob.pe/assets/img-reales/partidos/{:08d}.png"
FALLBACK = ["#6B7C93", "#8C5E3C", "#4E8F6F", "#9B6BA8", "#B08D2A", "#3F7CAC", "#A9483B", "#5C6B2E"]


# False mientras el scraper no pida la elección distrital (ver `--descubrir`).
DISTRITAL_DESDE_DATA = False  # se activa solo si meta.json declara id_distrital == 4


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def jdump(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def iso_lima(fecha_iso):
    dt = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00")).astimezone(LIMA)
    return dt.strftime("%Y-%m-%dT%H:%M:%S-05:00")


def hora_onpe(fecha_iso):
    return formato_hora_onpe(fecha_iso).split(" · ")[1]


def sym_local(code):
    f = f"{code:08d}.png"
    return f"simbolos/{f}" if (ROOT / "site" / "simbolos" / f).exists() else SYM_URL.format(code)


def csv_text(rows, cols):
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])
    return buf.getvalue()


def main():
    global DISTRITAL_DESDE_DATA
    meta = jload(ROOT / "data" / "meta.json")
    DISTRITAL_DESDE_DATA = meta.get("id_distrital") == 4
    gen = meta["generado_utc"]
    dep = jload(ROOT / "data" / "regional_departamentos.json")
    prov = jload(ROOT / "data" / "municipal_provincias.json")
    dist = jload(ROOT / "data" / "municipal_distritos.json")

    old_res = jload(API / "results.json")
    old_prov = jload(API / "provincial.json")
    old_mun = jload(API / "municipal-data.json")

    # color/símbolo por organización (nombre) a partir de lo ya publicado
    color = {o["party"]: o["color"] for o in old_prov["organizations"]}
    for r in old_res["regiones"]:
        color.setdefault(r["nombre_oficial"], r["color"])
    corto = {r["nombre_oficial"]: r["organizacion"] for r in old_res["regiones"]}
    nfb = [0]

    def col(party):
        if party not in color:
            color[party] = FALLBACK[nfb[0] % len(FALLBACK)]
            nfb[0] += 1
        return color[party]

    def cand(p):
        n = (p.get("nombreCandidato") or "").strip()
        return titulo_es(n) if n else "Candidato no informado en el corte"

    def ordena(parts):
        return sorted(parts, key=lambda p: p["totalVotosValidos"], reverse=True)

    # ---------- REGIONAL ----------
    por_reg = {r["region"]: r for r in old_res["regiones"]}
    regs = []
    for d in dep:
        nom = nombre_region(d["nombre"], d["ubigeo"])
        base = por_reg.get(nom)
        if not base and nom == "Loreto":
            base = {"region": "Loreto", "id": "PE-LOR"}
        if not base:
            print("AVISO región sin plantilla:", nom, d["ubigeo"])
            continue
        t = d["totales"]
        top = ordena(d["participantes"])[:2]
        slug = slug_cartilla(d["nombre"], d["ubigeo"])
        fuente = f"https://votoinformado.jne.gob.pe/pdf/cartillas/cartilla-erm-{slug}.pdf"
        tops = []
        for p in top:
            code = p["codigoAgrupacionPolitica"]
            tops.append({
                "party": p["nombreAgrupacionPolitica"], "votes": p["totalVotosValidos"],
                "percent": p["porcentajeVotosValidos"], "candidate": cand(p),
                "candidate_source": fuente, "simbolo": sym_local(code),
            })
        p1 = top[0]
        ordenados = ordena(d["participantes"])
        tercero = None
        if len(ordenados) > 2:
            p3 = ordenados[2]
            tercero = {"party": p3["nombreAgrupacionPolitica"], "votes": p3["totalVotosValidos"],
                       "percent": p3["porcentajeVotosValidos"], "candidate": cand(p3)}
        nuevo = dict(base)
        nuevo.update({
            "organizacion": corto.get(p1["nombreAgrupacionPolitica"], titulo_es(p1["nombreAgrupacionPolitica"])),
            "nombre_oficial": p1["nombreAgrupacionPolitica"], "color": col(p1["nombreAgrupacionPolitica"]),
            "simbolo": sym_local(p1["codigoAgrupacionPolitica"]), "votos": p1["totalVotosValidos"],
            "porcentaje_validos": p1["porcentajeVotosValidos"], "actas_contabilizadas": t["actasContabilizadas"],
            "hora_onpe": hora_onpe(t["fechaActualizacion"]), "actualizacion": formato_hora_onpe(t["fechaActualizacion"]),
            "valid": t["totalVotosValidos"], "checked_at": gen, "top": tops, "tercero": tercero,
            "actas_total": t["totalActas"], "actas_contadas": t["contabilizadas"],
            "actas_jee": t["enviadasJee"], "actas_pendientes": t["pendientesJee"],
        })
        regs.append(nuevo)
    cortes = sorted(r["actualizacion"] for r in regs)
    cut_ts = sorted(d["totales"]["fechaActualizacion"] for d in dep)
    pub_time = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    old_res["regiones"] = regs
    old_res["automatico"] = False
    old_res["publication"] = {
        "revision": meta["huella"][:24], "complete": True, "mode": "downloaded", "automatic": False,
        "collected_from": cut_ts[0], "collected_until": gen, "published_at": pub_time,
        "regional_count": len(regs), "provincial_count": len(prov), "provincial_total": 196,
        "source_cut_from": formato_hora_onpe(cut_ts[0]), "source_cut_until": formato_hora_onpe(cut_ts[-1]),
        "state": "fresh", "age_minutes": 0, "target_minutes": 60,
    }
    old_res["update_status"] = {"state": "ok", "message": "Datos de la descarga ONPE más reciente. Cada región conserva su hora de corte."}
    jdump(API / "results.json", old_res)
    # results.csv
    (API / "results.csv").write_bytes((ROOT / "data" / "results.csv").read_bytes())

    # ---------- PROVINCIAL ----------
    orgs = {o["party"]: o for o in old_prov["organizations"]}
    orglist = list(old_prov["organizations"])
    for p in prov:
        for q in p["participantes"]:
            n = q["nombreAgrupacionPolitica"]
            if n not in orgs:
                o = {"id": len(orglist), "party": n, "color": col(n), "pattern": len(orglist) % 8, "regional_color": False,
                     "symbol": SYM_URL.format(q["codigoAgrupacionPolitica"]), "jne_party_id": None}
                orgs[n] = o
                orglist.append(o)
    import unicodedata

    def norm(x):
        x = unicodedata.normalize("NFD", x.lower())
        return "".join(c for c in x if unicodedata.category(c) != "Mn").strip().replace("raimondi", "raymondi")

    dep_nombre = {d["ubigeo"][:2]: norm(nombre_region(d["nombre"], d["ubigeo"]).replace(" región", "")) for d in dep}
    terr = {(norm(t["department"]), norm(t["province"])): t for t in old_prov["territories"]}
    cut_p = []
    n_ok = 0
    for p in prov:
        tt = terr.get((dep_nombre[p["dep"][:2]], norm(p["nombre"])))
        if not tt:
            print("AVISO provincia sin geometría:", p["ubigeo"], p["nombre"])
            continue
        t = p["totales"]
        top = ordena(p["participantes"])[:2]
        res_top = []
        for q in top:
            o = orgs[q["nombreAgrupacionPolitica"]]
            res_top.append({
                "party": q["nombreAgrupacionPolitica"], "votes": q["totalVotosValidos"],
                "percent": q["porcentajeVotosValidos"], "candidate": cand(q),
                "candidate_source": "https://votoinformado.jne.gob.pe/candidatos",
                "org": o["id"], "symbol": o["symbol"],
            })
        tt["result"] = {"valid": t["totalVotosValidos"], "advance": t["actasContabilizadas"],
                        "updated": formato_hora_onpe(t["fechaActualizacion"]), "top": res_top}
        cut_p.append(t["fechaActualizacion"])
        n_ok += 1
    old_prov["organizations"] = orglist
    old_prov["update_status"] = {"state": "ok", "mode": "downloaded", "uploaded_at": pub_time,
                                 "message": "Datos de la descarga ONPE más reciente."}
    old_prov["publication"] = old_res["publication"]
    jdump(API / "provincial.json", old_prov)
    rows = []
    for t in old_prov["territories"]:
        r = t.get("result")
        if not r:
            continue
        for i, q in enumerate(r["top"], 1):
            rows.append({"Elección": "Alcalde provincial", "Departamento": t["department"], "Provincia": t["province"],
                         "Código INEI": t["id"], "Puesto": i, "Organización": q["party"], "Candidato JNE": q["candidate"],
                         "Votos": q["votes"], "Porcentaje votos válidos": f'{q["percent"]:.3f}',
                         "Total votos válidos": r["valid"], "Actas contabilizadas %": f'{r["advance"]:.3f}',
                         "Corte ONPE (Perú UTC-5)": r["updated"]})
    (API / "provincial.csv").write_text(csv_text(rows, list(rows[0].keys())), encoding="utf-8")

    # ---------- MUNICIPAL (distrital + provincial) ----------
    old_cov = {c["key"]: c for c in old_mun["coverage"]}
    URL = "https://resultadoelectoral.onpe.gob.pe/main/elecciones-municipales"

    def registro(level, d, depname, provname, distname):
        t = d["totales"]
        valid = t["totalVotosValidos"]
        emit = t["totalVotosEmitidos"]
        orgs_out = []
        for q in ordena(d["participantes"]):
            orgs_out.append({
                "organization_id": f'{q["codigoAgrupacionPolitica"]:08d}', "organization": q["nombreAgrupacionPolitica"],
                "votes": q["totalVotosValidos"], "pct_valid": q["porcentajeVotosValidos"],
                "pct_emitted": q["porcentajeVotosEmitidos"], "symbol_url": SYM_URL.format(q["codigoAgrupacionPolitica"]),
            })
        rec = {
            "key": f'{level}:{d["ubigeo"]}', "level": level, "ubigeo": d["ubigeo"],
            "department_code": d["dep"], "department": depname, "province_code": d["prov"], "province": provname,
            "district": distname,
            "heading": "Elecciones Municipales - Municipal " + level,
            "selected": [x for x in (depname, provname, distname) if x],
            "source_url": URL, "organization_count": len(orgs_out),
            "valid_votes": valid, "emitted_votes": emit, "blank_votes": None, "null_votes": None,
            "blank_null_votes": max(emit - valid, 0),
            "total_actas": t["totalActas"], "counted_actas": t["contabilizadas"], "jee_actas": t["enviadasJee"],
            "pending_actas": t["pendientesJee"], "counted_pct": t["actasContabilizadas"],
            "source_updated_at": iso_lima(t["fechaActualizacion"]), "retrieved_at": gen,
            "organizations": orgs_out,
        }
        return rec

    names_dep = {}
    names_prov = {}
    for k, c in old_cov.items():
        names_dep[c["department_code"]] = c["department"]
        names_prov[c["province_code"]] = c["province"]

    records = []
    cov = []
    n_dist = 0
    for p in prov:
        dn = names_dep.get(p["dep"], p["nombre"])
        pn = names_prov.get(p["prov"], p["nombre"])
        records.append(registro("provincial", p, dn, pn, ""))
    n_prov = len(records)
    if not DISTRITAL_DESDE_DATA:
        # La descarga actual trae la elección PROVINCIAL por distrito, no la distrital. Se conservan
        # los resultados distritales ya publicados hasta que el scraper pida la elección correcta.
        records += [r for r in old_mun["records"] if r["level"] == "distrital"]
        cov = [c for c in old_mun["coverage"] if c["level"] == "distrital"]
        dist = []
        n_dist = sum(1 for r in records if r["level"] == "distrital")
    for d in dist:
        key = f'distrital:{d["ubigeo"]}'
        oc = old_cov.get(key)
        if not oc:
            print("AVISO distrito sin cobertura previa:", d["ubigeo"], d["nombre"])
            continue
        if d.get("sin_eleccion") or (not d["participantes"] and not d["totales"]):
            cov.append({**oc, "status": "not_applicable",
                        "reason": "No figura como elección municipal distrital en las opciones oficiales de su provincia."})
            continue
        if not d["participantes"] or not d["totales"]:
            cov.append({**oc, "status": "pending", "reason": "Sin datos en la descarga"})
            continue
        records.append(registro("distrital", d, oc["department"], oc["province"], oc["district"]))
        cov.append({**oc, "status": "downloaded", "reason": ""})
        n_dist += 1
    for c in old_mun["coverage"]:
        if c["level"] == "provincial":
            cov.append({**c, "status": "downloaded", "reason": ""})
    # Capitales de provincia: sin alcalde distrital, pero con su votación (voto provincial en el distrito)
    n_cap = 0
    cap_path = ROOT / "data" / "municipal_capitales.json"
    if DISTRITAL_DESDE_DATA and cap_path.exists():
        cov = [c for c in cov if not (c["level"] == "distrital" and c["status"] == "not_applicable")]
        for d in jload(cap_path):
            oc = old_cov.get(f'distrital:{d["ubigeo"]}')
            if not oc or not d.get("participantes") or not d.get("totales"):
                if oc:
                    cov.append({**oc, "status": "not_applicable", "reason": "Capital de provincia sin datos en la descarga."})
                continue
            rec = registro("distrital", d, oc["department"], oc["province"], oc["district"])
            rec["eleccion_fuente"] = "provincial"
            rec["heading"] = "Elecciones Municipales - Alcalde provincial (votación en el distrito)"
            records.append(rec)
            cov.append({**oc, "status": "downloaded",
                        "reason": "Capital de provincia: sin alcalde distrital; se muestra la votación provincial en el distrito."})
            n_cap += 1
    # distritos no devueltos por la descarga conservan su estado previo como pendientes
    seen = {c["key"] for c in cov}
    for c in ([] if not DISTRITAL_DESDE_DATA else old_mun["coverage"]):
        if c["key"] not in seen:
            cov.append({**c, "status": "pending" if c["status"] != "not_applicable" else c["status"]})
    pend = sum(1 for c in cov if c["status"] == "pending")
    na = sum(1 for c in cov if c["status"] == "not_applicable")
    cuts = sorted(r["source_updated_at"] for r in records)
    old_mun["records"] = records
    old_mun["coverage"] = cov
    esperado_d = sum(1 for c in cov if c["level"] == "distrital" and c["status"] != "not_applicable")
    old_mun["metadata"] = {
        "provincial": n_prov, "distrital": n_dist + n_cap, "capitales_provincial": n_cap, "not_applicable": na, "pending": pend,
        "organization_rows": sum(len(r["organizations"]) for r in records), "state": "complete" if pend == 0 else "downloading",
        "source_cut_from": cuts[0], "source_cut_until": cuts[-1], "retrieved_from": gen, "retrieved_until": gen,
        "expected_provincial": 196, "expected_distrital": 1696 if not DISTRITAL_DESDE_DATA else esperado_d + 0, "revision": meta["huella"][:24], "published_at": pub_time,
    }
    # paleta única de partidos: la de regional/provincial manda; los que solo aparecen en distritos reciben color estable
    import colorsys, hashlib

    def hash_color(n):
        h = int(hashlib.md5(n.encode()).hexdigest()[:6], 16) % 360 / 360
        r, g, b = colorsys.hls_to_rgb(h, .43, .6)
        return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))

    paleta = dict(color)
    for r in records:
        for o in r["organizations"]:
            paleta.setdefault(o["organization"], hash_color(o["organization"]))
    jdump(API / "party-colors.json", paleta)
    jdump(API / "municipal-data.json", old_mun)
    jdump(API / "municipal-status.json", old_mun["metadata"])
    jdump(API / "update-status.json", old_res["publication"])

    cols_m = ["election", "ubigeo", "department", "province", "district", "organization_id", "organization", "votes",
              "pct_valid", "pct_emitted", "valid_votes", "emitted_votes", "blank_votes", "null_votes", "blank_null_votes",
              "total_actas", "counted_actas", "jee_actas", "pending_actas", "counted_pct", "source_updated_at",
              "retrieved_at", "source_url", "symbol_url"]
    rows = []
    for r in records:
        for o in r["organizations"]:
            rows.append({**r, **o, "election": r["level"]})
    (API / "municipal-data.csv").write_text(csv_text(rows, cols_m), encoding="utf-8")
    cols_t = ["level", "ubigeo", "department", "province", "district", "organization_count", "valid_votes", "emitted_votes",
              "blank_votes", "null_votes", "blank_null_votes", "total_actas", "counted_actas", "jee_actas", "pending_actas",
              "counted_pct", "source_updated_at", "retrieved_at", "source_url"]
    (API / "municipal-totals.csv").write_text(csv_text(records, cols_t), encoding="utf-8")
    (API / "municipal-coverage.csv").write_text(
        csv_text(cov, ["level", "ubigeo", "department", "province", "district", "status", "reason"]), encoding="utf-8")

    # ---------- LIMA METROPOLITANA ----------
    lp = ROOT / "site" / "lima-metropolitana-onpe.json"
    lima = jload(lp)
    reg_lima = next((r for r in records if r["level"] == "provincial" and r["ubigeo"] == "140100"), None)
    if reg_lima:
        tb = dict(lima["metropolitan"]["total_before"])
        tb.update({k: reg_lima[k] for k in ("valid_votes", "emitted_votes", "total_actas", "counted_actas", "jee_actas",
                                            "pending_actas", "counted_pct", "source_updated_at", "retrieved_at",
                                            "organization_count", "organizations")})
        tb["blank_votes"] = None
        tb["null_votes"] = None
        tb["blank_null_votes"] = reg_lima["blank_null_votes"]
        lima["metropolitan"]["total_before"] = tb
        lima["metropolitan"]["metadata"]["source_cut_until"] = reg_lima["source_updated_at"]
        lima["metropolitan"]["metadata"]["last_saved_at"] = gen
    # Voto metropolitano por distrito (estratos del modelo MAG aplicado a Lima), con el mismo corte que el total.
    mp = ROOT / "data" / "municipal_lima.json"
    if mp.exists():
        ml = [registro("provincial", d, "LIMA", "LIMA", d["nombre"]) for d in jload(mp) if d.get("participantes") and d.get("totales")]
        if len(ml) == lima["metropolitan"]["expected_districts"]:
            lima["metropolitan"]["records"] = ml
        else:
            print(f"AVISO: voto metropolitano en {len(ml)} distritos (se esperaban {lima['metropolitan']['expected_districts']}); se conservan los anteriores")
    lima_d = [r for r in records if r["level"] == "distrital" and r["province_code"] == "140100"]
    if DISTRITAL_DESDE_DATA:
        lima["district_mayors"]["records"] = lima_d
    jdump(lp, lima)

    print(f"Regional {len(regs)} · provincial {n_ok} · distrital {n_dist} (pendientes {pend}, no aplica {na}) · Lima distritales {len(lima_d)}")
    print("Cortes regionales:", cortes[0], "→", cortes[-1])
    print("Cortes municipales:", cuts[0], "→", cuts[-1])


if __name__ == "__main__":
    main()
