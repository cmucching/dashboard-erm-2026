#!/usr/bin/env python3
"""Quita de un mesas-<ubigeo>.jsonl las mesas con alguna acta no contabilizada (estado != 'C'),
para que bajar_mesas.py (que reanuda) las vuelva a consultar. Uso: refrescar_pendientes.py <jsonl>"""
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]); L = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
pend = {r["m"] for r in L if r["st"] != "C"}
p.write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in L if r["m"] not in pend), encoding="utf-8")
print(f"{p.name}: {len(pend)} mesas pendientes a re-consultar, {len(L)} -> {len({r['m'] for r in L})-len(pend)} mesas conservadas")
