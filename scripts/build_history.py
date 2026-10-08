"""Genera site/api/history.json: serie de cortes ONPE (desde el historial de git de data/).
Por unidad (departamento / provincia / distrito) y corte: [% actas, válidos, índice líder, votos 1.º, votos 2.º]."""
import json, subprocess, sys
from pathlib import Path
R = Path(__file__).resolve().parent.parent

def git(*a):
    return subprocess.run(["git", *a], cwd=R, capture_output=True, text=True, encoding="utf-8").stdout

def show(sha, name):
    t = git("show", f"{sha}:data/{name}")
    try: return json.loads(t)
    except Exception: return None

def fila(r, par_idx):
    t, p = r.get("totales"), r.get("participantes")
    if not t or not p: return None
    o = sorted(p, key=lambda q: -(q.get("totalVotosValidos") or 0))
    v = [q.get("totalVotosValidos") or 0 for q in o]
    if not v or not v[0]: return [t.get("actasContabilizadas"), t.get("totalVotosValidos") or 0, -1, 0, 0]
    n = o[0]["nombreAgrupacionPolitica"]
    return [round(t.get("actasContabilizadas") or 0, 3), t.get("totalVotosValidos") or 0,
            par_idx.setdefault(n, len(par_idx)), v[0], v[1] if len(v) > 1 else 0]

def main():
    commits = [l.split()[0] for l in git("log", "--reverse", "--format=%h", "--", "data").splitlines()]
    par_idx, cortes, vistos, pend = {}, [], set(), []
    series = {"dep": {}, "prov": {}, "dist": {}}
    for sha in commits:
        meta = show(sha, "meta.json") or {}
        if meta.get("id_distrital") != 4: continue
        dep, prov, dist = (show(sha, f) for f in ("regional_departamentos.json", "municipal_provincias.json", "municipal_distritos.json"))
        if not (dep and prov and dist): continue
        corte = max((r["totales"]["fechaActualizacion"] for r in dep if r.get("totales")), default=None)
        if not corte or corte in vistos: continue
        vistos.add(corte); pend.append((corte, dep, prov, dist))
    for k, (corte, dep, prov, dist) in enumerate(sorted(pend, key=lambda x: x[0])):
        cortes.append(corte)
        for nivel, datos in (("dep", dep), ("prov", prov), ("dist", dist)):
            for r in datos:
                f = fila(r, par_idx)
                if f: series[nivel].setdefault(r["ubigeo"], {})[k] = f
    n = len(cortes)
    out = {"cortes": cortes, "partidos": [p for p, _ in sorted(par_idx.items(), key=lambda x: x[1])]}
    for nivel, d in series.items():
        out[nivel] = {u: [d_[i] if i in d_ else None for i in range(n)] for u, d_ in d.items()}
    dest = R / "site" / "api" / "history.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{n} cortes · {len(par_idx)} partidos · dep {len(out['dep'])} prov {len(out['prov'])} dist {len(out['dist'])} · {dest.stat().st_size/1e6:.2f} MB")
if __name__ == "__main__": main()
